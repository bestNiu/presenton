from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class EnterpriseDocumentModel(SQLModel, table=True):
    __tablename__ = "enterprise_documents"
    __table_args__ = (
        UniqueConstraint(
            "version_group_id", "version_no", name="uq_enterprise_document_version"
        ),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    version_group_id: uuid.UUID = Field(default_factory=uuid.uuid4, index=True)
    version_no: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    is_latest: bool = Field(
        default=True, sa_column=Column(Boolean, nullable=False, index=True)
    )
    supersedes_document_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_documents.id", ondelete="SET NULL"), index=True
        ),
    )
    duplicate_of_document_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_documents.id", ondelete="SET NULL"), index=True
        ),
    )
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
    created_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True),
    )
    scope_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    logical_name: str = Field(sa_column=Column(String(300), nullable=False, index=True))
    category: str = Field(default="general", sa_column=Column(String(64), nullable=False, index=True))
    file_name: str = Field(sa_column=Column(String(500), nullable=False))
    mime_type: str = Field(sa_column=Column(String(200), nullable=False))
    object_key: str = Field(sa_column=Column(String(1000), nullable=False, unique=True, index=True))
    sha256: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    size_bytes: int = Field(sa_column=Column(Integer, nullable=False))
    authorization_status: str = Field(
        default="internal", sa_column=Column(String(32), nullable=False, index=True)
    )
    confidentiality: str = Field(
        default="L2", sa_column=Column(String(8), nullable=False, index=True)
    )
    status: str = Field(
        default="active", sa_column=Column(String(32), nullable=False, index=True)
    )
    parse_status: str = Field(
        default="queued", sa_column=Column(String(32), nullable=False, index=True)
    )
    parse_task_id: str | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("async_tasks.id", ondelete="SET NULL"), index=True
        ),
    )
    parse_error: str | None = Field(default=None, sa_column=Column(String(2000)))
    extracted_text: str | None = Field(default=None, sa_column=Column(Text))
    extracted_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), index=True))
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=get_current_utc_datetime,
            index=True,
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
