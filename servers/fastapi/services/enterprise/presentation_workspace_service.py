import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    PresentationCreationMode,
    PresentationEntryStatus,
    WorkspaceRole,
)
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.workspace import WorkspaceFolderModel
from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from models.sql.user import User
from services.enterprise.audit_service import record_audit_event
from services.enterprise.scene_service import get_active_scene
from services.enterprise.scene_registry_service import (
    require_direct_presentation_creation,
)
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
    allow_dedicated_scene: bool = False,
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
    scene = await get_active_scene(session, scene_type)
    if scene is None:
        raise HTTPException(status_code=422, detail="Scene is not active")
    if not allow_dedicated_scene:
        require_direct_presentation_creation(scene)
    entry = PresentationEntryModel(
        workspace_id=workspace_id,
        folder_id=folder_id,
        presentation_id=presentation.id,
        created_by=principal.user_id,
        title=presentation.title,
        scene_type=scene_type,
        scene_version=scene.version,
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
            "scene_version": scene.version,
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


async def search_presentation_entries(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    query_text: str | None,
    folder_id: uuid.UUID | None,
    unfiled_only: bool,
    status: PresentationEntryStatus | None,
    creation_mode: PresentationCreationMode | None,
    mine_only: bool,
    sort_by: str,
    page: int,
    page_size: int,
) -> tuple[list[tuple[PresentationEntryModel, str | None]], int]:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal
    )
    filters = [PresentationEntryModel.workspace_id == workspace_id]
    if query_text and query_text.strip():
        filters.append(
            func.lower(func.coalesce(PresentationEntryModel.title, "")).contains(
                query_text.strip().casefold(), autoescape=True
            )
        )
    if folder_id is not None:
        filters.append(PresentationEntryModel.folder_id == folder_id)
    elif unfiled_only:
        filters.append(PresentationEntryModel.folder_id.is_(None))
    if status is not None:
        filters.append(PresentationEntryModel.status == status)
    if creation_mode is not None:
        filters.append(PresentationEntryModel.creation_mode == creation_mode)
    if mine_only:
        filters.append(PresentationEntryModel.created_by == principal.user_id)

    total = int(
        await session.scalar(
            select(func.count())
            .select_from(PresentationEntryModel)
            .where(*filters)
        )
        or 0
    )
    sort_expression = {
        "updated_asc": PresentationEntryModel.updated_at.asc(),
        "title_asc": PresentationEntryModel.title.asc(),
        "title_desc": PresentationEntryModel.title.desc(),
        "created_desc": PresentationEntryModel.created_at.desc(),
    }.get(sort_by, PresentationEntryModel.updated_at.desc())
    rows = (
        await session.execute(
            select(PresentationEntryModel, User.username)
            .outerjoin(User, User.id == PresentationEntryModel.created_by)
            .where(*filters)
            .order_by(sort_expression, PresentationEntryModel.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return [(entry, username) for entry, username in rows], total


async def set_presentation_archived(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    archived: bool,
) -> PresentationEntryModel:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    entry = await session.scalar(
        select(PresentationEntryModel).where(
            PresentationEntryModel.id == entry_id,
            PresentationEntryModel.workspace_id == workspace_id,
        )
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="文稿不存在或不属于当前工作空间")
    current_status = PresentationEntryStatus(entry.status)
    if archived:
        if current_status != PresentationEntryStatus.DRAFT:
            raise HTTPException(status_code=409, detail="只有草稿状态的文稿可以归档")
        previous_folder_id = entry.folder_id
        entry.status = PresentationEntryStatus.ARCHIVED
        entry.folder_id = None
        action = "presentation.archived"
    else:
        if current_status != PresentationEntryStatus.ARCHIVED:
            raise HTTPException(status_code=409, detail="只有已归档文稿可以恢复")
        previous_folder_id = None
        entry.status = PresentationEntryStatus.DRAFT
        action = "presentation.restored"
    entry.row_version += 1
    session.add(entry)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action=action,
        resource_type="presentation_entry",
        resource_id=entry.id,
        metadata={
            "previous_status": current_status.value,
            "status": PresentationEntryStatus(entry.status).value,
            "previous_folder_id": (
                str(previous_folder_id) if previous_folder_id else None
            ),
        },
    )
    await session.commit()
    await session.refresh(entry)
    return entry


async def bulk_set_presentation_archived(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    entry_ids: list[uuid.UUID],
    archived: bool,
) -> list[PresentationEntryModel]:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    unique_ids = set(entry_ids)
    entries = list(
        (
            await session.scalars(
                select(PresentationEntryModel).where(
                    PresentationEntryModel.workspace_id == workspace_id,
                    PresentationEntryModel.id.in_(unique_ids),
                )
            )
        ).all()
    )
    if len(entries) != len(unique_ids):
        raise HTTPException(status_code=404, detail="部分文稿不存在或不属于当前工作空间")
    required_status = (
        PresentationEntryStatus.DRAFT
        if archived
        else PresentationEntryStatus.ARCHIVED
    )
    if any(PresentationEntryStatus(entry.status) != required_status for entry in entries):
        detail = (
            "批量归档仅支持草稿文稿"
            if archived
            else "批量恢复仅支持已归档文稿"
        )
        raise HTTPException(status_code=409, detail=detail)
    target_status = (
        PresentationEntryStatus.ARCHIVED
        if archived
        else PresentationEntryStatus.DRAFT
    )
    action = "presentation.archived" if archived else "presentation.restored"
    for entry in entries:
        previous_folder_id = entry.folder_id
        entry.status = target_status
        if archived:
            entry.folder_id = None
        entry.row_version += 1
        session.add(entry)
        record_audit_event(
            session,
            actor_id=principal.user_id,
            workspace_id=workspace_id,
            action=action,
            resource_type="presentation_entry",
            resource_id=entry.id,
            metadata={
                "bulk": True,
                "previous_status": required_status.value,
                "status": target_status.value,
                "previous_folder_id": (
                    str(previous_folder_id) if previous_folder_id else None
                ),
            },
        )
    await session.commit()
    for entry in entries:
        await session.refresh(entry)
    return entries


async def copy_presentation_to_workspace(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    source_workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    target_workspace_id: uuid.UUID,
    target_folder_id: uuid.UUID | None,
    title: str | None,
) -> PresentationEntryModel:
    await require_workspace_role(
        session,
        workspace_id=source_workspace_id,
        principal=principal,
    )
    await require_workspace_role(
        session,
        workspace_id=target_workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    source_entry = await session.scalar(
        select(PresentationEntryModel).where(
            PresentationEntryModel.id == entry_id,
            PresentationEntryModel.workspace_id == source_workspace_id,
        )
    )
    if source_entry is None:
        raise HTTPException(status_code=404, detail="源文稿不存在或不属于当前工作空间")
    if PresentationEntryStatus(source_entry.status) == PresentationEntryStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="请先恢复源文稿，再复制到其他工作空间")
    if target_folder_id is not None:
        target_folder = await session.get(WorkspaceFolderModel, target_folder_id)
        if (
            target_folder is None
            or target_folder.workspace_id != target_workspace_id
            or target_folder.is_archived
        ):
            raise HTTPException(status_code=404, detail="目标文件夹不存在")
    source_presentation = await session.scalar(
        select(PresentationModel)
        .execution_options(skip_owner_scope=True)
        .where(PresentationModel.id == source_entry.presentation_id)
    )
    if source_presentation is None:
        raise HTTPException(status_code=404, detail="源演示文稿不存在")
    source_slides = list(
        await session.scalars(
            select(SlideModel)
            .execution_options(skip_owner_scope=True)
            .where(SlideModel.presentation == source_presentation.id)
            .order_by(SlideModel.index)
        )
    )
    copied_presentation = source_presentation.get_new_presentation()
    copied_presentation.owner_id = principal.user_id
    copied_presentation.title = title or f"{source_presentation.title or '未命名文稿'}（副本）"
    copied_slides = [
        slide.get_new_slide(copied_presentation.id) for slide in source_slides
    ]
    for slide in copied_slides:
        slide.owner_id = principal.user_id
    copied_entry = PresentationEntryModel(
        workspace_id=target_workspace_id,
        folder_id=target_folder_id,
        presentation_id=copied_presentation.id,
        created_by=principal.user_id,
        title=copied_presentation.title,
        scene_type=source_entry.scene_type,
        scene_version=source_entry.scene_version,
        creation_mode=source_entry.creation_mode,
        status=PresentationEntryStatus.DRAFT,
    )
    session.add(copied_presentation)
    session.add_all(copied_slides)
    session.add(copied_entry)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=target_workspace_id,
        action="presentation.copied_in",
        resource_type="presentation_entry",
        resource_id=copied_entry.id,
        metadata={
            "source_workspace_id": str(source_workspace_id),
            "source_entry_id": str(source_entry.id),
            "source_presentation_id": str(source_presentation.id),
            "presentation_id": str(copied_presentation.id),
        },
    )
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=source_workspace_id,
        action="presentation.copied_out",
        resource_type="presentation_entry",
        resource_id=source_entry.id,
        metadata={
            "target_workspace_id": str(target_workspace_id),
            "target_entry_id": str(copied_entry.id),
        },
    )
    await session.commit()
    await session.refresh(copied_entry)
    return copied_entry


async def move_presentation_entries(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    entry_ids: list[uuid.UUID],
    folder_id: uuid.UUID | None,
) -> list[PresentationEntryModel]:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    if folder_id is not None:
        folder = await session.get(WorkspaceFolderModel, folder_id)
        if folder is None or folder.workspace_id != workspace_id or folder.is_archived:
            raise HTTPException(status_code=404, detail="Folder not found")
    entries = list(
        (
            await session.scalars(
                select(PresentationEntryModel).where(
                    PresentationEntryModel.workspace_id == workspace_id,
                    PresentationEntryModel.id.in_(entry_ids),
                )
            )
        ).all()
    )
    if len(entries) != len(set(entry_ids)):
        raise HTTPException(status_code=404, detail="文稿不存在或不属于当前工作空间")
    for entry in entries:
        previous_folder_id = entry.folder_id
        entry.folder_id = folder_id
        session.add(entry)
        record_audit_event(
            session,
            actor_id=principal.user_id,
            workspace_id=workspace_id,
            action="presentation.folder_changed",
            resource_type="presentation_entry",
            resource_id=entry.id,
            metadata={
                "previous_folder_id": (
                    str(previous_folder_id) if previous_folder_id else None
                ),
                "folder_id": str(folder_id) if folder_id else None,
            },
        )
    await session.commit()
    for entry in entries:
        await session.refresh(entry)
    return entries
