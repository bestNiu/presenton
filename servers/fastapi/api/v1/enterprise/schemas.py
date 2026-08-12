from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domains.platform.enums import (
    ConfidentialityLevel,
    PresentationCreationMode,
    PresentationEntryStatus,
    SceneStatus,
    TemplatePublicationStatus,
    TemplateScopeType,
    WorkspaceRole,
    WorkspaceType,
)


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
