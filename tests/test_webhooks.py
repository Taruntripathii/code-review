import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
SECRET = "devsecret123"  # matches .env for the test environment


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def make_payload(action="opened"):
    return json.dumps({"action": action, "pull_request": {"number": 1}}).encode()


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