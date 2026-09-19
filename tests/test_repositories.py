import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base
from backend.app.repositories import PullRequestRepo

# SQLite in-memory: fast, no Docker needed for this test tier
ENGINE = create_engine("sqlite:///:memory:")
TestSession = sessionmaker(bind=ENGINE)


@pytest.fixture()
def db():
    Base.metadata.create_all(ENGINE)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(ENGINE)


def test_get_or_create_pull_request(db):
    repo = PullRequestRepo(db)
    pr = repo.get_or_create(repository_id=1, number=42, head_sha="abc123", author="tarun")
    assert pr.id is not None

    same_pr = repo.get_or_create(repository_id=1, number=42, head_sha="def456", author="tarun")
    assert same_pr.id == pr.id
    assert same_pr.head_sha == "def456"
