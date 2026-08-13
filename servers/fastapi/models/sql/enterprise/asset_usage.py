from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class AssetUsageEventModel(SQLModel, table=True):
    __tablename__ = "enterprise_asset_usage_events"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    asset_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_asset_items.id", ondelete="CASCADE"), nullable=False, index=True))
    workspace_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), nullable=False, index=True))
    presentation_entry_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_entries.id", ondelete="CASCADE"), nullable=False, index=True))
    slide_id: uuid.UUID = Field(sa_column=Column(ForeignKey("slides.id", ondelete="CASCADE"), nullable=False, index=True))
    reused_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    insert_index: int = Field(sa_column=Column(Integer, nullable=False))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True))
