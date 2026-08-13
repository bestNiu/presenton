"""knowledge outlines

Revision ID: n0g4i8k2f6h9
Revises: m9f3h7j1e5g8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n0g4i8k2f6h9"
down_revision: Union[str, None] = "m9f3h7j1e5g8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_knowledge_outlines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), nullable=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("presentation_entry_id", sa.Uuid(), sa.ForeignKey("enterprise_presentation_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("topic", sa.String(500), nullable=False),
        sa.Column("audience", sa.String(300), nullable=True),
        sa.Column("language", sa.String(64), nullable=False, server_default="Chinese"),
        sa.Column("n_slides", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("task_id", sa.String(), sa.ForeignKey("async_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("context_manifest", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("outline", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("workspace_id", "project_id", "presentation_entry_id", "created_by", "scope_type", "status", "task_id", "created_at"):
        op.create_index(f"ix_enterprise_knowledge_outlines_{column}", "enterprise_knowledge_outlines", [column])


def downgrade() -> None:
    op.drop_table("enterprise_knowledge_outlines")
