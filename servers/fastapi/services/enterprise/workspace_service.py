import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    ConfidentialityLevel,
    WorkspaceRole,
    WorkspaceType,
)
from domains.platform.permissions import role_allows
from models.sql.enterprise.workspace import (
    WorkspaceFolderModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from models.sql.user import User
from services.enterprise.audit_service import record_audit_event


async def get_workspace_membership(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMemberModel | None:
    return await session.scalar(
        select(WorkspaceMemberModel).where(
            WorkspaceMemberModel.workspace_id == workspace_id,
            WorkspaceMemberModel.user_id == user_id,
        )
    )


async def require_workspace_role(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    required_role: WorkspaceRole = WorkspaceRole.VIEWER,
) -> tuple[WorkspaceModel, WorkspaceMemberModel]:
    workspace = await session.get(WorkspaceModel, workspace_id)
    if workspace is None or workspace.is_archived:
        raise HTTPException(status_code=404, detail="Workspace not found")
    membership = await get_workspace_membership(
        session, workspace_id=workspace_id, user_id=principal.user_id
    )
    if membership is None or not role_allows(membership.role, required_role):
        # Do not reveal whether a workspace exists to a non-member.
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace, membership


async def update_workspace_governance_policy(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    policy: dict,
) -> WorkspaceModel:
    workspace, _ = await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    workspace.governance_policy = dict(policy)
    session.add(workspace)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="workspace.governance_policy_updated",
        resource_type="workspace",
        resource_id=workspace.id,
        metadata={"policy": workspace.governance_policy},
    )
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def list_workspaces(
    session: AsyncSession, principal: AuthPrincipal
) -> list[tuple[WorkspaceModel, WorkspaceRole]]:
    rows = (
        await session.execute(
            select(WorkspaceModel, WorkspaceMemberModel.role)
            .join(
                WorkspaceMemberModel,
                WorkspaceMemberModel.workspace_id == WorkspaceModel.id,
            )
            .where(
                WorkspaceMemberModel.user_id == principal.user_id,
                WorkspaceModel.is_archived.is_(False),
            )
            .order_by(WorkspaceModel.updated_at.desc(), WorkspaceModel.name.asc())
        )
    ).all()
    return [(workspace, WorkspaceRole(role)) for workspace, role in rows]


async def create_workspace(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    name: str,
    workspace_type: WorkspaceType,
    confidentiality: ConfidentialityLevel,
) -> tuple[WorkspaceModel, WorkspaceMemberModel]:
    normalized_name = name.strip()
    if not normalized_name:
        raise HTTPException(status_code=422, detail="Workspace name is required")
    if workspace_type == WorkspaceType.DEPARTMENT and not principal.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only an administrator can create a department workspace",
        )
    if workspace_type == WorkspaceType.PERSONAL:
        existing = await session.scalar(
            select(WorkspaceModel)
            .join(
                WorkspaceMemberModel,
                WorkspaceMemberModel.workspace_id == WorkspaceModel.id,
            )
            .where(
                WorkspaceMemberModel.user_id == principal.user_id,
                WorkspaceModel.workspace_type == WorkspaceType.PERSONAL,
                WorkspaceModel.is_archived.is_(False),
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=409, detail="A personal workspace already exists"
            )

    workspace = WorkspaceModel(
        owner_id=principal.user_id,
        name=normalized_name,
        workspace_type=workspace_type,
        confidentiality=confidentiality,
    )
    membership = WorkspaceMemberModel(
        workspace_id=workspace.id,
        user_id=principal.user_id,
        role=WorkspaceRole.OWNER,
    )
    session.add(workspace)
    # These models use explicit identifiers instead of an ORM relationship, so
    # SQLAlchemy cannot infer that the workspace must be inserted first.
    await session.flush()
    session.add(membership)
    # The audit row references both the workspace and its creator. Flush the
    # owner membership before adding the audit event for deterministic FK order.
    await session.flush()
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace.id,
        action="workspace.created",
        resource_type="workspace",
        resource_id=workspace.id,
        metadata={"workspace_type": workspace_type.value},
    )
    await session.commit()
    await session.refresh(workspace)
    await session.refresh(membership)
    return workspace, membership


async def ensure_personal_workspace(
    session: AsyncSession, principal: AuthPrincipal
) -> tuple[WorkspaceModel, WorkspaceMemberModel, bool]:
    row = (
        await session.execute(
            select(WorkspaceModel, WorkspaceMemberModel)
            .join(
                WorkspaceMemberModel,
                WorkspaceMemberModel.workspace_id == WorkspaceModel.id,
            )
            .where(
                WorkspaceMemberModel.user_id == principal.user_id,
                WorkspaceModel.workspace_type == WorkspaceType.PERSONAL,
                WorkspaceModel.is_archived.is_(False),
            )
        )
    ).first()
    if row:
        return row[0], row[1], False
    workspace, membership = await create_workspace(
        session,
        principal=principal,
        name=f"{principal.username} 的个人空间",
        workspace_type=WorkspaceType.PERSONAL,
        confidentiality=ConfidentialityLevel.L2,
    )
    return workspace, membership, True


async def add_or_update_member(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    user_id: uuid.UUID,
    role: WorkspaceRole,
) -> WorkspaceMemberModel:
    workspace, _ = await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    if role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=422,
            detail="Workspace ownership cannot be assigned through membership",
        )
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    membership = await get_workspace_membership(
        session, workspace_id=workspace_id, user_id=user_id
    )
    previous_role: str | None = None
    if membership is None:
        membership = WorkspaceMemberModel(
            workspace_id=workspace_id, user_id=user_id, role=role
        )
        session.add(membership)
        action = "workspace.member_added"
    else:
        if membership.role == WorkspaceRole.OWNER:
            raise HTTPException(status_code=409, detail="Owner role cannot be changed")
        previous_role = str(membership.role)
        membership.role = role
        session.add(membership)
        action = "workspace.member_role_changed"
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace.id,
        action=action,
        resource_type="workspace_member",
        resource_id=membership.id,
        metadata={
            "user_id": str(user_id),
            "role": role.value,
            "previous_role": previous_role,
        },
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Workspace member already exists") from exc
    await session.refresh(membership)
    return membership


async def remove_member(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    user_id: uuid.UUID,
) -> None:
    workspace, _ = await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    membership = await get_workspace_membership(
        session, workspace_id=workspace_id, user_id=user_id
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if membership.role == WorkspaceRole.OWNER or workspace.owner_id == user_id:
        raise HTTPException(status_code=409, detail="Workspace owner cannot be removed")
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace.id,
        action="workspace.member_removed",
        resource_type="workspace_member",
        resource_id=membership.id,
        metadata={"user_id": str(user_id), "role": str(membership.role)},
    )
    await session.delete(membership)
    await session.commit()


async def list_members(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
) -> list[tuple[WorkspaceMemberModel, User]]:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal
    )
    return list(
        (
            await session.execute(
                select(WorkspaceMemberModel, User)
                .join(User, User.id == WorkspaceMemberModel.user_id)
                .where(WorkspaceMemberModel.workspace_id == workspace_id)
                .order_by(WorkspaceMemberModel.created_at.asc())
            )
        ).all()
    )


async def create_folder(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    name: str,
    parent_id: uuid.UUID | None,
) -> WorkspaceFolderModel:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    normalized_name = name.strip()
    if not normalized_name:
        raise HTTPException(status_code=422, detail="Folder name is required")
    if parent_id is not None:
        parent = await session.get(WorkspaceFolderModel, parent_id)
        if parent is None or parent.workspace_id != workspace_id or parent.is_archived:
            raise HTTPException(status_code=404, detail="Parent folder not found")
    duplicate_count = await session.scalar(
        select(func.count())
        .select_from(WorkspaceFolderModel)
        .where(
            WorkspaceFolderModel.workspace_id == workspace_id,
            WorkspaceFolderModel.parent_id == parent_id,
            func.lower(WorkspaceFolderModel.name) == normalized_name.casefold(),
            WorkspaceFolderModel.is_archived.is_(False),
        )
    )
    if duplicate_count:
        raise HTTPException(status_code=409, detail="Folder name already exists")
    folder = WorkspaceFolderModel(
        workspace_id=workspace_id,
        parent_id=parent_id,
        created_by=principal.user_id,
        name=normalized_name,
    )
    session.add(folder)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="workspace.folder_created",
        resource_type="workspace_folder",
        resource_id=folder.id,
        metadata={"parent_id": str(parent_id) if parent_id else None},
    )
    await session.commit()
    await session.refresh(folder)
    return folder


async def list_folders(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
) -> list[WorkspaceFolderModel]:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal
    )
    return list(
        (
            await session.scalars(
                select(WorkspaceFolderModel)
                .where(
                    WorkspaceFolderModel.workspace_id == workspace_id,
                    WorkspaceFolderModel.is_archived.is_(False),
                )
                .order_by(WorkspaceFolderModel.name.asc())
            )
        ).all()
    )
