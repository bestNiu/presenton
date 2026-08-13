"""enterprise document chunks

Revision ID: m9f3h7j1e5g8
Revises: l8e2g6i0d4f7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m9f3h7j1e5g8"
down_revision: Union[str, None] = "l8e2g6i0d4f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("enterprise_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column(
            "locator", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_enterprise_document_chunk_index",
        ),
    )
    op.create_index(
        "ix_enterprise_document_chunks_document_id",
        "enterprise_document_chunks",
        ["document_id"],
    )
    op.create_index(
        "ix_enterprise_document_chunks_content_hash",
        "enterprise_document_chunks",
        ["content_hash"],
    )
    op.create_index(
        "ix_enterprise_document_chunks_created_at",
        "enterprise_document_chunks",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("enterprise_document_chunks")
