from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from domains.platform.enums import (
    PresentationDeliveryFormat,
    PresentationDeliveryStatus,
    PresentationCommentStatus,
    PresentationReviewStatus,
    PresentationQualitySeverity,
    PresentationQualityStatus,
)
from utils.datetime_utils import get_current_utc_datetime


class PresentationReviewModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_reviews"
    __table_args__ = (
        UniqueConstraint("presentation_entry_id", "submission_no", name="uq_presentation_review_submission"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    presentation_entry_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_entries.id", ondelete="CASCADE"), nullable=False, index=True))
    submission_no: int = Field(sa_column=Column(Integer, nullable=False))
    slide_snapshot_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    status: PresentationReviewStatus = Field(default=PresentationReviewStatus.PENDING, sa_column=Column(String(32), nullable=False, index=True))
    submitted_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    decided_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    decision_comment: str | None = Field(default=None, sa_column=Column(String(2000)))
    submitted_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    decided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class PresentationSnapshotModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_snapshots"
    __table_args__ = (
        UniqueConstraint("presentation_entry_id", "version_no", name="uq_presentation_snapshot_version"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    presentation_entry_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_entries.id", ondelete="CASCADE"), nullable=False, index=True))
    review_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_reviews.id", ondelete="RESTRICT"), nullable=False, index=True))
    quality_run_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_presentation_quality_runs.id", ondelete="RESTRICT"), index=True))
    version_no: int = Field(sa_column=Column(Integer, nullable=False))
    manifest: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    content_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    manifest_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    slide_snapshot_hash: str = Field(sa_column=Column(String(64), nullable=False))
    frozen_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    frozen_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))


class PresentationDeliveryArtifactModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_delivery_artifacts"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    snapshot_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_snapshots.id", ondelete="CASCADE"), nullable=False, index=True))
    derived_presentation_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("presentations.id", ondelete="SET NULL"), index=True))
    format: PresentationDeliveryFormat = Field(sa_column=Column(String(16), nullable=False, index=True))
    watermark_text: str = Field(sa_column=Column(String(300), nullable=False))
    file_path: str = Field(sa_column=Column(String(2000), nullable=False))
    object_key: str | None = Field(default=None, sa_column=Column(String(1000), index=True))
    file_name: str = Field(sa_column=Column(String(500), nullable=False))
    sha256: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    size_bytes: int = Field(sa_column=Column(Integer, nullable=False))
    status: PresentationDeliveryStatus = Field(default=PresentationDeliveryStatus.READY, sa_column=Column(String(32), nullable=False, index=True))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))


class PresentationDownloadGrantModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_download_grants"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    artifact_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_delivery_artifacts.id", ondelete="CASCADE"), nullable=False, index=True))
    token_hash: str = Field(sa_column=Column(String(64), nullable=False, unique=True, index=True))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    max_downloads: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    download_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    last_downloaded_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class PresentationQualityRunModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_quality_runs"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    presentation_entry_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_entries.id", ondelete="CASCADE"), nullable=False, index=True))
    slide_snapshot_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    status: PresentationQualityStatus = Field(sa_column=Column(String(32), nullable=False, index=True))
    blocking_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    warning_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    policy_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime, index=True))


class PresentationQualityIssueModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_quality_issues"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    quality_run_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_quality_runs.id", ondelete="CASCADE"), nullable=False, index=True))
    rule_code: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    severity: PresentationQualitySeverity = Field(sa_column=Column(String(32), nullable=False, index=True))
    slide_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("slides.id", ondelete="SET NULL"), index=True))
    slide_index: int | None = Field(default=None, sa_column=Column(Integer))
    element_ref: str | None = Field(default=None, sa_column=Column(String(500)))
    message: str = Field(sa_column=Column(String(1000), nullable=False))
    details: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class PresentationSourceCitationModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_source_citations"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    presentation_entry_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_entries.id", ondelete="CASCADE"), nullable=False, index=True))
    slide_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("slides.id", ondelete="CASCADE"), index=True))
    element_ref: str | None = Field(default=None, sa_column=Column(String(500)))
    source_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    source_id: str = Field(sa_column=Column(String(500), nullable=False, index=True))
    source_version: str | None = Field(default=None, sa_column=Column(String(100)))
    locator: str | None = Field(default=None, sa_column=Column(String(500)))
    excerpt: str | None = Field(default=None, sa_column=Column(String(2000)))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))


class PresentationCommentThreadModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_comment_threads"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    presentation_entry_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_entries.id", ondelete="CASCADE"), nullable=False, index=True))
    slide_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("slides.id", ondelete="SET NULL"), index=True))
    slide_index: int | None = Field(default=None, sa_column=Column(Integer))
    element_ref: str | None = Field(default=None, sa_column=Column(String(500)))
    title: str = Field(sa_column=Column(String(300), nullable=False))
    body: str = Field(sa_column=Column(Text, nullable=False))
    is_blocking: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False, index=True))
    status: PresentationCommentStatus = Field(default=PresentationCommentStatus.OPEN, sa_column=Column(String(32), nullable=False, index=True))
    assigned_to: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    due_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), index=True))
    slide_snapshot_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    resolved_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime, index=True))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class PresentationCommentReplyModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_comment_replies"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    thread_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_comment_threads.id", ondelete="CASCADE"), nullable=False, index=True))
    body: str = Field(sa_column=Column(Text, nullable=False))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
