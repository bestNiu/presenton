"""enterprise notifications

Revision ID: f5d9b3c7e1a2
Revises: e4c8a2b6d0f1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5d9b3c7e1a2"
down_revision: Union[str, None] = "e4c8a2b6d0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid()),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("notification_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("action_url", sa.String(1000)),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["enterprise_workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("recipient_id", "workspace_id", "actor_id", "notification_type", "resource_type", "is_read", "created_at"):
        op.create_index(f"ix_enterprise_notifications_{column}", "enterprise_notifications", [column])


def downgrade() -> None:
    op.drop_table("enterprise_notifications")
