"""scene runtime contract and presentation scene version

Revision ID: d7b1f5a9c3e4
Revises: c6a0e4f8b2d3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7b1f5a9c3e4"
down_revision: Union[str, None] = "c6a0e4f8b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enterprise_presentation_entries",
        sa.Column(
            "scene_version",
            sa.String(length=32),
            nullable=False,
            server_default="1.0",
        ),
    )
    scene_table = sa.table(
        "enterprise_scene_definitions",
        sa.column("scene_type", sa.String()),
        sa.column("config", sa.JSON()),
    )
    op.execute(
        scene_table.update()
        .where(scene_table.c.scene_type == "general")
        .values(
            config={
                "create_schema": "general-presentation-v1",
                "navigation": ["create", "presentations", "templates"],
                "document_policy": "general-documents-v1",
                "workflow_policy": "general-flexible-v1",
                "quality_policy": "general-v1",
                "assembly_policy": "general-presentation-v1",
            }
        )
    )
    op.execute(
        scene_table.update()
        .where(scene_table.c.scene_type == "bid")
        .values(
            config={
                "create_schema": "bid-project-v1",
                "navigation": [
                    "dashboard",
                    "documents",
                    "profile",
                    "requirements",
                    "strategy",
                    "modules",
                    "reviews",
                    "releases",
                ],
                "document_policy": "bid-documents-v1",
                "workflow_policy": "bid-gates-v1",
                "quality_policy": "bid-gates-v1",
                "assembly_policy": "bid-modules-v1",
            }
        )
    )


def downgrade() -> None:
    op.drop_column("enterprise_presentation_entries", "scene_version")
