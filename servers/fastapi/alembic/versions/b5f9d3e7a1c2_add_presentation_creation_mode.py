"""add presentation creation mode

Revision ID: b5f9d3e7a1c2
Revises: a4e8c2d6f0b1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5f9d3e7a1c2"
down_revision: Union[str, None] = "a4e8c2d6f0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enterprise_presentation_entries",
        sa.Column(
            "creation_mode",
            sa.String(length=32),
            nullable=False,
            server_default="import",
        )
    )
    op.create_index(
        "ix_enterprise_presentation_entries_creation_mode",
        "enterprise_presentation_entries",
        ["creation_mode"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_enterprise_presentation_entries_creation_mode",
        table_name="enterprise_presentation_entries",
    )
    op.drop_column("enterprise_presentation_entries", "creation_mode")
