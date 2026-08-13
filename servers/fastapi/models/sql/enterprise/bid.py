from datetime import date, datetime
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from domains.platform.enums import (
    BidCommitmentStatus,
    BidContentStatus,
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
)
from utils.datetime_utils import get_current_utc_datetime


class BidProjectModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "bid_code", name="uq_bid_project_code"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    workspace_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    created_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True),
    )
    bid_code: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    name: str = Field(sa_column=Column(String(300), nullable=False))
    sponsor_name: str | None = Field(default=None, sa_column=Column(String(300)))
    drug_name: str | None = Field(default=None, sa_column=Column(String(300)))
    indication: str | None = Field(default=None, sa_column=Column(String(300)))
    due_date: date | None = Field(default=None, sa_column=Column(Date))
    confidentiality: ConfidentialityLevel = Field(
        default=ConfidentialityLevel.L3,
        sa_column=Column(String(8), nullable=False),
    )
    status: BidProjectStatus = Field(
        default=BidProjectStatus.UNDERSTANDING,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    row_version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=get_current_utc_datetime,
            onupdate=get_current_utc_datetime,
        )
    )


class BidProjectMemberModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_bid_project_member"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    )
    role: BidProjectRole = Field(
        default=BidProjectRole.VIEWER,
        sa_column=Column(String(32), nullable=False),
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime)
    )


class BidProjectDocumentModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_project_documents"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "logical_name", "version_no", name="uq_bid_document_version"
        ),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    logical_name: str = Field(sa_column=Column(String(300), nullable=False))
    category: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    version_no: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    file_ref: str = Field(sa_column=Column(String(2000), nullable=False))
    sha256: str | None = Field(default=None, sa_column=Column(String(64), index=True))
    status: BidDocumentStatus = Field(
        default=BidDocumentStatus.ACTIVE,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    created_by: uuid.UUID | None = Field(
        default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"))
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime)
    )


class BidProjectProfileModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_project_profiles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_bid_project_profile"),)

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    schema_version: str = Field(default="1.0", sa_column=Column(String(32)))
    facts: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    conflicts: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: BidContentStatus = Field(
        default=BidContentStatus.DRAFT,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    row_version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    updated_by: uuid.UUID | None = Field(
        default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"))
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=get_current_utc_datetime,
            onupdate=get_current_utc_datetime,
        )
    )


class BidRequirementModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_requirements"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    category: str = Field(sa_column=Column(String(100), nullable=False, index=True))
    original_text: str = Field(sa_column=Column(Text, nullable=False))
    mandatory: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))
    score: float | None = Field(default=None, sa_column=Column(Float))
    source_ref: str | None = Field(default=None, sa_column=Column(String(1000)))
    owner_department: str | None = Field(default=None, sa_column=Column(String(200)))
    target_module: str | None = Field(default=None, sa_column=Column(String(100)))
    response: str | None = Field(default=None, sa_column=Column(Text))
    status: BidRequirementStatus = Field(
        default=BidRequirementStatus.OPEN,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    row_version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=get_current_utc_datetime,
            onupdate=get_current_utc_datetime,
        )
    )


class BidStrategyModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_strategies"
    __table_args__ = (
        UniqueConstraint("project_id", "version_no", name="uq_bid_strategy_version"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    version_no: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    elements: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: BidContentStatus = Field(
        default=BidContentStatus.DRAFT,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    row_version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    created_by: uuid.UUID | None = Field(
        default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"))
    )
    confirmed_by: uuid.UUID | None = Field(
        default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"))
    )
    confirmed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=get_current_utc_datetime,
            onupdate=get_current_utc_datetime,
        )
    )


class BidProfessionalModuleModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_professional_modules"
    __table_args__ = (
        UniqueConstraint("project_id", "module_type", "version_no", name="uq_bid_module_version"),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"), nullable=False, index=True))
    module_type: BidModuleType = Field(sa_column=Column(String(32), nullable=False, index=True))
    version_no: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    input_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    content: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: BidModuleStatus = Field(default=BidModuleStatus.DRAFT, sa_column=Column(String(32), nullable=False, index=True))
    row_version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    updated_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    reviewed_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    review_comment: str | None = Field(default=None, sa_column=Column(String(2000)))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class BidCommitmentModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_commitments"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"), nullable=False, index=True))
    content: str = Field(sa_column=Column(Text, nullable=False))
    commitment_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    conditions: str | None = Field(default=None, sa_column=Column(Text))
    evidence_ref: str | None = Field(default=None, sa_column=Column(String(1000)))
    risk_level: str = Field(default="medium", sa_column=Column(String(16), nullable=False))
    status: BidCommitmentStatus = Field(default=BidCommitmentStatus.CANDIDATE, sa_column=Column(String(32), nullable=False, index=True))
    row_version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    proposed_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    decided_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    decision_comment: str | None = Field(default=None, sa_column=Column(String(2000)))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class BidReviewGateModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_review_gates"
    __table_args__ = (UniqueConstraint("project_id", "gate_type", name="uq_bid_review_gate"),)

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"), nullable=False, index=True))
    gate_type: BidGateType = Field(sa_column=Column(String(32), nullable=False, index=True))
    status: BidGateStatus = Field(default=BidGateStatus.LOCKED, sa_column=Column(String(32), nullable=False, index=True))
    opened_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    passed_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    opened_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    passed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class BidReviewIssueModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_review_issues"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    gate_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_bid_review_gates.id", ondelete="CASCADE"), nullable=False, index=True))
    title: str = Field(sa_column=Column(String(300), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text))
    severity: str = Field(default="blocking", sa_column=Column(String(32), nullable=False, index=True))
    status: BidIssueStatus = Field(default=BidIssueStatus.OPEN, sa_column=Column(String(32), nullable=False, index=True))
    owner_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    resolved_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    resolution: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class BidPresentationReleaseModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_presentation_releases"
    __table_args__ = (UniqueConstraint("project_id", "release_type", "version_no", name="uq_bid_release_version"),)

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    project_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_bid_projects.id", ondelete="CASCADE"), nullable=False, index=True))
    presentation_entry_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_presentation_entries.id", ondelete="RESTRICT"), nullable=False, index=True))
    template_publication_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_template_publications.id", ondelete="RESTRICT"), nullable=False, index=True))
    release_type: str = Field(default="management-summary", sa_column=Column(String(64), nullable=False, index=True))
    version_no: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    manifest: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    manifest_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    slide_snapshot_hash: str = Field(sa_column=Column(String(64), nullable=False))
    status: BidReleaseStatus = Field(default=BidReleaseStatus.DRAFT, sa_column=Column(String(32), nullable=False, index=True))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    frozen_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    frozen_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime, onupdate=get_current_utc_datetime))


class BidDeliveryArtifactModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_delivery_artifacts"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    release_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_bid_presentation_releases.id", ondelete="CASCADE"), nullable=False, index=True))
    derived_presentation_id: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("presentations.id", ondelete="SET NULL"), index=True))
    format: BidDeliveryFormat = Field(sa_column=Column(String(16), nullable=False, index=True))
    watermark_text: str = Field(sa_column=Column(String(300), nullable=False))
    file_path: str = Field(sa_column=Column(String(2000), nullable=False))
    object_key: str | None = Field(default=None, sa_column=Column(String(1000), index=True))
    file_name: str = Field(sa_column=Column(String(500), nullable=False))
    sha256: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    size_bytes: int = Field(sa_column=Column(Integer, nullable=False))
    status: BidDeliveryStatus = Field(default=BidDeliveryStatus.READY, sa_column=Column(String(32), nullable=False, index=True))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class BidDownloadGrantModel(SQLModel, table=True):
    __tablename__ = "enterprise_bid_download_grants"

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    artifact_id: uuid.UUID = Field(sa_column=Column(ForeignKey("enterprise_bid_delivery_artifacts.id", ondelete="CASCADE"), nullable=False, index=True))
    token_hash: str = Field(sa_column=Column(String(64), nullable=False, unique=True, index=True))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    max_downloads: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    download_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    created_by: uuid.UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL")))
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True), default=get_current_utc_datetime))
    last_downloaded_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
