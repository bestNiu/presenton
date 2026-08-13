from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    BidContentStatus,
    BidDocumentStatus,
    BidProjectRole,
    BidProjectStatus,
    BidRequirementStatus,
    ConfidentialityLevel,
    WorkspaceRole,
)
from models.sql.enterprise.bid import (
    BidProjectDocumentModel,
    BidProjectMemberModel,
    BidProjectModel,
    BidProjectProfileModel,
    BidRequirementModel,
    BidStrategyModel,
)
from models.sql.enterprise.workspace import WorkspaceMemberModel
from services.enterprise.audit_service import record_audit_event
from services.enterprise.workspace_service import require_workspace_role


PROJECT_ROLE_GRANTS = {
    BidProjectRole.VIEWER: set(BidProjectRole),
    BidProjectRole.CONTRIBUTOR: {
        BidProjectRole.CONTRIBUTOR,
        BidProjectRole.BID_MANAGER,
    },
    BidProjectRole.REVIEWER: {
        BidProjectRole.REVIEWER,
        BidProjectRole.BID_MANAGER,
    },
    BidProjectRole.BID_MANAGER: {BidProjectRole.BID_MANAGER},
}
STRATEGY_ELEMENTS = (
    "project_assessment",
    "client_concerns",
    "solutions",
    "differentiators",
    "commitments",
    "joint_decisions",
)
REQUIRED_DOCUMENT_GROUPS = (
    ("rfp",),
    ("protocol", "protocol_summary"),
)


def _role_allows(actual: BidProjectRole | str, required: BidProjectRole) -> bool:
    try:
        actual_role = actual if isinstance(actual, BidProjectRole) else BidProjectRole(actual)
    except ValueError:
        return False
    return actual_role in PROJECT_ROLE_GRANTS[required]


async def require_project_role(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    principal: AuthPrincipal,
    required_role: BidProjectRole = BidProjectRole.VIEWER,
) -> tuple[BidProjectModel, BidProjectMemberModel]:
    project = await session.get(BidProjectModel, project_id)
    if project is None or BidProjectStatus(project.status) == BidProjectStatus.ARCHIVED:
        raise HTTPException(status_code=404, detail="Bid project not found")
    await require_workspace_role(
        session,
        workspace_id=project.workspace_id,
        principal=principal,
        required_role=WorkspaceRole.VIEWER,
    )
    member = await session.scalar(
        select(BidProjectMemberModel).where(
            BidProjectMemberModel.project_id == project_id,
            BidProjectMemberModel.user_id == principal.user_id,
        )
    )
    if member is None or not _role_allows(member.role, required_role):
        raise HTTPException(status_code=404, detail="Bid project not found")
    return project, member


async def create_bid_project(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    bid_code: str,
    name: str,
    sponsor_name: str | None,
    drug_name: str | None,
    indication: str | None,
    due_date,
    confidentiality: ConfidentialityLevel,
) -> tuple[BidProjectModel, BidProjectMemberModel]:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    project = BidProjectModel(
        workspace_id=workspace_id,
        created_by=principal.user_id,
        bid_code=bid_code.strip().upper(),
        name=name.strip(),
        sponsor_name=sponsor_name.strip() if sponsor_name else None,
        drug_name=drug_name.strip() if drug_name else None,
        indication=indication.strip() if indication else None,
        due_date=due_date,
        confidentiality=confidentiality,
    )
    member = BidProjectMemberModel(
        project_id=project.id,
        user_id=principal.user_id,
        role=BidProjectRole.BID_MANAGER,
    )
    profile = BidProjectProfileModel(project_id=project.id, updated_by=principal.user_id)
    strategy = BidStrategyModel(project_id=project.id, created_by=principal.user_id)
    session.add_all([project, member, profile, strategy])
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="bid.project_created",
        resource_type="bid_project",
        resource_id=project.id,
        metadata={"bid_code": project.bid_code},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Bid code already exists") from exc
    await session.refresh(project)
    return project, member


async def list_bid_projects(
    session: AsyncSession, *, principal: AuthPrincipal, workspace_id: uuid.UUID
) -> list[tuple[BidProjectModel, BidProjectRole]]:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal
    )
    rows = (
        await session.execute(
            select(BidProjectModel, BidProjectMemberModel.role)
            .join(
                BidProjectMemberModel,
                BidProjectMemberModel.project_id == BidProjectModel.id,
            )
            .where(
                BidProjectModel.workspace_id == workspace_id,
                BidProjectModel.status != BidProjectStatus.ARCHIVED,
                BidProjectMemberModel.user_id == principal.user_id,
            )
            .order_by(BidProjectModel.updated_at.desc())
        )
    ).all()
    return [(project, BidProjectRole(role)) for project, role in rows]


async def upsert_project_member(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    principal: AuthPrincipal,
    user_id: uuid.UUID,
    role: BidProjectRole,
) -> BidProjectMemberModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.BID_MANAGER,
    )
    workspace_member = await session.scalar(
        select(WorkspaceMemberModel.id).where(
            WorkspaceMemberModel.workspace_id == project.workspace_id,
            WorkspaceMemberModel.user_id == user_id,
        )
    )
    if workspace_member is None:
        raise HTTPException(status_code=422, detail="User must be a workspace member")
    member = await session.scalar(
        select(BidProjectMemberModel).where(
            BidProjectMemberModel.project_id == project_id,
            BidProjectMemberModel.user_id == user_id,
        )
    )
    if member is None:
        member = BidProjectMemberModel(project_id=project_id, user_id=user_id, role=role)
    else:
        member.role = role
    session.add(member)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.member_upserted",
        resource_type="bid_project_member",
        resource_id=member.id,
        metadata={"project_id": str(project_id), "user_id": str(user_id), "role": role.value},
    )
    await session.commit()
    await session.refresh(member)
    return member


async def add_project_document(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    principal: AuthPrincipal,
    logical_name: str,
    category: str,
    version_no: int,
    file_ref: str,
    sha256: str | None,
) -> BidProjectDocumentModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.CONTRIBUTOR,
    )
    normalized_name = logical_name.strip()
    normalized_category = category.strip().lower()
    await session.execute(
        update(BidProjectDocumentModel)
        .where(
            BidProjectDocumentModel.project_id == project_id,
            BidProjectDocumentModel.logical_name == normalized_name,
            BidProjectDocumentModel.status == BidDocumentStatus.ACTIVE,
        )
        .values(status=BidDocumentStatus.SUPERSEDED)
    )
    document = BidProjectDocumentModel(
        project_id=project_id,
        logical_name=normalized_name,
        category=normalized_category,
        version_no=version_no,
        file_ref=file_ref.strip(),
        sha256=sha256,
        created_by=principal.user_id,
    )
    if await _fork_confirmed_strategy(session, project_id, principal.user_id):
        project.status = BidProjectStatus.STRATEGY_PENDING
        project.row_version += 1
        session.add(project)
    session.add(document)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.document_registered",
        resource_type="bid_document",
        resource_id=document.id,
        metadata={"project_id": str(project_id), "category": normalized_category},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Document version already exists") from exc
    await session.refresh(document)
    return document


async def update_project_profile(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    principal: AuthPrincipal,
    facts: dict,
    conflicts: list,
    row_version: int,
) -> BidProjectProfileModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.CONTRIBUTOR,
    )
    profile = await session.scalar(
        select(BidProjectProfileModel).where(BidProjectProfileModel.project_id == project_id)
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Bid profile not found")
    if profile.row_version != row_version:
        raise HTTPException(status_code=409, detail="Bid profile was updated; reload and retry")
    profile.facts = facts
    profile.conflicts = conflicts
    profile.status = BidContentStatus.DRAFT
    profile.row_version += 1
    profile.updated_by = principal.user_id
    await _fork_confirmed_strategy(session, project_id, principal.user_id)
    project.status = BidProjectStatus.UNDERSTANDING
    session.add_all([profile, project])
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.profile_updated",
        resource_type="bid_profile",
        resource_id=profile.id,
        metadata={"project_id": str(project_id), "row_version": profile.row_version},
    )
    await session.commit()
    await session.refresh(profile)
    return profile


async def confirm_project_profile(
    session: AsyncSession, *, project_id: uuid.UUID, principal: AuthPrincipal
) -> BidProjectProfileModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.REVIEWER,
    )
    profile = await session.scalar(
        select(BidProjectProfileModel).where(BidProjectProfileModel.project_id == project_id)
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Bid profile not found")
    if profile.conflicts:
        raise HTTPException(status_code=409, detail="Resolve profile conflicts before confirmation")
    if not profile.facts:
        raise HTTPException(status_code=422, detail="Profile facts are required")
    profile.status = BidContentStatus.CONFIRMED
    profile.row_version += 1
    project.status = BidProjectStatus.STRATEGY_PENDING
    session.add_all([profile, project])
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.profile_confirmed",
        resource_type="bid_profile",
        resource_id=profile.id,
    )
    await session.commit()
    await session.refresh(profile)
    return profile


async def create_requirement(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    principal: AuthPrincipal,
    values: dict,
) -> BidRequirementModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.CONTRIBUTOR,
    )
    requirement = BidRequirementModel(project_id=project_id, **values)
    if await _fork_confirmed_strategy(session, project_id, principal.user_id):
        project.status = BidProjectStatus.STRATEGY_PENDING
        project.row_version += 1
        session.add(project)
    session.add(requirement)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.requirement_created",
        resource_type="bid_requirement",
        resource_id=requirement.id,
        metadata={"project_id": str(project_id), "mandatory": requirement.mandatory},
    )
    await session.commit()
    await session.refresh(requirement)
    return requirement


async def update_requirement(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    principal: AuthPrincipal,
    response: str | None,
    status: BidRequirementStatus,
    owner_department: str | None,
    target_module: str | None,
    row_version: int,
) -> BidRequirementModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.CONTRIBUTOR,
    )
    requirement = await session.get(BidRequirementModel, requirement_id)
    if requirement is None or requirement.project_id != project_id:
        raise HTTPException(status_code=404, detail="Bid requirement not found")
    if requirement.row_version != row_version:
        raise HTTPException(status_code=409, detail="Requirement was updated; reload and retry")
    if status in {BidRequirementStatus.ANSWERED, BidRequirementStatus.VERIFIED} and not (response or "").strip():
        raise HTTPException(status_code=422, detail="Answered requirements need a response")
    requirement.response = response.strip() if response else None
    requirement.status = status
    requirement.owner_department = owner_department
    requirement.target_module = target_module
    requirement.row_version += 1
    if await _fork_confirmed_strategy(session, project_id, principal.user_id):
        project.status = BidProjectStatus.STRATEGY_PENDING
        project.row_version += 1
        session.add(project)
    session.add(requirement)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.requirement_updated",
        resource_type="bid_requirement",
        resource_id=requirement.id,
        metadata={"status": status.value, "row_version": requirement.row_version},
    )
    await session.commit()
    await session.refresh(requirement)
    return requirement


async def update_strategy(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    principal: AuthPrincipal,
    elements: dict,
    row_version: int,
) -> BidStrategyModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.CONTRIBUTOR,
    )
    strategy = await _current_strategy(session, project_id)
    if strategy.row_version != row_version:
        raise HTTPException(status_code=409, detail="Strategy was updated; reload and retry")
    if BidContentStatus(strategy.status) == BidContentStatus.CONFIRMED:
        raise HTTPException(status_code=409, detail="Confirmed strategy is immutable")
    strategy.elements = elements
    strategy.row_version += 1
    session.add(strategy)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.strategy_updated",
        resource_type="bid_strategy",
        resource_id=strategy.id,
        metadata={"row_version": strategy.row_version},
    )
    await session.commit()
    await session.refresh(strategy)
    return strategy


async def _current_strategy(session: AsyncSession, project_id: uuid.UUID) -> BidStrategyModel:
    strategy = await session.scalar(
        select(BidStrategyModel)
        .where(BidStrategyModel.project_id == project_id)
        .order_by(BidStrategyModel.version_no.desc())
        .limit(1)
    )
    if strategy is None:
        raise HTTPException(status_code=404, detail="Bid strategy not found")
    return strategy


async def _fork_confirmed_strategy(
    session: AsyncSession, project_id: uuid.UUID, actor_id: uuid.UUID
) -> bool:
    """Create a new draft when upstream inputs change after strategy confirmation."""
    strategy = await _current_strategy(session, project_id)
    if BidContentStatus(strategy.status) != BidContentStatus.CONFIRMED:
        return False
    session.add(
        BidStrategyModel(
            project_id=project_id,
            version_no=strategy.version_no + 1,
            elements=dict(strategy.elements),
            created_by=actor_id,
        )
    )
    return True


async def _strategy_blockers(
    session: AsyncSession,
    project_id: uuid.UUID,
    profile: BidProjectProfileModel,
    strategy: BidStrategyModel,
) -> list[str]:
    blockers: list[str] = []
    if BidContentStatus(profile.status) != BidContentStatus.CONFIRMED:
        blockers.append("项目画像尚未确认")
    if profile.conflicts:
        blockers.append("项目画像仍有未解决冲突")
    document_categories = set(
        (
            await session.scalars(
                select(BidProjectDocumentModel.category).where(
                    BidProjectDocumentModel.project_id == project_id,
                    BidProjectDocumentModel.status == BidDocumentStatus.ACTIVE,
                )
            )
        ).all()
    )
    for group in REQUIRED_DOCUMENT_GROUPS:
        if not document_categories.intersection(group):
            blockers.append(f"缺少必传资料：{'/'.join(group)}")
    missing_elements = [
        element for element in STRATEGY_ELEMENTS if not strategy.elements.get(element)
    ]
    if missing_elements:
        blockers.append(f"策略六要素未完成：{', '.join(missing_elements)}")
    mandatory_open = await session.scalar(
        select(func.count(BidRequirementModel.id)).where(
            BidRequirementModel.project_id == project_id,
            BidRequirementModel.mandatory.is_(True),
            BidRequirementModel.status.not_in(
                [BidRequirementStatus.ANSWERED, BidRequirementStatus.VERIFIED]
            ),
        )
    )
    if mandatory_open:
        blockers.append(f"仍有 {mandatory_open} 个必答需求未覆盖")
    return blockers


async def confirm_strategy(
    session: AsyncSession, *, project_id: uuid.UUID, principal: AuthPrincipal
) -> BidStrategyModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.BID_MANAGER,
    )
    profile = await session.scalar(
        select(BidProjectProfileModel).where(BidProjectProfileModel.project_id == project_id)
    )
    strategy = await _current_strategy(session, project_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Bid profile not found")
    blockers = await _strategy_blockers(session, project_id, profile, strategy)
    if blockers:
        raise HTTPException(status_code=409, detail={"message": "Strategy gate is blocked", "blockers": blockers})
    strategy.status = BidContentStatus.CONFIRMED
    strategy.confirmed_by = principal.user_id
    strategy.confirmed_at = datetime.now(timezone.utc)
    strategy.row_version += 1
    project.status = BidProjectStatus.STRATEGY_CONFIRMED
    project.row_version += 1
    session.add_all([strategy, project])
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.strategy_confirmed",
        resource_type="bid_strategy",
        resource_id=strategy.id,
        metadata={"project_id": str(project_id), "version": strategy.version_no},
    )
    await session.commit()
    await session.refresh(strategy)
    return strategy


async def get_project_dashboard(
    session: AsyncSession, *, project_id: uuid.UUID, principal: AuthPrincipal
) -> dict:
    project, member = await require_project_role(
        session, project_id=project_id, principal=principal
    )
    profile = await session.scalar(
        select(BidProjectProfileModel).where(BidProjectProfileModel.project_id == project_id)
    )
    strategy = await _current_strategy(session, project_id)
    documents = list(
        (
            await session.scalars(
                select(BidProjectDocumentModel)
                .where(BidProjectDocumentModel.project_id == project_id)
                .order_by(BidProjectDocumentModel.created_at.desc())
            )
        ).all()
    )
    requirements = list(
        (
            await session.scalars(
                select(BidRequirementModel)
                .where(BidRequirementModel.project_id == project_id)
                .order_by(BidRequirementModel.created_at.asc())
            )
        ).all()
    )
    mandatory = [item for item in requirements if item.mandatory]
    covered = [
        item
        for item in mandatory
        if BidRequirementStatus(item.status)
        in {BidRequirementStatus.ANSWERED, BidRequirementStatus.VERIFIED}
    ]
    coverage = 100.0 if not mandatory else round(len(covered) / len(mandatory) * 100, 1)
    blockers = await _strategy_blockers(session, project_id, profile, strategy)
    return {
        "project": project,
        "current_user_role": BidProjectRole(member.role),
        "profile": profile,
        "documents": documents,
        "requirements": requirements,
        "strategy": strategy,
        "mandatory_requirement_coverage": coverage,
        "strategy_blockers": blockers,
    }
