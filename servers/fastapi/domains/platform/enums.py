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


class PresentationReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PresentationDeliveryFormat(str, Enum):
    PPTX = "pptx"
    PDF = "pdf"


class PresentationDeliveryStatus(str, Enum):
    READY = "ready"
    REVOKED = "revoked"


class PresentationQualityStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


class PresentationQualitySeverity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"


class PresentationCommentStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class AssetScopeType(str, Enum):
    PERSONAL = "personal"
    WORKSPACE = "workspace"
    ENTERPRISE = "enterprise"


class AssetStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    OFFLINE = "offline"
    ARCHIVED = "archived"


class AssetPromotionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


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


class BidProjectStatus(str, Enum):
    UNDERSTANDING = "understanding"
    STRATEGY_PENDING = "strategy_pending"
    STRATEGY_CONFIRMED = "strategy_confirmed"
    ARCHIVED = "archived"


class BidProjectRole(str, Enum):
    BID_MANAGER = "bid_manager"
    CONTRIBUTOR = "contributor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class BidContentStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    STALE = "stale"


class BidRequirementStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    VERIFIED = "verified"


class BidDocumentStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class BidModuleType(str, Enum):
    MEDICAL = "medical"
    OPERATIONS = "operations"
    STATISTICS = "statistics"


class BidModuleStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    STALE = "stale"


class BidCommitmentStatus(str, Enum):
    CANDIDATE = "candidate"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class BidGateType(str, Enum):
    GATE_1 = "gate_1"
    GATE_2 = "gate_2"
    GATE_3 = "gate_3"


class BidGateStatus(str, Enum):
    LOCKED = "locked"
    OPEN = "open"
    BLOCKED = "blocked"
    PASSED = "passed"


class BidIssueStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class BidReleaseStatus(str, Enum):
    DRAFT = "draft"
    FROZEN = "frozen"
    ARCHIVED = "archived"


class BidDeliveryFormat(str, Enum):
    PPTX = "pptx"
    PDF = "pdf"


class BidDeliveryStatus(str, Enum):
    READY = "ready"
    REVOKED = "revoked"


class AuditResult(str, Enum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILED = "failed"
