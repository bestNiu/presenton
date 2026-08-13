"""asset versioning

Revision ID: f1d5b9c3e7a8
Revises: e0c4a8b2d6f7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1d5b9c3e7a8"
down_revision: Union[str, None] = "e0c4a8b2d6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprise_asset_items", sa.Column("version_group_id", sa.Uuid(), nullable=True))
    op.add_column("enterprise_asset_items", sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("enterprise_asset_items", sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("enterprise_asset_items", sa.Column("supersedes_asset_id", sa.Uuid(), nullable=True))
    op.execute(sa.text("UPDATE enterprise_asset_items SET version_group_id = id WHERE version_group_id IS NULL"))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("enterprise_asset_items", "version_group_id", nullable=False)
        op.create_foreign_key(
            "fk_enterprise_asset_supersedes",
            "enterprise_asset_items",
            "enterprise_asset_items",
            ["supersedes_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_enterprise_asset_items_version_group_id", "enterprise_asset_items", ["version_group_id"])
    op.create_index("ix_enterprise_asset_items_is_latest", "enterprise_asset_items", ["is_latest"])
    op.create_index("ix_enterprise_asset_items_supersedes_asset_id", "enterprise_asset_items", ["supersedes_asset_id"])
    if op.get_bind().dialect.name != "sqlite":
        op.create_unique_constraint(
            "uq_enterprise_asset_version",
            "enterprise_asset_items",
            ["version_group_id", "version_no"],
        )
    else:
        op.create_index(
            "uq_enterprise_asset_version",
            "enterprise_asset_items",
            ["version_group_id", "version_no"],
            unique=True,
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("uq_enterprise_asset_version", "enterprise_asset_items", type_="unique")
        op.drop_constraint("fk_enterprise_asset_supersedes", "enterprise_asset_items", type_="foreignkey")
    else:
        op.drop_index("uq_enterprise_asset_version", table_name="enterprise_asset_items")
    op.drop_index("ix_enterprise_asset_items_supersedes_asset_id", table_name="enterprise_asset_items")
    op.drop_index("ix_enterprise_asset_items_is_latest", table_name="enterprise_asset_items")
    op.drop_index("ix_enterprise_asset_items_version_group_id", table_name="enterprise_asset_items")
    op.drop_column("enterprise_asset_items", "supersedes_asset_id")
    op.drop_column("enterprise_asset_items", "is_latest")
    op.drop_column("enterprise_asset_items", "version_no")
    op.drop_column("enterprise_asset_items", "version_group_id")
