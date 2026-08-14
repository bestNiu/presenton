from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    BidDeliveryFormat,
    BidDeliveryStatus,
    BidProjectRole,
    BidReleaseStatus,
)
from models.sql.enterprise.bid import (
    BidDeliveryArtifactModel,
    BidDownloadGrantModel,
    BidPresentationReleaseModel,
)
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from services.enterprise.audit_service import record_audit_event
from services.enterprise.bid_project_service import require_project_role
from services.enterprise.object_storage_service import (
    StoredObjectLocation,
    get_enterprise_object_storage,
)
from utils.export_utils import export_presentation


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _watermarked_ui(ui: dict | None, text: str) -> dict:
    value = dict(ui or {})
    elements = list(value.get("elements") or [])
    elements.append(
        {
            "type": "text",
            "name": "Enterprise Delivery Watermark",
            "decorative": True,
            "position": {"x": 755, "y": 680},
            "size": {"width": 465, "height": 32},
            "runs": [
                {
                    "text": text,
                    "font": {
                        "size": 11,
                        "family": "Arial",
                        "color": "#8B91A1",
                    },
                }
            ],
        }
    )
    value["elements"] = elements
    return value


async def create_delivery_artifact(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    release_id: uuid.UUID,
    principal: AuthPrincipal,
    format: BidDeliveryFormat,
    watermark_text: str | None,
    cookie_header: str | None,
) -> BidDeliveryArtifactModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.BID_MANAGER,
    )
    release = await session.get(BidPresentationReleaseModel, release_id)
    if release is None or release.project_id != project_id:
        raise HTTPException(status_code=404, detail="Release not found")
    if BidReleaseStatus(release.status) not in {
        BidReleaseStatus.FROZEN,
        BidReleaseStatus.ARCHIVED,
    }:
        raise HTTPException(status_code=409, detail="Release must be frozen before export")

    entry = await session.get(PresentationEntryModel, release.presentation_entry_id)
    if entry is None:
        raise HTTPException(status_code=409, detail="Release presentation entry is missing")
    source = await session.scalar(
        select(PresentationModel)
        .execution_options(skip_owner_scope=True)
        .where(PresentationModel.id == entry.presentation_id)
    )
    if source is None:
        raise HTTPException(status_code=409, detail="Release presentation is missing")
    source_slides = list(
        (
            await session.scalars(
                select(SlideModel)
                .execution_options(skip_owner_scope=True)
                .where(SlideModel.presentation == source.id)
                .order_by(SlideModel.index)
            )
        ).all()
    )

    effective_watermark = (watermark_text or "").strip()
    if not effective_watermark:
        effective_watermark = (
            f"{project.bid_code} · {getattr(project.confidentiality, 'value', project.confidentiality)} · {principal.username}"
        )
    derived = source.get_new_presentation()
    derived.owner_id = principal.user_id
    derived.title = f"{source.title or project.name}｜交付版"
    slides = []
    for source_slide in source_slides:
        slide = source_slide.get_new_slide(derived.id)
        slide.owner_id = principal.user_id
        slide.ui = _watermarked_ui(slide.ui, effective_watermark)
        slides.append(slide)
    session.add(derived)
    session.add_all(slides)
    await session.commit()

    artifact = BidDeliveryArtifactModel(
        release_id=release.id,
        derived_presentation_id=derived.id,
        format=format,
        watermark_text=effective_watermark,
        file_path="pending",
        file_name=f"{derived.title}.{BidDeliveryFormat(format).value}",
        sha256="",
        size_bytes=0,
        created_by=principal.user_id,
    )
    try:
        exported = await export_presentation(
            derived.id,
            derived.title,
            BidDeliveryFormat(format).value,
            cookie_header=cookie_header,
        )
        file_path = os.path.realpath(exported.path)
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=500, detail="Exported delivery file is missing")
        artifact.file_name = os.path.basename(file_path)
        stored = await get_enterprise_object_storage().put_file(
            file_path,
            f"bid-deliveries/{project.workspace_id}/{project_id}/{artifact.id}.{BidDeliveryFormat(format).value}",
            content_type=(
                "application/pdf"
                if BidDeliveryFormat(format).value == "pdf"
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
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.delivery_exported",
        resource_type="bid_delivery_artifact",
        resource_id=artifact.id,
        metadata={
            "release_id": str(release.id),
            "format": BidDeliveryFormat(format).value,
            "sha256": artifact.sha256,
            "watermarked": True,
        },
    )
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def list_delivery_artifacts(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    release_id: uuid.UUID,
    principal: AuthPrincipal,
) -> list[BidDeliveryArtifactModel]:
    await require_project_role(
        session, project_id=project_id, principal=principal
    )
    release = await session.get(BidPresentationReleaseModel, release_id)
    if release is None or release.project_id != project_id:
        raise HTTPException(status_code=404, detail="Release not found")
    return list(
        (
            await session.scalars(
                select(BidDeliveryArtifactModel)
                .where(BidDeliveryArtifactModel.release_id == release_id)
                .order_by(BidDeliveryArtifactModel.created_at.desc())
            )
        ).all()
    )


async def issue_download_grant(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    principal: AuthPrincipal,
    expires_in_minutes: int,
    max_downloads: int,
) -> tuple[BidDownloadGrantModel, str]:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.BID_MANAGER,
    )
    artifact = await session.get(BidDeliveryArtifactModel, artifact_id)
    release = (
        await session.get(BidPresentationReleaseModel, artifact.release_id)
        if artifact
        else None
    )
    if artifact is None or release is None or release.project_id != project_id:
        raise HTTPException(status_code=404, detail="Delivery artifact not found")
    if BidDeliveryStatus(artifact.status) != BidDeliveryStatus.READY:
        raise HTTPException(status_code=409, detail="Delivery artifact is not available")
    from services.enterprise.delivery_integrity_incident_service import ensure_delivery_not_quarantined

    await ensure_delivery_not_quarantined(
        session, scene_type="bid", artifact_id=artifact.id
    )
    token = secrets.token_urlsafe(32)
    grant = BidDownloadGrantModel(
        artifact_id=artifact.id,
        token_hash=_token_hash(token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        max_downloads=max_downloads,
        created_by=principal.user_id,
    )
    session.add(grant)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.download_grant_issued",
        resource_type="bid_download_grant",
        resource_id=grant.id,
        metadata={
            "artifact_id": str(artifact.id),
            "expires_in_minutes": expires_in_minutes,
            "max_downloads": max_downloads,
        },
    )
    await session.commit()
    await session.refresh(grant)
    return grant, token


async def consume_download_grant(
    session: AsyncSession, *, token: str
) -> tuple[BidDeliveryArtifactModel, StoredObjectLocation]:
    grant = await session.scalar(
        select(BidDownloadGrantModel).where(
            BidDownloadGrantModel.token_hash == _token_hash(token)
        )
    )
    if grant is None or grant.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Download grant not found")
    expires_at = grant.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Download grant expired")
    if grant.download_count >= grant.max_downloads:
        raise HTTPException(status_code=410, detail="Download grant exhausted")
    artifact = await session.get(BidDeliveryArtifactModel, grant.artifact_id)
    if artifact is None or BidDeliveryStatus(artifact.status) != BidDeliveryStatus.READY:
        raise HTTPException(status_code=410, detail="Delivery artifact is unavailable")
    location = StoredObjectLocation(object_key=artifact.object_key, legacy_path=artifact.file_path)
    try:
        await get_enterprise_object_storage().verify(
            location,
            expected_sha256=artifact.sha256,
            expected_size=artifact.size_bytes,
        )
    except HTTPException as exc:
        raise HTTPException(status_code=409, detail="Delivery artifact integrity check failed") from exc
    grant.download_count += 1
    grant.last_downloaded_at = datetime.now(timezone.utc)
    session.add(grant)
    release = await session.get(BidPresentationReleaseModel, artifact.release_id)
    record_audit_event(
        session,
        actor_id=None,
        action="bid.delivery_downloaded",
        resource_type="bid_delivery_artifact",
        resource_id=artifact.id,
        metadata={
            "grant_id": str(grant.id),
            "download_count": grant.download_count,
            "manifest_hash": release.manifest_hash if release else None,
        },
    )
    await session.commit()
    return artifact, location


async def revoke_delivery_artifact(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    principal: AuthPrincipal,
) -> BidDeliveryArtifactModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.BID_MANAGER,
    )
    artifact = await session.get(BidDeliveryArtifactModel, artifact_id)
    release = await session.get(BidPresentationReleaseModel, artifact.release_id) if artifact else None
    if artifact is None or release is None or release.project_id != project_id:
        raise HTTPException(status_code=404, detail="Delivery artifact not found")
    if BidDeliveryStatus(artifact.status) == BidDeliveryStatus.REVOKED:
        return artifact
    revoked_at = datetime.now(timezone.utc)
    artifact.status = BidDeliveryStatus.REVOKED
    artifact.revoked_at = revoked_at
    grants = list(
        (
            await session.scalars(
                select(BidDownloadGrantModel).where(
                    BidDownloadGrantModel.artifact_id == artifact.id,
                    BidDownloadGrantModel.revoked_at.is_(None),
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
        workspace_id=project.workspace_id,
        action="bid.delivery_revoked",
        resource_type="bid_delivery_artifact",
        resource_id=artifact.id,
        metadata={"revoked_grant_count": len(grants), "object_retained": True},
    )
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def archive_release(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    release_id: uuid.UUID,
    principal: AuthPrincipal,
) -> BidPresentationReleaseModel:
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.BID_MANAGER,
    )
    release = await session.get(BidPresentationReleaseModel, release_id)
    if release is None or release.project_id != project_id:
        raise HTTPException(status_code=404, detail="Release not found")
    if BidReleaseStatus(release.status) != BidReleaseStatus.FROZEN:
        raise HTTPException(status_code=409, detail="Only frozen release can be archived")
    artifact = await session.scalar(
        select(BidDeliveryArtifactModel).where(
            BidDeliveryArtifactModel.release_id == release.id,
            BidDeliveryArtifactModel.status == BidDeliveryStatus.READY,
        )
    )
    if artifact is None:
        raise HTTPException(status_code=409, detail="Export a delivery artifact before archive")
    release.status = BidReleaseStatus.ARCHIVED
    session.add(release)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=project.workspace_id,
        action="bid.release_archived",
        resource_type="bid_release",
        resource_id=release.id,
        metadata={"manifest_hash": release.manifest_hash},
    )
    await session.commit()
    await session.refresh(release)
    return release
