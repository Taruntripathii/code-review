import os

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.github_client import GitHubClient
from backend.app.models import Finding, Review, WebhookDelivery
from backend.app.webhooks import verify_signature

ACCEPTED_EVENTS = {"pull_request"}
ACCEPTED_ACTIONS = {"opened", "synchronize"}

app = FastAPI()


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "This is the home page of your code review bot"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/webhooks/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
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

    return {"status": "accepted"}


@app.post("/api/reviews/{review_id}/publish")
def publish_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(404, "Review not found")

    approved_findings = db.query(Finding).filter(Finding.review_id == review.id, Finding.decision == "approved").all()

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
