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
    WorkspaceRole,
)
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.presentation_governance import (
    PresentationReviewModel,
    PresentationSnapshotModel,
)
from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from services.enterprise.audit_service import record_audit_event
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
    return slide_hash, manifest


async def submit_presentation_review(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
) -> PresentationReviewModel:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    entry = await _require_entry(
        session, workspace_id=workspace_id, entry_id=entry_id
    )
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
    await require_workspace_role(
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
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    entry = await _require_entry(
        session, workspace_id=workspace_id, entry_id=entry_id
    )
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
    slide_hash, manifest = await _presentation_snapshot(session, entry)
    if slide_hash != review.slide_snapshot_hash:
        raise HTTPException(status_code=409, detail="Approved presentation changed; reopen review")
    version_no = (
        await session.scalar(
            select(func.max(PresentationSnapshotModel.version_no)).where(
                PresentationSnapshotModel.presentation_entry_id == entry.id
            )
        )
        or 0
    ) + 1
    manifest["snapshot_version"] = version_no
    manifest["review_id"] = str(review.id)
    snapshot = PresentationSnapshotModel(
        presentation_entry_id=entry.id,
        review_id=review.id,
        version_no=version_no,
        manifest=manifest,
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
    if PresentationEntryStatus(entry.status) != PresentationEntryStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Only approved presentation can be reopened")
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
