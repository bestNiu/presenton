"""bid professional collaboration

Revision ID: f9d3b7c1e5a6
Revises: e8c2a6b0d4f5
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f9d3b7c1e5a6"
down_revision: Union[str, None] = "e8c2a6b0d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_bid_professional_modules",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("module_type", sa.String(32), nullable=False), sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False), sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid()), sa.Column("updated_by", sa.Uuid()), sa.Column("reviewed_by", sa.Uuid()),
        sa.Column("review_comment", sa.String(2000)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["enterprise_bid_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["updated_by"], ["user.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["reviewed_by"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "module_type", "version_no", name="uq_bid_module_version"),
    )
    op.create_table(
        "enterprise_bid_commitments",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False), sa.Column("commitment_type", sa.String(64), nullable=False),
        sa.Column("conditions", sa.Text()), sa.Column("evidence_ref", sa.String(1000)), sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("proposed_by", sa.Uuid()), sa.Column("decided_by", sa.Uuid()), sa.Column("decision_comment", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["enterprise_bid_projects.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["proposed_by"], ["user.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["decided_by"], ["user.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "enterprise_bid_review_gates",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), nullable=False), sa.Column("gate_type", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("opened_by", sa.Uuid()), sa.Column("passed_by", sa.Uuid()), sa.Column("opened_at", sa.DateTime(timezone=True)), sa.Column("passed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["enterprise_bid_projects.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["opened_by"], ["user.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["passed_by"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "gate_type", name="uq_bid_review_gate"),
    )
    op.create_table(
        "enterprise_bid_review_issues",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("gate_id", sa.Uuid(), nullable=False), sa.Column("title", sa.String(300), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("severity", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("owner_id", sa.Uuid()), sa.Column("created_by", sa.Uuid()), sa.Column("resolved_by", sa.Uuid()), sa.Column("resolution", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gate_id"], ["enterprise_bid_review_gates.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["resolved_by"], ["user.id"], ondelete="SET NULL"),
    )
    for table, columns in {"enterprise_bid_professional_modules": ("project_id", "module_type", "status"), "enterprise_bid_commitments": ("project_id", "commitment_type", "status"), "enterprise_bid_review_gates": ("project_id", "gate_type", "status"), "enterprise_bid_review_issues": ("gate_id", "severity", "status")}.items():
        for column in columns: op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table in ("enterprise_bid_review_issues", "enterprise_bid_review_gates", "enterprise_bid_commitments", "enterprise_bid_professional_modules"):
        op.drop_table(table)
