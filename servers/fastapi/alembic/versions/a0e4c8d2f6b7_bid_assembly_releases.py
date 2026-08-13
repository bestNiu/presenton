"""bid assembly releases

Revision ID: a0e4c8d2f6b7
Revises: f9d3b7c1e5a6
"""

from datetime import datetime, timezone
from typing import Sequence, Union
import uuid
from alembic import op
import sqlalchemy as sa

revision: str = "a0e4c8d2f6b7"
down_revision: Union[str, None] = "f9d3b7c1e5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_bid_presentation_releases",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("presentation_entry_id", sa.Uuid(), nullable=False), sa.Column("template_publication_id", sa.Uuid(), nullable=False),
        sa.Column("release_type", sa.String(64), nullable=False), sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False), sa.Column("manifest_hash", sa.String(64), nullable=False), sa.Column("slide_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("created_by", sa.Uuid()), sa.Column("frozen_by", sa.Uuid()), sa.Column("frozen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["enterprise_bid_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["presentation_entry_id"], ["enterprise_presentation_entries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_publication_id"], ["enterprise_template_publications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["frozen_by"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "release_type", "version_no", name="uq_bid_release_version"),
    )
    for column in ("project_id", "presentation_entry_id", "template_publication_id", "release_type", "manifest_hash", "status"):
        op.create_index(f"ix_enterprise_bid_presentation_releases_{column}", "enterprise_bid_presentation_releases", [column])
    connection = op.get_bind()
    gate_table = sa.table("enterprise_bid_review_gates", sa.column("id", sa.Uuid()), sa.column("project_id", sa.Uuid()), sa.column("gate_type", sa.String()), sa.column("status", sa.String()), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    project_table = sa.table("enterprise_bid_projects", sa.column("id", sa.Uuid()))
    project_ids = connection.execute(sa.select(project_table.c.id)).scalars().all()
    now = datetime.now(timezone.utc)
    if project_ids:
        connection.execute(gate_table.insert(), [{"id": uuid.uuid4(), "project_id": project_id, "gate_type": "gate_3", "status": "locked", "created_at": now, "updated_at": now} for project_id in project_ids])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM enterprise_bid_review_gates WHERE gate_type = 'gate_3'"))
    op.drop_table("enterprise_bid_presentation_releases")
