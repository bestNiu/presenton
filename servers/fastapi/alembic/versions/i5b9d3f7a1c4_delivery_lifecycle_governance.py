"""delivery lifecycle governance

Revision ID: i5b9d3f7a1c4
Revises: h4a8c2e6g0b3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5b9d3f7a1c4"
down_revision: Union[str, None] = "h4a8c2e6g0b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprise_presentation_delivery_artifacts", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_enterprise_presentation_delivery_artifacts_revoked_at", "enterprise_presentation_delivery_artifacts", ["revoked_at"])
    op.add_column("enterprise_presentation_download_grants", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_enterprise_presentation_download_grants_revoked_at", "enterprise_presentation_download_grants", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_enterprise_presentation_download_grants_revoked_at", table_name="enterprise_presentation_download_grants")
    op.drop_column("enterprise_presentation_download_grants", "revoked_at")
    op.drop_index("ix_enterprise_presentation_delivery_artifacts_revoked_at", table_name="enterprise_presentation_delivery_artifacts")
    op.drop_column("enterprise_presentation_delivery_artifacts", "revoked_at")
