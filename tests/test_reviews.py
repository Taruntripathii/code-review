from unittest.mock import patch

import pytest

from backend.app.models import Finding, PullRequest, Repository, Review
from tests.conftest import _TestSession


@pytest.fixture()
def seeded():
    """Seed a Repository → PR → Review → Finding chain and return their ids."""
    db = _TestSession()
    try:
        repo = Repository(full_name="octocat/hello-world")
        db.add(repo)
        db.flush()
        pr = PullRequest(repository_id=repo.id, number=7, head_sha="cafe1234", author="octocat")
        db.add(pr)
        db.flush()
        review = Review(pull_request_id=pr.id, status="PENDING_HUMAN_REVIEW", summary="Found: 1 style issue(s)")
        db.add(review)
        db.flush()
        finding = Finding(
            review_id=review.id,
            file_path="app.py",
            line=1,
            category="style",
            explanation="stub finding for the reviews endpoint tests",
            llm_confidence=0.5,
        )
        db.add(finding)
        db.commit()
        return {"review_id": review.id, "finding_id": finding.id}
    finally:
        db.close()


def test_list_reviews_filters_by_status(client, seeded):
    resp = client.get("/api/reviews", params={"status": "PENDING_HUMAN_REVIEW"})
    assert resp.status_code == 200
    reviews = resp.json()
    assert len(reviews) == 1
    assert reviews[0]["id"] == seeded["review_id"]
    assert reviews[0]["status"] == "PENDING_HUMAN_REVIEW"

    # A status with no matching rows comes back empty.
    assert client.get("/api/reviews", params={"status": "PUBLISHED"}).json() == []


def test_list_findings_includes_latest_decision(client, seeded):
    review_id = seeded["review_id"]
    finding_id = seeded["finding_id"]

    resp = client.get(f"/api/reviews/{review_id}/findings")
    assert resp.status_code == 200
    findings = resp.json()
    assert len(findings) == 1
    assert findings[0]["id"] == finding_id
    assert findings[0]["decision"] is None  # no decision yet

    # Record a decision, then confirm it surfaces on the next read.
    client.patch(f"/api/findings/{finding_id}", json={"decision": "approved"})
    findings = client.get(f"/api/reviews/{review_id}/findings").json()
    assert findings[0]["decision"] == "approved"


def test_decide_finding_validates_decision(client, seeded):
    finding_id = seeded["finding_id"]

    ok = client.patch(f"/api/findings/{finding_id}", json={"decision": "rejected"})
    assert ok.status_code == 200
    assert ok.json()["decision"] == "rejected"

    bad = client.patch(f"/api/findings/{finding_id}", json={"decision": "maybe"})
    assert bad.status_code == 422

    missing = client.patch("/api/findings/999999", json={"decision": "approved"})
    assert missing.status_code == 404


def test_publish_selects_only_approved_findings(client, seeded, monkeypatch):
    review_id = seeded["review_id"]
    finding_id = seeded["finding_id"]

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    # Nothing approved yet → publish is skipped without calling GitHub.
    with patch("backend.app.main.GitHubClient") as mock_gh_cls:
        resp = client.post(f"/api/reviews/{review_id}/publish")
        assert resp.json()["status"] == "skipped"
        mock_gh_cls.return_value.create_review.assert_not_called()

    # Approve the finding, then publish selects it and posts to GitHub.
    client.patch(f"/api/findings/{finding_id}", json={"decision": "approved"})
    with patch("backend.app.main.GitHubClient") as mock_gh_cls:
        resp = client.post(f"/api/reviews/{review_id}/publish")
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"
        mock_gh_cls.return_value.create_review.assert_called_once()
        owner, repo, number, comments = mock_gh_cls.return_value.create_review.call_args.args
        assert owner == "octocat"
        assert repo == "hello-world"
        assert number == 7
        assert len(comments) == 1
        assert comments[0]["path"] == "app.py"
