"""generic presentation governance

Revision ID: c2a6e0f4b8d9
Revises: b1f5d9e3a7c8
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2a6e0f4b8d9"
down_revision: Union[str, None] = "b1f5d9e3a7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_presentation_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("presentation_entry_id", sa.Uuid(), nullable=False),
        sa.Column("submission_no", sa.Integer(), nullable=False),
        sa.Column("slide_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("submitted_by", sa.Uuid()),
        sa.Column("decided_by", sa.Uuid()),
        sa.Column("decision_comment", sa.String(2000)),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["presentation_entry_id"], ["enterprise_presentation_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("presentation_entry_id", "submission_no", name="uq_presentation_review_submission"),
    )
    for column in ("presentation_entry_id", "slide_snapshot_hash", "status", "submitted_by", "decided_by"):
        op.create_index(f"ix_enterprise_presentation_reviews_{column}", "enterprise_presentation_reviews", [column])

    op.create_table(
        "enterprise_presentation_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("presentation_entry_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("slide_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("frozen_by", sa.Uuid()),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["presentation_entry_id"], ["enterprise_presentation_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_id"], ["enterprise_presentation_reviews.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["frozen_by"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("presentation_entry_id", "version_no", name="uq_presentation_snapshot_version"),
    )
    for column in ("presentation_entry_id", "review_id", "manifest_hash", "frozen_by"):
        op.create_index(f"ix_enterprise_presentation_snapshots_{column}", "enterprise_presentation_snapshots", [column])

    op.create_table(
        "enterprise_presentation_delivery_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("derived_presentation_id", sa.Uuid()),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("watermark_text", sa.String(300), nullable=False),
        sa.Column("file_path", sa.String(2000), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["enterprise_presentation_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["derived_presentation_id"], ["presentations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("snapshot_id", "derived_presentation_id", "format", "sha256", "status"):
        op.create_index(f"ix_enterprise_presentation_delivery_artifacts_{column}", "enterprise_presentation_delivery_artifacts", [column])

    op.create_table(
        "enterprise_presentation_download_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_downloads", sa.Integer(), nullable=False),
        sa.Column("download_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["artifact_id"], ["enterprise_presentation_delivery_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("token_hash", name="uq_presentation_download_grant_token_hash"),
    )
    for column in ("artifact_id", "token_hash", "expires_at"):
        op.create_index(f"ix_enterprise_presentation_download_grants_{column}", "enterprise_presentation_download_grants", [column])


def downgrade() -> None:
    op.drop_table("enterprise_presentation_download_grants")
    op.drop_table("enterprise_presentation_delivery_artifacts")
    op.drop_table("enterprise_presentation_snapshots")
    op.drop_table("enterprise_presentation_reviews")
