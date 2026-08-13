from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from domains.platform.enums import (
    PresentationDeliveryFormat,
    PresentationDeliveryStatus,
    PresentationReviewStatus,
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
    version_no: int = Field(sa_column=Column(Integer, nullable=False))
    manifest: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
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
