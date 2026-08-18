import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal, principal_from_request
from api.v1.enterprise.schemas import (
    AssetCreateRequest,
    AssetCompatibilityResponse,
    AssetElementInsertRequest,
    AssetElementInsertResponse,
    AssetDiscoveryItemResponse,
    AssetDuplicateDecisionRequest,
    AssetDuplicateDecisionResponse,
    AssetItemResponse,
    AssetPageInsertRequest,
    AssetPageInsertResponse,
    AssetPromotionCreateRequest,
    AssetPromotionDecisionRequest,
    AssetPromotionResponse,
    AssetAnalyticsResponse,
    AssetBulkTransitionRequest,
    AssetFavoriteResponse,
    AssetPersonalizedItemResponse,
    AssetPreviewTaskResponse,
    SlideAssetCreateRequest,
    SlideElementAssetCreateRequest,
    SlideAssetVersionCreateRequest,
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
    FolderUpdateRequest,
    EnterpriseNotificationListResponse,
    EnterpriseNotificationReadAllResponse,
    EnterpriseNotificationResponse,
    EnterpriseDocumentDetailResponse,
    DeliveryCenterResponse,
    DeliveryIntegrityScanResponse,
    DeliveryIntegrityBatchResponse,
    DeliveryIntegrityBatchRunResponse,
    DeliveryIntegrityHealthResponse,
    DeliveryIntegrityIncidentResponse,
    DeliveryIntegrityIncidentUpdateRequest,
    EnterpriseDocumentParseTaskResponse,
    EnterpriseDocumentResponse,
    EnterpriseKnowledgeSearchItemResponse,
    EnterpriseKnowledgeSearchRequest,
    EnterpriseKnowledgeOutlineCreateRequest,
    EnterpriseKnowledgeOutlineResponse,
    EnterpriseKnowledgeEvaluationRequest,
    EnterpriseKnowledgeEvaluationResponse,
    EnterpriseKnowledgePresentationCreateRequest,
    EnterpriseKnowledgePresentationResponse,
    PresentationEntryResponse,
    PresentationBulkMoveRequest,
    PresentationBulkLifecycleRequest,
    PresentationCatalogItemResponse,
    PresentationCatalogResponse,
    PresentationCopyRequest,
    PresentationCommentCreateRequest,
    PresentationCommentReplyCreateRequest,
    PresentationCommentReplyResponse,
    PresentationCommentThreadResponse,
    PresentationGovernanceResponse,
    PresentationFreezePreflightResponse,
    PresentationQualityReportResponse,
    PresentationQualityRunResponse,
    PresentationSourceCitationCreateRequest,
    PresentationSourceCitationDetailResponse,
    PresentationSourceCitationPreviewResponse,
    PresentationSourceCitationResponse,
    PresentationSourceCitationSummaryResponse,
    PresentationDeliveryCreateRequest,
    PresentationDeliveryArtifactResponse,
    PresentationDeliveryEvidenceResponse,
    PresentationDeliveryEvidenceVerifyRequest,
    PresentationDeliveryEvidenceVerifyResponse,
    PresentationRegisterRequest,
    PresentationReviewDecisionRequest,
    PresentationReviewResponse,
    PresentationReviewInboxResponse,
    PresentationSnapshotResponse,
    PresentationSnapshotDiffResponse,
    PresentationSnapshotEvidenceResponse,
    SceneDefinitionResponse,
    SceneRuntimeResponse,
    TemplatePublicationCreateRequest,
    TemplatePublicationResponse,
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
    WorkspaceMemberInviteRequest,
    WorkspaceMemberResponse,
    WorkspaceMemberUpsertRequest,
    WorkspaceResponse,
    WorkspaceGovernancePolicyRequest,
    StorageLifecycleRunRequest,
    StorageLifecycleRunResponse,
    StorageLifecycleHistoryResponse,
)
from domains.platform.enums import (
    AssetStatus,
    BidGateType,
    PresentationCreationMode,
    PresentationEntryStatus,
    TemplatePublicationStatus,
    WorkspaceRole,
)
from models.sql.enterprise.audit_event import AuditEventModel
from models.sql.user import User
from services.database import get_async_session
from services.enterprise.presentation_workspace_service import (
    bulk_set_presentation_archived,
    copy_presentation_to_workspace,
    list_presentation_entries,
    move_presentation_entries,
    register_presentation,
    search_presentation_entries,
    set_presentation_archived,
)
from services.enterprise.presentation_governance_service import (
    compare_presentation_snapshots,
    decide_presentation_review,
    freeze_presentation,
    get_presentation_governance,
    get_presentation_freeze_preflight,
    get_presentation_snapshot_evidence,
    reopen_presentation_review,
    submit_presentation_review,
)
from services.enterprise.presentation_comment_service import (
    add_comment_reply,
    create_comment_thread,
    list_comment_threads,
    get_workspace_review_inbox,
    transition_comment_thread,
)
from services.enterprise.presentation_quality_service import (
    create_source_citation,
    delete_source_citation,
    get_source_citation_preview,
    latest_quality_report,
    list_source_citation_details,
    run_quality_check,
    source_citation_summary,
)
from services.enterprise.presentation_delivery_service import (
    consume_presentation_download_grant,
    build_presentation_delivery_evidence_package,
    create_presentation_delivery,
    get_presentation_delivery_evidence,
    issue_presentation_download_grant,
    list_presentation_deliveries,
    list_presentation_delivery_activity,
    verify_presentation_delivery_evidence_package,
    revoke_presentation_delivery,
)
from services.enterprise.delivery_center_service import (
    get_delivery_integrity_health,
    get_delivery_center,
    list_delivery_integrity_batch_runs,
    list_delivery_integrity_scans,
    run_delivery_integrity_scan,
    run_all_workspace_delivery_integrity_scans,
)
from services.enterprise.delivery_integrity_incident_service import (
    list_delivery_integrity_incidents,
    recheck_delivery_integrity_incident,
    update_delivery_integrity_incident,
)
from services.enterprise.notification_service import (
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    refresh_due_notifications,
)
from services.enterprise.document_service import (
    get_document_download_location,
    get_enterprise_document,
    list_enterprise_documents,
    retry_document_parse,
    run_document_parse_task,
    upload_enterprise_document,
)
from services.enterprise.knowledge_service import search_enterprise_knowledge
from services.enterprise.knowledge_outline_service import (
    apply_knowledge_outline_to_presentation,
    create_knowledge_presentation,
    create_knowledge_outline,
    get_knowledge_outline,
    materialize_knowledge_outline_citations,
    run_knowledge_outline_task,
)
from services.enterprise.knowledge_evaluation_service import evaluate_ranked_results
from services.enterprise.asset_library_service import (
    create_asset,
    bulk_transition_assets,
    get_asset_analytics,
    get_asset_compatibility,
    insert_asset_page,
    insert_asset_element,
    list_asset_versions,
    list_assets,
    save_slide_as_asset,
    save_slide_element_as_asset,
    save_slide_as_asset_version,
    transition_asset,
)
from services.enterprise.asset_promotion_service import (
    create_promotion_request,
    decide_promotion_request,
    list_promotion_requests,
)
from services.enterprise.asset_personalization_service import (
    list_personalized_assets,
    set_asset_favorite,
)
from services.enterprise.asset_preview_service import (
    get_asset_preview_location,
    queue_asset_preview,
    run_asset_preview_task,
)
from services.enterprise.object_storage_service import get_enterprise_object_storage
from services.enterprise.asset_discovery_service import (
    decide_asset_duplicate,
    find_similar_assets,
    search_assets,
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
    revoke_delivery_artifact,
)
from services.enterprise.scene_service import list_active_scenes
from services.enterprise.storage_lifecycle_service import (
    list_storage_lifecycle_runs,
    run_storage_lifecycle,
)
from services.enterprise.scene_registry_service import resolve_scene_runtime
from services.enterprise.template_publication_service import (
    create_template_publication,
    list_visible_publications,
    set_default_publication,
    transition_publication,
)
from services.enterprise.workspace_service import (
    add_or_update_member,
    add_or_update_member_by_username,
    archive_folder,
    create_folder,
    create_workspace,
    ensure_personal_workspace,
    list_folders,
    list_members,
    list_workspaces,
    remove_member,
    require_workspace_role,
    update_folder,
    update_workspace_governance_policy,
    update_workspace_details,
)


API_V1_ENTERPRISE_ROUTER = APIRouter(
    prefix="/api/v1/enterprise", tags=["Enterprise Platform"]
)


@API_V1_ENTERPRISE_ROUTER.post(
    "/admin/delivery-integrity-runs",
    response_model=DeliveryIntegrityBatchResponse,
)
async def post_all_workspace_delivery_integrity_runs(principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await run_all_workspace_delivery_integrity_scans(session, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get(
    "/admin/delivery-integrity-runs",
    response_model=list[DeliveryIntegrityBatchRunResponse],
)
async def get_all_workspace_delivery_integrity_runs(
    limit: int = Query(default=30, ge=1, le=100),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_delivery_integrity_batch_runs(
        session, principal=principal, limit=limit
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/admin/delivery-integrity-health",
    response_model=DeliveryIntegrityHealthResponse,
)
async def get_all_workspace_delivery_integrity_health(
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_delivery_integrity_health(session, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get(
    "/admin/delivery-integrity-incidents",
    response_model=list[DeliveryIntegrityIncidentResponse],
)
async def get_all_delivery_integrity_incidents(
    status: str | None = Query(default=None),
    scene_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_delivery_integrity_incidents(
        session,
        principal=principal,
        status=status,
        scene_type=scene_type,
        limit=limit,
    )


@API_V1_ENTERPRISE_ROUTER.patch(
    "/admin/delivery-integrity-incidents/{incident_id}",
    response_model=DeliveryIntegrityIncidentResponse,
)
async def patch_delivery_integrity_incident(
    incident_id: uuid.UUID,
    body: DeliveryIntegrityIncidentUpdateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    return await update_delivery_integrity_incident(
        session,
        incident_id=incident_id,
        principal=principal,
        status=body.status,
        assigned_to=body.assigned_to,
        resolution_note=body.resolution_note,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/admin/delivery-integrity-incidents/{incident_id}/recheck",
    response_model=DeliveryIntegrityIncidentResponse,
)
async def post_delivery_integrity_incident_recheck(
    incident_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    return await recheck_delivery_integrity_incident(
        session, incident_id=incident_id, principal=principal
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/admin/storage/lifecycle-runs",
    response_model=StorageLifecycleRunResponse,
)
async def post_storage_lifecycle_run(
    body: StorageLifecycleRunRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await run_storage_lifecycle(
        session,
        principal=principal,
        execute=body.execute,
        max_delete=body.max_delete,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/admin/storage/lifecycle-runs",
    response_model=list[StorageLifecycleHistoryResponse],
)
async def get_storage_lifecycle_runs(
    limit: int = Query(default=30, ge=1, le=100),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_storage_lifecycle_runs(
        session, principal=principal, limit=limit
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/documents",
    response_model=EnterpriseDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_enterprise_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    scope_type: str = Form(...),
    workspace_id: uuid.UUID | None = Form(default=None),
    project_id: uuid.UUID | None = Form(default=None),
    logical_name: str | None = Form(default=None),
    category: str = Form(default="general"),
    authorization_status: str = Form(default="internal"),
    confidentiality: str = Form(default="L2"),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    document, task = await upload_enterprise_document(
        session,
        principal=principal,
        file=file,
        scope_type=scope_type,
        workspace_id=workspace_id,
        project_id=project_id,
        logical_name=logical_name,
        category=category,
        authorization_status=authorization_status,
        confidentiality=confidentiality,
    )
    background_tasks.add_task(run_document_parse_task, document.id, task.id)
    return document


@API_V1_ENTERPRISE_ROUTER.get(
    "/documents",
    response_model=list[EnterpriseDocumentResponse],
)
async def get_enterprise_documents(
    scope_type: str = Query(...),
    workspace_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    include_versions: bool = Query(default=False),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_enterprise_documents(
        session,
        principal=principal,
        scope_type=scope_type,
        workspace_id=workspace_id,
        project_id=project_id,
        include_versions=include_versions,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/documents/{document_id}",
    response_model=EnterpriseDocumentDetailResponse,
)
async def get_enterprise_document_detail(
    document_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_enterprise_document(
        session, document_id=document_id, principal=principal
    )


@API_V1_ENTERPRISE_ROUTER.get("/documents/{document_id}/download")
async def download_enterprise_document(
    document_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    document, location = await get_document_download_location(
        session, document_id=document_id, principal=principal
    )
    return await get_enterprise_object_storage().download_response(
        location, filename=document.file_name, media_type=document.mime_type
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/documents/{document_id}/parse-tasks",
    response_model=EnterpriseDocumentParseTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_enterprise_document_parse_task(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    document, task = await retry_document_parse(
        session, document_id=document_id, principal=principal
    )
    background_tasks.add_task(run_document_parse_task, document.id, task.id)
    return EnterpriseDocumentParseTaskResponse(
        document_id=document.id,
        task_id=task.id,
        status=task.status.value if hasattr(task.status, "value") else task.status,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/knowledge/search",
    response_model=list[EnterpriseKnowledgeSearchItemResponse],
)
async def post_enterprise_knowledge_search(
    body: EnterpriseKnowledgeSearchRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await search_enterprise_knowledge(
        session,
        principal=principal,
        query=body.query,
        scope_type=body.scope_type,
        workspace_id=body.workspace_id,
        project_id=body.project_id,
        categories=body.categories,
        latest_only=body.latest_only,
        limit=body.limit,
        document_ids=body.document_ids,
        retrieval_mode=body.retrieval_mode,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/knowledge/outlines",
    response_model=EnterpriseKnowledgeOutlineResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_enterprise_knowledge_outline(
    body: EnterpriseKnowledgeOutlineCreateRequest,
    background_tasks: BackgroundTasks,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    outline, task = await create_knowledge_outline(
        session, principal=principal, values=body.model_dump()
    )
    background_tasks.add_task(run_knowledge_outline_task, outline.id, task.id)
    return outline


@API_V1_ENTERPRISE_ROUTER.post(
    "/knowledge/presentations",
    response_model=EnterpriseKnowledgePresentationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_enterprise_knowledge_presentation(
    body: EnterpriseKnowledgePresentationCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    presentation, entry, outline, task, replayed = await create_knowledge_presentation(
        session,
        principal=principal,
        values=body.model_dump(),
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    if replayed:
        response.headers["Idempotency-Replayed"] = "true"
    elif outline.status == "queued":
        background_tasks.add_task(run_knowledge_outline_task, outline.id, task.id)
    return EnterpriseKnowledgePresentationResponse(
        presentation_id=presentation.id,
        presentation_entry_id=entry.id,
        outline=outline,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/knowledge/outlines/{outline_id}",
    response_model=EnterpriseKnowledgeOutlineResponse,
)
async def get_enterprise_knowledge_outline(
    outline_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_knowledge_outline(
        session, principal=principal, outline_id=outline_id
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/knowledge/outlines/{outline_id}/workspaces/{workspace_id}/presentations/{entry_id}/apply",
    response_model=EnterpriseKnowledgeOutlineResponse,
)
async def post_apply_enterprise_knowledge_outline(
    outline_id: uuid.UUID,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await apply_knowledge_outline_to_presentation(
        session,
        principal=principal,
        outline_id=outline_id,
        workspace_id=workspace_id,
        entry_id=entry_id,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/knowledge/outlines/{outline_id}/workspaces/{workspace_id}/presentations/{entry_id}/citations",
    response_model=list[PresentationSourceCitationResponse],
)
async def post_materialize_enterprise_knowledge_citations(
    outline_id: uuid.UUID,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await materialize_knowledge_outline_citations(
        session,
        principal=principal,
        outline_id=outline_id,
        workspace_id=workspace_id,
        entry_id=entry_id,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/knowledge/evaluations",
    response_model=EnterpriseKnowledgeEvaluationResponse,
)
async def post_enterprise_knowledge_evaluation(
    body: EnterpriseKnowledgeEvaluationRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
):
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    return evaluate_ranked_results(
        [item.model_dump() for item in body.cases], k=body.k
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets",
    response_model=AssetItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_enterprise_asset(
    body: AssetCreateRequest,
    background_tasks: BackgroundTasks,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    asset = await create_asset(
        session, principal=principal, values=body.model_dump()
    )
    if asset.asset_type == "page" and asset.payload.get("format") == "presentation-page-v1":
        task = await queue_asset_preview(session, asset_id=asset.id, principal=principal)
        background_tasks.add_task(run_asset_preview_task, asset.id, task.id)
    return asset


@API_V1_ENTERPRISE_ROUTER.get(
    "/assets",
    response_model=list[AssetItemResponse],
)
async def get_enterprise_assets(
    workspace_id: uuid.UUID | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    asset_status: AssetStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=300),
    tags: list[str] = Query(default=[]),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_assets(
        session,
        principal=principal,
        workspace_id=workspace_id,
        asset_type=asset_type,
        status=asset_status,
        query=q,
        tags=tags,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/assets/analytics",
    response_model=AssetAnalyticsResponse,
)
async def get_enterprise_asset_analytics(
    workspace_id: uuid.UUID = Query(),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_asset_analytics(
        session, principal=principal, workspace_id=workspace_id
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/assets/personalized",
    response_model=list[AssetPersonalizedItemResponse],
)
async def get_enterprise_personalized_assets(
    workspace_id: uuid.UUID = Query(),
    view: str = Query(default="recommended", pattern="^(favorites|recent|recommended)$"),
    scene_type: str | None = Query(default=None, max_length=64),
    tags: list[str] = Query(default=[]),
    limit: int = Query(default=20, ge=1, le=100),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_personalized_assets(
        session,
        principal=principal,
        workspace_id=workspace_id,
        view=view,
        scene_type=scene_type,
        tags=tags,
        limit=limit,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/assets/search",
    response_model=list[AssetDiscoveryItemResponse],
)
async def get_enterprise_asset_search(
    workspace_id: uuid.UUID = Query(),
    q: str = Query(min_length=1, max_length=300),
    asset_type: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await search_assets(session, principal=principal, workspace_id=workspace_id, query=q, asset_type=asset_type, limit=limit)


@API_V1_ENTERPRISE_ROUTER.get(
    "/assets/{asset_id}/similar",
    response_model=list[AssetDiscoveryItemResponse],
)
async def get_enterprise_similar_assets(
    asset_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(),
    limit: int = Query(default=10, ge=1, le=50),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await find_similar_assets(session, principal=principal, asset_id=asset_id, workspace_id=workspace_id, limit=limit)


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets/{asset_id}/duplicate-decision",
    response_model=AssetDuplicateDecisionResponse,
)
async def post_enterprise_asset_duplicate_decision(
    asset_id: uuid.UUID,
    body: AssetDuplicateDecisionRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await decide_asset_duplicate(session, principal=principal, asset_id=asset_id, action=body.action, canonical_asset_id=body.canonical_asset_id)


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets/{asset_id}/favorite",
    response_model=AssetFavoriteResponse,
)
async def post_enterprise_asset_favorite(
    asset_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await set_asset_favorite(
        session, asset_id=asset_id, principal=principal, favorite=True
    )


@API_V1_ENTERPRISE_ROUTER.delete(
    "/assets/{asset_id}/favorite",
    response_model=AssetFavoriteResponse,
)
async def delete_enterprise_asset_favorite(
    asset_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await set_asset_favorite(
        session, asset_id=asset_id, principal=principal, favorite=False
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/slides/{slide_id}/assets",
    response_model=AssetItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_slide_asset(
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    slide_id: uuid.UUID,
    body: SlideAssetCreateRequest,
    background_tasks: BackgroundTasks,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    asset = await save_slide_as_asset(
        session,
        principal=principal,
        workspace_id=workspace_id,
        entry_id=entry_id,
        slide_id=slide_id,
        values=body.model_dump(),
    )
    task = await queue_asset_preview(session, asset_id=asset.id, principal=principal)
    background_tasks.add_task(run_asset_preview_task, asset.id, task.id)
    return asset


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/slides/{slide_id}/element-assets",
    response_model=AssetItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_slide_element_asset(
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    slide_id: uuid.UUID,
    body: SlideElementAssetCreateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await save_slide_element_as_asset(
        session,
        principal=principal,
        workspace_id=workspace_id,
        entry_id=entry_id,
        slide_id=slide_id,
        values=body.model_dump(),
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/slides/{slide_id}/assets/{asset_id}/versions",
    response_model=AssetItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_slide_asset_version(
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    slide_id: uuid.UUID,
    asset_id: uuid.UUID,
    body: SlideAssetVersionCreateRequest,
    background_tasks: BackgroundTasks,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    asset = await save_slide_as_asset_version(
        session,
        principal=principal,
        workspace_id=workspace_id,
        entry_id=entry_id,
        slide_id=slide_id,
        asset_id=asset_id,
        values=body.model_dump(),
    )
    task = await queue_asset_preview(session, asset_id=asset.id, principal=principal)
    background_tasks.add_task(run_asset_preview_task, asset.id, task.id)
    return asset


@API_V1_ENTERPRISE_ROUTER.get(
    "/assets/{asset_id}/versions",
    response_model=list[AssetItemResponse],
)
async def get_enterprise_asset_versions(
    asset_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_asset_versions(
        session, asset_id=asset_id, principal=principal
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/assets/{asset_id}/compatibility",
    response_model=AssetCompatibilityResponse,
)
async def get_enterprise_asset_compatibility(
    asset_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(),
    presentation_entry_id: uuid.UUID = Query(),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_asset_compatibility(
        session,
        asset_id=asset_id,
        workspace_id=workspace_id,
        entry_id=presentation_entry_id,
        principal=principal,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets/{asset_id}/preview-tasks",
    response_model=AssetPreviewTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_enterprise_asset_preview_task(
    asset_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    task = await queue_asset_preview(session, asset_id=asset_id, principal=principal)
    background_tasks.add_task(run_asset_preview_task, asset_id, task.id)
    return AssetPreviewTaskResponse(asset_id=asset_id, task_id=task.id, status=task.status)


@API_V1_ENTERPRISE_ROUTER.get("/assets/{asset_id}/thumbnail")
async def get_enterprise_asset_thumbnail(
    asset_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    location = await get_asset_preview_location(session, asset_id=asset_id, principal=principal)
    return await get_enterprise_object_storage().download_response(
        location, filename=None, media_type="image/png"
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets/{asset_id}/transitions/{action}",
    response_model=AssetItemResponse,
)
async def post_enterprise_asset_transition(
    asset_id: uuid.UUID,
    action: str,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    if action not in {"publish", "offline", "archive"}:
        raise HTTPException(status_code=404, detail="Asset action not found")
    return await transition_asset(
        session, asset_id=asset_id, principal=principal, action=action
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets/bulk-transition",
    response_model=list[AssetItemResponse],
)
async def post_enterprise_asset_bulk_transition(
    body: AssetBulkTransitionRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await bulk_transition_assets(
        session,
        asset_ids=body.asset_ids,
        principal=principal,
        action=body.action,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets/{asset_id}/insert-page",
    response_model=AssetPageInsertResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_enterprise_asset_insert_page(
    asset_id: uuid.UUID,
    body: AssetPageInsertRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    slide, compatibility = await insert_asset_page(
        session,
        asset_id=asset_id,
        workspace_id=body.workspace_id,
        entry_id=body.presentation_entry_id,
        principal=principal,
        after_index=body.after_index,
    )
    return AssetPageInsertResponse(
        slide_id=slide.id,
        slide_index=slide.index,
        asset_id=asset_id,
        compatibility=AssetCompatibilityResponse.model_validate(compatibility),
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets/{asset_id}/insert-element",
    response_model=AssetElementInsertResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_enterprise_asset_insert_element(
    asset_id: uuid.UUID,
    body: AssetElementInsertRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    slide, component_id, component_index, asset_type = await insert_asset_element(
        session,
        asset_id=asset_id,
        workspace_id=body.workspace_id,
        entry_id=body.presentation_entry_id,
        slide_id=body.slide_id,
        principal=principal,
    )
    return AssetElementInsertResponse(
        asset_id=asset_id,
        slide_id=slide.id,
        component_id=component_id,
        component_index=component_index,
        asset_type=asset_type,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/assets/{asset_id}/promotion-requests",
    response_model=AssetPromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_asset_promotion_request(
    asset_id: uuid.UUID,
    body: AssetPromotionCreateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await create_promotion_request(
        session,
        asset_id=asset_id,
        principal=principal,
        values=body.model_dump(),
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/asset-promotion-requests",
    response_model=list[AssetPromotionResponse],
)
async def get_asset_promotion_requests(
    workspace_id: uuid.UUID | None = Query(default=None),
    view: str = Query(default="mine", pattern="^(mine|review)$"),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_promotion_requests(
        session,
        principal=principal,
        workspace_id=workspace_id,
        view=view,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/asset-promotion-requests/{request_id}/decision",
    response_model=AssetPromotionResponse,
)
async def post_asset_promotion_decision(
    request_id: uuid.UUID,
    body: AssetPromotionDecisionRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await decide_promotion_request(
        session,
        request_id=request_id,
        principal=principal,
        action=body.action,
        comment=body.comment,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/notifications",
    response_model=EnterpriseNotificationListResponse,
)
async def get_enterprise_notifications(workspace_id: uuid.UUID | None = Query(default=None), unread_only: bool = Query(default=False), limit: int = Query(default=30, ge=1, le=100), principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    await refresh_due_notifications(session, principal=principal, workspace_id=workspace_id)
    return await list_notifications(session, principal=principal, workspace_id=workspace_id, unread_only=unread_only, limit=limit)


@API_V1_ENTERPRISE_ROUTER.post(
    "/notifications/{notification_id}/read",
    response_model=EnterpriseNotificationResponse,
)
async def post_enterprise_notification_read(notification_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await mark_notification_read(session, principal=principal, notification_id=notification_id)


@API_V1_ENTERPRISE_ROUTER.post(
    "/notifications/read-all",
    response_model=EnterpriseNotificationReadAllResponse,
)
async def post_enterprise_notifications_read_all(workspace_id: uuid.UUID | None = Query(default=None), principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return {"updated_count": await mark_all_notifications_read(session, principal=principal, workspace_id=workspace_id)}


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


@API_V1_ENTERPRISE_ROUTER.post("/bid/projects/{project_id}/deliveries/{artifact_id}/revoke", response_model=BidDeliveryArtifactResponse)
async def post_bid_delivery_revoke(project_id: uuid.UUID, artifact_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await revoke_delivery_artifact(session, project_id=project_id, artifact_id=artifact_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get("/bid/deliveries/download/{token}")
async def get_bid_delivery_download(token: str, session: AsyncSession = Depends(get_async_session)):
    artifact, location = await consume_download_grant(session, token=token)
    artifact_format = getattr(artifact.format, "value", artifact.format)
    media_type = "application/pdf" if artifact_format == "pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return await get_enterprise_object_storage().download_response(
        location, filename=artifact.file_name, media_type=media_type
    )


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
    "/workspaces/{workspace_id}", response_model=WorkspaceResponse
)
async def put_workspace(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    workspace = await update_workspace_details(
        session,
        workspace_id=workspace_id,
        principal=principal,
        name=body.name,
        confidentiality=body.confidentiality,
    )
    _, membership = await require_workspace_role(
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


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_workspace_member(
    workspace_id: uuid.UUID,
    body: WorkspaceMemberInviteRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    member, user = await add_or_update_member_by_username(
        session,
        workspace_id=workspace_id,
        principal=principal,
        username=body.username,
        role=body.role,
    )
    return WorkspaceMemberResponse(
        id=member.id,
        user_id=member.user_id,
        username=user.username,
        role=member.role,
        created_at=member.created_at,
    )


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


@API_V1_ENTERPRISE_ROUTER.put(
    "/workspaces/{workspace_id}/folders/{folder_id}",
    response_model=FolderResponse,
)
async def put_workspace_folder(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    body: FolderUpdateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await update_folder(
        session,
        workspace_id=workspace_id,
        folder_id=folder_id,
        principal=principal,
        name=body.name,
        parent_id=body.parent_id,
    )


@API_V1_ENTERPRISE_ROUTER.delete(
    "/workspaces/{workspace_id}/folders/{folder_id}", status_code=204
)
async def delete_workspace_folder(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    await archive_folder(
        session,
        workspace_id=workspace_id,
        folder_id=folder_id,
        principal=principal,
    )
    return Response(status_code=204)


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
    "/workspaces/{workspace_id}/presentations/search",
    response_model=PresentationCatalogResponse,
)
async def get_presentation_catalog(
    workspace_id: uuid.UUID,
    query: str | None = Query(default=None, max_length=200),
    folder_id: uuid.UUID | None = Query(default=None),
    unfiled_only: bool = Query(default=False),
    presentation_status: PresentationEntryStatus | None = Query(default=None),
    creation_mode: PresentationCreationMode | None = Query(default=None),
    mine_only: bool = Query(default=False),
    sort_by: str = Query(
        default="updated_desc",
        pattern="^(updated_desc|updated_asc|title_asc|title_desc|created_desc)$",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    rows, total = await search_presentation_entries(
        session,
        principal=principal,
        workspace_id=workspace_id,
        query_text=query,
        folder_id=folder_id,
        unfiled_only=unfiled_only,
        status=presentation_status,
        creation_mode=creation_mode,
        mine_only=mine_only,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    return PresentationCatalogResponse(
        items=[
            PresentationCatalogItemResponse.model_validate(entry).model_copy(
                update={"can_open": True, "creator_username": username}
            )
            for entry, username in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/move",
    response_model=list[PresentationEntryResponse],
)
async def post_presentation_entries_move(
    workspace_id: uuid.UUID,
    body: PresentationBulkMoveRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    entries = await move_presentation_entries(
        session,
        principal=principal,
        workspace_id=workspace_id,
        entry_ids=body.entry_ids,
        folder_id=body.folder_id,
    )
    return [
        PresentationEntryResponse.model_validate(entry).model_copy(
            update={"can_open": True}
        )
        for entry in entries
    ]


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/lifecycle",
    response_model=list[PresentationEntryResponse],
)
async def post_presentation_entries_lifecycle(
    workspace_id: uuid.UUID,
    body: PresentationBulkLifecycleRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await bulk_set_presentation_archived(
        session,
        principal=principal,
        workspace_id=workspace_id,
        entry_ids=body.entry_ids,
        archived=body.action == "archive",
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/copy",
    response_model=PresentationEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_entry_copy(
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: PresentationCopyRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await copy_presentation_to_workspace(
        session,
        principal=principal,
        source_workspace_id=workspace_id,
        entry_id=entry_id,
        target_workspace_id=body.target_workspace_id,
        target_folder_id=body.target_folder_id,
        title=body.title,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/archive",
    response_model=PresentationEntryResponse,
)
async def post_presentation_entry_archive(
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await set_presentation_archived(
        session,
        principal=principal,
        workspace_id=workspace_id,
        entry_id=entry_id,
        archived=True,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/restore",
    response_model=PresentationEntryResponse,
)
async def post_presentation_entry_restore(
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await set_presentation_archived(
        session,
        principal=principal,
        workspace_id=workspace_id,
        entry_id=entry_id,
        archived=False,
    )


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/governance",
    response_model=PresentationGovernanceResponse,
)
async def get_presentation_entry_governance(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await get_presentation_governance(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/freeze-preflight",
    response_model=PresentationFreezePreflightResponse,
)
async def get_presentation_entry_freeze_preflight(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await get_presentation_freeze_preflight(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/snapshots/{snapshot_id}/evidence",
    response_model=PresentationSnapshotEvidenceResponse,
)
async def get_presentation_entry_snapshot_evidence(workspace_id: uuid.UUID, entry_id: uuid.UUID, snapshot_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await get_presentation_snapshot_evidence(session, workspace_id=workspace_id, entry_id=entry_id, snapshot_id=snapshot_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/review-inbox",
    response_model=PresentationReviewInboxResponse,
)
async def get_workspace_presentation_review_inbox(workspace_id: uuid.UUID, scope: str = Query(default="all", pattern="^(all|mine)$"), task_status: str = Query(default="open", pattern="^(all|open|resolved)$"), overdue_only: bool = Query(default=False), principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    result = await get_workspace_review_inbox(session, workspace_id=workspace_id, principal=principal, scope=scope, status=task_status, overdue_only=overdue_only)
    return {
        "summary": result["summary"],
        "tasks": [{**PresentationCommentThreadResponse.model_validate(row["thread"]).model_dump(), **{key: value for key, value in row.items() if key != "thread"}} for row in result["tasks"]],
    }


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/comment-threads",
    response_model=PresentationCommentThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_comment_thread(workspace_id: uuid.UUID, entry_id: uuid.UUID, body: PresentationCommentCreateRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await create_comment_thread(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal, values=body.model_dump())


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/comment-threads",
    response_model=list[PresentationCommentThreadResponse],
)
async def get_presentation_comment_threads(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    rows = await list_comment_threads(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)
    return [PresentationCommentThreadResponse.model_validate(row["thread"]).model_copy(update={"replies": row["replies"]}) for row in rows]


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/comment-threads/{thread_id}/replies",
    response_model=PresentationCommentReplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_presentation_comment_reply(workspace_id: uuid.UUID, entry_id: uuid.UUID, thread_id: uuid.UUID, body: PresentationCommentReplyCreateRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await add_comment_reply(session, workspace_id=workspace_id, entry_id=entry_id, thread_id=thread_id, principal=principal, body=body.body)


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/presentations/{entry_id}/comment-threads/{thread_id}/{action}",
    response_model=PresentationCommentThreadResponse,
)
async def post_presentation_comment_transition(workspace_id: uuid.UUID, entry_id: uuid.UUID, thread_id: uuid.UUID, action: str, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    if action not in {"resolve", "reopen"}:
        raise HTTPException(status_code=404, detail="Comment action not found")
    return await transition_comment_thread(session, workspace_id=workspace_id, entry_id=entry_id, thread_id=thread_id, principal=principal, action=action)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/snapshot-diff",
    response_model=PresentationSnapshotDiffResponse,
)
async def get_presentation_snapshot_diff(workspace_id: uuid.UUID, entry_id: uuid.UUID, from_snapshot_id: uuid.UUID = Query(), to_snapshot_id: uuid.UUID = Query(), principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await compare_presentation_snapshots(session, workspace_id=workspace_id, entry_id=entry_id, from_snapshot_id=from_snapshot_id, to_snapshot_id=to_snapshot_id, principal=principal)


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
    response_model=list[PresentationSourceCitationDetailResponse],
)
async def get_presentation_source_citations(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await list_source_citation_details(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/citations/summary",
    response_model=PresentationSourceCitationSummaryResponse,
)
async def get_presentation_source_citation_summary(workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await source_citation_summary(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/presentations/{entry_id}/citations/{citation_id}/source",
    response_model=PresentationSourceCitationPreviewResponse,
)
async def get_presentation_source_citation_preview(workspace_id: uuid.UUID, entry_id: uuid.UUID, citation_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await get_source_citation_preview(session, workspace_id=workspace_id, entry_id=entry_id, citation_id=citation_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.delete(
    "/workspaces/{workspace_id}/presentations/{entry_id}/citations/{citation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_presentation_source_citation(workspace_id: uuid.UUID, entry_id: uuid.UUID, citation_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    await delete_source_citation(session, workspace_id=workspace_id, entry_id=entry_id, citation_id=citation_id, principal=principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@API_V1_ENTERPRISE_ROUTER.get("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries/{artifact_id}/evidence", response_model=PresentationDeliveryEvidenceResponse)
async def get_presentation_delivery_evidence_record(workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await get_presentation_delivery_evidence(session, workspace_id=workspace_id, entry_id=entry_id, artifact_id=artifact_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries/{artifact_id}/activity", response_model=list[AuditEventResponse])
async def get_presentation_delivery_activity(workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await list_presentation_delivery_activity(session, workspace_id=workspace_id, entry_id=entry_id, artifact_id=artifact_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries/{artifact_id}/evidence-package")
async def get_presentation_delivery_evidence_package(workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    content, filename, package_hash = await build_presentation_delivery_evidence_package(session, workspace_id=workspace_id, entry_id=entry_id, artifact_id=artifact_id, principal=principal)
    return Response(content=content, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Evidence-Package-SHA256": package_hash})


@API_V1_ENTERPRISE_ROUTER.post("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries/{artifact_id}/evidence-package/verify", response_model=PresentationDeliveryEvidenceVerifyResponse)
async def post_presentation_delivery_evidence_package_verify(workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, body: PresentationDeliveryEvidenceVerifyRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await verify_presentation_delivery_evidence_package(session, workspace_id=workspace_id, entry_id=entry_id, artifact_id=artifact_id, package=body.package, principal=principal)


@API_V1_ENTERPRISE_ROUTER.post("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries/{artifact_id}/grants", response_model=BidDownloadGrantResponse, status_code=status.HTTP_201_CREATED)
async def post_presentation_download_grant(workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, body: BidDownloadGrantRequest, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    grant, token = await issue_presentation_download_grant(session, workspace_id=workspace_id, entry_id=entry_id, artifact_id=artifact_id, principal=principal, **body.model_dump())
    return BidDownloadGrantResponse(grant_id=grant.id, artifact_id=grant.artifact_id, download_url=f"/api/v1/enterprise/presentations/deliveries/download/{token}", expires_at=grant.expires_at, max_downloads=grant.max_downloads)


@API_V1_ENTERPRISE_ROUTER.post("/workspaces/{workspace_id}/presentations/{entry_id}/deliveries/{artifact_id}/revoke", response_model=PresentationDeliveryArtifactResponse)
async def post_presentation_delivery_revoke(workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await revoke_presentation_delivery(session, workspace_id=workspace_id, entry_id=entry_id, artifact_id=artifact_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get("/presentations/deliveries/download/{token}")
async def get_presentation_delivery_download(token: str, session: AsyncSession = Depends(get_async_session)):
    artifact, location = await consume_presentation_download_grant(session, token=token)
    artifact_format = getattr(artifact.format, "value", artifact.format)
    media_type = "application/pdf" if artifact_format == "pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return await get_enterprise_object_storage().download_response(
        location, filename=artifact.file_name, media_type=media_type
    )


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


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/delivery-center",
    response_model=DeliveryCenterResponse,
)
async def get_workspace_delivery_center(
    workspace_id: uuid.UUID,
    scene_type: str | None = Query(default=None, pattern="^(general|bid)$"),
    delivery_status: str | None = Query(default=None, pattern="^(ready|revoked)$"),
    integrity_status: str | None = Query(default=None, pattern="^(passed|failed)$"),
    q: str | None = Query(default=None, max_length=200),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_delivery_center(session, workspace_id=workspace_id, principal=principal, scene_type=scene_type, delivery_status=delivery_status, integrity_status=integrity_status, query=q)


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/delivery-center/integrity-runs",
    response_model=DeliveryIntegrityScanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_workspace_delivery_integrity_run(workspace_id: uuid.UUID, principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await run_delivery_integrity_scan(session, workspace_id=workspace_id, principal=principal)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/delivery-center/integrity-runs",
    response_model=list[DeliveryIntegrityScanResponse],
)
async def get_workspace_delivery_integrity_runs(workspace_id: uuid.UUID, limit: int = Query(default=20, ge=1, le=100), principal: AuthPrincipal = Depends(principal_from_request), session: AsyncSession = Depends(get_async_session)):
    return await list_delivery_integrity_scans(session, workspace_id=workspace_id, principal=principal, limit=limit)


@API_V1_ENTERPRISE_ROUTER.get(
    "/workspaces/{workspace_id}/delivery-integrity-incidents",
    response_model=list[DeliveryIntegrityIncidentResponse],
)
async def get_workspace_delivery_integrity_incidents(
    workspace_id: uuid.UUID,
    status: str | None = Query(default=None),
    scene_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_delivery_integrity_incidents(
        session,
        principal=principal,
        workspace_id=workspace_id,
        status=status,
        scene_type=scene_type,
        limit=limit,
    )


@API_V1_ENTERPRISE_ROUTER.patch(
    "/workspaces/{workspace_id}/delivery-integrity-incidents/{incident_id}",
    response_model=DeliveryIntegrityIncidentResponse,
)
async def patch_workspace_delivery_integrity_incident(
    workspace_id: uuid.UUID,
    incident_id: uuid.UUID,
    body: DeliveryIntegrityIncidentUpdateRequest,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await update_delivery_integrity_incident(
        session,
        incident_id=incident_id,
        principal=principal,
        status=body.status,
        assigned_to=body.assigned_to,
        resolution_note=body.resolution_note,
        workspace_id=workspace_id,
    )


@API_V1_ENTERPRISE_ROUTER.post(
    "/workspaces/{workspace_id}/delivery-integrity-incidents/{incident_id}/recheck",
    response_model=DeliveryIntegrityIncidentResponse,
)
async def post_workspace_delivery_integrity_incident_recheck(
    workspace_id: uuid.UUID,
    incident_id: uuid.UUID,
    principal: AuthPrincipal = Depends(principal_from_request),
    session: AsyncSession = Depends(get_async_session),
):
    return await recheck_delivery_integrity_incident(
        session,
        incident_id=incident_id,
        principal=principal,
        workspace_id=workspace_id,
    )
