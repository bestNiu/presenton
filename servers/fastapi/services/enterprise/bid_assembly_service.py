from datetime import datetime, timezone
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    BidCommitmentStatus, BidGateStatus, BidGateType, BidModuleStatus,
    BidModuleType, BidProjectRole, BidReleaseStatus, PresentationCreationMode,
    TemplatePublicationStatus, TemplateScopeType,
)
from models.sql.enterprise.bid import (
    BidCommitmentModel, BidPresentationReleaseModel, BidProfessionalModuleModel,
    BidReviewGateModel, BidStrategyModel,
)
from models.sql.enterprise.template_publication import TemplatePublicationModel
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.slide import SlideModel
from models.sql.template_v2 import TemplateV2
from services.enterprise.audit_service import record_audit_event
from services.enterprise.bid_project_service import require_project_role
from services.enterprise.presentation_workspace_service import attach_presentation_to_workspace
from services.enterprise.scene_service import get_active_scene


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text_slide(slide_id: str, title: str, body: str) -> dict:
    return {"id": slide_id, "description": title, "background": "#FFFFFF", "components": [], "elements": [
        {"type": "text", "name": "Title", "decorative": False, "position": {"x": 80, "y": 70}, "size": {"width": 1120, "height": 100}, "runs": [{"text": title, "font": {"size": 34, "family": "Arial", "weight": 700}}]},
        {"type": "text", "name": "Body", "decorative": False, "position": {"x": 90, "y": 200}, "size": {"width": 1100, "height": 430}, "runs": [{"text": body, "font": {"size": 20, "family": "Arial"}}]},
    ]}


async def assemble_management_summary(session: AsyncSession, *, project_id: uuid.UUID, principal: AuthPrincipal, template_publication_id: uuid.UUID, release_type: str):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.BID_MANAGER)
    gate2 = await session.scalar(select(BidReviewGateModel).where(BidReviewGateModel.project_id == project_id, BidReviewGateModel.gate_type == BidGateType.GATE_2))
    if gate2 is None or BidGateStatus(gate2.status) != BidGateStatus.PASSED:
        raise HTTPException(status_code=409, detail="Gate 2 must pass before assembly")
    publication = await session.scalar(select(TemplatePublicationModel).where(
        TemplatePublicationModel.id == template_publication_id,
        TemplatePublicationModel.status == TemplatePublicationStatus.PUBLISHED,
        or_(TemplatePublicationModel.scope_type == TemplateScopeType.ENTERPRISE, TemplatePublicationModel.workspace_id == project.workspace_id),
        or_(TemplatePublicationModel.scene_type.is_(None), TemplatePublicationModel.scene_type == "bid"),
    ))
    if publication is None: raise HTTPException(status_code=404, detail="Published bid template not found")
    template = await session.scalar(select(TemplateV2).execution_options(skip_owner_scope=True).where(TemplateV2.id == publication.template_id))
    if template is None: raise HTTPException(status_code=404, detail="Template not found")
    modules = list((await session.scalars(select(BidProfessionalModuleModel).where(BidProfessionalModuleModel.project_id == project_id, BidProfessionalModuleModel.status == BidModuleStatus.APPROVED).order_by(BidProfessionalModuleModel.module_type))).all())
    if {BidModuleType(item.module_type) for item in modules} != set(BidModuleType): raise HTTPException(status_code=409, detail="All professional modules must be approved")
    commitments = list((await session.scalars(select(BidCommitmentModel).where(BidCommitmentModel.project_id == project_id, BidCommitmentModel.status == BidCommitmentStatus.APPROVED))).all())
    strategy = await session.scalar(select(BidStrategyModel).where(BidStrategyModel.project_id == project_id, BidStrategyModel.status == "confirmed").order_by(BidStrategyModel.version_no.desc()).limit(1))
    if strategy is None: raise HTTPException(status_code=409, detail="Confirmed strategy not found")
    scene = await get_active_scene(session, "bid")
    version_no = (await session.scalar(select(func.max(BidPresentationReleaseModel.version_no)).where(BidPresentationReleaseModel.project_id == project_id, BidPresentationReleaseModel.release_type == release_type)) or 0) + 1
    slide_specs = [{"order": 1, "layout_tag": "cover", "content_ref": f"bid_project:{project.id}"}]
    slide_specs += [{"order": index + 2, "layout_tag": "professional-module", "content_ref": f"bid_module:{module.id}:v{module.version_no}"} for index, module in enumerate(modules)]
    if commitments: slide_specs.append({"order": len(slide_specs) + 1, "layout_tag": "commitments", "content_ref": "approved_commitments"})
    manifest = {"manifest_version": "1.0", "workspace_id": str(project.workspace_id), "project_id": str(project.id), "scene": {"type": "bid", "version": scene.version}, "release_type": release_type, "template": {"publication_id": str(publication.id), "version": publication.version}, "strategy": {"id": str(strategy.id), "version": strategy.version_no}, "sources": [{"type": "module_content", "id": str(item.id), "version": item.version_no, "status": "approved", "content_hash": _canonical_hash(item.content)} for item in modules] + [{"type": "commitment", "id": str(item.id), "status": "approved", "content_hash": _canonical_hash(item.content)} for item in commitments], "slides": slide_specs, "quality_policy": "bid-gates-v1"}
    presentation = PresentationModel(owner_id=principal.user_id, version=PresentationVersion.V2_STANDARD, content=project.name, n_slides=len(slide_specs), language="Chinese", title=f"{project.name}｜管理层摘要 v{version_no}", layout=template.layouts, include_title_slide=True)
    session.add(presentation)
    entry = await attach_presentation_to_workspace(session, principal=principal, workspace_id=project.workspace_id, presentation=presentation, folder_id=None, scene_type="bid", creation_mode=PresentationCreationMode.TEMPLATE, allow_dedicated_scene=True)
    manifest["presentation_id"] = str(presentation.id)
    manifest["presentation_entry_id"] = str(entry.id)
    slide_payloads = [(project.name, f"{project.sponsor_name or ''}\n{project.drug_name or ''} {project.indication or ''}")]
    slide_payloads += [(f"{BidModuleType(item.module_type).value} 专业方案", str(item.content.get("summary", ""))) for item in modules]
    if commitments: slide_payloads.append(("关键服务承诺", "\n".join(f"• {item.content}" for item in commitments)))
    slides = [SlideModel(owner_id=principal.user_id, presentation=presentation.id, layout_group="bid-summary", layout=f"bid-summary-{index}", index=index, content={}, speaker_note="", ui=_text_slide(f"bid-summary-{index}", title, body)) for index, (title, body) in enumerate(slide_payloads)]
    session.add_all(slides)
    snapshot_hash = _canonical_hash([slide.ui for slide in slides])
    release = BidPresentationReleaseModel(project_id=project_id, presentation_entry_id=entry.id, template_publication_id=publication.id, release_type=release_type, version_no=version_no, manifest=manifest, manifest_hash=_canonical_hash(manifest), slide_snapshot_hash=snapshot_hash, created_by=principal.user_id)
    session.add(release); record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action="bid.release_assembled", resource_type="bid_release", resource_id=release.id, metadata={"manifest_hash": release.manifest_hash, "version": version_no})
    await session.commit(); await session.refresh(release); return release


async def freeze_release(session: AsyncSession, *, project_id: uuid.UUID, release_id: uuid.UUID, principal: AuthPrincipal):
    project, _ = await require_project_role(session, project_id=project_id, principal=principal, required_role=BidProjectRole.BID_MANAGER)
    release = await session.get(BidPresentationReleaseModel, release_id)
    if release is None or release.project_id != project_id: raise HTTPException(status_code=404, detail="Release not found")
    if BidReleaseStatus(release.status) != BidReleaseStatus.DRAFT: raise HTTPException(status_code=409, detail="Only draft release can be frozen")
    gate3 = await session.scalar(select(BidReviewGateModel).where(BidReviewGateModel.project_id == project_id, BidReviewGateModel.gate_type == BidGateType.GATE_3))
    if gate3 is None or BidGateStatus(gate3.status) != BidGateStatus.PASSED: raise HTTPException(status_code=409, detail="Gate 3 must pass before freeze")
    if _canonical_hash(release.manifest) != release.manifest_hash: raise HTTPException(status_code=409, detail="Release manifest integrity check failed")
    entry = await session.get(PresentationEntryModel, release.presentation_entry_id)
    if entry is None: raise HTTPException(status_code=409, detail="Release presentation entry is missing")
    slides = list((await session.scalars(select(SlideModel).execution_options(skip_owner_scope=True).where(SlideModel.presentation == entry.presentation_id).order_by(SlideModel.index))).all())
    if _canonical_hash([slide.ui for slide in slides]) != release.slide_snapshot_hash:
        raise HTTPException(status_code=409, detail="Release slide snapshot changed; assemble a new version")
    release.status = BidReleaseStatus.FROZEN; release.frozen_by = principal.user_id; release.frozen_at = datetime.now(timezone.utc); session.add(release)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=project.workspace_id, action="bid.release_frozen", resource_type="bid_release", resource_id=release.id, metadata={"manifest_hash": release.manifest_hash})
    await session.commit(); await session.refresh(release); return release


async def list_releases(session: AsyncSession, *, project_id: uuid.UUID, principal: AuthPrincipal):
    await require_project_role(session, project_id=project_id, principal=principal)
    return list((await session.scalars(select(BidPresentationReleaseModel).where(BidPresentationReleaseModel.project_id == project_id).order_by(BidPresentationReleaseModel.version_no.desc()))).all())
