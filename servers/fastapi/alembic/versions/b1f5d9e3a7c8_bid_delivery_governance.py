"""bid delivery governance

Revision ID: b1f5d9e3a7c8
Revises: a0e4c8d2f6b7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1f5d9e3a7c8"
down_revision: Union[str, None] = "a0e4c8d2f6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_bid_delivery_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("release_id", sa.Uuid(), nullable=False),
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
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["release_id"], ["enterprise_bid_presentation_releases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["derived_presentation_id"], ["presentations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
    )
    for column in ("release_id", "derived_presentation_id", "format", "sha256", "status"):
        op.create_index(f"ix_enterprise_bid_delivery_artifacts_{column}", "enterprise_bid_delivery_artifacts", [column])

    op.create_table(
        "enterprise_bid_download_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_downloads", sa.Integer(), nullable=False),
        sa.Column("download_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["artifact_id"], ["enterprise_bid_delivery_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("token_hash", name="uq_bid_download_grant_token_hash"),
    )
    for column in ("artifact_id", "token_hash", "expires_at"):
        op.create_index(f"ix_enterprise_bid_download_grants_{column}", "enterprise_bid_download_grants", [column])


def downgrade() -> None:
    op.drop_table("enterprise_bid_download_grants")
    op.drop_table("enterprise_bid_delivery_artifacts")
