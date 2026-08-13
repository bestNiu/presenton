from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class AssetFavoriteModel(SQLModel, table=True):
    __tablename__ = "enterprise_asset_favorites"
    __table_args__ = (
        UniqueConstraint("asset_id", "user_id", name="uq_enterprise_asset_favorite"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    asset_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_asset_items.id", ondelete="CASCADE"), nullable=False, index=True))
    user_id: uuid.UUID = Field(sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True))
