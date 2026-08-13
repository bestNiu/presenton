"""presentation review collaboration and version snapshots

Revision ID: e4c8a2b6d0f1
Revises: d3b7f1a5c9e0
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4c8a2b6d0f1"
down_revision: Union[str, None] = "d3b7f1a5c9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enterprise_presentation_snapshots",
        sa.Column("content_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_table(
        "enterprise_presentation_comment_threads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("presentation_entry_id", sa.Uuid(), nullable=False),
        sa.Column("slide_id", sa.Uuid()),
        sa.Column("slide_index", sa.Integer()),
        sa.Column("element_ref", sa.String(500)),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_blocking", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assigned_to", sa.Uuid()),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("slide_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("resolved_by", sa.Uuid()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["presentation_entry_id"], ["enterprise_presentation_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("presentation_entry_id", "slide_id", "is_blocking", "status", "assigned_to", "due_at", "slide_snapshot_hash", "created_by", "resolved_by", "created_at"):
        op.create_index(f"ix_enterprise_presentation_comment_threads_{column}", "enterprise_presentation_comment_threads", [column])
    op.create_table(
        "enterprise_presentation_comment_replies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["enterprise_presentation_comment_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_enterprise_presentation_comment_replies_thread_id", "enterprise_presentation_comment_replies", ["thread_id"])
    op.create_index("ix_enterprise_presentation_comment_replies_created_by", "enterprise_presentation_comment_replies", ["created_by"])


def downgrade() -> None:
    op.drop_table("enterprise_presentation_comment_replies")
    op.drop_table("enterprise_presentation_comment_threads")
    op.drop_column("enterprise_presentation_snapshots", "content_snapshot")
