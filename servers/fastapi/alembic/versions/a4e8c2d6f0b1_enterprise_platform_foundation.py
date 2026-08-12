"""enterprise platform foundation

Revision ID: a4e8c2d6f0b1
Revises: f3a7c1d9e5b2
"""

from collections.abc import Sequence
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "a4e8c2d6f0b1"
down_revision: str | None = "f3a7c1d9e5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GENERAL_SCENE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
BID_SCENE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def upgrade() -> None:
    op.create_table(
        "enterprise_workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("workspace_type", sa.String(length=32), nullable=False),
        sa.Column("confidentiality", sa.String(length=8), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_enterprise_workspaces_owner_id",
        "enterprise_workspaces",
        ["owner_id"],
    )
    op.create_index(
        "ix_enterprise_workspaces_workspace_type",
        "enterprise_workspaces",
        ["workspace_type"],
    )

    op.create_table(
        "enterprise_workspace_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["enterprise_workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )
    op.create_index(
        "ix_enterprise_workspace_members_workspace_id",
        "enterprise_workspace_members",
        ["workspace_id"],
    )
    op.create_index(
        "ix_enterprise_workspace_members_user_id",
        "enterprise_workspace_members",
        ["user_id"],
    )

    op.create_table(
        "enterprise_workspace_folders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["enterprise_workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["enterprise_workspace_folders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_enterprise_workspace_folders_workspace_id",
        "enterprise_workspace_folders",
        ["workspace_id"],
    )
    op.create_index(
        "ix_enterprise_workspace_folders_parent_id",
        "enterprise_workspace_folders",
        ["parent_id"],
    )
    op.create_index(
        "ix_enterprise_workspace_folders_created_by",
        "enterprise_workspace_folders",
        ["created_by"],
    )

    op.create_table(
        "enterprise_scene_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scene_type", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scene_type", "version", name="uq_scene_type_version"),
    )
    op.create_index(
        "ix_enterprise_scene_definitions_scene_type",
        "enterprise_scene_definitions",
        ["scene_type"],
    )
    op.create_index(
        "ix_enterprise_scene_definitions_status",
        "enterprise_scene_definitions",
        ["status"],
    )

    op.create_table(
        "enterprise_presentation_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("folder_id", sa.Uuid(), nullable=True),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("scene_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["enterprise_workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["folder_id"], ["enterprise_workspace_folders.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["presentation_id"], ["presentations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("presentation_id", name="uq_enterprise_presentation_id"),
    )
    for column in (
        "workspace_id",
        "folder_id",
        "presentation_id",
        "created_by",
        "scene_type",
        "status",
    ):
        op.create_index(
            f"ix_enterprise_presentation_entries_{column}",
            "enterprise_presentation_entries",
            [column],
        )

    op.create_table(
        "enterprise_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["enterprise_workspaces.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("actor_id", "workspace_id", "action", "resource_type", "created_at"):
        op.create_index(
            f"ix_enterprise_audit_events_{column}",
            "enterprise_audit_events",
            [column],
        )

    scene_table = sa.table(
        "enterprise_scene_definitions",
        sa.column("id", sa.Uuid()),
        sa.column("scene_type", sa.String()),
        sa.column("version", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("config", sa.JSON()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        scene_table,
        [
            {
                "id": GENERAL_SCENE_ID,
                "scene_type": "general",
                "version": "1.0",
                "display_name": "通用 PPT 工作台",
                "description": "面向全员的通用演示文稿创建、编辑与发布流程",
                "config": {
                    "navigation": ["outline", "design", "edit", "review", "quality", "publish"],
                    "quality_policy": "general-v1",
                },
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": BID_SCENE_ID,
                "scene_type": "bid",
                "version": "1.0",
                "display_name": "竞标方案工作台",
                "description": "临床项目竞标方案生成、专业协作与审核工作台",
                "config": {
                    "navigation": [
                        "dashboard",
                        "documents",
                        "profile",
                        "requirements",
                        "strategy",
                        "modules",
                        "reviews",
                        "releases",
                    ],
                    "quality_policy": "bid-gates-v1",
                },
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("enterprise_audit_events")
    op.drop_table("enterprise_presentation_entries")
    op.drop_table("enterprise_scene_definitions")
    op.drop_table("enterprise_workspace_folders")
    op.drop_table("enterprise_workspace_members")
    op.drop_table("enterprise_workspaces")
