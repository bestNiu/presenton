import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal, principal_from_request
from api.v1.enterprise.schemas import (
    AuditEventResponse,
    BidDocumentCreateRequest,
    BidDocumentResponse,
    BidProfileResponse,
    BidProfileUpdateRequest,
    BidProjectCreateRequest,
    BidProjectDashboardResponse,
    BidProjectMemberRequest,
    BidProjectMemberResponse,
    BidProjectResponse,
    BidRequirementCreateRequest,
    BidRequirementResponse,
    BidRequirementUpdateRequest,
    BidStrategyResponse,
    BidStrategyUpdateRequest,
    FolderCreateRequest,
    FolderResponse,
    PresentationEntryResponse,
    PresentationRegisterRequest,
    SceneDefinitionResponse,
    SceneRuntimeResponse,
    TemplatePublicationCreateRequest,
    TemplatePublicationResponse,
    WorkspaceCreateRequest,
    WorkspaceMemberResponse,
    WorkspaceMemberUpsertRequest,
    WorkspaceResponse,
)
from domains.platform.enums import TemplatePublicationStatus, WorkspaceRole
from models.sql.enterprise.audit_event import AuditEventModel
from models.sql.user import User
from services.database import get_async_session
from services.enterprise.presentation_workspace_service import (
    list_presentation_entries,
    register_presentation,
)
from services.enterprise.bid_project_service import (
    add_project_document,
    confirm_project_profile,
    confirm_strategy,
    create_bid_project,
    create_requirement,
    get_project_dashboard,
    list_bid_projects,
    update_project_profile,
    update_requirement,
    update_strategy,
    upsert_project_member,
)
from services.enterprise.scene_service import list_active_scenes
from services.enterprise.scene_registry_service import resolve_scene_runtime
from services.enterprise.template_publication_service import (
    create_template_publication,
    list_visible_publications,
    set_default_publication,
    transition_publication,
)
from services.enterprise.workspace_service import (
    add_or_update_member,
    create_folder,
    create_workspace,
    ensure_personal_workspace,
    list_folders,
    list_members,
    list_workspaces,
    remove_member,
    require_workspace_role,
)


API_V1_ENTERPRISE_ROUTER = APIRouter(
    prefix="/api/v1/enterprise", tags=["Enterprise Platform"]
)


@API_V1_ENTERPRISE_ROUTER.post(
    "/bid/projects", response_model=BidProjectResponse, status_code=status.HTTP_201_CREATED
)
async def post_bid_project(
    body: BidProjectCreateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    project, membership = await create_bid_project(
        session,
        principal=principal,
        workspace_id=body.workspace_id,
        bid_code=body.bid_code,
        name=body.name,
        sponsor_name=body.sponsor_name,
        drug_name=body.drug_name,
        indication=body.indication,
        due_date=body.due_date,
        confidentiality=body.confidentiality,
    )
    return BidProjectResponse.model_validate(project).model_copy(
        update={"current_user_role": membership.role}
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/bid/projects", response_model=list[BidProjectResponse]
)
async def get_bid_projects(
    workspace_id: uuid.UUID = Query(),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    rows = await list_bid_projects(
        session, principal=principal, workspace_id=workspace_id
    )
    return [
        BidProjectResponse.model_validate(project).model_copy(
            update={"current_user_role": role}
        )
        for project, role in rows
    ]


@API_V1_ENTERPRISE_ROUTER.get(
    "/bid/projects/{project_id}", response_model=BidProjectDashboardResponse
)
async def get_bid_project_dashboard(
    project_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    dashboard = await get_project_dashboard(
        session, project_id=project_id, principal=principal
    )
    project = BidProjectResponse.model_validate(dashboard["project"]).model_copy(
        update={"current_user_role": dashboard["current_user_role"]}
    )
    return {**dashboard, "project": project}


@API_V1_ENTERPRISE_ROUTER.put(
    "/bid/projects/{project_id}/members/{user_id}",
    response_model=BidProjectMemberResponse,
)
async def put_bid_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: BidProjectMemberRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    if body.user_id != user_id:
        raise HTTPException(status_code=422, detail="User ID does not match path")
    return await upsert_project_member(
        session,
        project_id=project_id,
        principal=principal,
        user_id=user_id,
        role=body.role,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/bid/projects/{project_id}/documents",
    response_model=BidDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_bid_document(
    project_id: uuid.UUID,
    body: BidDocumentCreateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await add_project_document(
        session, project_id=project_id, principal=principal, **body.model_dump()
    )


@API_V1_ENTERPRISE_ROUTER.put(
    "/bid/projects/{project_id}/profile", response_model=BidProfileResponse
)
async def put_bid_profile(
    project_id: uuid.UUID,
    body: BidProfileUpdateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await update_project_profile(
        session, project_id=project_id, principal=principal, **body.model_dump()
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/bid/projects/{project_id}/profile/confirm", response_model=BidProfileResponse
)
async def post_bid_profile_confirm(
    project_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await confirm_project_profile(
        session, project_id=project_id, principal=principal
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/bid/projects/{project_id}/requirements",
    response_model=BidRequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_bid_requirement(
    project_id: uuid.UUID,
    body: BidRequirementCreateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await create_requirement(
        session,
        project_id=project_id,
        principal=principal,
        values=body.model_dump(),
    )


@API_V1_ENTERPRISE_ROUTER.patch(
    "/bid/projects/{project_id}/requirements/{requirement_id}",
    response_model=BidRequirementResponse,
)
async def patch_bid_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    body: BidRequirementUpdateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await update_requirement(
        session,
        project_id=project_id,
        requirement_id=requirement_id,
        principal=principal,
        **body.model_dump(),
    )


@API_V1_ENTERPRISE_ROUTER.put(
    "/bid/projects/{project_id}/strategy", response_model=BidStrategyResponse
)
async def put_bid_strategy(
    project_id: uuid.UUID,
    body: BidStrategyUpdateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await update_strategy(
        session, project_id=project_id, principal=principal, **body.model_dump()
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/bid/projects/{project_id}/strategy/confirm",
    response_model=BidStrategyResponse,
)
async def post_bid_strategy_confirm(
    project_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await confirm_strategy(
        session, project_id=project_id, principal=principal
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/template-publications",
    response_model=TemplatePublicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_template_publication(
    body: TemplatePublicationCreateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await create_template_publication(
        session,
        principal=principal,
        template_id=body.template_id,
        publication_key=body.publication_key,
        version=body.version,
        scope_type=body.scope_type,
        workspace_id=body.workspace_id,
        scene_type=body.scene_type,
        display_name=body.display_name,
        description=body.description,
        rules=body.rules,
        compatibility=body.compatibility,
        preview_url=body.preview_url,
        recommended_order=body.recommended_order,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/template-publications", response_model=list[TemplatePublicationResponse]
)
async def get_template_publications(
    workspace_id: uuid.UUID | None = Query(default=None),
    publication_status: TemplatePublicationStatus | None = Query(
        default=None, alias="status"
    ),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_visible_publications(
        session,
        principal=principal,
        workspace_id=workspace_id,
        status=publication_status,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/template-publications/{publication_id}/{action}",
    response_model=TemplatePublicationResponse,
)
async def post_template_publication_action(
    publication_id: uuid.UUID,
    action: str,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    if action == "set-default":
        return await set_default_publication(
            session, publication_id=publication_id, principal=principal
        )
    if action not in {"submit", "publish", "reject", "offline", "archive"}:
        raise HTTPException(status_code=404, detail="Template action not found")
    return await transition_publication(
        session,
        publication_id=publication_id,
        principal=principal,
        action=action,
    )


def _workspace_response(workspace, role: WorkspaceRole) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        owner_id=workspace.owner_id,
        name=workspace.name,
        workspace_type=workspace.workspace_type,
        confidentiality=workspace.confidentiality,
        is_archived=workspace.is_archived,
        current_user_role=WorkspaceRole(role),
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces", response_model=list[WorkspaceResponse]
)
async def get_workspaces(
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    rows = await list_workspaces(session, principal)
    return [_workspace_response(workspace, role) for workspace, role in rows]


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_workspace(
    body: WorkspaceCreateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    workspace, membership = await create_workspace(
        session,
        principal=principal,
        name=body.name,
        workspace_type=body.workspace_type,
        confidentiality=body.confidentiality,
    )
    return _workspace_response(workspace, membership.role)


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/personal", response_model=WorkspaceResponse
)
async def post_personal_workspace(
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    workspace, membership, _ = await ensure_personal_workspace(session, principal)
    return _workspace_response(workspace, membership.role)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}", response_model=WorkspaceResponse
)
async def get_workspace(
    workspace_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    workspace, membership = await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal
    )
    return _workspace_response(workspace, membership.role)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
)
async def get_workspace_members(
    workspace_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    rows = await list_members(
        session, workspace_id=workspace_id, principal=principal
    )
    return [
        WorkspaceMemberResponse(
            id=member.id,
            user_id=member.user_id,
            username=user.username,
            role=member.role,
            created_at=member.created_at,
        )
        for member, user in rows
    ]


@API_V1_ENTERPRISE_ROUTER.put(
    "/workspaces/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
)
async def put_workspace_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    body: WorkspaceMemberUpsertRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    if body.user_id != user_id:
        raise HTTPException(status_code=422, detail="User ID does not match path")
    member = await add_or_update_member(
        session,
        workspace_id=workspace_id,
        principal=principal,
        user_id=user_id,
        role=body.role,
    )
    user = await session.get(User, user_id)
    return WorkspaceMemberResponse(
        id=member.id,
        user_id=member.user_id,
        username=user.username,
        role=member.role,
        created_at=member.created_at,
    )


@API_V1_ENTERPRISE_ROUTER.delete(
    "/workspaces/{workspace_id}/members/{user_id}", status_code=204
)
async def delete_workspace_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    await remove_member(
        session,
        workspace_id=workspace_id,
        principal=principal,
        user_id=user_id,
    )
    return Response(status_code=204)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/folders", response_model=list[FolderResponse]
)
async def get_workspace_folders(
    workspace_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_folders(
        session, workspace_id=workspace_id, principal=principal
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/folders",
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_workspace_folder(
    workspace_id: uuid.UUID,
    body: FolderCreateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await create_folder(
        session,
        workspace_id=workspace_id,
        principal=principal,
        name=body.name,
        parent_id=body.parent_id,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/presentations",
    response_model=PresentationEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_entry(
    body: PresentationRegisterRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await register_presentation(
        session,
        principal=principal,
        workspace_id=body.workspace_id,
        presentation_id=body.presentation_id,
        folder_id=body.folder_id,
        scene_type=body.scene_type,
        creation_mode=body.creation_mode,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations",
    response_model=list[PresentationEntryResponse],
)
async def get_presentation_entries(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID | None = Query(default=None),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    entries = await list_presentation_entries(
        session,
        principal=principal,
        workspace_id=workspace_id,
        folder_id=folder_id,
    )
    return [
        PresentationEntryResponse.model_validate(entry).model_copy(
            update={"can_open": entry.created_by == principal.user_id}
        )
        for entry in entries
    ]


@API_V1_ENTERPRISE_ROUTER.get(
    "/scenes", response_model=list[SceneDefinitionResponse]
)
async def get_scenes(
    _: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_active_scenes(session)


@API_V1_ENTERPRISE_ROUTER.get(
    "/scenes/{scene_type}/runtime", response_model=SceneRuntimeResponse
)
async def get_scene_runtime(
    scene_type: str,
    workspace_id: uuid.UUID = Query(),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await resolve_scene_runtime(
        session,
        scene_type=scene_type,
        workspace_id=workspace_id,
        principal=principal,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/audit-events",
    response_model=list[AuditEventResponse],
)
async def get_workspace_audit_events(
    workspace_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    return list(
        (
            await session.scalars(
                select(AuditEventModel)
                .where(AuditEventModel.workspace_id == workspace_id)
                .order_by(AuditEventModel.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
