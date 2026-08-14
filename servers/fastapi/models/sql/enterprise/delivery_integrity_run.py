from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class DeliveryIntegrityRunModel(SQLModel, table=True):
    __tablename__ = "enterprise_delivery_integrity_runs"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    triggered_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True),
    )
    source: str = Field(default="api", sa_column=Column(String(32), nullable=False, index=True))
    lock_key: str | None = Field(default=None, sa_column=Column(String(64), unique=True))
    status: str = Field(default="running", sa_column=Column(String(32), nullable=False, index=True))
    health: str = Field(default="unknown", sa_column=Column(String(32), nullable=False, index=True))
    timeout_seconds: int = Field(default=1800, sa_column=Column(Integer, nullable=False))
    workspace_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    completed_workspace_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    failed_workspace_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    artifact_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    integrity_failed: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    new_anomalies: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    duration_ms: int | None = Field(default=None, sa_column=Column(Integer))
    failure_detail: str | None = Field(default=None, sa_column=Column(String(2000)))
    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True)
    )
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
