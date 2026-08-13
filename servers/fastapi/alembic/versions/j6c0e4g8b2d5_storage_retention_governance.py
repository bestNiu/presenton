"""storage retention governance

Revision ID: j6c0e4g8b2d5
Revises: i5b9d3f7a1c4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j6c0e4g8b2d5"
down_revision: Union[str, None] = "i5b9d3f7a1c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprise_presentation_delivery_artifacts", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_enterprise_presentation_delivery_artifacts_purged_at", "enterprise_presentation_delivery_artifacts", ["purged_at"])
    op.add_column("enterprise_bid_delivery_artifacts", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_enterprise_bid_delivery_artifacts_purged_at", "enterprise_bid_delivery_artifacts", ["purged_at"])


def downgrade() -> None:
    op.drop_index("ix_enterprise_bid_delivery_artifacts_purged_at", table_name="enterprise_bid_delivery_artifacts")
    op.drop_column("enterprise_bid_delivery_artifacts", "purged_at")
    op.drop_index("ix_enterprise_presentation_delivery_artifacts_purged_at", table_name="enterprise_presentation_delivery_artifacts")
    op.drop_column("enterprise_presentation_delivery_artifacts", "purged_at")
