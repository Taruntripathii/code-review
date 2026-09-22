"""Shared test fixtures and hermetic environment setup.

Import order matters: env vars are set *before* any backend module is imported,
because backend.app.db and backend.app.webhooks read them at import time. This
keeps the suite independent of any local .env file or CI environment.
"""

import os

# Must be set before backend modules load their module-level config.
os.environ["GITHUB_WEBHOOK_SECRET"] = "devsecret123"
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import webhooks
from backend.app.db import Base, get_db
from backend.app.main import app

# StaticPool + shared in-memory DB: one database shared across every connection
# within the process, so the app's get_db and the test see the same schema/rows.
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

# Belt-and-suspenders: this module attr is read at import time in webhooks.py,
# so pin it here too in case something imported that module before conftest ran.
webhooks.WEBHOOK_SECRET = "devsecret123"


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _fresh_schema():
    """Create every table before a test and drop it after, so no state leaks
    between tests (the webhook_deliveries dedup table in particular)."""
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture()
def client():
    return TestClient(app)
