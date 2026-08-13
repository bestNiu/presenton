"""asset personalization

Revision ID: d9b3f7a1c5e6
Revises: c8a2e6f0b4d5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9b3f7a1c5e6"
down_revision: Union[str, None] = "c8a2e6f0b4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_asset_favorites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["enterprise_asset_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("asset_id", "user_id", name="uq_enterprise_asset_favorite"),
    )
    for column in ("asset_id", "user_id", "created_at"):
        op.create_index(f"ix_enterprise_asset_favorites_{column}", "enterprise_asset_favorites", [column])


def downgrade() -> None:
    op.drop_table("enterprise_asset_favorites")
