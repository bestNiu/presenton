"""delivery integrity operations

Revision ID: p2i6k0m4h8j1
Revises: o1h5j9l3g7i0
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p2i6k0m4h8j1"
down_revision: Union[str, None] = "o1h5j9l3g7i0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_delivery_integrity_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("triggered_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="api"),
        sa.Column("lock_key", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("health", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="1800"),
        sa.Column("workspace_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_workspace_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_workspace_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifact_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("integrity_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_anomalies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("failure_detail", sa.String(2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("triggered_by", "source", "status", "health", "started_at"):
        op.create_index(
            f"ix_enterprise_delivery_integrity_runs_{column}",
            "enterprise_delivery_integrity_runs",
            [column],
        )
    op.create_index(
        "uq_enterprise_delivery_integrity_runs_lock_key",
        "enterprise_delivery_integrity_runs",
        ["lock_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("enterprise_delivery_integrity_runs")
