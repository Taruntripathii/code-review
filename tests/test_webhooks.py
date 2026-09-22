import hashlib
import hmac
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
SECRET = "devsecret123"  # matches .env for the test environment


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def make_payload(action="opened"):
    return json.dumps({"action": action, "pull_request": {"number": 1}}).encode()


def make_full_payload(delivery_pr_number=7):
    """A realistic pull_request payload with the repository + head blocks the
    webhook needs to actually schedule a review."""
    return json.dumps(
        {
            "action": "opened",
            "repository": {"full_name": "octocat/hello-world"},
            "pull_request": {
                "number": delivery_pr_number,
                "head": {"sha": "cafe1234"},
                "user": {"login": "octocat"},
            },
        }
    ).encode()


def test_valid_signature_accepted():
    body = make_payload()
    resp = client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sign(body),
            "X-GitHub-Delivery": "delivery-1",
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_invalid_signature_rejected():
    body = make_payload()
    resp = client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": "sha256=deadbeef",
            "X-GitHub-Delivery": "delivery-2",
            "X-GitHub-Event": "pull_request",
        },
    )
    assert resp.status_code == 401


def test_duplicate_delivery_deduped():
    body = make_payload()
    headers = {
        "X-Hub-Signature-256": sign(body),
        "X-GitHub-Delivery": "delivery-3",
        "X-GitHub-Event": "pull_request",
    }
    first = client.post("/api/webhooks/github", content=body, headers=headers)
    second = client.post("/api/webhooks/github", content=body, headers=headers)
    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "duplicate"


def test_unhandled_action_ignored():
    body = make_payload(action="closed")
    resp = client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sign(body),
            "X-GitHub-Delivery": "delivery-4",
            "X-GitHub-Event": "pull_request",
        },
    )
    assert resp.json()["status"] == "ignored"


def test_full_payload_schedules_review():
    """A realistic payload (repository + head blocks) upserts the PR and schedules
    the pipeline. trigger_review is patched because TestClient runs BackgroundTasks
    synchronously after the response — otherwise it would hit the real LLM/GitHub."""
    body = make_full_payload()
    with patch("backend.app.main.trigger_review") as mock_trigger:
        resp = client.post(
            "/api/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sign(body),
                "X-GitHub-Delivery": "delivery-5",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    mock_trigger.assert_called_once()
    kwargs = mock_trigger.call_args.kwargs
    assert kwargs["owner"] == "octocat"
    assert kwargs["repo"] == "hello-world"
    assert kwargs["pr_number"] == 7
    assert kwargs["head_sha"] == "cafe1234"
