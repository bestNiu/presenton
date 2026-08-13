from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    BidCommitmentStatus,
    BidContentStatus,
    BidGateStatus,
    BidGateType,
    BidIssueStatus,
    BidModuleStatus,
    BidModuleType,
    BidProjectRole,
    BidRequirementStatus,
)
from models.sql.enterprise.bid import (
    BidCommitmentModel,
    BidProfessionalModuleModel,
    BidRequirementModel,
    BidReviewGateModel,
    BidReviewIssueModel,
    BidStrategyModel,
)
from services.enterprise.audit_service import record_audit_event
from services.enterprise.bid_project_service import require_project_role


async def initialize_modules(session: AsyncSession, *, project_id: uuid.UUID, principal: AuthPrincipal):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.BID_MANAGER)
    strategy = await session.scalar(select(BidStrategyModel).where(BidStrategyModel.project_id == project_id).order_by(BidStrategyModel.version_no.desc()).limit(1))
    if strategy is None or BidContentStatus(strategy.status) != BidContentStatus.CONFIRMED:
        raise HTTPException(status_code=409, detail="Confirm strategy before initializing modules")
    existing = list((await session.scalars(select(BidProfessionalModuleModel).where(BidProfessionalModuleModel.project_id == project_id))).all())
    if not existing:
        snapshot = {"strategy_id": str(strategy.id), "strategy_version": strategy.version_no}
        existing = [BidProfessionalModuleModel(project_id=project_id, module_type=kind, input_snapshot=snapshot, created_by=principal.user_id, updated_by=principal.user_id) for kind in BidModuleType]
        session.add_all(existing)
        session.add_all([BidReviewGateModel(project_id=project_id, gate_type=BidGateType.GATE_1), BidReviewGateModel(project_id=project_id, gate_type=BidGateType.GATE_2)])
        record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action="bid.modules_initialized", resource_type="bid_project", resource_id=project_id)
        await session.commit()
    return await list_collaboration(session, project_id=project_id, principal=principal)


async def update_module(session: AsyncSession, *, project_id: uuid.UUID, module_id: uuid.UUID, principal: AuthPrincipal, content: dict, row_version: int):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.CONTRIBUTOR)
    module = await session.get(BidProfessionalModuleModel, module_id)
    if module is None or module.project_id != project_id:
        raise HTTPException(status_code=404, detail="Professional module not found")
    if module.row_version != row_version:
        raise HTTPException(status_code=409, detail="Module was updated; reload and retry")
    if BidModuleStatus(module.status) in {BidModuleStatus.IN_REVIEW, BidModuleStatus.APPROVED}:
        raise HTTPException(status_code=409, detail="Module is not editable in current status")
    module.content = content
    module.status = BidModuleStatus.DRAFT
    module.updated_by = principal.user_id
    module.row_version += 1
    session.add(module)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action="bid.module_updated", resource_type="bid_module", resource_id=module.id)
    await session.commit(); await session.refresh(module)
    return module


async def submit_module(session: AsyncSession, *, project_id: uuid.UUID, module_id: uuid.UUID, principal: AuthPrincipal):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.CONTRIBUTOR)
    module = await session.get(BidProfessionalModuleModel, module_id)
    if module is None or module.project_id != project_id:
        raise HTTPException(status_code=404, detail="Professional module not found")
    if BidModuleStatus(module.status) not in {BidModuleStatus.DRAFT, BidModuleStatus.REJECTED} or not module.content:
        raise HTTPException(status_code=409, detail="Only non-empty draft modules can be submitted")
    module.status = BidModuleStatus.IN_REVIEW; module.row_version += 1; session.add(module)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action="bid.module_submitted", resource_type="bid_module", resource_id=module.id)
    await session.commit(); await session.refresh(module)
    return module


async def review_module(session: AsyncSession, *, project_id: uuid.UUID, module_id: uuid.UUID, principal: AuthPrincipal, action: str, comment: str | None):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.REVIEWER)
    module = await session.get(BidProfessionalModuleModel, module_id)
    if module is None or module.project_id != project_id:
        raise HTTPException(status_code=404, detail="Professional module not found")
    if BidModuleStatus(module.status) != BidModuleStatus.IN_REVIEW:
        raise HTTPException(status_code=409, detail="Module is not in review")
    if module.updated_by == principal.user_id:
        raise HTTPException(status_code=409, detail="Module author cannot review own content")
    if action == "approve" and not module.content.get("sources"):
        raise HTTPException(status_code=422, detail="Approved module content requires sources")
    module.status = BidModuleStatus.APPROVED if action == "approve" else BidModuleStatus.REJECTED
    module.reviewed_by = principal.user_id; module.review_comment = comment; module.row_version += 1; session.add(module)
    audit_action = "bid.module_approved" if action == "approve" else "bid.module_rejected"
    record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action=audit_action, resource_type="bid_module", resource_id=module.id)
    await session.commit(); await session.refresh(module)
    return module


async def create_commitment(session: AsyncSession, *, project_id: uuid.UUID, principal: AuthPrincipal, values: dict):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.CONTRIBUTOR)
    item = BidCommitmentModel(project_id=project_id, proposed_by=principal.user_id, **values); session.add(item)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action="bid.commitment_created", resource_type="bid_commitment", resource_id=item.id)
    await session.commit(); await session.refresh(item); return item


async def act_on_commitment(session: AsyncSession, *, project_id: uuid.UUID, commitment_id: uuid.UUID, principal: AuthPrincipal, action: str, comment: str | None):
    required = BidProjectRole.CONTRIBUTOR if action == "submit" else BidProjectRole.BID_MANAGER
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=required)
    item = await session.get(BidCommitmentModel, commitment_id)
    if item is None or item.project_id != project_id: raise HTTPException(status_code=404, detail="Commitment not found")
    current = BidCommitmentStatus(item.status)
    allowed = {"submit": ({BidCommitmentStatus.CANDIDATE}, BidCommitmentStatus.PENDING), "approve": ({BidCommitmentStatus.PENDING}, BidCommitmentStatus.APPROVED), "reject": ({BidCommitmentStatus.PENDING}, BidCommitmentStatus.REJECTED), "revoke": ({BidCommitmentStatus.APPROVED}, BidCommitmentStatus.REVOKED)}
    sources, target = allowed[action]
    if current not in sources: raise HTTPException(status_code=409, detail="Invalid commitment transition")
    if action == "approve" and not item.evidence_ref: raise HTTPException(status_code=422, detail="Commitment evidence is required")
    if action == "approve" and item.proposed_by == principal.user_id:
        raise HTTPException(status_code=409, detail="Commitment proposer cannot approve own commitment")
    item.status = target; item.row_version += 1
    if action != "submit": item.decided_by = principal.user_id; item.decision_comment = comment
    session.add(item); record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action=f"bid.commitment_{action}", resource_type="bid_commitment", resource_id=item.id)
    await session.commit(); await session.refresh(item); return item


async def act_on_gate(session: AsyncSession, *, project_id: uuid.UUID, gate_type: BidGateType, principal: AuthPrincipal, action: str):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.REVIEWER)
    gate = await session.scalar(select(BidReviewGateModel).where(BidReviewGateModel.project_id == project_id, BidReviewGateModel.gate_type == gate_type))
    if gate is None: raise HTTPException(status_code=404, detail="Review gate not found")
    blockers = await gate_blockers(session, project_id, gate_type)
    now = datetime.now(timezone.utc)
    if action == "open":
        if gate_type == BidGateType.GATE_2:
            gate1 = await session.scalar(select(BidReviewGateModel).where(BidReviewGateModel.project_id == project_id, BidReviewGateModel.gate_type == BidGateType.GATE_1))
            if gate1 is None or BidGateStatus(gate1.status) != BidGateStatus.PASSED: blockers.append("Gate 1 尚未通过")
        gate.status = BidGateStatus.BLOCKED if blockers else BidGateStatus.OPEN; gate.opened_by = principal.user_id; gate.opened_at = now
    else:
        if blockers: raise HTTPException(status_code=409, detail={"message": "Gate is blocked", "blockers": blockers})
        gate.status = BidGateStatus.PASSED; gate.passed_by = principal.user_id; gate.passed_at = now
    session.add(gate); record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action=f"bid.{gate_type.value}_{action}", resource_type="bid_review_gate", resource_id=gate.id, metadata={"blockers": blockers})
    await session.commit(); await session.refresh(gate); return gate


async def gate_blockers(session: AsyncSession, project_id: uuid.UUID, gate_type: BidGateType) -> list[str]:
    blockers = []
    if gate_type == BidGateType.GATE_1:
        modules = list((await session.scalars(select(BidProfessionalModuleModel).where(BidProfessionalModuleModel.project_id == project_id))).all())
        missing = [kind.value for kind in BidModuleType if not any(m.module_type == kind and m.status == BidModuleStatus.APPROVED for m in modules)]
        if missing: blockers.append(f"专业模块未批准：{', '.join(missing)}")
    else:
        open_required = await session.scalar(select(func.count(BidRequirementModel.id)).where(BidRequirementModel.project_id == project_id, BidRequirementModel.mandatory.is_(True), BidRequirementModel.status.not_in([BidRequirementStatus.ANSWERED, BidRequirementStatus.VERIFIED])))
        if open_required: blockers.append(f"仍有 {open_required} 个必答需求未覆盖")
        undecided = await session.scalar(select(func.count(BidCommitmentModel.id)).where(BidCommitmentModel.project_id == project_id, BidCommitmentModel.status.in_([BidCommitmentStatus.CANDIDATE, BidCommitmentStatus.PENDING])))
        if undecided: blockers.append(f"仍有 {undecided} 个承诺未完成审批")
    gate = await session.scalar(select(BidReviewGateModel).where(BidReviewGateModel.project_id == project_id, BidReviewGateModel.gate_type == gate_type))
    if gate:
        open_issues = await session.scalar(select(func.count(BidReviewIssueModel.id)).where(BidReviewIssueModel.gate_id == gate.id, BidReviewIssueModel.status == BidIssueStatus.OPEN, BidReviewIssueModel.severity == "blocking"))
        if open_issues: blockers.append(f"仍有 {open_issues} 个阻断问题未关闭")
    return blockers


async def create_gate_issue(session: AsyncSession, *, project_id: uuid.UUID, gate_type: BidGateType, principal: AuthPrincipal, values: dict):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.REVIEWER)
    gate = await session.scalar(select(BidReviewGateModel).where(BidReviewGateModel.project_id == project_id, BidReviewGateModel.gate_type == gate_type))
    if gate is None: raise HTTPException(status_code=404, detail="Review gate not found")
    issue = BidReviewIssueModel(gate_id=gate.id, created_by=principal.user_id, **values); session.add(issue)
    gate.status = BidGateStatus.BLOCKED; session.add(gate)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action="bid.gate_issue_created", resource_type="bid_review_issue", resource_id=issue.id, metadata={"gate_type": gate_type.value})
    await session.commit(); await session.refresh(issue); return issue


async def resolve_gate_issue(session: AsyncSession, *, project_id: uuid.UUID, issue_id: uuid.UUID, principal: AuthPrincipal, resolution: str):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.REVIEWER)
    issue = await session.get(BidReviewIssueModel, issue_id)
    gate = await session.get(BidReviewGateModel, issue.gate_id) if issue else None
    if issue is None or gate is None or gate.project_id != project_id: raise HTTPException(status_code=404, detail="Review issue not found")
    issue.status = BidIssueStatus.RESOLVED; issue.resolved_by = principal.user_id; issue.resolution = resolution; session.add(issue)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action="bid.gate_issue_resolved", resource_type="bid_review_issue", resource_id=issue.id)
    await session.commit(); await session.refresh(issue); return issue


async def list_collaboration(session: AsyncSession, *, project_id: uuid.UUID, principal: AuthPrincipal):
    await require_project_role(session, project_id=project_id, principal=principal)
    modules = list((await session.scalars(select(BidProfessionalModuleModel).where(BidProfessionalModuleModel.project_id == project_id).order_by(BidProfessionalModuleModel.module_type))).all())
    commitments = list((await session.scalars(select(BidCommitmentModel).where(BidCommitmentModel.project_id == project_id).order_by(BidCommitmentModel.created_at))).all())
    gates = list((await session.scalars(select(BidReviewGateModel).where(BidReviewGateModel.project_id == project_id).order_by(BidReviewGateModel.gate_type))).all())
    issues = list((await session.scalars(select(BidReviewIssueModel).where(BidReviewIssueModel.gate_id.in_([g.id for g in gates])))).all()) if gates else []
    return {"modules": modules, "commitments": commitments, "gates": [{"gate": gate, "issues": [i for i in issues if i.gate_id == gate.id]} for gate in gates]}
