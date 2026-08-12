from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from domains.platform.enums import ConfidentialityLevel, WorkspaceRole, WorkspaceType
from utils.datetime_utils import get_current_utc_datetime


class WorkspaceModel(SQLModel, table=True):
    __tablename__ = "enterprise_workspaces"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    owner_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True
        )
    )
    name: str = Field(sa_column=Column(String(200), nullable=False))
    workspace_type: WorkspaceType = Field(
        default=WorkspaceType.PERSONAL,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    confidentiality: ConfidentialityLevel = Field(
        default=ConfidentialityLevel.L2,
        sa_column=Column(String(8), nullable=False),
    )
    is_archived: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
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


class WorkspaceMemberModel(SQLModel, table=True):
    __tablename__ = "enterprise_workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    workspace_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    role: WorkspaceRole = Field(
        default=WorkspaceRole.VIEWER,
        sa_column=Column(String(32), nullable=False),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, default=get_current_utc_datetime
        )
    )


class WorkspaceFolderModel(SQLModel, table=True):
    __tablename__ = "enterprise_workspace_folders"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    workspace_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    parent_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("enterprise_workspace_folders.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )
    created_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
        )
    )
    name: str = Field(sa_column=Column(String(200), nullable=False))
    is_archived: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
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
