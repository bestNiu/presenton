from datetime import datetime, timezone
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import WorkspaceRole
from models.sql.enterprise.bid import (
    BidDeliveryArtifactModel,
    BidDownloadGrantModel,
    BidPresentationReleaseModel,
    BidProjectModel,
)
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.presentation_governance import (
    PresentationDeliveryArtifactModel,
    PresentationDownloadGrantModel,
    PresentationSnapshotModel,
)
from services.enterprise.object_storage_service import (
    StoredObjectLocation,
    get_enterprise_object_storage,
)
from services.enterprise.workspace_service import require_workspace_role


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _grant_stats(grants: list) -> dict:
    now = datetime.now(timezone.utc)
    downloads = sum(item.download_count for item in grants)
    active = 0
    for item in grants:
        expires_at = item.expires_at if item.expires_at.tzinfo else item.expires_at.replace(tzinfo=timezone.utc)
        if item.revoked_at is None and expires_at > now and item.download_count < item.max_downloads:
            active += 1
    return {"grant_count": len(grants), "active_grant_count": active, "download_count": downloads}


async def _file_integrity(artifact) -> bool:
    if not artifact.object_key and not artifact.file_path:
        return False
    try:
        await get_enterprise_object_storage().verify(
            StoredObjectLocation(object_key=artifact.object_key, legacy_path=artifact.file_path),
            expected_sha256=artifact.sha256,
            expected_size=artifact.size_bytes,
        )
        return True
    except HTTPException:
        return False


async def get_delivery_center(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    scene_type: str | None = None,
    delivery_status: str | None = None,
    integrity_status: str | None = None,
    query: str | None = None,
) -> dict:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    general_rows = (
        await session.execute(
            select(PresentationDeliveryArtifactModel, PresentationSnapshotModel, PresentationEntryModel)
            .join(PresentationSnapshotModel, PresentationSnapshotModel.id == PresentationDeliveryArtifactModel.snapshot_id)
            .join(PresentationEntryModel, PresentationEntryModel.id == PresentationSnapshotModel.presentation_entry_id)
            .where(PresentationEntryModel.workspace_id == workspace_id)
        )
    ).all()
    bid_rows = (
        await session.execute(
            select(BidDeliveryArtifactModel, BidPresentationReleaseModel, BidProjectModel)
            .join(BidPresentationReleaseModel, BidPresentationReleaseModel.id == BidDeliveryArtifactModel.release_id)
            .join(BidProjectModel, BidProjectModel.id == BidPresentationReleaseModel.project_id)
            .where(BidProjectModel.workspace_id == workspace_id)
        )
    ).all()
    general_ids = [artifact.id for artifact, _, _ in general_rows]
    bid_ids = [artifact.id for artifact, _, _ in bid_rows]
    general_grants = list((await session.scalars(select(PresentationDownloadGrantModel).where(PresentationDownloadGrantModel.artifact_id.in_(general_ids)))).all()) if general_ids else []
    bid_grants = list((await session.scalars(select(BidDownloadGrantModel).where(BidDownloadGrantModel.artifact_id.in_(bid_ids)))).all()) if bid_ids else []
    grant_map: dict[uuid.UUID, list] = {}
    for grant in [*general_grants, *bid_grants]:
        grant_map.setdefault(grant.artifact_id, []).append(grant)

    items: list[dict] = []
    for artifact, snapshot, entry in general_rows:
        manifest = snapshot.manifest or {}
        citations = manifest.get("citation_manifest") if isinstance(manifest.get("citation_manifest"), list) else []
        file_ok = await _file_integrity(artifact)
        snapshot_ok = _canonical_hash(manifest) == snapshot.manifest_hash
        citation_hash = manifest.get("citation_manifest_hash")
        citation_ok = isinstance(citation_hash, str) and _canonical_hash(citations) == citation_hash
        integrity = "passed" if file_ok and snapshot_ok and citation_ok else "failed"
        stats = _grant_stats(grant_map.get(artifact.id, []))
        items.append({
            "artifact_id": artifact.id, "scene_type": "general", "resource_id": entry.id,
            "resource_title": entry.title or "未命名演示文稿", "resource_code": None,
            "version_no": snapshot.version_no, "format": _enum_value(artifact.format),
            "file_name": artifact.file_name, "sha256": artifact.sha256, "size_bytes": artifact.size_bytes,
            "watermark_text": artifact.watermark_text, "status": _enum_value(artifact.status),
            "integrity_status": integrity, "file_integrity": file_ok, "snapshot_integrity": snapshot_ok,
            "citation_integrity": citation_ok, "citation_count": len(citations), **stats,
            "created_at": artifact.created_at, "revoked_at": artifact.revoked_at, "purged_at": artifact.purged_at,
            "detail_url": f"/workspace/presentations/{entry.id}/review?workspace_id={workspace_id}",
        })
    for artifact, release, project in bid_rows:
        manifest = release.manifest or {}
        file_ok = await _file_integrity(artifact)
        snapshot_ok = _canonical_hash(manifest) == release.manifest_hash
        integrity = "passed" if file_ok and snapshot_ok else "failed"
        stats = _grant_stats(grant_map.get(artifact.id, []))
        items.append({
            "artifact_id": artifact.id, "scene_type": "bid", "resource_id": project.id,
            "resource_title": project.name, "resource_code": project.bid_code,
            "version_no": release.version_no, "format": _enum_value(artifact.format),
            "file_name": artifact.file_name, "sha256": artifact.sha256, "size_bytes": artifact.size_bytes,
            "watermark_text": artifact.watermark_text, "status": _enum_value(artifact.status),
            "integrity_status": integrity, "file_integrity": file_ok, "snapshot_integrity": snapshot_ok,
            "citation_integrity": None, "citation_count": 0, **stats,
            "created_at": artifact.created_at, "revoked_at": artifact.revoked_at, "purged_at": artifact.purged_at,
            "detail_url": f"/workspace/scenes/bid/projects/{project.id}",
        })
    normalized_query = (query or "").strip().casefold()
    if scene_type:
        items = [item for item in items if item["scene_type"] == scene_type]
    if delivery_status:
        items = [item for item in items if item["status"] == delivery_status]
    if integrity_status:
        items = [item for item in items if item["integrity_status"] == integrity_status]
    if normalized_query:
        items = [item for item in items if normalized_query in " ".join(filter(None, [item["resource_title"], item["resource_code"], item["file_name"], item["sha256"]])).casefold()]
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {
        "summary": {
            "total": len(items),
            "ready": sum(item["status"] == "ready" for item in items),
            "revoked": sum(item["status"] == "revoked" for item in items),
            "integrity_failed": sum(item["integrity_status"] == "failed" for item in items),
            "downloads": sum(item["download_count"] for item in items),
            "active_grants": sum(item["active_grant_count"] for item in items),
        },
        "items": items,
    }
