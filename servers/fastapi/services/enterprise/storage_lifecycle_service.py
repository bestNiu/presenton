from datetime import datetime, timedelta, timezone
import os

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import AuditResult, BidDeliveryStatus, PresentationDeliveryStatus
from models.sql.enterprise.asset_item import AssetItemModel
from models.sql.enterprise.bid import (
    BidDeliveryArtifactModel,
    BidPresentationReleaseModel,
    BidProjectModel,
)
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.presentation_governance import (
    PresentationDeliveryArtifactModel,
    PresentationSnapshotModel,
)
from models.sql.enterprise.storage_lifecycle import StorageLifecycleRunModel
from models.sql.enterprise.workspace import WorkspaceModel
from models.sql.user import User
from services.enterprise.audit_service import record_audit_event
from services.enterprise.notification_service import queue_notifications
from services.enterprise.object_storage_service import get_enterprise_object_storage


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _retention_days(workspace: WorkspaceModel) -> int:
    default = int(os.getenv("ENTERPRISE_OBJECT_STORAGE_REVOKED_RETENTION_DAYS", "90"))
    configured = (workspace.governance_policy or {}).get(
        "revoked_delivery_retention_days", default
    )
    return max(1, min(int(configured), 3650))


async def _perform_storage_lifecycle(
    session: AsyncSession,
    *,
    execute: bool,
    max_delete: int,
    run_id,
    started_at: datetime,
) -> dict:
    now = started_at
    orphan_grace_days = max(
        1,
        min(
            int(os.getenv("ENTERPRISE_OBJECT_STORAGE_ORPHAN_GRACE_DAYS", "7")),
            3650,
        ),
    )
    storage = get_enterprise_object_storage()
    stored_objects = await storage.list_objects()
    inventory = {item.object_key: item for item in stored_objects}

    asset_keys = set(
        (
            await session.scalars(
                select(AssetItemModel.preview_object_key).where(
                    AssetItemModel.preview_object_key.is_not(None)
                )
            )
        ).all()
    )
    presentation_rows = (
        await session.execute(
            select(PresentationDeliveryArtifactModel, WorkspaceModel)
            .join(
                PresentationSnapshotModel,
                PresentationSnapshotModel.id
                == PresentationDeliveryArtifactModel.snapshot_id,
            )
            .join(
                PresentationEntryModel,
                PresentationEntryModel.id
                == PresentationSnapshotModel.presentation_entry_id,
            )
            .join(
                WorkspaceModel,
                WorkspaceModel.id == PresentationEntryModel.workspace_id,
            )
            .where(PresentationDeliveryArtifactModel.object_key.is_not(None))
        )
    ).all()
    bid_rows = (
        await session.execute(
            select(BidDeliveryArtifactModel, WorkspaceModel)
            .join(
                BidPresentationReleaseModel,
                BidPresentationReleaseModel.id == BidDeliveryArtifactModel.release_id,
            )
            .join(BidProjectModel, BidProjectModel.id == BidPresentationReleaseModel.project_id)
            .join(WorkspaceModel, WorkspaceModel.id == BidProjectModel.workspace_id)
            .where(BidDeliveryArtifactModel.object_key.is_not(None))
        )
    ).all()

    referenced_keys = set(asset_keys)
    referenced_keys.update(artifact.object_key for artifact, _ in presentation_rows)
    referenced_keys.update(artifact.object_key for artifact, _ in bid_rows)
    expected_keys = set(asset_keys)
    expected_keys.update(
        artifact.object_key
        for artifact, _ in presentation_rows
        if artifact.purged_at is None
    )
    expected_keys.update(
        artifact.object_key for artifact, _ in bid_rows if artifact.purged_at is None
    )
    candidates: dict[str, tuple[str, object | None]] = {}

    for artifact, workspace in presentation_rows:
        if (
            PresentationDeliveryStatus(artifact.status)
            == PresentationDeliveryStatus.REVOKED
            and artifact.revoked_at is not None
            and artifact.purged_at is None
            and _aware(artifact.revoked_at)
            <= now - timedelta(days=_retention_days(workspace))
            and artifact.object_key in inventory
        ):
            candidates[artifact.object_key] = ("revoked_presentation_delivery", artifact)

    for artifact, workspace in bid_rows:
        if (
            BidDeliveryStatus(artifact.status) == BidDeliveryStatus.REVOKED
            and artifact.revoked_at is not None
            and artifact.purged_at is None
            and _aware(artifact.revoked_at)
            <= now - timedelta(days=_retention_days(workspace))
            and artifact.object_key in inventory
        ):
            candidates[artifact.object_key] = ("revoked_bid_delivery", artifact)

    orphan_cutoff = now - timedelta(days=orphan_grace_days)
    for item in stored_objects:
        if item.object_key not in referenced_keys and _aware(item.last_modified) <= orphan_cutoff:
            candidates[item.object_key] = ("orphan", None)

    candidate_rows = [
        {
            "object_key": key,
            "reason": reason,
            "size_bytes": inventory[key].size_bytes,
            "last_modified": inventory[key].last_modified,
        }
        for key, (reason, _) in sorted(candidates.items())
    ]
    protected_keys = (referenced_keys & inventory.keys()) - candidates.keys()
    deleted_keys: list[str] = []
    deleted_bytes = 0
    if execute:
        for row in candidate_rows[:max_delete]:
            key = row["object_key"]
            if await storage.delete_object(key):
                deleted_keys.append(key)
                deleted_bytes += row["size_bytes"]
                artifact = candidates[key][1]
                if artifact is not None:
                    artifact.purged_at = now
                    session.add(artifact)

    report = {
        "run_id": run_id,
        "mode": "execute" if execute else "dry_run",
        "backend": storage.backend,
        "scanned_count": len(stored_objects),
        "stored_bytes": sum(item.size_bytes for item in stored_objects),
        "referenced_count": len(referenced_keys),
        "protected_count": len(protected_keys),
        "protected_bytes": sum(inventory[key].size_bytes for key in protected_keys),
        "missing_referenced_count": len(expected_keys - inventory.keys()),
        "candidate_count": len(candidate_rows),
        "candidate_bytes": sum(row["size_bytes"] for row in candidate_rows),
        "orphan_candidate_count": sum(row["reason"] == "orphan" for row in candidate_rows),
        "revoked_candidate_count": sum(row["reason"] != "orphan" for row in candidate_rows),
        "deleted_count": len(deleted_keys),
        "deleted_bytes": deleted_bytes,
        "truncated": execute and len(candidate_rows) > max_delete,
        "candidates": candidate_rows[:100],
        "started_at": now,
        "completed_at": datetime.now(timezone.utc),
    }
    return report


def _health_from_report(report: dict) -> str:
    if report["missing_referenced_count"] > 0:
        return "critical"
    remaining_candidates = report["candidate_count"] - report["deleted_count"]
    if remaining_candidates > 0 or report["truncated"]:
        return "warning"
    return "healthy"


def _apply_report(run: StorageLifecycleRunModel, report: dict) -> None:
    for field in (
        "backend",
        "scanned_count",
        "stored_bytes",
        "protected_count",
        "protected_bytes",
        "missing_referenced_count",
        "candidate_count",
        "candidate_bytes",
        "orphan_candidate_count",
        "revoked_candidate_count",
        "deleted_count",
        "deleted_bytes",
        "truncated",
        "completed_at",
    ):
        setattr(run, field, report[field])
    run.candidate_sample = [
        {
            **candidate,
            "last_modified": candidate["last_modified"].isoformat(),
        }
        for candidate in report["candidates"]
    ]
    run.status = "completed"
    run.health = _health_from_report(report)


async def _queue_health_alert(
    session: AsyncSession,
    *,
    run: StorageLifecycleRunModel,
    detail: str,
) -> None:
    admin_ids = set(
        (
            await session.scalars(
                select(User.id).where(
                    User.is_superuser.is_(True), User.is_active.is_(True)
                )
            )
        ).all()
    )
    queue_notifications(
        session,
        recipient_ids=admin_ids,
        actor_id=None,
        workspace_id=None,
        notification_type="storage.lifecycle_health_alert",
        title="企业对象存储生命周期异常",
        body=detail[:1000],
        resource_type="storage_lifecycle_run",
        resource_id=run.id,
        action_url="/admin",
        metadata={"health": run.health, "status": run.status, "mode": run.mode},
    )


async def run_storage_lifecycle(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    execute: bool,
    max_delete: int,
    source: str = "api",
) -> dict:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    if source not in {"api", "cli"}:
        raise ValueError("Storage lifecycle source must be api or cli")

    run = StorageLifecycleRunModel(
        triggered_by=principal.user_id,
        source=source,
        mode="execute" if execute else "dry_run",
        status="running",
        health="unknown",
    )
    session.add(run)
    await session.commit()
    try:
        report = await _perform_storage_lifecycle(
            session,
            execute=execute,
            max_delete=max_delete,
            run_id=run.id,
            started_at=_aware(run.started_at),
        )
        _apply_report(run, report)
        session.add(run)
        if run.health == "critical":
            await _queue_health_alert(
                session,
                run=run,
                detail=f"检测到 {run.missing_referenced_count} 个数据库引用对象缺失，请立即检查存储完整性。",
            )
        record_audit_event(
            session,
            actor_id=principal.user_id,
            action="storage.lifecycle_executed" if execute else "storage.lifecycle_scanned",
            resource_type="storage_lifecycle_run",
            resource_id=run.id,
            metadata={key: value for key, value in report.items() if key not in {"candidates", "run_id", "started_at", "completed_at"}},
        )
        await session.commit()
        return report
    except Exception as exc:
        await session.rollback()
        failed_run = await session.get(StorageLifecycleRunModel, run.id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.health = "critical"
            failed_run.failure_detail = str(getattr(exc, "detail", exc))[:2000]
            failed_run.completed_at = datetime.now(timezone.utc)
            session.add(failed_run)
            await _queue_health_alert(
                session,
                run=failed_run,
                detail=f"生命周期作业执行失败：{failed_run.failure_detail}",
            )
            record_audit_event(
                session,
                actor_id=principal.user_id,
                action="storage.lifecycle_failed",
                resource_type="storage_lifecycle_run",
                resource_id=failed_run.id,
                result=AuditResult.FAILED,
                metadata={"mode": failed_run.mode, "source": source, "detail": failed_run.failure_detail},
            )
            await session.commit()
        raise


async def list_storage_lifecycle_runs(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    limit: int,
) -> list[StorageLifecycleRunModel]:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")
    return list(
        (
            await session.scalars(
                select(StorageLifecycleRunModel)
                .order_by(StorageLifecycleRunModel.started_at.desc())
                .limit(limit)
            )
        ).all()
    )
