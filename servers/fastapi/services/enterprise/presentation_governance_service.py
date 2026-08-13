from datetime import datetime, timezone
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    PresentationEntryStatus,
    PresentationReviewStatus,
    PresentationQualityStatus,
    WorkspaceRole,
)
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.workspace import WorkspaceMemberModel
from models.sql.enterprise.presentation_governance import (
    PresentationReviewModel,
    PresentationQualityRunModel,
    PresentationSnapshotModel,
)
from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from services.enterprise.audit_service import record_audit_event
from services.enterprise.notification_service import queue_notifications
from services.enterprise.workspace_service import require_workspace_role


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _require_entry(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> PresentationEntryModel:
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    return entry


async def _presentation_snapshot(
    session: AsyncSession, entry: PresentationEntryModel
) -> tuple[str, dict]:
    slide_hash, manifest, _ = await _presentation_state(session, entry)
    return slide_hash, manifest


async def _presentation_state(
    session: AsyncSession, entry: PresentationEntryModel
) -> tuple[str, dict, dict]:
    presentation = await session.scalar(
        select(PresentationModel)
        .execution_options(skip_owner_scope=True)
        .where(PresentationModel.id == entry.presentation_id)
    )
    if presentation is None:
        raise HTTPException(status_code=409, detail="Presentation is missing")
    slides = list(
        (
            await session.scalars(
                select(SlideModel)
                .execution_options(skip_owner_scope=True)
                .where(SlideModel.presentation == presentation.id)
                .order_by(SlideModel.index)
            )
        ).all()
    )
    slide_payload = [
        {
            "id": str(slide.id),
            "index": slide.index,
            "ui": slide.ui,
            "content": slide.content,
            "speaker_note": slide.speaker_note,
        }
        for slide in slides
    ]
    slide_hash = _canonical_hash(slide_payload)
    manifest = {
        "manifest_version": "1.0",
        "workspace_id": str(entry.workspace_id),
        "presentation_entry_id": str(entry.id),
        "presentation_id": str(presentation.id),
        "scene": {"type": entry.scene_type, "version": entry.scene_version},
        "title": entry.title or presentation.title,
        "creation_mode": getattr(entry.creation_mode, "value", entry.creation_mode),
        "presentation_version": getattr(presentation.version, "value", presentation.version),
        "slide_count": len(slides),
        "slide_snapshot_hash": slide_hash,
    }
    content_snapshot = {
        "snapshot_format": "presentation-slides-v1",
        "slides": slide_payload,
    }
    return slide_hash, manifest, content_snapshot


def compare_snapshot_content(from_snapshot: dict, to_snapshot: dict) -> dict:
    from_slides = {slide["id"]: slide for slide in from_snapshot.get("slides", [])}
    to_slides = {slide["id"]: slide for slide in to_snapshot.get("slides", [])}
    changes = []
    for slide_id in sorted(set(from_slides) | set(to_slides), key=lambda value: (to_slides.get(value) or from_slides[value]).get("index", 0)):
        before = from_slides.get(slide_id)
        after = to_slides.get(slide_id)
        change_type = "added" if before is None else "removed" if after is None else "unchanged" if _canonical_hash(before) == _canonical_hash(after) else "changed"
        changes.append({
            "slide_id": slide_id,
            "before_index": before.get("index") if before else None,
            "after_index": after.get("index") if after else None,
            "change_type": change_type,
            "changed_fields": [] if before is None or after is None else [field for field in ("index", "ui", "content", "speaker_note") if _canonical_hash(before.get(field)) != _canonical_hash(after.get(field))],
        })
    return {
        "added": sum(change["change_type"] == "added" for change in changes),
        "removed": sum(change["change_type"] == "removed" for change in changes),
        "changed": sum(change["change_type"] == "changed" for change in changes),
        "unchanged": sum(change["change_type"] == "unchanged" for change in changes),
        "slides": changes,
    }


async def submit_presentation_review(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
) -> PresentationReviewModel:
    workspace, _ = await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    entry = await _require_entry(
        session, workspace_id=workspace_id, entry_id=entry_id
    )
    if (workspace.governance_policy or {}).get("review_mode", "single") == "none":
        raise HTTPException(status_code=409, detail="Workspace review is disabled")
    if PresentationEntryStatus(entry.status) != PresentationEntryStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft presentation can be submitted")
    slide_hash, _ = await _presentation_snapshot(session, entry)
    submission_no = (
        await session.scalar(
            select(func.max(PresentationReviewModel.submission_no)).where(
                PresentationReviewModel.presentation_entry_id == entry.id
            )
        )
        or 0
    ) + 1
    review = PresentationReviewModel(
        presentation_entry_id=entry.id,
        submission_no=submission_no,
        slide_snapshot_hash=slide_hash,
        submitted_by=principal.user_id,
    )
    entry.status = PresentationEntryStatus.IN_REVIEW
    entry.row_version += 1
    session.add_all([review, entry])
    reviewer_ids = set((await session.scalars(
        select(WorkspaceMemberModel.user_id).where(
            WorkspaceMemberModel.workspace_id == workspace_id,
            WorkspaceMemberModel.role.in_([WorkspaceRole.REVIEWER, WorkspaceRole.ADMIN, WorkspaceRole.OWNER]),
        )
    )).all())
    queue_notifications(
        session,
        recipient_ids=reviewer_ids,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        notification_type="presentation.review_submitted",
        title="有新的演示文稿待审批",
        body=entry.title or "未命名演示文稿",
        resource_type="presentation_review",
        resource_id=review.id,
        action_url=f"/workspace/presentations/{entry.id}/review?workspace_id={workspace_id}",
        metadata={"entry_id": str(entry.id), "submission_no": submission_no},
    )
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="presentation.review_submitted",
        resource_type="presentation_entry",
        resource_id=entry.id,
        metadata={"submission_no": submission_no, "slide_snapshot_hash": slide_hash},
    )
    await session.commit()
    await session.refresh(review)
    return review


async def decide_presentation_review(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
    action: str,
    comment: str | None,
) -> PresentationReviewModel:
    workspace, _ = await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.REVIEWER,
    )
    entry = await _require_entry(
        session, workspace_id=workspace_id, entry_id=entry_id
    )
    if PresentationEntryStatus(entry.status) != PresentationEntryStatus.IN_REVIEW:
        raise HTTPException(status_code=409, detail="Presentation is not in review")
    review = await session.scalar(
        select(PresentationReviewModel)
        .where(
            PresentationReviewModel.presentation_entry_id == entry.id,
            PresentationReviewModel.status == PresentationReviewStatus.PENDING,
        )
        .order_by(PresentationReviewModel.submission_no.desc())
        .limit(1)
    )
    if review is None:
        raise HTTPException(status_code=409, detail="Pending review not found")
    if review.submitted_by == principal.user_id:
        raise HTTPException(status_code=409, detail="Submitter cannot review own presentation")
    current_hash, _ = await _presentation_snapshot(session, entry)
    if current_hash != review.slide_snapshot_hash:
        raise HTTPException(status_code=409, detail="Presentation changed after submission")
    if action == "approve" and (workspace.governance_policy or {}).get("quality_gate_enabled", True):
        quality_run = await session.scalar(
            select(PresentationQualityRunModel)
            .where(PresentationQualityRunModel.presentation_entry_id == entry.id)
            .order_by(PresentationQualityRunModel.created_at.desc())
            .limit(1)
        )
        if quality_run is None or PresentationQualityStatus(quality_run.status) != PresentationQualityStatus.PASSED or quality_run.slide_snapshot_hash != current_hash:
            raise HTTPException(status_code=409, detail="Latest quality check must pass before approval")
    if action == "approve":
        from services.enterprise.presentation_comment_service import count_open_blocking_comments
        if await count_open_blocking_comments(session, entry_id=entry.id):
            raise HTTPException(status_code=409, detail="Resolve blocking review comments before approval")
    if action == "reject" and not (comment or "").strip():
        raise HTTPException(status_code=422, detail="Rejection comment is required")
    review.status = (
        PresentationReviewStatus.APPROVED
        if action == "approve"
        else PresentationReviewStatus.REJECTED
    )
    review.decided_by = principal.user_id
    review.decision_comment = (comment or "").strip() or None
    review.decided_at = datetime.now(timezone.utc)
    entry.status = (
        PresentationEntryStatus.APPROVED
        if action == "approve"
        else PresentationEntryStatus.DRAFT
    )
    entry.row_version += 1
    session.add_all([review, entry])
    if review.submitted_by:
        queue_notifications(
            session,
            recipient_ids={review.submitted_by},
            actor_id=principal.user_id,
            workspace_id=workspace_id,
            notification_type=("presentation.review_approved" if action == "approve" else "presentation.review_rejected"),
            title="演示文稿审批通过" if action == "approve" else "演示文稿已退回",
            body=entry.title or "未命名演示文稿",
            resource_type="presentation_review",
            resource_id=review.id,
            action_url=f"/workspace/presentations/{entry.id}/review?workspace_id={workspace_id}",
            metadata={"entry_id": str(entry.id), "comment": review.decision_comment},
        )
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action=("presentation.review_approved" if action == "approve" else "presentation.review_rejected"),
        resource_type="presentation_entry",
        resource_id=entry.id,
        metadata={"review_id": str(review.id), "comment": review.decision_comment},
    )
    await session.commit()
    await session.refresh(review)
    return review


async def freeze_presentation(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
) -> PresentationSnapshotModel:
    workspace, _ = await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    entry = await _require_entry(
        session, workspace_id=workspace_id, entry_id=entry_id
    )
    policy = workspace.governance_policy or {}
    review_mode = policy.get("review_mode", "single")
    review = None
    if review_mode == "single":
        if PresentationEntryStatus(entry.status) != PresentationEntryStatus.APPROVED:
            raise HTTPException(status_code=409, detail="Presentation must be approved before freeze")
        review = await session.scalar(
            select(PresentationReviewModel)
            .where(
                PresentationReviewModel.presentation_entry_id == entry.id,
                PresentationReviewModel.status == PresentationReviewStatus.APPROVED,
            )
            .order_by(PresentationReviewModel.submission_no.desc())
            .limit(1)
        )
        if review is None:
            raise HTTPException(status_code=409, detail="Approved review not found")
    elif PresentationEntryStatus(entry.status) != PresentationEntryStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft presentation can be frozen without review")
    slide_hash, manifest, content_snapshot = await _presentation_state(session, entry)
    if review is not None and slide_hash != review.slide_snapshot_hash:
        raise HTTPException(status_code=409, detail="Approved presentation changed; reopen review")
    # Citation validity can change without changing the presentation snapshot
    # (for example when a source is revoked or superseded), so always recheck it.
    from services.enterprise.presentation_quality_service import (
        invalid_source_citations,
        list_source_citation_details,
    )

    invalid_citations = await invalid_source_citations(session, entry_id=entry.id)
    if invalid_citations:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Resolve invalid source citations before freeze",
                "invalid_citation_ids": [str(item.id) for item in invalid_citations],
            },
        )
    if review is None:
        submission_no = (
            await session.scalar(
                select(func.max(PresentationReviewModel.submission_no)).where(
                    PresentationReviewModel.presentation_entry_id == entry.id
                )
            )
            or 0
        ) + 1
        review = PresentationReviewModel(
            presentation_entry_id=entry.id,
            submission_no=submission_no,
            slide_snapshot_hash=slide_hash,
            status=PresentationReviewStatus.APPROVED,
            submitted_by=principal.user_id,
            decided_by=principal.user_id,
            decision_comment="Workspace policy: review not required",
            decided_at=datetime.now(timezone.utc),
        )
        session.add(review)
    quality_run = None
    if policy.get("quality_gate_enabled", True):
        quality_run = await session.scalar(
            select(PresentationQualityRunModel)
            .where(PresentationQualityRunModel.presentation_entry_id == entry.id)
            .order_by(PresentationQualityRunModel.created_at.desc())
            .limit(1)
        )
        if quality_run is None or PresentationQualityStatus(quality_run.status) != PresentationQualityStatus.PASSED or quality_run.slide_snapshot_hash != slide_hash:
            raise HTTPException(status_code=409, detail="Latest quality check must pass for the current presentation")
    from services.enterprise.presentation_comment_service import count_open_blocking_comments
    if await count_open_blocking_comments(session, entry_id=entry.id):
        raise HTTPException(status_code=409, detail="Resolve blocking review comments before freeze")
    version_no = (
        await session.scalar(
            select(func.max(PresentationSnapshotModel.version_no)).where(
                PresentationSnapshotModel.presentation_entry_id == entry.id
            )
        )
        or 0
    ) + 1
    manifest["manifest_version"] = "1.1"
    manifest["snapshot_version"] = version_no
    manifest["review_id"] = str(review.id)
    manifest["quality_run_id"] = str(quality_run.id) if quality_run else None
    citation_details = await list_source_citation_details(
        session,
        workspace_id=workspace_id,
        entry_id=entry.id,
        principal=principal,
    )
    citation_manifest = [
        {
            "id": str(item["id"]),
            "slide_id": str(item["slide_id"]) if item["slide_id"] else None,
            "element_ref": item["element_ref"],
            "source_type": item["source_type"],
            "source_id": item["source_id"],
            "source_version": item["source_version"],
            "locator": item["locator"],
            "excerpt": item["excerpt"],
            "status": item["status"],
            "source_name": item["source_name"],
            "current_version": item["current_version"],
        }
        for item in citation_details
    ]
    manifest["citation_manifest"] = citation_manifest
    manifest["citation_manifest_hash"] = _canonical_hash(citation_manifest)
    snapshot = PresentationSnapshotModel(
        presentation_entry_id=entry.id,
        review_id=review.id,
        quality_run_id=quality_run.id if quality_run else None,
        version_no=version_no,
        manifest=manifest,
        content_snapshot=content_snapshot,
        manifest_hash=_canonical_hash(manifest),
        slide_snapshot_hash=slide_hash,
        frozen_by=principal.user_id,
    )
    entry.status = PresentationEntryStatus.FROZEN
    entry.row_version += 1
    session.add_all([snapshot, entry])
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="presentation.frozen",
        resource_type="presentation_snapshot",
        resource_id=snapshot.id,
        metadata={"entry_id": str(entry.id), "manifest_hash": snapshot.manifest_hash},
    )
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


async def reopen_presentation_review(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
) -> PresentationEntryModel:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    entry = await _require_entry(session, workspace_id=workspace_id, entry_id=entry_id)
    if PresentationEntryStatus(entry.status) not in (PresentationEntryStatus.APPROVED, PresentationEntryStatus.FROZEN):
        raise HTTPException(status_code=409, detail="Only approved or frozen presentation can be reopened")
    entry.status = PresentationEntryStatus.DRAFT
    entry.row_version += 1
    session.add(entry)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=workspace_id, action="presentation.review_reopened", resource_type="presentation_entry", resource_id=entry.id)
    await session.commit()
    await session.refresh(entry)
    return entry


async def get_presentation_governance(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
) -> dict:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    entry = await _require_entry(session, workspace_id=workspace_id, entry_id=entry_id)
    reviews = list((await session.scalars(select(PresentationReviewModel).where(PresentationReviewModel.presentation_entry_id == entry.id).order_by(PresentationReviewModel.submission_no.desc()))).all())
    snapshots = list((await session.scalars(select(PresentationSnapshotModel).where(PresentationSnapshotModel.presentation_entry_id == entry.id).order_by(PresentationSnapshotModel.version_no.desc()))).all())
    return {"entry": entry, "reviews": reviews, "snapshots": snapshots}


async def get_presentation_freeze_preflight(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
) -> dict:
    workspace, _ = await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal
    )
    entry = await _require_entry(session, workspace_id=workspace_id, entry_id=entry_id)
    slide_hash, _ = await _presentation_snapshot(session, entry)
    policy = workspace.governance_policy or {}
    checks: list[dict] = []

    review_mode = policy.get("review_mode", "single")
    if review_mode == "single":
        review = await session.scalar(
            select(PresentationReviewModel)
            .where(
                PresentationReviewModel.presentation_entry_id == entry.id,
                PresentationReviewModel.status == PresentationReviewStatus.APPROVED,
            )
            .order_by(PresentationReviewModel.submission_no.desc())
            .limit(1)
        )
        review_passed = (
            PresentationEntryStatus(entry.status) == PresentationEntryStatus.APPROVED
            and review is not None
            and review.slide_snapshot_hash == slide_hash
        )
        checks.append({"code": "review", "label": "审批状态", "passed": review_passed, "message": "当前内容已审批" if review_passed else "需要完成当前版本审批", "count": 0 if review_passed else 1})
    else:
        review_passed = PresentationEntryStatus(entry.status) == PresentationEntryStatus.DRAFT
        checks.append({"code": "review", "label": "审批状态", "passed": review_passed, "message": "空间策略无需审批" if review_passed else "仅草稿可按免审策略冻结", "count": 0 if review_passed else 1})

    quality_enabled = policy.get("quality_gate_enabled", True)
    quality_passed = True
    if quality_enabled:
        quality_run = await session.scalar(
            select(PresentationQualityRunModel)
            .where(PresentationQualityRunModel.presentation_entry_id == entry.id)
            .order_by(PresentationQualityRunModel.created_at.desc())
            .limit(1)
        )
        quality_passed = bool(quality_run and PresentationQualityStatus(quality_run.status) == PresentationQualityStatus.PASSED and quality_run.slide_snapshot_hash == slide_hash)
    quality_message = "空间策略未启用质量门禁" if not quality_enabled else ("当前版本质量检查已通过" if quality_passed else "需要重新运行并通过质量检查")
    checks.append({"code": "quality", "label": "质量门禁", "passed": quality_passed, "message": quality_message, "count": 0 if quality_passed else 1})

    from services.enterprise.presentation_comment_service import count_open_blocking_comments
    from services.enterprise.presentation_quality_service import invalid_source_citations

    blocking_comments = await count_open_blocking_comments(session, entry_id=entry.id)
    invalid_citations = await invalid_source_citations(session, entry_id=entry.id)
    checks.append({"code": "comments", "label": "阻断整改", "passed": blocking_comments == 0, "message": "无未解决阻断项" if blocking_comments == 0 else f"仍有 {blocking_comments} 个阻断整改项", "count": blocking_comments})
    checks.append({"code": "citations", "label": "引用证据", "passed": not invalid_citations, "message": "全部引用当前有效" if not invalid_citations else f"仍有 {len(invalid_citations)} 条失效引用", "count": len(invalid_citations)})
    return {"can_freeze": all(item["passed"] for item in checks), "slide_snapshot_hash": slide_hash, "checks": checks}


async def compare_presentation_snapshots(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    from_snapshot_id: uuid.UUID,
    to_snapshot_id: uuid.UUID,
    principal: AuthPrincipal,
) -> dict:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    await _require_entry(session, workspace_id=workspace_id, entry_id=entry_id)
    snapshots = list((await session.scalars(select(PresentationSnapshotModel).where(
        PresentationSnapshotModel.presentation_entry_id == entry_id,
        PresentationSnapshotModel.id.in_([from_snapshot_id, to_snapshot_id]),
    ))).all())
    by_id = {snapshot.id: snapshot for snapshot in snapshots}
    if from_snapshot_id not in by_id or to_snapshot_id not in by_id:
        raise HTTPException(status_code=404, detail="Presentation snapshot not found")
    before, after = by_id[from_snapshot_id], by_id[to_snapshot_id]
    result = compare_snapshot_content(before.content_snapshot or {}, after.content_snapshot or {})
    return {
        "from_snapshot_id": before.id,
        "from_version_no": before.version_no,
        "to_snapshot_id": after.id,
        "to_version_no": after.version_no,
        **result,
    }
