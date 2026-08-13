"""knowledge presentation orchestration

Revision ID: o1h5j9l3g7i0
Revises: n0g4i8k2f6h9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o1h5j9l3g7i0"
down_revision: Union[str, None] = "n0g4i8k2f6h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enterprise_knowledge_outlines",
        sa.Column("idempotency_key", sa.String(200), nullable=True),
    )
    op.add_column(
        "enterprise_knowledge_outlines",
        sa.Column("input_manifest_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "enterprise_knowledge_outlines",
        sa.Column(
            "input_manifest",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "enterprise_knowledge_outlines",
        sa.Column(
            "input_status", sa.String(32), nullable=False, server_default="current"
        ),
    )
    for column in (
        "idempotency_key",
        "input_manifest_hash",
        "input_status",
    ):
        op.create_index(
            f"ix_enterprise_knowledge_outlines_{column}",
            "enterprise_knowledge_outlines",
            [column],
        )
    op.create_index(
        "uq_enterprise_knowledge_outline_idempotency",
        "enterprise_knowledge_outlines",
        ["created_by", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_enterprise_knowledge_outline_idempotency",
        table_name="enterprise_knowledge_outlines",
    )
    for column in (
        "input_status",
        "input_manifest_hash",
        "idempotency_key",
    ):
        op.drop_index(
            f"ix_enterprise_knowledge_outlines_{column}",
            table_name="enterprise_knowledge_outlines",
        )
    for column in (
        "input_status",
        "input_manifest",
        "input_manifest_hash",
        "idempotency_key",
    ):
        op.drop_column("enterprise_knowledge_outlines", column)
