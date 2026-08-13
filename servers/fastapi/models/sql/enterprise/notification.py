from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class EnterpriseNotificationModel(SQLModel, table=True):
    __tablename__ = "enterprise_notifications"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    recipient_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    workspace_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), index=True))
    actor_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    notification_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    title: str = Field(sa_column=Column(String(300), nullable=False))
    body: str = Field(sa_column=Column(String(1000), nullable=False))
    resource_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    resource_id: str = Field(sa_column=Column(String(128), nullable=False))
    action_url: str | None = Field(default=None, sa_column=Column(String(1000)))
    event_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    is_read: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False, index=True))
    read_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True))
