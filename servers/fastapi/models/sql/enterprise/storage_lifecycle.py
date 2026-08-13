from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class StorageLifecycleRunModel(SQLModel, table=True):
    __tablename__ = "enterprise_storage_lifecycle_runs"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    triggered_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True),
    )
    source: str = Field(default="api", sa_column=Column(String(32), nullable=False, index=True))
    mode: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    backend: str | None = Field(default=None, sa_column=Column(String(32)))
    status: str = Field(default="running", sa_column=Column(String(32), nullable=False, index=True))
    health: str = Field(default="unknown", sa_column=Column(String(32), nullable=False, index=True))
    scanned_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    stored_bytes: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    protected_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    protected_bytes: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    missing_referenced_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    candidate_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    candidate_bytes: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    orphan_candidate_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    revoked_candidate_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    deleted_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    deleted_bytes: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    truncated: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    candidate_sample: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    failure_detail: str | None = Field(default=None, sa_column=Column(String(2000)))
    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True)
    )
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
