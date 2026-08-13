from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class EnterpriseKnowledgeOutlineModel(SQLModel, table=True):
    __tablename__ = "enterprise_knowledge_outlines"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    workspace_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), index=True
        ),
    )
    project_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"), index=True
        ),
    )
    presentation_entry_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_presentation_entries.id", ondelete="SET NULL"),
            index=True,
        ),
    )
    created_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True),
    )
    scope_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    topic: str = Field(sa_column=Column(String(500), nullable=False))
    audience: str | None = Field(default=None, sa_column=Column(String(300)))
    language: str = Field(default="Chinese", sa_column=Column(String(64), nullable=False))
    n_slides: int = Field(sa_column=Column(Integer, nullable=False))
    status: str = Field(default="queued", sa_column=Column(String(32), nullable=False, index=True))
    task_id: str | None = Field(
        default=None,
        sa_column=Column(ForeignKey("async_tasks.id", ondelete="SET NULL"), index=True),
    )
    query: str = Field(sa_column=Column(String(500), nullable=False))
    document_ids: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    context_manifest: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    outline: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    prompt_version: str = Field(default="knowledge-outline-v1", sa_column=Column(String(64), nullable=False))
    schema_version: str = Field(default="cited-outline-v1", sa_column=Column(String(64), nullable=False))
    error: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, index=True)
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=get_current_utc_datetime, onupdate=get_current_utc_datetime)
    )
