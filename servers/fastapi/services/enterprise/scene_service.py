from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.platform.enums import SceneStatus
from models.sql.enterprise.scene_definition import SceneDefinitionModel


async def list_active_scenes(session: AsyncSession) -> list[SceneDefinitionModel]:
    return list(
        (
            await session.scalars(
                select(SceneDefinitionModel)
                .where(SceneDefinitionModel.status == SceneStatus.ACTIVE)
                .order_by(SceneDefinitionModel.scene_type, SceneDefinitionModel.version)
            )
        ).all()
    )


async def get_active_scene(
    session: AsyncSession, scene_type: str
) -> SceneDefinitionModel | None:
    return await session.scalar(
        select(SceneDefinitionModel)
        .where(
            SceneDefinitionModel.scene_type == scene_type,
            SceneDefinitionModel.status == SceneStatus.ACTIVE,
        )
        .order_by(SceneDefinitionModel.version.desc())
        .limit(1)
    )
