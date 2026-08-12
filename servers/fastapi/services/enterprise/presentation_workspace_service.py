import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import PresentationCreationMode, WorkspaceRole
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.workspace import WorkspaceFolderModel
from models.sql.presentation import PresentationModel
from services.enterprise.audit_service import record_audit_event
from services.enterprise.scene_service import get_active_scene
from services.enterprise.workspace_service import require_workspace_role


async def register_presentation(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    presentation_id: uuid.UUID,
    folder_id: uuid.UUID | None,
    scene_type: str,
    creation_mode: PresentationCreationMode = PresentationCreationMode.IMPORT,
) -> PresentationEntryModel:
    presentation = await session.scalar(
        select(PresentationModel)
        .execution_options(skip_owner_scope=True)
        .where(
            PresentationModel.id == presentation_id,
            PresentationModel.owner_id == principal.user_id,
        )
    )
    if presentation is None:
        raise HTTPException(status_code=404, detail="Presentation not found")
    entry = await attach_presentation_to_workspace(
        session,
        principal=principal,
        workspace_id=workspace_id,
        presentation=presentation,
        folder_id=folder_id,
        scene_type=scene_type,
        creation_mode=creation_mode,
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Presentation is already registered"
        ) from exc
    await session.refresh(entry)
    return entry


async def attach_presentation_to_workspace(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    presentation: PresentationModel,
    folder_id: uuid.UUID | None,
    scene_type: str,
    creation_mode: PresentationCreationMode,
) -> PresentationEntryModel:
    """Attach a presentation inside the caller's transaction.

    Creation endpoints use this helper so the presentation, workspace entry and
    audit event either commit together or all roll back.
    """
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    if presentation.owner_id != principal.user_id:
        raise HTTPException(status_code=404, detail="Presentation not found")
    if folder_id is not None:
        folder = await session.get(WorkspaceFolderModel, folder_id)
        if folder is None or folder.workspace_id != workspace_id or folder.is_archived:
            raise HTTPException(status_code=404, detail="Folder not found")
    if await get_active_scene(session, scene_type) is None:
        raise HTTPException(status_code=422, detail="Scene is not active")
    entry = PresentationEntryModel(
        workspace_id=workspace_id,
        folder_id=folder_id,
        presentation_id=presentation.id,
        created_by=principal.user_id,
        title=presentation.title,
        scene_type=scene_type,
        creation_mode=creation_mode,
    )
    session.add(entry)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="presentation.registered",
        resource_type="presentation_entry",
        resource_id=entry.id,
        metadata={
            "presentation_id": str(presentation.id),
            "scene_type": scene_type,
            "creation_mode": creation_mode.value,
        },
    )
    return entry


async def list_presentation_entries(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
) -> list[PresentationEntryModel]:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal
    )
    query = select(PresentationEntryModel).where(
        PresentationEntryModel.workspace_id == workspace_id
    )
    if folder_id is not None:
        query = query.where(PresentationEntryModel.folder_id == folder_id)
    return list(
        (
            await session.scalars(
                query.order_by(PresentationEntryModel.updated_at.desc())
            )
        ).all()
    )
