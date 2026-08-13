from datetime import datetime, timedelta, timezone
import os
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import BidDeliveryStatus, PresentationDeliveryStatus
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
from models.sql.enterprise.workspace import WorkspaceModel
from services.enterprise.audit_service import record_audit_event
from services.enterprise.object_storage_service import get_enterprise_object_storage


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _retention_days(workspace: WorkspaceModel) -> int:
    default = int(os.getenv("ENTERPRISE_OBJECT_STORAGE_REVOKED_RETENTION_DAYS", "90"))
    configured = (workspace.governance_policy or {}).get(
        "revoked_delivery_retention_days", default
    )
    return max(1, min(int(configured), 3650))


async def run_storage_lifecycle(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    execute: bool,
    max_delete: int,
) -> dict:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required")

    now = datetime.now(timezone.utc)
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

    run_id = uuid.uuid4()
    report = {
        "run_id": run_id,
        "mode": "execute" if execute else "dry_run",
        "backend": storage.backend,
        "scanned_count": len(stored_objects),
        "referenced_count": len(referenced_keys),
        "missing_referenced_count": len(expected_keys - inventory.keys()),
        "candidate_count": len(candidate_rows),
        "candidate_bytes": sum(row["size_bytes"] for row in candidate_rows),
        "deleted_count": len(deleted_keys),
        "deleted_bytes": deleted_bytes,
        "truncated": execute and len(candidate_rows) > max_delete,
        "candidates": candidate_rows[:100],
        "started_at": now,
        "completed_at": datetime.now(timezone.utc),
    }
    record_audit_event(
        session,
        actor_id=principal.user_id,
        action="storage.lifecycle_executed" if execute else "storage.lifecycle_scanned",
        resource_type="storage_lifecycle_run",
        resource_id=run_id,
        metadata={key: value for key, value in report.items() if key not in {"candidates", "run_id", "started_at", "completed_at"}},
    )
    await session.commit()
    return report
