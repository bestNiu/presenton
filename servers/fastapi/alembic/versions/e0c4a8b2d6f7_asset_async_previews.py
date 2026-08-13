"""asset async previews

Revision ID: e0c4a8b2d6f7
Revises: d9b3f7a1c5e6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e0c4a8b2d6f7"
down_revision: Union[str, None] = "d9b3f7a1c5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprise_asset_items", sa.Column("preview_image_path", sa.String(2000)))
    op.add_column("enterprise_asset_items", sa.Column("preview_status", sa.String(32), nullable=False, server_default="structured"))
    op.add_column("enterprise_asset_items", sa.Column("preview_task_id", sa.String(), nullable=True))
    op.add_column("enterprise_asset_items", sa.Column("preview_error", sa.String(1000)))
    op.create_index("ix_enterprise_asset_items_preview_status", "enterprise_asset_items", ["preview_status"])
    op.create_index("ix_enterprise_asset_items_preview_task_id", "enterprise_asset_items", ["preview_task_id"])
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key("fk_enterprise_asset_items_preview_task", "enterprise_asset_items", "async_tasks", ["preview_task_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_enterprise_asset_items_preview_task", "enterprise_asset_items", type_="foreignkey")
    op.drop_index("ix_enterprise_asset_items_preview_task_id", table_name="enterprise_asset_items")
    op.drop_index("ix_enterprise_asset_items_preview_status", table_name="enterprise_asset_items")
    op.drop_column("enterprise_asset_items", "preview_error")
    op.drop_column("enterprise_asset_items", "preview_task_id")
    op.drop_column("enterprise_asset_items", "preview_status")
    op.drop_column("enterprise_asset_items", "preview_image_path")
