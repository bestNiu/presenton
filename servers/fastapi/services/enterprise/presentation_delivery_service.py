from datetime import datetime, timedelta, timezone
import hashlib
import json
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
from models.sql.enterprise.audit_event import AuditEventModel
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


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def get_presentation_delivery_evidence(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    artifact_id: uuid.UUID,
    principal: AuthPrincipal,
) -> dict:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    artifact = await session.get(PresentationDeliveryArtifactModel, artifact_id)
    snapshot = await session.get(PresentationSnapshotModel, artifact.snapshot_id) if artifact else None
    entry = await session.get(PresentationEntryModel, entry_id)
    if artifact is None or snapshot is None or entry is None or entry.workspace_id != workspace_id or snapshot.presentation_entry_id != entry.id:
        raise HTTPException(status_code=404, detail="Presentation delivery not found")
    manifest = snapshot.manifest or {}
    citations = manifest.get("citation_manifest")
    citations = citations if isinstance(citations, list) else []
    citation_hash = manifest.get("citation_manifest_hash")
    snapshot_integrity = _canonical_hash(manifest) == snapshot.manifest_hash
    citation_integrity = isinstance(citation_hash, str) and _canonical_hash(citations) == citation_hash
    file_integrity = False
    if artifact.object_key or artifact.file_path:
        try:
            await get_enterprise_object_storage().verify(
                StoredObjectLocation(object_key=artifact.object_key, legacy_path=artifact.file_path),
                expected_sha256=artifact.sha256,
                expected_size=artifact.size_bytes,
            )
            file_integrity = True
        except HTTPException:
            file_integrity = False
    credential = {
        "credential_version": "1.0",
        "artifact_id": str(artifact.id),
        "artifact_sha256": artifact.sha256,
        "artifact_size_bytes": artifact.size_bytes,
        "snapshot_id": str(snapshot.id),
        "snapshot_version": snapshot.version_no,
        "snapshot_manifest_hash": snapshot.manifest_hash,
        "citation_manifest_hash": citation_hash,
        "citation_count": len(citations),
    }
    return {
        "artifact": artifact,
        "snapshot_id": snapshot.id,
        "snapshot_version": snapshot.version_no,
        "snapshot_manifest_hash": snapshot.manifest_hash,
        "citation_manifest_hash": citation_hash,
        "citation_count": len(citations),
        "file_integrity": file_integrity,
        "snapshot_integrity": snapshot_integrity,
        "citation_integrity": citation_integrity,
        "credential_hash": _canonical_hash(credential),
    }


async def issue_presentation_download_grant(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, artifact_id: uuid.UUID, principal: AuthPrincipal, expires_in_minutes: int, max_downloads: int) -> tuple[PresentationDownloadGrantModel, str]:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.ADMIN)
    artifact = await session.get(PresentationDeliveryArtifactModel, artifact_id)
    snapshot = await session.get(PresentationSnapshotModel, artifact.snapshot_id) if artifact else None
    entry = await session.get(PresentationEntryModel, entry_id)
    if artifact is None or snapshot is None or entry is None or entry.workspace_id != workspace_id or snapshot.presentation_entry_id != entry.id:
        raise HTTPException(status_code=404, detail="Presentation delivery not found")
    if PresentationDeliveryStatus(artifact.status) != PresentationDeliveryStatus.READY:
        raise HTTPException(status_code=409, detail="Presentation delivery is not available")
    token = secrets.token_urlsafe(32)
    grant = PresentationDownloadGrantModel(artifact_id=artifact.id, token_hash=_token_hash(token), expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes), max_downloads=max_downloads, created_by=principal.user_id)
    session.add(grant)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=workspace_id, action="presentation.download_grant_issued", resource_type="presentation_download_grant", resource_id=grant.id, metadata={"artifact_id": str(artifact.id), "max_downloads": max_downloads})
    await session.commit()
    await session.refresh(grant)
    return grant, token


async def consume_presentation_download_grant(session: AsyncSession, *, token: str) -> tuple[PresentationDeliveryArtifactModel, StoredObjectLocation]:
    grant = await session.scalar(select(PresentationDownloadGrantModel).where(PresentationDownloadGrantModel.token_hash == _token_hash(token)))
    if grant is None or grant.revoked_at is not None:
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
    snapshot = await session.get(PresentationSnapshotModel, artifact.snapshot_id)
    entry = await session.get(PresentationEntryModel, snapshot.presentation_entry_id) if snapshot else None
    record_audit_event(session, actor_id=None, workspace_id=entry.workspace_id if entry else None, action="presentation.delivery_downloaded", resource_type="presentation_delivery_artifact", resource_id=artifact.id, metadata={"grant_id": str(grant.id), "download_count": grant.download_count})
    await session.commit()
    return artifact, location


async def list_presentation_delivery_activity(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    artifact_id: uuid.UUID,
    principal: AuthPrincipal,
) -> list[AuditEventModel]:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.ADMIN)
    artifact = await session.get(PresentationDeliveryArtifactModel, artifact_id)
    snapshot = await session.get(PresentationSnapshotModel, artifact.snapshot_id) if artifact else None
    entry = await session.get(PresentationEntryModel, entry_id)
    if artifact is None or snapshot is None or entry is None or entry.workspace_id != workspace_id or snapshot.presentation_entry_id != entry.id:
        raise HTTPException(status_code=404, detail="Presentation delivery not found")
    grant_ids = {
        str(item)
        for item in (
            await session.scalars(
                select(PresentationDownloadGrantModel.id).where(
                    PresentationDownloadGrantModel.artifact_id == artifact.id
                )
            )
        ).all()
    }
    candidate_ids = grant_ids | {str(artifact.id)}
    events = list(
        (
            await session.scalars(
                select(AuditEventModel)
                .where(AuditEventModel.workspace_id == workspace_id)
                .order_by(AuditEventModel.created_at.desc())
                .limit(1000)
            )
        ).all()
    )
    return [
        event
        for event in events
        if event.resource_id in candidate_ids
        or str((event.event_metadata or {}).get("artifact_id", "")) == str(artifact.id)
    ]


async def build_presentation_delivery_evidence_package(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    artifact_id: uuid.UUID,
    principal: AuthPrincipal,
) -> tuple[bytes, str, str]:
    evidence = await get_presentation_delivery_evidence(
        session,
        workspace_id=workspace_id,
        entry_id=entry_id,
        artifact_id=artifact_id,
        principal=principal,
    )
    activity = await list_presentation_delivery_activity(
        session,
        workspace_id=workspace_id,
        entry_id=entry_id,
        artifact_id=artifact_id,
        principal=principal,
    )
    snapshot = await session.get(PresentationSnapshotModel, evidence["snapshot_id"])
    artifact = evidence["artifact"]
    manifest = snapshot.manifest or {} if snapshot else {}
    body = {
        "package_version": "1.0",
        "artifact": {
            "id": str(artifact.id),
            "snapshot_id": str(artifact.snapshot_id),
            "format": getattr(artifact.format, "value", artifact.format),
            "file_name": artifact.file_name,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "watermark_text": artifact.watermark_text,
            "status": getattr(artifact.status, "value", artifact.status),
        },
        "integrity": {
            "file": evidence["file_integrity"],
            "snapshot": evidence["snapshot_integrity"],
            "citations": evidence["citation_integrity"],
            "credential_hash": evidence["credential_hash"],
        },
        "snapshot": {
            "id": str(evidence["snapshot_id"]),
            "version_no": evidence["snapshot_version"],
            "manifest_hash": evidence["snapshot_manifest_hash"],
            "citation_manifest_hash": evidence["citation_manifest_hash"],
            "citations": manifest.get("citation_manifest", []),
        },
        "activity": [
            {
                "id": str(event.id),
                "actor_id": str(event.actor_id) if event.actor_id else None,
                "workspace_id": str(event.workspace_id) if event.workspace_id else None,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "result": getattr(event.result, "value", event.result),
                "event_metadata": event.event_metadata,
                "created_at": event.created_at.isoformat(),
            }
            for event in activity
        ],
    }
    package_hash = _canonical_hash(body)
    package = {**body, "package_hash": package_hash}
    content = json.dumps(package, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    filename = f"presentation-delivery-{artifact.id}-evidence.json"
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="presentation.delivery_evidence_exported",
        resource_type="presentation_delivery_artifact",
        resource_id=artifact.id,
        metadata={"package_hash": package_hash},
    )
    await session.commit()
    return content, filename, package_hash


async def revoke_presentation_delivery(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    artifact_id: uuid.UUID,
    principal: AuthPrincipal,
) -> PresentationDeliveryArtifactModel:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    artifact = await session.get(PresentationDeliveryArtifactModel, artifact_id)
    snapshot = await session.get(PresentationSnapshotModel, artifact.snapshot_id) if artifact else None
    entry = await session.get(PresentationEntryModel, entry_id)
    if (
        artifact is None
        or snapshot is None
        or entry is None
        or entry.workspace_id != workspace_id
        or snapshot.presentation_entry_id != entry.id
    ):
        raise HTTPException(status_code=404, detail="Presentation delivery not found")
    if PresentationDeliveryStatus(artifact.status) == PresentationDeliveryStatus.REVOKED:
        return artifact
    revoked_at = datetime.now(timezone.utc)
    artifact.status = PresentationDeliveryStatus.REVOKED
    artifact.revoked_at = revoked_at
    grants = list(
        (
            await session.scalars(
                select(PresentationDownloadGrantModel).where(
                    PresentationDownloadGrantModel.artifact_id == artifact.id,
                    PresentationDownloadGrantModel.revoked_at.is_(None),
                )
            )
        ).all()
    )
    for grant in grants:
        grant.revoked_at = revoked_at
        session.add(grant)
    session.add(artifact)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="presentation.delivery_revoked",
        resource_type="presentation_delivery_artifact",
        resource_id=artifact.id,
        metadata={"revoked_grant_count": len(grants), "object_retained": True},
    )
    await session.commit()
    await session.refresh(artifact)
    return artifact
