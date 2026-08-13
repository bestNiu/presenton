"""enterprise asset library

Revision ID: g6e0c4d8f2b3
Revises: f5d9b3c7e1a2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g6e0c4d8f2b3"
down_revision: Union[str, None] = "f5d9b3c7e1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_asset_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("scene_type", sa.String(64)),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("source_presentation_entry_id", sa.Uuid()),
        sa.Column("source_slide_id", sa.Uuid()),
        sa.Column("authorization_status", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("compatibility", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("published_by", sa.Uuid()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["enterprise_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_presentation_entry_id"], ["enterprise_presentation_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_slide_id"], ["slides.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("workspace_id", "created_by", "scope_type", "asset_type", "name", "scene_type", "payload_hash", "source_presentation_entry_id", "source_slide_id", "authorization_status", "expires_at", "status", "published_by", "created_at"):
        op.create_index(f"ix_enterprise_asset_items_{column}", "enterprise_asset_items", [column])


def downgrade() -> None:
    op.drop_table("enterprise_asset_items")
