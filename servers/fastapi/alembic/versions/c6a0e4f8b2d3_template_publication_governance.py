"""template publication governance

Revision ID: c6a0e4f8b2d3
Revises: b5f9d3e7a1c2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6a0e4f8b2d3"
down_revision: Union[str, None] = "b5f9d3e7a1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_template_publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_key", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scene_type", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("compatibility", sa.JSON(), nullable=False),
        sa.Column("preview_url", sa.String(length=2000), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("recommended_order", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["template_v2.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["enterprise_workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publication_key",
            "version",
            name="uq_enterprise_template_publication_version",
        ),
    )
    for column in (
        "publication_key",
        "template_id",
        "workspace_id",
        "created_by",
        "scope_type",
        "scene_type",
        "status",
    ):
        op.create_index(
            f"ix_enterprise_template_publications_{column}",
            "enterprise_template_publications",
            [column],
            unique=column == "template_id",
        )


def downgrade() -> None:
    op.drop_table("enterprise_template_publications")
