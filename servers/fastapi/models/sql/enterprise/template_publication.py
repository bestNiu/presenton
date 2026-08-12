from datetime import datetime
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from domains.platform.enums import TemplatePublicationStatus, TemplateScopeType
from utils.datetime_utils import get_current_utc_datetime


class TemplatePublicationModel(SQLModel, table=True):
    __tablename__ = "enterprise_template_publications"
    __table_args__ = (
        UniqueConstraint(
            "publication_key",
            "version",
            name="uq_enterprise_template_publication_version",
        ),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    publication_key: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    template_id: str = Field(
        sa_column=Column(
            ForeignKey("template_v2.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
            index=True,
        )
    )
    workspace_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )
    created_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
        ),
    )
    scope_type: TemplateScopeType = Field(
        sa_column=Column(String(32), nullable=False, index=True)
    )
    scene_type: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True, index=True)
    )
    version: int = Field(sa_column=Column(Integer, nullable=False))
    status: TemplatePublicationStatus = Field(
        default=TemplatePublicationStatus.DRAFT,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    display_name: str = Field(sa_column=Column(String(200), nullable=False))
    description: str | None = Field(
        default=None, sa_column=Column(String(1000), nullable=True)
    )
    rules: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    compatibility: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    preview_url: str | None = Field(
        default=None, sa_column=Column(String(2000), nullable=True)
    )
    is_default: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
    )
    recommended_order: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, default=0)
    )
    submitted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    published_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    offline_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
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
