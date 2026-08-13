from datetime import datetime, timedelta, timezone
import os
import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    PresentationDeliveryFormat,
    PresentationDeliveryStatus,
    WorkspaceRole,
)
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.presentation_governance import (
    PresentationDeliveryArtifactModel,
    PresentationDownloadGrantModel,
    PresentationSnapshotModel,
)
from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from services.enterprise.audit_service import record_audit_event
from services.enterprise.bid_delivery_service import (
    _token_hash,
    _watermarked_ui,
)
from services.enterprise.workspace_service import require_workspace_role
from services.enterprise.object_storage_service import (
    StoredObjectLocation,
    get_enterprise_object_storage,
)
from utils.export_utils import export_presentation


async def _require_snapshot(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    snapshot_id: uuid.UUID,
) -> tuple[PresentationEntryModel, PresentationSnapshotModel]:
    entry = await session.get(PresentationEntryModel, entry_id)
    snapshot = await session.get(PresentationSnapshotModel, snapshot_id)
    if (
        entry is None
        or entry.workspace_id != workspace_id
        or snapshot is None
        or snapshot.presentation_entry_id != entry.id
    ):
        raise HTTPException(status_code=404, detail="Presentation snapshot not found")
    return entry, snapshot


async def create_presentation_delivery(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    principal: AuthPrincipal,
    format: PresentationDeliveryFormat,
    watermark_text: str | None,
    cookie_header: str | None,
) -> PresentationDeliveryArtifactModel:
    workspace, _ = await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.ADMIN
    )
    entry, snapshot = await _require_snapshot(session, workspace_id=workspace_id, entry_id=entry_id, snapshot_id=snapshot_id)
    source = await session.scalar(select(PresentationModel).execution_options(skip_owner_scope=True).where(PresentationModel.id == entry.presentation_id))
    source_slides = list((await session.scalars(select(SlideModel).execution_options(skip_owner_scope=True).where(SlideModel.presentation == entry.presentation_id).order_by(SlideModel.index))).all())
    if source is None:
        raise HTTPException(status_code=409, detail="Presentation is missing")
    current_hash = snapshot.slide_snapshot_hash
    from services.enterprise.presentation_governance_service import _presentation_snapshot
    live_hash, _ = await _presentation_snapshot(session, entry)
    if live_hash != current_hash:
        raise HTTPException(status_code=409, detail="Frozen presentation integrity check failed")
    confidentiality = getattr(workspace.confidentiality, "value", workspace.confidentiality)
    watermark = (watermark_text or "").strip() or f"{workspace.name} · {confidentiality} · {principal.username}"
    derived = source.get_new_presentation()
    derived.owner_id = principal.user_id
    derived.title = f"{source.title or '演示文稿'}｜受控交付版"
    slides = []
    for source_slide in source_slides:
        slide = source_slide.get_new_slide(derived.id)
        slide.owner_id = principal.user_id
        slide.ui = _watermarked_ui(slide.ui, watermark)
        slides.append(slide)
    session.add(derived)
    session.add_all(slides)
    await session.commit()
    artifact = PresentationDeliveryArtifactModel(
        snapshot_id=snapshot.id,
        derived_presentation_id=derived.id,
        format=format,
        watermark_text=watermark,
        file_path="pending",
        file_name=f"{derived.title}.{PresentationDeliveryFormat(format).value}",
        sha256="",
        size_bytes=0,
        created_by=principal.user_id,
    )
    try:
        exported = await export_presentation(derived.id, derived.title, PresentationDeliveryFormat(format).value, cookie_header=cookie_header)
        file_path = os.path.realpath(exported.path)
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=500, detail="Exported delivery file is missing")
        artifact.file_name = os.path.basename(file_path)
        stored = await get_enterprise_object_storage().put_file(
            file_path,
            f"presentation-deliveries/{workspace_id}/{entry_id}/{artifact.id}.{PresentationDeliveryFormat(format).value}",
            content_type=(
                "application/pdf"
                if PresentationDeliveryFormat(format).value == "pdf"
                else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
        )
    except Exception:
        await session.delete(derived)
        await session.commit()
        raise
    artifact.object_key = stored.object_key
    artifact.file_path = stored.object_key
    artifact.sha256 = stored.sha256
    artifact.size_bytes = stored.size_bytes
    session.add(artifact)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=workspace_id, action="presentation.delivery_exported", resource_type="presentation_delivery_artifact", resource_id=artifact.id, metadata={"snapshot_id": str(snapshot.id), "format": PresentationDeliveryFormat(format).value, "sha256": artifact.sha256})
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def list_presentation_deliveries(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal) -> list[PresentationDeliveryArtifactModel]:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    return list((await session.scalars(select(PresentationDeliveryArtifactModel).join(PresentationSnapshotModel, PresentationSnapshotModel.id == PresentationDeliveryArtifactModel.snapshot_id).where(PresentationSnapshotModel.presentation_entry_id == entry.id).order_by(PresentationDeliveryArtifactModel.created_at.desc()))).all())


async def issue_presentation_download_grant(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, principal: AuthPrincipal, expires_in_minutes: int, max_downloads: int) -> tuple[PresentationDownloadGrantModel, str]:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.ADMIN)
    artifact = await session.get(PresentationDeliveryArtifactModel, artifact_id)
    snapshot = await session.get(PresentationSnapshotModel, artifact.snapshot_id) if artifact else None
    entry = await session.get(PresentationEntryModel, entry_id)
    if artifact is None or snapshot is None or entry is None or entry.workspace_id != workspace_id or snapshot.presentation_entry_id != entry.id:
        raise HTTPException(status_code=404, detail="Presentation delivery not found")
    token = secrets.token_urlsafe(32)
    grant = PresentationDownloadGrantModel(artifact_id=artifact.id, token_hash=_token_hash(token), expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes), max_downloads=max_downloads, created_by=principal.user_id)
    session.add(grant)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=workspace_id, action="presentation.download_grant_issued", resource_type="presentation_download_grant", resource_id=grant.id, metadata={"artifact_id": str(artifact.id), "max_downloads": max_downloads})
    await session.commit()
    await session.refresh(grant)
    return grant, token


async def consume_presentation_download_grant(session: AsyncSession, *, token: str) -> tuple[PresentationDeliveryArtifactModel, StoredObjectLocation]:
    grant = await session.scalar(select(PresentationDownloadGrantModel).where(PresentationDownloadGrantModel.token_hash == _token_hash(token)))
    if grant is None:
        raise HTTPException(status_code=404, detail="Download grant not found")
    expires_at = grant.expires_at if grant.expires_at.tzinfo else grant.expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc) or grant.download_count >= grant.max_downloads:
        raise HTTPException(status_code=410, detail="Download grant expired or exhausted")
    artifact = await session.get(PresentationDeliveryArtifactModel, grant.artifact_id)
    if artifact is None or PresentationDeliveryStatus(artifact.status) != PresentationDeliveryStatus.READY:
        raise HTTPException(status_code=410, detail="Presentation delivery is unavailable")
    location = StoredObjectLocation(object_key=artifact.object_key, legacy_path=artifact.file_path)
    try:
        await get_enterprise_object_storage().verify(
            location,
            expected_sha256=artifact.sha256,
            expected_size=artifact.size_bytes,
        )
    except HTTPException as exc:
        raise HTTPException(status_code=409, detail="Presentation delivery integrity check failed") from exc
    grant.download_count += 1
    grant.last_downloaded_at = datetime.now(timezone.utc)
    session.add(grant)
    record_audit_event(session, actor_id=None, action="presentation.delivery_downloaded", resource_type="presentation_delivery_artifact", resource_id=artifact.id, metadata={"grant_id": str(grant.id), "download_count": grant.download_count})
    await session.commit()
    return artifact, location
