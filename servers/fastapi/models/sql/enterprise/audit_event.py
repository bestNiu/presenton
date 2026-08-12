from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlmodel import Field, SQLModel

from domains.platform.enums import AuditResult
from utils.datetime_utils import get_current_utc_datetime


class AuditEventModel(SQLModel, table=True):
    __tablename__ = "enterprise_audit_events"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    actor_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    workspace_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_workspaces.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    action: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    resource_type: str = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    resource_id: str = Field(sa_column=Column(String(128), nullable=False))
    result: AuditResult = Field(
        default=AuditResult.SUCCESS,
        sa_column=Column(String(32), nullable=False),
    )
    event_metadata: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=get_current_utc_datetime,
            index=True,
        )
    )
