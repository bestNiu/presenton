from enum import Enum


class WorkspaceType(str, Enum):
    PERSONAL = "personal"
    TEAM = "team"
    DEPARTMENT = "department"


class WorkspaceRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class ConfidentialityLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class PresentationEntryStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    FROZEN = "frozen"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PresentationCreationMode(str, Enum):
    TOPIC = "topic"
    DOCUMENT = "document"
    TEMPLATE = "template"
    BLANK = "blank"
    IMPORT = "import"


class TemplateScopeType(str, Enum):
    ENTERPRISE = "enterprise"
    WORKSPACE = "workspace"
    SCENE = "scene"


class TemplatePublicationStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    OFFLINE = "offline"
    ARCHIVED = "archived"


class SceneStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AuditResult(str, Enum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"
