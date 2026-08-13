import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal, principal_from_request
from api.v1.enterprise.schemas import (
    AuditEventResponse,
    BidDocumentCreateRequest,
    BidDocumentResponse,
    BidCollaborationResponse,
    BidCommitmentActionRequest,
    BidCommitmentCreateRequest,
    BidCommitmentResponse,
    BidGateActionRequest,
    BidGateResponse,
    BidIssueCreateRequest,
    BidIssueResolveRequest,
    BidIssueResponse,
    BidModuleResponse,
    BidModuleReviewRequest,
    BidModuleUpdateRequest,
    BidAssemblyRequest,
    BidReleaseResponse,
    BidDeliveryCreateRequest,
    BidDeliveryArtifactResponse,
    BidDownloadGrantRequest,
    BidDownloadGrantResponse,
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
    PresentationGovernanceResponse,
    PresentationQualityReportResponse,
    PresentationQualityRunResponse,
    PresentationSourceCitationCreateRequest,
    PresentationSourceCitationResponse,
    PresentationDeliveryCreateRequest,
    PresentationDeliveryArtifactResponse,
    PresentationRegisterRequest,
    PresentationReviewDecisionRequest,
    PresentationReviewResponse,
    PresentationSnapshotResponse,
    SceneDefinitionResponse,
    SceneRuntimeResponse,
    TemplatePublicationCreateRequest,
    TemplatePublicationResponse,
    WorkspaceCreateRequest,
    WorkspaceMemberResponse,
    WorkspaceMemberUpsertRequest,
    WorkspaceResponse,
    WorkspaceGovernancePolicyRequest,
)
from domains.platform.enums import BidGateType, TemplatePublicationStatus, WorkspaceRole
from models.sql.enterprise.audit_event import AuditEventModel
from models.sql.user import User
from services.database import get_async_session
from services.enterprise.presentation_workspace_service import (
    list_presentation_entries,
    register_presentation,
)
from services.enterprise.presentation_governance_service import (
    decide_presentation_review,
    freeze_presentation,
    get_presentation_governance,
    reopen_presentation_review,
    submit_presentation_review,
)
from services.enterprise.presentation_quality_service import (
    create_source_citation,
    latest_quality_report,
    list_source_citations,
    run_quality_check,
)
from services.enterprise.presentation_delivery_service import (
    consume_presentation_download_grant,
    create_presentation_delivery,
    issue_presentation_download_grant,
    list_presentation_deliveries,
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
from services.enterprise.bid_collaboration_service import (
    act_on_commitment,
    act_on_gate,
    create_commitment,
    create_gate_issue,
    initialize_modules,
    list_collaboration,
    review_module,
    resolve_gate_issue,
    submit_module,
    update_module,
)
from services.enterprise.bid_assembly_service import (
    assemble_management_summary,
    freeze_release,
    list_releases,
)
from services.enterprise.bid_delivery_service import (
    archive_release,
    consume_download_grant,
    create_delivery_artifact,
    issue_download_grant,
    list_delivery_artifacts,
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
    update_workspace_governance_policy,
)


API_V1_ENTERPRISE_ROUTER = APIRouter(
    prefix="/api/v1/enterprise", tags=["Enterprise Platform"]
)


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/releases/assemble", response_model=BidReleaseResponse, status_code=status.HTTP_201_CREATED)
async def post_bid_release_assemble(project_id: uuid.UUID, body: BidAssemblyRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await assemble_management_summary(session, project_id=project_id, principal=principal, **body.model_dump())


@API_V1_ENTERPRISE_ROUTER.get("/bid/projects/{project_id}/releases", response_model=list[BidReleaseResponse])
async def get_bid_releases(project_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await list_releases(session, project_id=project_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/releases/{release_id}/freeze", response_model=BidReleaseResponse)
async def post_bid_release_freeze(project_id: uuid.UUID, release_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await freeze_release(session, project_id=project_id, release_id=release_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/releases/{release_id}/archive", response_model=BidReleaseResponse)
async def post_bid_release_archive(project_id: uuid.UUID, release_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await archive_release(session, project_id=project_id, release_id=release_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/releases/{release_id}/deliveries", response_model=BidDeliveryArtifactResponse, status_code=status.HTTP_201_CREATED)
async def post_bid_delivery(request: Request, project_id: uuid.UUID, release_id: uuid.UUID, body: BidDeliveryCreateRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await create_delivery_artifact(session, project_id=project_id, release_id=release_id, principal=principal, cookie_header=request.headers.get("cookie"), **body.model_dump())


@API_V1_ENTERPRISE_ROUTER.get("/bid/projects/{project_id}/releases/{release_id}/deliveries", response_model=list[BidDeliveryArtifactResponse])
async def get_bid_deliveries(project_id: uuid.UUID, release_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await list_delivery_artifacts(session, project_id=project_id, release_id=release_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/deliveries/{artifact_id}/grants", response_model=BidDownloadGrantResponse, status_code=status.HTTP_201_CREATED)
async def post_bid_download_grant(project_id: uuid.UUID, artifact_id: uuid.UUID, body: BidDownloadGrantRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    grant, token = await issue_download_grant(session, project_id=project_id, artifact_id=artifact_id, principal=principal, **body.model_dump())
    return BidDownloadGrantResponse(grant_id=grant.id, artifact_id=grant.artifact_id, download_url=f"/api/v1/enterprise/bid/deliveries/download/{token}", expires_at=grant.expires_at, max_downloads=grant.max_downloads)


@API_V1_ENTERPRISE_ROUTER.get("/bid/deliveries/download/{token}")
async def get_bid_delivery_download(token: str, session: AsyncSession = Depends(get_async_session)):
    artifact, file_path = await consume_download_grant(session, token=token)
    artifact_format = getattr(artifact.format, "value", artifact.format)
    media_type = "application/pdf" if artifact_format == "pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return FileResponse(file_path, filename=artifact.file_name, media_type=media_type)


def _collaboration_response(rows: dict) -> dict:
    return {
        "modules": rows["modules"],
        "commitments": rows["commitments"],
        "gates": [BidGateResponse.model_validate(item["gate"]).model_copy(update={"issues": item["issues"]}) for item in rows["gates"]],
    }


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/modules/initialize", response_model=BidCollaborationResponse)
async def post_bid_modules_initialize(project_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return _collaboration_response(await initialize_modules(session, project_id=project_id, principal=principal))


@API_V1_ENTERPRISE_ROUTER.get("/bid/projects/{project_id}/collaboration", response_model=BidCollaborationResponse)
async def get_bid_collaboration(project_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return _collaboration_response(await list_collaboration(session, project_id=project_id, principal=principal))


@API_V1_ENTERPRISE_ROUTER.put("/bid/projects/{project_id}/modules/{module_id}", response_model=BidModuleResponse)
async def put_bid_module(project_id: uuid.UUID, module_id: uuid.UUID, body: BidModuleUpdateRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await update_module(session, project_id=project_id, module_id=module_id, principal=principal, **body.model_dump())


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/modules/{module_id}/submit", response_model=BidModuleResponse)
async def post_bid_module_submit(project_id: uuid.UUID, module_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await submit_module(session, project_id=project_id, module_id=module_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/modules/{module_id}/review", response_model=BidModuleResponse)
async def post_bid_module_review(project_id: uuid.UUID, module_id: uuid.UUID, body: BidModuleReviewRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await review_module(session, project_id=project_id, module_id=module_id, principal=principal, **body.model_dump())


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/commitments", response_model=BidCommitmentResponse, status_code=status.HTTP_201_CREATED)
async def post_bid_commitment(project_id: uuid.UUID, body: BidCommitmentCreateRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await create_commitment(session, project_id=project_id, principal=principal, values=body.model_dump())


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/commitments/{commitment_id}/action", response_model=BidCommitmentResponse)
async def post_bid_commitment_action(project_id: uuid.UUID, commitment_id: uuid.UUID, body: BidCommitmentActionRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await act_on_commitment(session, project_id=project_id, commitment_id=commitment_id, principal=principal, **body.model_dump())


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/gates/{gate_type}/action", response_model=BidGateResponse)
async def post_bid_gate_action(project_id: uuid.UUID, gate_type: BidGateType, body: BidGateActionRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    gate = await act_on_gate(session, project_id=project_id, gate_type=gate_type, principal=principal, action=body.action)
    return BidGateResponse.model_validate(gate).model_copy(update={"issues": []})


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/gates/{gate_type}/issues", response_model=BidIssueResponse, status_code=status.HTTP_201_CREATED)
async def post_bid_gate_issue(project_id: uuid.UUID, gate_type: BidGateType, body: BidIssueCreateRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await create_gate_issue(session, project_id=project_id, gate_type=gate_type, principal=principal, values=body.model_dump())


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/gate-issues/{issue_id}/resolve", response_model=BidIssueResponse)
async def post_bid_gate_issue_resolve(project_id: uuid.UUID, issue_id: uuid.UUID, body: BidIssueResolveRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await resolve_gate_issue(session, project_id=project_id, issue_id=issue_id, principal=principal, resolution=body.resolution)


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
        governance_policy=workspace.governance_policy,
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


@API_V1_ENTERPRISE_ROUTER.put(
    "/workspaces/{workspace_id}/governance-policy", response_model=WorkspaceResponse
)
async def put_workspace_governance_policy(workspace_id: uuid.UUID, body: WorkspaceGovernancePolicyRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    workspace = await update_workspace_governance_policy(session, workspace_id=workspace_id, principal=principal, policy=body.model_dump())
    _, membership = await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
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
            update={"can_open": True}
        )
        for entry in entries
    ]


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/governance",
    response_model=PresentationGovernanceResponse,
)
async def get_presentation_entry_governance(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await get_presentation_governance(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/quality-runs",
    response_model=PresentationQualityRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_quality_run(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    run, issues = await run_quality_check(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)
    return PresentationQualityRunResponse.model_validate(run).model_copy(update={"issues": issues})


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/quality-report",
    response_model=PresentationQualityReportResponse,
)
async def get_presentation_quality_report(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    run, issues = await latest_quality_report(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)
    response = None if run is None else PresentationQualityRunResponse.model_validate(run).model_copy(update={"issues": issues})
    return PresentationQualityReportResponse(run=response)


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/citations",
    response_model=PresentationSourceCitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_source_citation(workspace_id: uuid.UUID, entry_id: uuid.UUID, body: PresentationSourceCitationCreateRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await create_source_citation(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal, values=body.model_dump())


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/citations",
    response_model=list[PresentationSourceCitationResponse],
)
async def get_presentation_source_citations(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await list_source_citations(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/review/submit",
    response_model=PresentationReviewResponse,
)
async def post_presentation_review_submit(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await submit_presentation_review(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/review/decision",
    response_model=PresentationReviewResponse,
)
async def post_presentation_review_decision(workspace_id: uuid.UUID, entry_id: uuid.UUID, body: PresentationReviewDecisionRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await decide_presentation_review(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal, **body.model_dump())


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/review/reopen",
    response_model=PresentationEntryResponse,
)
async def post_presentation_review_reopen(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await reopen_presentation_review(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/freeze",
    response_model=PresentationSnapshotResponse,
)
async def post_presentation_freeze(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await freeze_presentation(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries", response_model=PresentationDeliveryArtifactResponse, status_code=status.HTTP_201_CREATED)
async def post_presentation_delivery(request: Request, workspace_id: uuid.UUID, entry_id: uuid.UUID, body: PresentationDeliveryCreateRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await create_presentation_delivery(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal, cookie_header=request.headers.get("cookie"), **body.model_dump())


@API_V1_ENTERPRISE_ROUTER.get("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries", response_model=list[PresentationDeliveryArtifactResponse])
async def get_presentation_deliveries(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await list_presentation_deliveries(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries/{artifact_id}/grants", response_model=BidDownloadGrantResponse, status_code=status.HTTP_201_CREATED)
async def post_presentation_download_grant(workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, body: BidDownloadGrantRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    grant, token = await issue_presentation_download_grant(session, workspace_id=workspace_id, entry_id=entry_id, artifact_id=artifact_id, principal=principal, **body.model_dump())
    return BidDownloadGrantResponse(grant_id=grant.id, artifact_id=grant.artifact_id, download_url=f"/api/v1/enterprise/presentations/deliveries/download/{token}", expires_at=grant.expires_at, max_downloads=grant.max_downloads)


@API_V1_ENTERPRISE_ROUTER.get("/presentations/deliveries/download/{token}")
async def get_presentation_delivery_download(token: str, session: AsyncSession = Depends(get_async_session)):
    artifact, file_path = await consume_presentation_download_grant(session, token=token)
    artifact_format = getattr(artifact.format, "value", artifact.format)
    media_type = "application/pdf" if artifact_format == "pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return FileResponse(file_path, filename=artifact.file_name, media_type=media_type)


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
