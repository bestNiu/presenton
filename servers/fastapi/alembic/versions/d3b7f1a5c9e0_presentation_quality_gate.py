"""presentation quality gate and citations

Revision ID: d3b7f1a5c9e0
Revises: c2a6e0f4b8d9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3b7f1a5c9e0"
down_revision: Union[str, None] = "c2a6e0f4b8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enterprise_workspaces",
        sa.Column(
            "governance_policy",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{\"review_mode\":\"single\",\"quality_gate_enabled\":true,\"require_numeric_citations\":false}'"),
        ),
    )
    op.create_table(
        "enterprise_presentation_quality_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("presentation_entry_id", sa.Uuid(), nullable=False),
        sa.Column("slide_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("blocking_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["presentation_entry_id"], ["enterprise_presentation_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("presentation_entry_id", "slide_snapshot_hash", "status", "created_by", "created_at"):
        op.create_index(f"ix_enterprise_presentation_quality_runs_{column}", "enterprise_presentation_quality_runs", [column])
    op.create_table(
        "enterprise_presentation_quality_issues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quality_run_id", sa.Uuid(), nullable=False),
        sa.Column("rule_code", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("slide_id", sa.Uuid()),
        sa.Column("slide_index", sa.Integer()),
        sa.Column("element_ref", sa.String(500)),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["quality_run_id"], ["enterprise_presentation_quality_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="SET NULL"),
    )
    for column in ("quality_run_id", "rule_code", "severity", "slide_id"):
        op.create_index(f"ix_enterprise_presentation_quality_issues_{column}", "enterprise_presentation_quality_issues", [column])
    op.create_table(
        "enterprise_presentation_source_citations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("presentation_entry_id", sa.Uuid(), nullable=False),
        sa.Column("slide_id", sa.Uuid()),
        sa.Column("element_ref", sa.String(500)),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(500), nullable=False),
        sa.Column("source_version", sa.String(100)),
        sa.Column("locator", sa.String(500)),
        sa.Column("excerpt", sa.String(2000)),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["presentation_entry_id"], ["enterprise_presentation_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("presentation_entry_id", "slide_id", "source_type", "source_id", "created_by"):
        op.create_index(f"ix_enterprise_presentation_source_citations_{column}", "enterprise_presentation_source_citations", [column])
    op.add_column("enterprise_presentation_snapshots", sa.Column("quality_run_id", sa.Uuid()))
    op.create_index("ix_enterprise_presentation_snapshots_quality_run_id", "enterprise_presentation_snapshots", ["quality_run_id"])


def downgrade() -> None:
    op.drop_index("ix_enterprise_presentation_snapshots_quality_run_id", table_name="enterprise_presentation_snapshots")
    op.drop_column("enterprise_presentation_snapshots", "quality_run_id")
    op.drop_table("enterprise_presentation_source_citations")
    op.drop_table("enterprise_presentation_quality_issues")
    op.drop_table("enterprise_presentation_quality_runs")
    op.drop_column("enterprise_workspaces", "governance_policy")
