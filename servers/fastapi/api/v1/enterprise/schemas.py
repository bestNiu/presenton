from datetime import date, datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domains.platform.enums import (
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
    ConfidentialityLevel,
    PresentationCreationMode,
    PresentationEntryStatus,
    SceneStatus,
    TemplatePublicationStatus,
    TemplateScopeType,
    WorkspaceRole,
    WorkspaceType,
)


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
    current_user_role: WorkspaceRole
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberUpsertRequest(BaseModel):
    user_id: uuid.UUID
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    role: WorkspaceRole
    created_at: datetime


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
