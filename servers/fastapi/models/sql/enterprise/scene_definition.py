from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, JSON, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from domains.platform.enums import SceneStatus
from utils.datetime_utils import get_current_utc_datetime


class SceneDefinitionModel(SQLModel, table=True):
    __tablename__ = "enterprise_scene_definitions"
    __table_args__ = (
        UniqueConstraint("scene_type", "version", name="uq_scene_type_version"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    scene_type: str = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    version: str = Field(sa_column=Column(String(32), nullable=False))
    display_name: str = Field(sa_column=Column(String(200), nullable=False))
    description: str | None = Field(
        default=None, sa_column=Column(String(1000), nullable=True)
    )
    config: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: SceneStatus = Field(
        default=SceneStatus.ACTIVE,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, default=get_current_utc_datetime
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=get_current_utc_datetime,
            onupdate=get_current_utc_datetime,
        )
    )
