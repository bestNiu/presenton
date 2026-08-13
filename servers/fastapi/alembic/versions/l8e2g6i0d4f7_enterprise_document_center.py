"""enterprise document center

Revision ID: l8e2g6i0d4f7
Revises: k7d1f5h9c3e6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l8e2g6i0d4f7"
down_revision: Union[str, None] = "k7d1f5h9c3e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_group_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("supersedes_document_id", sa.Uuid(), sa.ForeignKey("enterprise_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("duplicate_of_document_id", sa.Uuid(), sa.ForeignKey("enterprise_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), nullable=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("logical_name", sa.String(300), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(200), nullable=False),
        sa.Column("object_key", sa.String(1000), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("authorization_status", sa.String(32), nullable=False, server_default="internal"),
        sa.Column("confidentiality", sa.String(8), nullable=False, server_default="L2"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("parse_status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("parse_task_id", sa.String(), sa.ForeignKey("async_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parse_error", sa.String(2000), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "extracted_metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("version_group_id", "version_no", name="uq_enterprise_document_version"),
    )
    for column in ("version_group_id", "is_latest", "supersedes_document_id", "duplicate_of_document_id", "workspace_id", "project_id", "created_by", "scope_type", "logical_name", "category", "object_key", "sha256", "authorization_status", "confidentiality", "status", "parse_status", "parse_task_id", "expires_at", "created_at"):
        if column != "object_key":
            op.create_index(f"ix_enterprise_documents_{column}", "enterprise_documents", [column])


def downgrade() -> None:
    op.drop_table("enterprise_documents")
