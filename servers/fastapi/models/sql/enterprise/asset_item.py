from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from domains.platform.enums import AssetScopeType, AssetStatus
from utils.datetime_utils import get_current_utc_datetime


class AssetItemModel(SQLModel, table=True):
    __tablename__ = "enterprise_asset_items"
    __table_args__ = (
        UniqueConstraint("version_group_id", "version_no", name="uq_enterprise_asset_version"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    version_group_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True)
    version_no: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    is_latest: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, index=True))
    supersedes_asset_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_asset_items.id", ondelete="SET NULL"), index=True))
    duplicate_of_asset_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_asset_items.id", ondelete="SET NULL"), index=True))
    duplicate_status: str = Field(default="none", sa_column=Column(String(32), nullable=False, index=True))
    workspace_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), index=True))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    scope_type: AssetScopeType = Field(sa_column=Column(String(32), nullable=False, index=True))
    asset_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    name: str = Field(sa_column=Column(String(300), nullable=False, index=True))
    description: str | None = Field(default=None, sa_column=Column(Text))
    scene_type: str | None = Field(default=None, sa_column=Column(String(64), index=True))
    tags: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    payload_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    preview: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    preview_image_path: str | None = Field(default=None, sa_column=Column(String(2000)))
    preview_object_key: str | None = Field(default=None, sa_column=Column(String(1000), index=True))
    preview_sha256: str | None = Field(default=None, sa_column=Column(String(64)))
    preview_status: str = Field(default="structured", sa_column=Column(String(32), nullable=False, index=True))
    preview_task_id: str | None = Field(default=None, sa_column=Column(ForeignKey("async_tasks.id", ondelete="SET NULL"), index=True))
    preview_error: str | None = Field(default=None, sa_column=Column(String(1000)))
    source_presentation_entry_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_presentation_entries.id", ondelete="SET NULL"), index=True))
    source_slide_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("slides.id", ondelete="SET NULL"), index=True))
    parent_asset_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_asset_items.id", ondelete="SET NULL"), index=True))
    authorization_status: str = Field(default="internal", sa_column=Column(String(32), nullable=False, index=True))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), index=True))
    compatibility: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: AssetStatus = Field(default=AssetStatus.DRAFT, sa_column=Column(String(32), nullable=False, index=True))
    usage_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    published_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    published_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, onupdate=get_current_utc_datetime))
