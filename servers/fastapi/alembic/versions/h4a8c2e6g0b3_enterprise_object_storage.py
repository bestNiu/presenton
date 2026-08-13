"""enterprise object storage

Revision ID: h4a8c2e6g0b3
Revises: g2e6c0d4f8b9, f9d3b7c1e5a6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4a8c2e6g0b3"
down_revision: Union[str, Sequence[str], None] = ("g2e6c0d4f8b9", "f9d3b7c1e5a6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprise_asset_items", sa.Column("preview_object_key", sa.String(1000), nullable=True))
    op.add_column("enterprise_asset_items", sa.Column("preview_sha256", sa.String(64), nullable=True))
    op.create_index("ix_enterprise_asset_items_preview_object_key", "enterprise_asset_items", ["preview_object_key"])
    op.add_column("enterprise_presentation_delivery_artifacts", sa.Column("object_key", sa.String(1000), nullable=True))
    op.create_index("ix_enterprise_presentation_delivery_artifacts_object_key", "enterprise_presentation_delivery_artifacts", ["object_key"])
    op.add_column("enterprise_bid_delivery_artifacts", sa.Column("object_key", sa.String(1000), nullable=True))
    op.create_index("ix_enterprise_bid_delivery_artifacts_object_key", "enterprise_bid_delivery_artifacts", ["object_key"])


def downgrade() -> None:
    op.drop_index("ix_enterprise_bid_delivery_artifacts_object_key", table_name="enterprise_bid_delivery_artifacts")
    op.drop_column("enterprise_bid_delivery_artifacts", "object_key")
    op.drop_index("ix_enterprise_presentation_delivery_artifacts_object_key", table_name="enterprise_presentation_delivery_artifacts")
    op.drop_column("enterprise_presentation_delivery_artifacts", "object_key")
    op.drop_index("ix_enterprise_asset_items_preview_object_key", table_name="enterprise_asset_items")
    op.drop_column("enterprise_asset_items", "preview_sha256")
    op.drop_column("enterprise_asset_items", "preview_object_key")
