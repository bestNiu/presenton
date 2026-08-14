import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from models.sql.enterprise.audit_event import AuditEventModel
from models.sql.enterprise.delivery_integrity_run import DeliveryIntegrityRunModel
from models.sql.enterprise.workspace import WorkspaceMemberModel
from models.sql.user import User
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
from services.enterprise.audit_service import record_audit_event
from services.enterprise.delivery_integrity_incident_service import synchronize_delivery_integrity_incidents
from services.enterprise.notification_service import queue_notifications


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
    skip_access_check: bool = False,
) -> dict:
    if not skip_access_check:
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


async def run_delivery_integrity_scan(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    system_run: bool = False,
) -> dict:
    if system_run and not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    result = await get_delivery_center(
        session, workspace_id=workspace_id, principal=principal, skip_access_check=system_run
    )
    anomaly_ids = sorted(
        str(item["artifact_id"])
        for item in result["items"]
        if item["integrity_status"] == "failed"
    )
    previous = await session.scalar(
        select(AuditEventModel)
        .where(
            AuditEventModel.workspace_id == workspace_id,
            AuditEventModel.action == "delivery_center.integrity_scanned",
        )
        .order_by(AuditEventModel.created_at.desc())
        .limit(1)
    )
    previous_ids = set((previous.event_metadata or {}).get("anomaly_ids", [])) if previous else set()
    new_anomaly_ids = sorted(set(anomaly_ids) - previous_ids)
    incident_changes = await synchronize_delivery_integrity_incidents(
        session,
        workspace_id=workspace_id,
        items=result["items"],
        actor_id=principal.user_id,
    )
    event = record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="delivery_center.integrity_scanned",
        resource_type="enterprise_workspace",
        resource_id=workspace_id,
        metadata={
            "total": result["summary"]["total"],
            "ready": result["summary"]["ready"],
            "revoked": result["summary"]["revoked"],
            "integrity_failed": len(anomaly_ids),
            "anomaly_ids": anomaly_ids,
            "new_anomaly_ids": new_anomaly_ids,
            "opened_incident_ids": incident_changes["opened_ids"],
            "resolved_incident_ids": incident_changes["resolved_ids"],
            "revoked_grant_count": incident_changes["revoked_grant_count"],
        },
    )
    if new_anomaly_ids:
        recipients = set(
            (
                await session.scalars(
                    select(WorkspaceMemberModel.user_id).where(
                        WorkspaceMemberModel.workspace_id == workspace_id,
                        WorkspaceMemberModel.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
                    )
                )
            ).all()
        )
        queue_notifications(
            session,
            recipient_ids=recipients,
            actor_id=principal.user_id,
            workspace_id=workspace_id,
            notification_type="delivery.integrity_anomaly",
            title="交付件完整性异常",
            body=f"检测到 {len(new_anomaly_ids)} 个新增异常交付件，请暂停授权并核查。",
            resource_type="enterprise_workspace",
            resource_id=workspace_id,
            action_url=f"/workspace/deliveries?workspace_id={workspace_id}&integrity=failed",
            metadata={"artifact_ids": new_anomaly_ids},
        )
    await session.commit()
    await session.refresh(event)
    return {
        "id": event.id,
        "workspace_id": workspace_id,
        "total": result["summary"]["total"],
        "integrity_failed": len(anomaly_ids),
        "anomaly_ids": anomaly_ids,
        "new_anomaly_ids": new_anomaly_ids,
        "opened_incident_ids": incident_changes["opened_ids"],
        "resolved_incident_ids": incident_changes["resolved_ids"],
        "revoked_grant_count": incident_changes["revoked_grant_count"],
        "created_at": event.created_at,
    }


async def run_all_workspace_delivery_integrity_scans(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    source: str = "api",
    timeout_seconds: int | None = None,
) -> dict:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    if source not in {"api", "cli"}:
        raise ValueError("Delivery integrity source must be api or cli")
    from models.sql.enterprise.workspace import WorkspaceModel

    configured_timeout = timeout_seconds or int(
        os.getenv("ENTERPRISE_DELIVERY_INTEGRITY_TIMEOUT_SECONDS", "1800")
    )
    configured_timeout = max(30, min(configured_timeout, 86400))
    now = datetime.now(timezone.utc)
    existing = await session.scalar(
        select(DeliveryIntegrityRunModel)
        .where(DeliveryIntegrityRunModel.status == "running")
        .order_by(DeliveryIntegrityRunModel.started_at.desc())
        .limit(1)
    )
    if existing is not None:
        started_at = existing.started_at if existing.started_at.tzinfo else existing.started_at.replace(tzinfo=timezone.utc)
        if started_at + timedelta(seconds=existing.timeout_seconds + 60) > now:
            raise HTTPException(
                status_code=409,
                detail=f"Delivery integrity run {existing.id} is already running",
            )
        existing.status = "timed_out"
        existing.health = "critical"
        existing.lock_key = None
        existing.failure_detail = "Run exceeded its timeout and was recovered by the next scheduler invocation"
        existing.completed_at = now
        existing.duration_ms = int((now - started_at).total_seconds() * 1000)
        session.add(existing)
        await _queue_delivery_integrity_alert(
            session,
            run=existing,
            detail="交付完整性巡检超过执行时限，已由后续调度自动收口。",
        )
        await session.commit()

    batch_run = DeliveryIntegrityRunModel(
        triggered_by=principal.user_id,
        source=source,
        lock_key="delivery_integrity",
        timeout_seconds=configured_timeout,
    )
    session.add(batch_run)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Another delivery integrity run acquired the scheduler lock",
        ) from exc
    try:
        workspace_ids = list(
            (
                await session.scalars(
                    select(WorkspaceModel.id)
                    .where(WorkspaceModel.is_archived.is_(False))
                    .order_by(WorkspaceModel.created_at)
                )
            ).all()
        )
        batch_run.workspace_count = len(workspace_ids)
        session.add(batch_run)
        await session.commit()
        results = []
        async with asyncio.timeout(configured_timeout):
            for workspace_id in workspace_ids:
                results.append(
                    await run_delivery_integrity_scan(
                        session,
                        workspace_id=workspace_id,
                        principal=principal,
                        system_run=True,
                    )
                )
                batch_run.completed_workspace_count = len(results)

        completed_at = datetime.now(timezone.utc)
        failed_workspaces = sum(item["integrity_failed"] > 0 for item in results)
        new_anomalies = sum(len(item["new_anomaly_ids"]) for item in results)
        batch_run.status = "completed"
        batch_run.health = "critical" if failed_workspaces else "healthy"
        batch_run.lock_key = None
        batch_run.failed_workspace_count = failed_workspaces
        batch_run.artifact_count = sum(item["total"] for item in results)
        batch_run.integrity_failed = sum(item["integrity_failed"] for item in results)
        batch_run.new_anomalies = new_anomalies
        batch_run.completed_at = completed_at
        started_at = batch_run.started_at if batch_run.started_at.tzinfo else batch_run.started_at.replace(tzinfo=timezone.utc)
        batch_run.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        session.add(batch_run)
        if new_anomalies:
            await _queue_delivery_integrity_alert(
                session,
                run=batch_run,
                detail=f"全空间巡检发现 {new_anomalies} 个新增交付完整性异常。",
            )
        record_audit_event(
            session,
            actor_id=principal.user_id,
            action="delivery_center.batch_integrity_scanned",
            resource_type="delivery_integrity_run",
            resource_id=batch_run.id,
            metadata={
                "source": source,
                "workspace_count": len(results),
                "failed_workspace_count": failed_workspaces,
                "artifact_count": batch_run.artifact_count,
                "integrity_failed": batch_run.integrity_failed,
                "new_anomalies": new_anomalies,
                "duration_ms": batch_run.duration_ms,
            },
        )
        await session.commit()
        return {
            "run_id": batch_run.id,
            "source": source,
            "status": batch_run.status,
            "health": batch_run.health,
            "workspace_count": len(results),
            "failed_workspace_count": failed_workspaces,
            "artifact_count": batch_run.artifact_count,
            "integrity_failed": batch_run.integrity_failed,
            "new_anomalies": new_anomalies,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": batch_run.duration_ms,
            "runs": results,
        }
    except Exception as exc:
        await session.rollback()
        failed_run = await session.get(DeliveryIntegrityRunModel, batch_run.id)
        if failed_run is not None:
            completed_at = datetime.now(timezone.utc)
            started_at = failed_run.started_at if failed_run.started_at.tzinfo else failed_run.started_at.replace(tzinfo=timezone.utc)
            failed_run.status = "timed_out" if isinstance(exc, TimeoutError) else "failed"
            failed_run.health = "critical"
            failed_run.lock_key = None
            failed_run.failure_detail = str(getattr(exc, "detail", exc))[:2000] or type(exc).__name__
            failed_run.completed_at = completed_at
            failed_run.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
            session.add(failed_run)
            await _queue_delivery_integrity_alert(
                session,
                run=failed_run,
                detail=f"全空间交付完整性巡检{('超时' if isinstance(exc, TimeoutError) else '失败')}：{failed_run.failure_detail}",
            )
            record_audit_event(
                session,
                actor_id=principal.user_id,
                action="delivery_center.batch_integrity_failed",
                resource_type="delivery_integrity_run",
                resource_id=failed_run.id,
                metadata={"source": source, "status": failed_run.status, "detail": failed_run.failure_detail},
            )
            await session.commit()
        raise


async def _queue_delivery_integrity_alert(
    session: AsyncSession,
    *,
    run: DeliveryIntegrityRunModel,
    detail: str,
) -> None:
    admin_ids = set(
        (
            await session.scalars(
                select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
            )
        ).all()
    )
    queue_notifications(
        session,
        recipient_ids=admin_ids,
        actor_id=None,
        workspace_id=None,
        notification_type="delivery.integrity_run_alert",
        title="企业交付完整性巡检异常",
        body=detail[:1000],
        resource_type="delivery_integrity_run",
        resource_id=run.id,
        action_url="/admin",
        metadata={"status": run.status, "health": run.health, "source": run.source},
    )


async def list_delivery_integrity_batch_runs(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    limit: int,
) -> list[DeliveryIntegrityRunModel]:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    return list(
        (
            await session.scalars(
                select(DeliveryIntegrityRunModel)
                .order_by(DeliveryIntegrityRunModel.started_at.desc())
                .limit(limit)
            )
        ).all()
    )


async def get_delivery_integrity_health(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
) -> dict:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    max_age_hours = max(
        1,
        min(int(os.getenv("ENTERPRISE_DELIVERY_INTEGRITY_MAX_AGE_HOURS", "26")), 720),
    )
    latest = await session.scalar(
        select(DeliveryIntegrityRunModel)
        .order_by(DeliveryIntegrityRunModel.started_at.desc())
        .limit(1)
    )
    now = datetime.now(timezone.utc)
    if latest is None:
        return {
            "health": "critical",
            "reason": "never_run",
            "overdue": True,
            "max_age_hours": max_age_hours,
            "checked_at": now,
            "latest_run": None,
        }
    started_at = latest.started_at if latest.started_at.tzinfo else latest.started_at.replace(tzinfo=timezone.utc)
    reference_at = latest.completed_at or started_at
    reference_at = reference_at if reference_at.tzinfo else reference_at.replace(tzinfo=timezone.utc)
    overdue = reference_at + timedelta(hours=max_age_hours) < now
    if latest.status == "running":
        timed_out = started_at + timedelta(seconds=latest.timeout_seconds + 60) < now
        health, reason = ("critical", "run_timed_out") if timed_out else ("warning", "run_in_progress")
    elif latest.status != "completed":
        health, reason = "critical", "last_run_failed"
    elif overdue:
        health, reason = "critical", "schedule_overdue"
    else:
        health, reason = latest.health, ("integrity_anomalies" if latest.health == "critical" else "ok")
    return {
        "health": health,
        "reason": reason,
        "overdue": overdue,
        "max_age_hours": max_age_hours,
        "checked_at": now,
        "latest_run": latest,
    }


async def list_delivery_integrity_scans(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    limit: int,
) -> list[dict]:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.ADMIN
    )
    events = list(
        (
            await session.scalars(
                select(AuditEventModel)
                .where(
                    AuditEventModel.workspace_id == workspace_id,
                    AuditEventModel.action == "delivery_center.integrity_scanned",
                )
                .order_by(AuditEventModel.created_at.desc())
                .limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": event.id,
            "workspace_id": workspace_id,
            "total": int((event.event_metadata or {}).get("total", 0)),
            "integrity_failed": int((event.event_metadata or {}).get("integrity_failed", 0)),
            "anomaly_ids": (event.event_metadata or {}).get("anomaly_ids", []),
            "new_anomaly_ids": (event.event_metadata or {}).get("new_anomaly_ids", []),
            "opened_incident_ids": (event.event_metadata or {}).get("opened_incident_ids", []),
            "resolved_incident_ids": (event.event_metadata or {}).get("resolved_incident_ids", []),
            "revoked_grant_count": int((event.event_metadata or {}).get("revoked_grant_count", 0)),
            "created_at": event.created_at,
        }
        for event in events
    ]
