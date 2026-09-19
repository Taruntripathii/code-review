from sqlalchemy.orm import Session
from backend.app.models import PullRequest, Review



class PullRequestRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, repository_id: int, number: int, head_sha: str, author: str) -> PullRequest:
        pr = (
            self.db.query(PullRequest)
            .filter_by(repository_id=repository_id, number=number)
            .first()
        )
        if pr:
            pr.head_sha = head_sha  # type: ignore[assignment]  # keep it current on new pushes
        else:
            pr = PullRequest(repository_id=repository_id, number=number, head_sha=head_sha, author=author)
            self.db.add(pr)
        self.db.flush()
        self.db.refresh(pr)
        return pr


class ReviewRepo:
    def __init__(self, db: Session):
        self.db = db

    def create_pending(self, pull_request_id: int) -> Review:
        review = Review(pull_request_id=pull_request_id, status="PENDING_HUMAN_REVIEW")
        self.db.add(review)
        self.db.flush()
        self.db.refresh(review)
        return review