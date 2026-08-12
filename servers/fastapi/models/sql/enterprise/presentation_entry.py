from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from domains.platform.enums import PresentationEntryStatus
from utils.datetime_utils import get_current_utc_datetime


class PresentationEntryModel(SQLModel, table=True):
    __tablename__ = "enterprise_presentation_entries"
    __table_args__ = (
        UniqueConstraint("presentation_id", name="uq_enterprise_presentation_id"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    workspace_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    folder_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_workspace_folders.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    presentation_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("presentations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    created_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
        )
    )
    title: str | None = Field(
        default=None, sa_column=Column(String(500), nullable=True)
    )
    scene_type: str = Field(
        default="general", sa_column=Column(String(64), nullable=False, index=True)
    )
    status: PresentationEntryStatus = Field(
        default=PresentationEntryStatus.DRAFT,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    row_version: int = Field(
        default=1, sa_column=Column(Integer, nullable=False, default=1)
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
