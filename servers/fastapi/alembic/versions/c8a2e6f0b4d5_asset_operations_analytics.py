"""asset operations analytics

Revision ID: c8a2e6f0b4d5
Revises: b7f1d5e9a3c4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8a2e6f0b4d5"
down_revision: Union[str, None] = "b7f1d5e9a3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprise_asset_items", sa.Column("preview", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "enterprise_asset_usage_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("presentation_entry_id", sa.Uuid(), nullable=False),
        sa.Column("slide_id", sa.Uuid(), nullable=False),
        sa.Column("reused_by", sa.Uuid()),
        sa.Column("insert_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["enterprise_asset_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["enterprise_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["presentation_entry_id"], ["enterprise_presentation_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reused_by"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("asset_id", "workspace_id", "presentation_entry_id", "slide_id", "reused_by", "created_at"):
        op.create_index(f"ix_enterprise_asset_usage_events_{column}", "enterprise_asset_usage_events", [column])


def downgrade() -> None:
    op.drop_table("enterprise_asset_usage_events")
    op.drop_column("enterprise_asset_items", "preview")
