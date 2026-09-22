import os

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.github_client import GitHubClient
from backend.app.graph import compiled_graph
from backend.app.models import Finding, Review, ReviewDecision, WebhookDelivery
from backend.app.repositories import PullRequestRepo, RepositoryRepo
from backend.app.schemas import ReviewState
from backend.app.webhooks import verify_signature

ACCEPTED_EVENTS = {"pull_request"}
ACCEPTED_ACTIONS = {"opened", "synchronize"}

app = FastAPI()


def trigger_review(owner: str, repo: str, pr_number: int, pull_request_id: int, head_sha: str) -> None:
    """Runs the review pipeline for one PR. Scheduled as a background task so the webhook
    returns promptly; the graph opens its own DB session (see persist_review), so it takes
    plain values rather than the request-scoped session, which closes after the response."""
    state = ReviewState(
        pull_request_id=pull_request_id,
        head_sha=head_sha,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )
    compiled_graph.invoke(state)


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "This is the home page of your code review bot"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/webhooks/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="invalid signature")

    delivery_id = request.headers.get("X-GitHub-Delivery")

    """retrieves the value of the specified key(key-value pair of dictonary) from the github curl request """

    if not delivery_id:
        raise HTTPException(status_code=400, detail="missing delivery id")

    try:
        db.add(
            WebhookDelivery(
                delivery_id=delivery_id,
                event_type=request.headers.get("X-GitHub-Event"),
            )
        )
        db.commit()
    except IntegrityError:  # if unique constraint is violated then db will be not altered
        db.rollback()
        return {"status": "duplicate"}  # already-seen delivery_id — unique constraint caught it

    event = request.headers.get("X-GitHub-Event")
    if event not in ACCEPTED_EVENTS:
        return {"status": "ignored", "reason": "event type not handled"}

    payload = await request.json()
    if payload.get("action") not in ACCEPTED_ACTIONS:
        return {"status": "ignored", "reason": "action not handled"}

    # Resolve repo/PR from the payload defensively — a payload missing the repository
    # block (e.g. a minimal test ping) is still accepted, just not reviewed.
    repo_full_name = payload.get("repository", {}).get("full_name")
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    head_sha = pr.get("head", {}).get("sha")
    if not repo_full_name or pr_number is None or not head_sha:
        return {"status": "accepted", "reason": "no reviewable PR in payload"}

    # Upsert repo + PR rows synchronously so the FK target exists before the pipeline
    # (persist_review) writes the review in the background.
    repo_row = RepositoryRepo(db).get_or_create(repo_full_name)
    pr_row = PullRequestRepo(db).get_or_create(
        repository_id=int(repo_row.id),
        number=pr_number,
        head_sha=head_sha,
        author=pr.get("user", {}).get("login", ""),
    )
    db.commit()

    owner_name, repo_name = repo_full_name.split("/", 1)
    background_tasks.add_task(
        trigger_review,
        owner=owner_name,
        repo=repo_name,
        pr_number=pr_number,
        pull_request_id=int(pr_row.id),
        head_sha=head_sha,
    )

    return {"status": "accepted"}


@app.post("/api/reviews/{review_id}/publish")
def publish_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(404, "Review not found")

    # Approved findings live in ReviewDecision, not on Finding — join through it.
    approved_findings = (
        db.query(Finding)
        .join(ReviewDecision, ReviewDecision.finding_id == Finding.id)
        .filter(Finding.review_id == review.id, ReviewDecision.decision == "approved")
        .all()
    )

    if not approved_findings:
        return {"status": "skipped", "reason": "No approved findings to publish"}

    # Format for GitHub
    gh_comments = []
    for f in approved_findings:
        gh_comments.append(
            {"path": f.file_path, "line": f.line, "body": f"**[CodeReviewBot]** ({f.category})\n\n{f.explanation}"}
        )

    client = GitHubClient(os.environ["GITHUB_TOKEN"])

    # Note: Requires storing owner/repo somewhere (e.g. joining through PullRequest model)
    # For demo, we hardcode or extract from the DB relationships.
    pr = review.pull_request
    repo = pr.repository
    owner_name, repo_name = repo.full_name.split("/")

    try:
        client.create_review(owner_name, repo_name, pr.number, gh_comments)

        # Mark as published
        review.status = "PUBLISHED"  # type: ignore
        db.commit()
        return {"status": "published"}
    except Exception as e:
        raise HTTPException(500, f"GitHub API Error: {str(e)}")


@app.get("/api/reviews")
def list_reviews(status: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = db.query(Review)
    if status:
        query = query.filter(Review.status == status)
    reviews = query.order_by(Review.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "pull_request_id": r.pull_request_id,
            "status": r.status,
            "summary": r.summary,
        }
        for r in reviews
    ]


@app.get("/api/reviews/{review_id}/findings")
def list_findings(review_id: int, db: Session = Depends(get_db)) -> list[dict]:
    findings = db.query(Finding).filter(Finding.review_id == review_id).all()
    out = []
    for f in findings:
        # Surface the latest decision (if any) so the dashboard can show current state.
        latest = (
            db.query(ReviewDecision)
            .filter(ReviewDecision.finding_id == f.id)
            .order_by(ReviewDecision.decided_at.desc())
            .first()
        )
        out.append(
            {
                "id": f.id,
                "file_path": f.file_path,
                "line": f.line,
                "category": f.category,
                "explanation": f.explanation,
                "llm_confidence": f.llm_confidence,
                "ml_probability": f.ml_probability,
                "decision": latest.decision if latest else None,
            }
        )
    return out


@app.patch("/api/findings/{finding_id}")
def decide_finding(finding_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    decision = payload.get("decision")
    if decision not in {"approved", "edited", "rejected"}:
        raise HTTPException(422, "decision must be one of: approved, edited, rejected")

    db.add(
        ReviewDecision(
            finding_id=finding.id,
            decision=decision,
            edited_explanation=payload.get("edited_explanation"),
        )
    )
    db.commit()
    return {"status": "ok", "finding_id": finding_id, "decision": decision}
