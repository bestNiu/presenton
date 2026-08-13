from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlmodel import Field, SQLModel

from domains.platform.enums import AssetPromotionStatus, AssetScopeType
from utils.datetime_utils import get_current_utc_datetime


class AssetPromotionRequestModel(SQLModel, table=True):
    __tablename__ = "enterprise_asset_promotion_requests"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    source_asset_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_asset_items.id", ondelete="CASCADE"), nullable=False, index=True))
    promoted_asset_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_asset_items.id", ondelete="SET NULL"), index=True))
    target_scope_type: AssetScopeType = Field(sa_column=Column(String(32), nullable=False, index=True))
    target_workspace_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), index=True))
    requested_by: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    asset_name_snapshot: str = Field(sa_column=Column(String(300), nullable=False))
    justification: str = Field(sa_column=Column(Text, nullable=False))
    desensitization_notes: str = Field(sa_column=Column(Text, nullable=False))
    authorization_confirmed: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    status: AssetPromotionStatus = Field(default=AssetPromotionStatus.PENDING, sa_column=Column(String(32), nullable=False, index=True))
    decided_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True))
    decision_comment: str | None = Field(default=None, sa_column=Column(Text))
    decided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, onupdate=get_current_utc_datetime))
