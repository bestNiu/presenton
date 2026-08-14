from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class DeliveryIntegrityIncidentModel(SQLModel, table=True):
    __tablename__ = "enterprise_delivery_integrity_incidents"
    __table_args__ = (
        UniqueConstraint("scene_type", "artifact_id", name="uq_delivery_integrity_incident_artifact"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    workspace_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    scene_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    artifact_id: uuid.UUID = Field(index=True)
    resource_id: uuid.UUID = Field(index=True)
    resource_title: str = Field(sa_column=Column(String(500), nullable=False))
    detail_url: str = Field(sa_column=Column(String(1000), nullable=False))
    anomaly_types: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    severity: str = Field(default="high", sa_column=Column(String(32), nullable=False, index=True))
    status: str = Field(default="open", sa_column=Column(String(32), nullable=False, index=True))
    assigned_to: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True),
    )
    occurrence_count: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    resolution_note: str | None = Field(default=None, sa_column=Column(String(2000)))
    resolved_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")),
    )
    first_detected_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True)
    )
    last_detected_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True)
    )
    resolved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True)
    )
