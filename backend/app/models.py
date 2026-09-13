import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship

from backend.app.db import Base
''' why the lambda wrapper is used ?? --> SQLAlchemy's deafult= expects
 a callable so you can't use utcnow()
 The lambda defers execution so a fresh timestamp is generated for each new row,
  not once at import time.'''

class Repository(Base):
    __tablename__ = "repositories"
    id = Column(Integer, primary_key=True)
    full_name = Column(String, unique=True, nullable=False)  # "owner/repo"
    installed_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class PullRequest(Base):
    __tablename__ = "pull_requests"
    id = Column(Integer, primary_key=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    number = Column(Integer, nullable=False)
    head_sha = Column(String, nullable=False)
    author = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    repository = relationship("Repository")


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    status = Column(String, nullable=False, default="PENDING_HUMAN_REVIEW")
    summary = Column(Text)
    already_posted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    pull_request = relationship("PullRequest")


class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False)
    file_path = Column(String, nullable=False)
    line = Column(Integer, nullable=False)
    category = Column(String, nullable=False)  # bug | style | security
    explanation = Column(Text, nullable=False)
    llm_confidence = Column(Float)
    ml_probability = Column(Float)
    ranking_score = Column(Float)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"))

    review = relationship("Review")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id = Column(Integer, primary_key=True)
    finding_id = Column(Integer, ForeignKey("findings.id"), nullable=False)
    decision = Column(String, nullable=False)  # approved | edited | rejected
    edited_explanation = Column(Text)
    decided_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    finding = relationship("Finding")


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(Integer, primary_key=True)
    artifact_path = Column(String, nullable=False)
    metrics = Column(JSON)
    feature_schema = Column(JSON)
    threshold = Column(Float, default=0.5)
    trained_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class LLMRun(Base):
    __tablename__ = "llm_runs"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    prompt = Column(Text)
    raw_response = Column(Text)
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id = Column(Integer, primary_key=True)
    delivery_id = Column(String, unique=True, nullable=False)  # X-GitHub-Delivery
    event_type = Column(String)
    received_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))