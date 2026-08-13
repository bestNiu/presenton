"""storage lifecycle history

Revision ID: k7d1f5h9c3e6
Revises: j6c0e4g8b2d5
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k7d1f5h9c3e6"
down_revision: Union[str, None] = "j6c0e4g8b2d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_storage_lifecycle_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("triggered_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="api"),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("backend", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("health", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("scanned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stored_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("protected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("protected_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_referenced_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orphan_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("candidate_sample", sa.JSON(), nullable=False),
        sa.Column("failure_detail", sa.String(2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("triggered_by", "source", "mode", "status", "health", "started_at"):
        op.create_index(f"ix_enterprise_storage_lifecycle_runs_{column}", "enterprise_storage_lifecycle_runs", [column])


def downgrade() -> None:
    op.drop_table("enterprise_storage_lifecycle_runs")
