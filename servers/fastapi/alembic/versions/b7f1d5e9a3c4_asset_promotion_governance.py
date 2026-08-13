"""asset promotion governance

Revision ID: b7f1d5e9a3c4
Revises: g6e0c4d8f2b3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f1d5e9a3c4"
down_revision: Union[str, None] = "g6e0c4d8f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprise_asset_items", sa.Column("parent_asset_id", sa.Uuid()))
    op.create_index("ix_enterprise_asset_items_parent_asset_id", "enterprise_asset_items", ["parent_asset_id"])
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key("fk_enterprise_asset_items_parent", "enterprise_asset_items", "enterprise_asset_items", ["parent_asset_id"], ["id"], ondelete="SET NULL")
    op.create_table(
        "enterprise_asset_promotion_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("promoted_asset_id", sa.Uuid()),
        sa.Column("target_scope_type", sa.String(32), nullable=False),
        sa.Column("target_workspace_id", sa.Uuid()),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("asset_name_snapshot", sa.String(300), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("desensitization_notes", sa.Text(), nullable=False),
        sa.Column("authorization_confirmed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("decided_by", sa.Uuid()),
        sa.Column("decision_comment", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_asset_id"], ["enterprise_asset_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promoted_asset_id"], ["enterprise_asset_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_workspace_id"], ["enterprise_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("source_asset_id", "promoted_asset_id", "target_scope_type", "target_workspace_id", "requested_by", "status", "decided_by", "created_at"):
        op.create_index(f"ix_enterprise_asset_promotion_requests_{column}", "enterprise_asset_promotion_requests", [column])


def downgrade() -> None:
    op.drop_table("enterprise_asset_promotion_requests")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_enterprise_asset_items_parent", "enterprise_asset_items", type_="foreignkey")
    op.drop_index("ix_enterprise_asset_items_parent_asset_id", table_name="enterprise_asset_items")
    op.drop_column("enterprise_asset_items", "parent_asset_id")
