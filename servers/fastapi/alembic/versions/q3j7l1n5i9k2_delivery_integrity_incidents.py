"""delivery integrity incidents

Revision ID: q3j7l1n5i9k2
Revises: p2i6k0m4h8j1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q3j7l1n5i9k2"
down_revision: Union[str, None] = "p2i6k0m4h8j1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_delivery_integrity_incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_type", sa.String(32), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("resource_title", sa.String(500), nullable=False),
        sa.Column("detail_url", sa.String(1000), nullable=False),
        sa.Column("anomaly_types", sa.JSON(), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="high"),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("assigned_to", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resolution_note", sa.String(2000), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scene_type", "artifact_id", name="uq_delivery_integrity_incident_artifact"),
    )
    for column in (
        "workspace_id", "scene_type", "artifact_id", "resource_id", "severity", "status",
        "assigned_to", "first_detected_at", "last_detected_at", "updated_at",
    ):
        op.create_index(
            f"ix_enterprise_delivery_integrity_incidents_{column}",
            "enterprise_delivery_integrity_incidents",
            [column],
        )


def downgrade() -> None:
    op.drop_table("enterprise_delivery_integrity_incidents")
