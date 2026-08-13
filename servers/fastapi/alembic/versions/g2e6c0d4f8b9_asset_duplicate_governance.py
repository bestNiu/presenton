"""asset duplicate governance

Revision ID: g2e6c0d4f8b9
Revises: f1d5b9c3e7a8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g2e6c0d4f8b9"
down_revision: Union[str, None] = "f1d5b9c3e7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprise_asset_items", sa.Column("duplicate_of_asset_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_asset_items", sa.Column("duplicate_status", sa.String(32), nullable=False, server_default="none"))
    op.create_index("ix_enterprise_asset_items_duplicate_of_asset_id", "enterprise_asset_items", ["duplicate_of_asset_id"])
    op.create_index("ix_enterprise_asset_items_duplicate_status", "enterprise_asset_items", ["duplicate_status"])
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key("fk_enterprise_asset_duplicate_of", "enterprise_asset_items", "enterprise_asset_items", ["duplicate_of_asset_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_enterprise_asset_duplicate_of", "enterprise_asset_items", type_="foreignkey")
    op.drop_index("ix_enterprise_asset_items_duplicate_status", table_name="enterprise_asset_items")
    op.drop_index("ix_enterprise_asset_items_duplicate_of_asset_id", table_name="enterprise_asset_items")
    op.drop_column("enterprise_asset_items", "duplicate_status")
    op.drop_column("enterprise_asset_items", "duplicate_of_asset_id")
