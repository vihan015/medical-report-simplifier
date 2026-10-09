import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="patient")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")  # uploaded|extracted|simplified|failed
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    extraction_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    measurements: Mapped[list["ExtractedMeasurement"]] = relationship(cascade="all, delete-orphan")


class ExtractedMeasurement(Base):
    __tablename__ = "extracted_measurements"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    test_name: Mapped[str] = mapped_column(String(100))
    value_text: Mapped[str] = mapped_column(String(50))
    unit: Mapped[str] = mapped_column(String(50), default="")
    reference_range_text: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)


class GeneratedExplanation(Base):
    __tablename__ = "generated_explanations"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    language: Mapped[str] = mapped_column(String(8))
    draft_json: Mapped[str] = mapped_column(Text)  # the raw LLM draft that was validated
    response_json: Mapped[str] = mapped_column(Text)  # what the user saw
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(32), default="1")
    fallback_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    metric: Mapped[str] = mapped_column(String(64))
    score: Mapped[float] = mapped_column(Float)
    failure_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    evaluator_version: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc: Mapped[str] = mapped_column(String(200), unique=True)
    source: Mapped[str] = mapped_column(String(300))
    version: Mapped[str] = mapped_column(String(32))
    sections: Mapped[list] = mapped_column(JSON, default=list)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
