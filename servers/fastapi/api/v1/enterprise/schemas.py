from datetime import date, datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from domains.platform.enums import (
    AssetScopeType,
    AssetStatus,
    AssetPromotionStatus,
    BidContentStatus,
    BidCommitmentStatus,
    BidDocumentStatus,
    BidGateStatus,
    BidGateType,
    BidIssueStatus,
    BidModuleStatus,
    BidModuleType,
    BidProjectRole,
    BidProjectStatus,
    BidRequirementStatus,
    BidReleaseStatus,
    BidDeliveryFormat,
    BidDeliveryStatus,
    ConfidentialityLevel,
    PresentationCreationMode,
    PresentationCommentStatus,
    PresentationEntryStatus,
    PresentationDeliveryFormat,
    PresentationDeliveryStatus,
    PresentationQualitySeverity,
    PresentationQualityStatus,
    PresentationReviewStatus,
    SceneStatus,
    TemplatePublicationStatus,
    TemplateScopeType,
    WorkspaceRole,
    WorkspaceType,
)


class AssetMetadataRequest(BaseModel):
    scope_type: AssetScopeType = AssetScopeType.PERSONAL
    name: str = Field(min_length=1, max_length=300)
    description: str | None = None
    scene_type: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=30)
    authorization_status: str = Field(default="internal", pattern="^(internal|authorized|revoked)$")
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_asset_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Asset name is required")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_asset_tags(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            tag = value.strip()
            if tag and tag not in normalized:
                if len(tag) > 64:
                    raise ValueError("Asset tag cannot exceed 64 characters")
                normalized.append(tag)
        return normalized


class AssetCreateRequest(AssetMetadataRequest):
    workspace_id: uuid.UUID | None = None
    asset_type: str = Field(pattern="^(page|chart|image|logo|copy|component)$")
    payload: dict
    compatibility: dict = Field(default_factory=dict)


class SlideAssetCreateRequest(AssetMetadataRequest):
    pass


class SlideElementAssetCreateRequest(AssetMetadataRequest):
    asset_type: str = Field(pattern="^(chart|image|logo|copy|component)$")
    component_index: int = Field(ge=0)
    element_index: int | None = Field(default=None, ge=0)


class SlideAssetVersionCreateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    tags: list[str] | None = Field(default=None, max_length=30)


class AssetItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version_group_id: uuid.UUID
    version_no: int
    is_latest: bool
    supersedes_asset_id: uuid.UUID | None
    duplicate_of_asset_id: uuid.UUID | None
    duplicate_status: str
    workspace_id: uuid.UUID | None
    created_by: uuid.UUID | None
    scope_type: AssetScopeType
    asset_type: str
    name: str
    description: str | None
    scene_type: str | None
    tags: list[str]
    payload_hash: str
    preview: dict
    preview_status: str
    preview_task_id: str | None
    preview_error: str | None
    source_presentation_entry_id: uuid.UUID | None
    source_slide_id: uuid.UUID | None
    parent_asset_id: uuid.UUID | None
    authorization_status: str
    expires_at: datetime | None
    compatibility: dict
    status: AssetStatus
    usage_count: int
    published_by: uuid.UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def preview_url(self) -> str | None:
        if self.preview_status != "ready":
            return None
        return f"/api/v1/enterprise/assets/{self.id}/thumbnail"


class AssetPageInsertRequest(BaseModel):
    workspace_id: uuid.UUID
    presentation_entry_id: uuid.UUID
    after_index: int | None = Field(default=None, ge=-1)


class AssetCompatibilityIssue(BaseModel):
    code: str
    severity: str
    message: str


class AssetCompatibilityResponse(BaseModel):
    asset_id: uuid.UUID
    presentation_entry_id: uuid.UUID
    status: str
    can_insert: bool
    strategy: str
    source_template_id: str | None = None
    target_template_id: str | None = None
    issues: list[AssetCompatibilityIssue] = Field(default_factory=list)


class AssetPageInsertResponse(BaseModel):
    slide_id: uuid.UUID
    slide_index: int
    asset_id: uuid.UUID
    compatibility: AssetCompatibilityResponse


class AssetElementInsertRequest(BaseModel):
    workspace_id: uuid.UUID
    presentation_entry_id: uuid.UUID
    slide_id: uuid.UUID


class AssetElementInsertResponse(BaseModel):
    asset_id: uuid.UUID
    slide_id: uuid.UUID
    component_id: str
    component_index: int
    asset_type: str


class AssetBulkTransitionRequest(BaseModel):
    asset_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(publish|offline|archive)$")


class AssetPromotionCreateRequest(BaseModel):
    target_scope_type: AssetScopeType
    target_workspace_id: uuid.UUID | None = None
    justification: str = Field(min_length=5, max_length=2000)
    desensitization_notes: str = Field(min_length=5, max_length=4000)
    authorization_confirmed: bool


class AssetPromotionDecisionRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str = Field(min_length=2, max_length=2000)


class AssetPromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_asset_id: uuid.UUID
    promoted_asset_id: uuid.UUID | None
    target_scope_type: AssetScopeType
    target_workspace_id: uuid.UUID | None
    requested_by: uuid.UUID
    asset_name_snapshot: str
    justification: str
    desensitization_notes: str
    authorization_confirmed: bool
    status: AssetPromotionStatus
    decided_by: uuid.UUID | None
    decision_comment: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssetAnalyticsTopItem(BaseModel):
    asset_id: uuid.UUID
    name: str
    asset_type: str
    scope_type: AssetScopeType
    reuse_count: int


class AssetAnalyticsResponse(BaseModel):
    total_assets: int
    published_assets: int
    expiring_within_7_days: int
    expired_assets: int
    total_reuses: int
    reuses_last_30_days: int
    unique_presentations: int
    unique_users: int
    by_scope: dict[str, int]
    by_type: dict[str, int]
    top_assets: list[AssetAnalyticsTopItem]


class AssetPersonalizedItemResponse(BaseModel):
    asset: AssetItemResponse
    is_favorite: bool
    last_used_at: datetime | None = None
    recommendation_score: float | None = None
    recommendation_reasons: list[str] = Field(default_factory=list)


class AssetFavoriteResponse(BaseModel):
    asset_id: uuid.UUID
    is_favorite: bool


class AssetDiscoveryItemResponse(BaseModel):
    asset: AssetItemResponse
    score: float
    reasons: list[str] = Field(default_factory=list)
    exact_duplicate: bool = False


class AssetDuplicateDecisionRequest(BaseModel):
    action: str = Field(pattern="^(confirm|distinct)$")
    canonical_asset_id: uuid.UUID | None = None


class AssetDuplicateDecisionResponse(BaseModel):
    asset_id: uuid.UUID
    duplicate_status: str
    duplicate_of_asset_id: uuid.UUID | None


class AssetPreviewTaskResponse(BaseModel):
    asset_id: uuid.UUID
    task_id: str
    status: str


class BidProjectCreateRequest(BaseModel):
    workspace_id: uuid.UUID
    bid_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    sponsor_name: str | None = Field(default=None, max_length=300)
    drug_name: str | None = Field(default=None, max_length=300)
    indication: str | None = Field(default=None, max_length=300)
    due_date: date | None = None
    confidentiality: ConfidentialityLevel = ConfidentialityLevel.L3

    @field_validator("bid_code", "name")
    @classmethod
    def normalize_bid_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value is required")
        return value


class BidProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by: uuid.UUID | None
    bid_code: str
    name: str
    sponsor_name: str | None
    drug_name: str | None
    indication: str | None
    due_date: date | None
    confidentiality: ConfidentialityLevel
    status: BidProjectStatus
    current_user_role: BidProjectRole | None = None
    row_version: int
    created_at: datetime
    updated_at: datetime


class BidProjectMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: BidProjectRole


class BidProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: BidProjectRole
    created_at: datetime


class BidDocumentCreateRequest(BaseModel):
    logical_name: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=64)
    version_no: int = Field(default=1, ge=1)
    file_ref: str = Field(min_length=1, max_length=2000)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)


class BidDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    logical_name: str
    category: str
    version_no: int
    status: BidDocumentStatus
    created_by: uuid.UUID | None
    created_at: datetime


class BidProfileUpdateRequest(BaseModel):
    facts: dict = Field(default_factory=dict)
    conflicts: list = Field(default_factory=list)
    row_version: int = Field(ge=1)


class BidProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    schema_version: str
    facts: dict
    conflicts: list
    status: BidContentStatus
    row_version: int
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class BidRequirementCreateRequest(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    original_text: str = Field(min_length=1, max_length=10000)
    mandatory: bool = True
    score: float | None = Field(default=None, ge=0)
    source_ref: str | None = Field(default=None, max_length=1000)
    owner_department: str | None = Field(default=None, max_length=200)
    target_module: str | None = Field(default=None, max_length=100)


class BidRequirementUpdateRequest(BaseModel):
    response: str | None = Field(default=None, max_length=20000)
    status: BidRequirementStatus
    owner_department: str | None = Field(default=None, max_length=200)
    target_module: str | None = Field(default=None, max_length=100)
    row_version: int = Field(ge=1)


class BidRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    category: str
    original_text: str
    mandatory: bool
    score: float | None
    source_ref: str | None
    owner_department: str | None
    target_module: str | None
    response: str | None
    status: BidRequirementStatus
    row_version: int
    created_at: datetime
    updated_at: datetime


class BidStrategyUpdateRequest(BaseModel):
    elements: dict = Field(default_factory=dict)
    row_version: int = Field(default=1, ge=1)


class BidStrategyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    elements: dict
    status: BidContentStatus
    row_version: int
    created_by: uuid.UUID | None
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BidProjectDashboardResponse(BaseModel):
    project: BidProjectResponse
    profile: BidProfileResponse
    documents: list[BidDocumentResponse]
    requirements: list[BidRequirementResponse]
    strategy: BidStrategyResponse
    mandatory_requirement_coverage: float
    strategy_blockers: list[str]


class BidModuleUpdateRequest(BaseModel):
    content: dict = Field(default_factory=dict)
    row_version: int = Field(ge=1)


class BidModuleReviewRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str | None = Field(default=None, max_length=2000)


class BidModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    module_type: BidModuleType
    version_no: int
    input_snapshot: dict
    content: dict
    status: BidModuleStatus
    row_version: int
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    reviewed_by: uuid.UUID | None
    review_comment: str | None
    created_at: datetime
    updated_at: datetime


class BidCommitmentCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    commitment_type: str = Field(min_length=1, max_length=64)
    conditions: str | None = Field(default=None, max_length=10000)
    evidence_ref: str | None = Field(default=None, max_length=1000)
    risk_level: str = Field(default="medium", pattern="^(low|medium|high)$")


class BidCommitmentActionRequest(BaseModel):
    action: str = Field(pattern="^(submit|approve|reject|revoke)$")
    comment: str | None = Field(default=None, max_length=2000)


class BidCommitmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    content: str
    commitment_type: str
    conditions: str | None
    evidence_ref: str | None
    risk_level: str
    status: BidCommitmentStatus
    row_version: int
    proposed_by: uuid.UUID | None
    decided_by: uuid.UUID | None
    decision_comment: str | None
    created_at: datetime
    updated_at: datetime


class BidGateActionRequest(BaseModel):
    action: str = Field(pattern="^(open|pass)$")


class BidIssueCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    severity: str = Field(default="blocking", pattern="^(blocking|warning)$")
    owner_id: uuid.UUID | None = None


class BidIssueResolveRequest(BaseModel):
    resolution: str = Field(min_length=1, max_length=10000)


class BidIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    gate_id: uuid.UUID
    title: str
    description: str | None
    severity: str
    status: BidIssueStatus
    owner_id: uuid.UUID | None
    created_by: uuid.UUID | None
    resolved_by: uuid.UUID | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime


class BidGateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    gate_type: BidGateType
    status: BidGateStatus
    opened_by: uuid.UUID | None
    passed_by: uuid.UUID | None
    opened_at: datetime | None
    passed_at: datetime | None
    issues: list[BidIssueResponse] = Field(default_factory=list)


class BidCollaborationResponse(BaseModel):
    modules: list[BidModuleResponse]
    commitments: list[BidCommitmentResponse]
    gates: list[BidGateResponse]


class BidAssemblyRequest(BaseModel):
    template_publication_id: uuid.UUID
    release_type: str = Field(default="management-summary", pattern="^(management-summary)$")


class BidReleaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    presentation_entry_id: uuid.UUID
    template_publication_id: uuid.UUID
    release_type: str
    version_no: int
    manifest: dict
    manifest_hash: str
    slide_snapshot_hash: str
    status: BidReleaseStatus
    created_by: uuid.UUID | None
    frozen_by: uuid.UUID | None
    frozen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BidDeliveryCreateRequest(BaseModel):
    format: BidDeliveryFormat = BidDeliveryFormat.PPTX
    watermark_text: str | None = Field(default=None, max_length=300)


class BidDeliveryArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    release_id: uuid.UUID
    derived_presentation_id: uuid.UUID | None
    format: BidDeliveryFormat
    watermark_text: str
    file_name: str
    sha256: str
    size_bytes: int
    status: BidDeliveryStatus
    created_by: uuid.UUID | None
    created_at: datetime
    revoked_at: datetime | None
    purged_at: datetime | None


class BidDownloadGrantRequest(BaseModel):
    expires_in_minutes: int = Field(default=30, ge=1, le=1440)
    max_downloads: int = Field(default=1, ge=1, le=20)


class BidDownloadGrantResponse(BaseModel):
    grant_id: uuid.UUID
    artifact_id: uuid.UUID
    download_url: str
    expires_at: datetime
    max_downloads: int


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    workspace_type: WorkspaceType = WorkspaceType.TEAM
    confidentiality: ConfidentialityLevel = ConfidentialityLevel.L2

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Workspace name is required")
        return value


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    workspace_type: WorkspaceType
    confidentiality: ConfidentialityLevel
    is_archived: bool
    governance_policy: dict
    current_user_role: WorkspaceRole
    created_at: datetime
    updated_at: datetime


class WorkspaceGovernancePolicyRequest(BaseModel):
    review_mode: str = Field(default="single", pattern="^(none|single)$")
    quality_gate_enabled: bool = True
    require_numeric_citations: bool = False
    revoked_delivery_retention_days: int = Field(default=90, ge=1, le=3650)


class StorageLifecycleRunRequest(BaseModel):
    execute: bool = False
    max_delete: int = Field(default=100, ge=1, le=1000)


class StorageLifecycleCandidateResponse(BaseModel):
    object_key: str
    reason: str
    size_bytes: int
    last_modified: datetime


class StorageLifecycleRunResponse(BaseModel):
    run_id: uuid.UUID
    mode: str
    backend: str
    scanned_count: int
    stored_bytes: int
    referenced_count: int
    protected_count: int
    protected_bytes: int
    missing_referenced_count: int
    candidate_count: int
    candidate_bytes: int
    orphan_candidate_count: int
    revoked_candidate_count: int
    deleted_count: int
    deleted_bytes: int
    truncated: bool
    candidates: list[StorageLifecycleCandidateResponse]
    started_at: datetime
    completed_at: datetime


class StorageLifecycleHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    triggered_by: uuid.UUID | None
    source: str
    mode: str
    backend: str | None
    status: str
    health: str
    scanned_count: int
    stored_bytes: int
    protected_count: int
    protected_bytes: int
    missing_referenced_count: int
    candidate_count: int
    candidate_bytes: int
    orphan_candidate_count: int
    revoked_candidate_count: int
    deleted_count: int
    deleted_bytes: int
    truncated: bool
    candidate_sample: list[dict]
    failure_detail: str | None
    started_at: datetime
    completed_at: datetime | None


class WorkspaceMemberUpsertRequest(BaseModel):
    user_id: uuid.UUID
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    role: WorkspaceRole
    created_at: datetime


class EnterpriseNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recipient_id: uuid.UUID
    workspace_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    notification_type: str
    title: str
    body: str
    resource_type: str
    resource_id: str
    action_url: str | None
    event_metadata: dict
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class EnterpriseNotificationListResponse(BaseModel):
    unread_count: int
    notifications: list[EnterpriseNotificationResponse]


class EnterpriseNotificationReadAllResponse(BaseModel):
    updated_count: int


class FolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Folder name is required")
        return value


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    parent_id: uuid.UUID | None
    created_by: uuid.UUID | None
    name: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class PresentationRegisterRequest(BaseModel):
    workspace_id: uuid.UUID
    presentation_id: uuid.UUID
    folder_id: uuid.UUID | None = None
    scene_type: str = Field(default="general", min_length=1, max_length=64)
    creation_mode: PresentationCreationMode = PresentationCreationMode.IMPORT

    @field_validator("scene_type")
    @classmethod
    def normalize_scene_type(cls, value: str) -> str:
        return value.strip().lower()


class PresentationEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    folder_id: uuid.UUID | None
    presentation_id: uuid.UUID
    created_by: uuid.UUID | None
    title: str | None
    scene_type: str
    scene_version: str
    creation_mode: PresentationCreationMode
    status: PresentationEntryStatus
    can_open: bool = True
    row_version: int
    created_at: datetime
    updated_at: datetime


class PresentationReviewDecisionRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str | None = Field(default=None, max_length=2000)


class PresentationReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    presentation_entry_id: uuid.UUID
    submission_no: int
    slide_snapshot_hash: str
    status: PresentationReviewStatus
    submitted_by: uuid.UUID | None
    decided_by: uuid.UUID | None
    decision_comment: str | None
    submitted_at: datetime
    decided_at: datetime | None


class PresentationSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    presentation_entry_id: uuid.UUID
    review_id: uuid.UUID
    quality_run_id: uuid.UUID | None
    version_no: int
    manifest: dict
    manifest_hash: str
    slide_snapshot_hash: str
    frozen_by: uuid.UUID | None
    frozen_at: datetime


class PresentationGovernanceResponse(BaseModel):
    entry: PresentationEntryResponse
    reviews: list[PresentationReviewResponse]
    snapshots: list[PresentationSnapshotResponse]


class PresentationCommentCreateRequest(BaseModel):
    slide_id: uuid.UUID | None = None
    slide_index: int | None = Field(default=None, ge=0)
    element_ref: str | None = Field(default=None, max_length=500)
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    is_blocking: bool = False
    assigned_to: uuid.UUID | None = None
    due_at: datetime | None = None


class PresentationCommentReplyCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class PresentationCommentReplyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    thread_id: uuid.UUID
    body: str
    created_by: uuid.UUID | None
    created_at: datetime


class PresentationCommentThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    presentation_entry_id: uuid.UUID
    slide_id: uuid.UUID | None
    slide_index: int | None
    element_ref: str | None
    title: str
    body: str
    is_blocking: bool
    status: PresentationCommentStatus
    assigned_to: uuid.UUID | None
    due_at: datetime | None
    slide_snapshot_hash: str
    created_by: uuid.UUID | None
    resolved_by: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    replies: list[PresentationCommentReplyResponse] = Field(default_factory=list)


class PresentationSnapshotSlideDiffResponse(BaseModel):
    slide_id: str
    before_index: int | None
    after_index: int | None
    change_type: str
    changed_fields: list[str]


class PresentationSnapshotDiffResponse(BaseModel):
    from_snapshot_id: uuid.UUID
    from_version_no: int
    to_snapshot_id: uuid.UUID
    to_version_no: int
    added: int
    removed: int
    changed: int
    unchanged: int
    slides: list[PresentationSnapshotSlideDiffResponse]


class PresentationReviewTaskSummaryResponse(BaseModel):
    open_count: int
    blocking_count: int
    overdue_count: int
    assigned_to_me_count: int


class PresentationReviewTaskResponse(PresentationCommentThreadResponse):
    presentation_title: str
    scene_type: str
    presentation_status: PresentationEntryStatus
    assigned_to_username: str | None
    reply_count: int
    is_overdue: bool


class PresentationReviewInboxResponse(BaseModel):
    summary: PresentationReviewTaskSummaryResponse
    tasks: list[PresentationReviewTaskResponse]


class PresentationDeliveryCreateRequest(BaseModel):
    snapshot_id: uuid.UUID
    format: PresentationDeliveryFormat = PresentationDeliveryFormat.PPTX
    watermark_text: str | None = Field(default=None, max_length=300)


class PresentationDeliveryArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    snapshot_id: uuid.UUID
    derived_presentation_id: uuid.UUID | None
    format: PresentationDeliveryFormat
    watermark_text: str
    file_name: str
    sha256: str
    size_bytes: int
    status: PresentationDeliveryStatus
    created_by: uuid.UUID | None
    created_at: datetime
    revoked_at: datetime | None
    purged_at: datetime | None


class PresentationQualityIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    quality_run_id: uuid.UUID
    rule_code: str
    severity: PresentationQualitySeverity
    slide_id: uuid.UUID | None
    slide_index: int | None
    element_ref: str | None
    message: str
    details: dict


class PresentationQualityRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    presentation_entry_id: uuid.UUID
    slide_snapshot_hash: str
    status: PresentationQualityStatus
    blocking_count: int
    warning_count: int
    policy_snapshot: dict
    created_by: uuid.UUID | None
    created_at: datetime
    issues: list[PresentationQualityIssueResponse] = Field(default_factory=list)


class PresentationQualityReportResponse(BaseModel):
    run: PresentationQualityRunResponse | None


class PresentationSourceCitationCreateRequest(BaseModel):
    slide_id: uuid.UUID | None = None
    element_ref: str | None = Field(default=None, max_length=500)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=500)
    source_version: str | None = Field(default=None, max_length=100)
    locator: str | None = Field(default=None, max_length=500)
    excerpt: str | None = Field(default=None, max_length=2000)


class PresentationSourceCitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    presentation_entry_id: uuid.UUID
    slide_id: uuid.UUID | None
    element_ref: str | None
    source_type: str
    source_id: str
    source_version: str | None
    locator: str | None
    excerpt: str | None
    created_by: uuid.UUID | None
    created_at: datetime


class SceneDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scene_type: str
    version: str
    display_name: str
    description: str | None
    config: dict
    status: SceneStatus


class SceneNavigationItemResponse(BaseModel):
    code: str
    label: str
    route: str


class SceneRuntimeResponse(BaseModel):
    scene_type: str
    version: str
    display_name: str
    description: str | None
    workspace_id: uuid.UUID
    workspace_role: WorkspaceRole
    entry_route: str
    create_schema: str
    navigation: list[SceneNavigationItemResponse]
    permissions: list[str]
    capabilities: dict[str, bool]
    policies: dict[str, str]


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str
    result: str
    event_metadata: dict
    created_at: datetime


class TemplatePublicationCreateRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=128)
    publication_key: str = Field(min_length=1, max_length=128)
    version: int = Field(default=1, ge=1)
    scope_type: TemplateScopeType = TemplateScopeType.WORKSPACE
    workspace_id: uuid.UUID | None = None
    scene_type: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    rules: dict = Field(default_factory=dict)
    compatibility: dict = Field(default_factory=dict)
    preview_url: str | None = Field(default=None, max_length=2000)
    recommended_order: int = Field(default=0, ge=0, le=10000)

    @field_validator("template_id", "publication_key")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value is required")
        return value


class TemplatePublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    publication_key: str
    template_id: str
    workspace_id: uuid.UUID | None
    created_by: uuid.UUID | None
    scope_type: TemplateScopeType
    scene_type: str | None
    version: int
    status: TemplatePublicationStatus
    display_name: str
    description: str | None
    rules: dict
    compatibility: dict
    preview_url: str | None
    is_default: bool
    recommended_order: int
    submitted_at: datetime | None
    published_at: datetime | None
    offline_at: datetime | None
    created_at: datetime
    updated_at: datetime
    BidGateStatus,
    BidGateType,
    BidIssueStatus,
    BidModuleStatus,
    BidModuleType,
