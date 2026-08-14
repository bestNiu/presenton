from datetime import datetime, timezone
import os
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import WorkspaceRole
from models.sql.enterprise.bid import BidDownloadGrantModel
from models.sql.enterprise.delivery_integrity_incident import DeliveryIntegrityIncidentModel
from models.sql.enterprise.presentation_governance import PresentationDownloadGrantModel
from models.sql.enterprise.workspace import WorkspaceMemberModel, WorkspaceModel
from models.sql.user import User
from services.enterprise.audit_service import record_audit_event
from services.enterprise.workspace_service import require_workspace_role


ACTIVE_INCIDENT_STATUSES = {"open", "in_progress"}
CLOSED_INCIDENT_STATUSES = {"resolved", "accepted_risk", "false_positive"}
INCIDENT_STATUSES = ACTIVE_INCIDENT_STATUSES | CLOSED_INCIDENT_STATUSES


def _anomaly_types(item: dict) -> list[str]:
    anomalies = []
    if not item["file_integrity"]:
        anomalies.append("file_integrity")
    if not item["snapshot_integrity"]:
        anomalies.append("snapshot_integrity")
    if item["citation_integrity"] is False:
        anomalies.append("citation_integrity")
    return anomalies


async def _revoke_active_grants(
    session: AsyncSession,
    *,
    scene_type: str,
    artifact_id: uuid.UUID,
    revoked_at: datetime,
) -> int:
    model = PresentationDownloadGrantModel if scene_type == "general" else BidDownloadGrantModel
    grants = list(
        (
            await session.scalars(
                select(model).where(model.artifact_id == artifact_id, model.revoked_at.is_(None))
            )
        ).all()
    )
    for grant in grants:
        grant.revoked_at = revoked_at
        session.add(grant)
    return len(grants)


async def synchronize_delivery_integrity_incidents(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    items: list[dict],
    actor_id: uuid.UUID | None,
) -> dict:
    now = datetime.now(timezone.utc)
    artifact_ids = [item["artifact_id"] for item in items]
    incidents = list(
        (
            await session.scalars(
                select(DeliveryIntegrityIncidentModel).where(
                    DeliveryIntegrityIncidentModel.workspace_id == workspace_id,
                    DeliveryIntegrityIncidentModel.artifact_id.in_(artifact_ids),
                )
            )
        ).all()
    ) if artifact_ids else []
    incident_map = {(item.scene_type, item.artifact_id): item for item in incidents}
    opened_ids: list[str] = []
    resolved_ids: list[str] = []
    revoked_grant_count = 0
    revoke_existing = os.getenv(
        "ENTERPRISE_DELIVERY_INTEGRITY_REVOKE_ACTIVE_GRANTS", "false"
    ).lower() in {"1", "true", "yes"}

    for item in items:
        key = (item["scene_type"], item["artifact_id"])
        incident = incident_map.get(key)
        anomalies = _anomaly_types(item)
        if anomalies:
            if incident is None:
                incident = DeliveryIntegrityIncidentModel(
                    workspace_id=workspace_id,
                    scene_type=item["scene_type"],
                    artifact_id=item["artifact_id"],
                    resource_id=item["resource_id"],
                    resource_title=item["resource_title"],
                    detail_url=item["detail_url"],
                    anomaly_types=anomalies,
                    status="open",
                    first_detected_at=now,
                    last_detected_at=now,
                    updated_at=now,
                )
                session.add(incident)
                incident_map[key] = incident
                opened_ids.append(str(incident.id))
            else:
                previous_status = incident.status
                previous_anomalies = set(incident.anomaly_types or [])
                incident.resource_title = item["resource_title"]
                incident.detail_url = item["detail_url"]
                incident.anomaly_types = anomalies
                incident.last_detected_at = now
                incident.updated_at = now
                incident.occurrence_count += 1
                if previous_status == "resolved" or (
                    previous_status in {"accepted_risk", "false_positive"}
                    and set(anomalies) != previous_anomalies
                ):
                    incident.status = "open"
                    incident.resolved_at = None
                    incident.resolved_by = None
                    incident.resolution_note = None
                    opened_ids.append(str(incident.id))
                session.add(incident)
            if revoke_existing and incident.status in ACTIVE_INCIDENT_STATUSES:
                revoked_grant_count += await _revoke_active_grants(
                    session,
                    scene_type=item["scene_type"],
                    artifact_id=item["artifact_id"],
                    revoked_at=now,
                )
        elif incident is not None and incident.status in ACTIVE_INCIDENT_STATUSES:
            incident.status = "resolved"
            incident.resolved_at = now
            incident.resolved_by = actor_id
            incident.resolution_note = "完整性复检通过，系统自动关闭。"
            incident.updated_at = now
            session.add(incident)
            resolved_ids.append(str(incident.id))

    if opened_ids or resolved_ids:
        record_audit_event(
            session,
            actor_id=actor_id,
            workspace_id=workspace_id,
            action="delivery_integrity.incidents_synchronized",
            resource_type="enterprise_workspace",
            resource_id=workspace_id,
            metadata={
                "opened_ids": opened_ids,
                "resolved_ids": resolved_ids,
                "revoked_grant_count": revoked_grant_count,
            },
        )
    return {
        "opened_ids": opened_ids,
        "resolved_ids": resolved_ids,
        "revoked_grant_count": revoked_grant_count,
    }


async def ensure_delivery_not_quarantined(
    session: AsyncSession,
    *,
    scene_type: str,
    artifact_id: uuid.UUID,
) -> None:
    incident = await session.scalar(
        select(DeliveryIntegrityIncidentModel).where(
            DeliveryIntegrityIncidentModel.scene_type == scene_type,
            DeliveryIntegrityIncidentModel.artifact_id == artifact_id,
            DeliveryIntegrityIncidentModel.status.in_(ACTIVE_INCIDENT_STATUSES),
        )
    )
    if incident is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Delivery authorization paused by integrity incident {incident.id}",
        )


async def _serialize_incidents(
    session: AsyncSession,
    incidents: list[DeliveryIntegrityIncidentModel],
) -> list[dict]:
    workspace_ids = {item.workspace_id for item in incidents}
    user_ids = {item.assigned_to for item in incidents if item.assigned_to}
    workspaces = list(
        (await session.scalars(select(WorkspaceModel).where(WorkspaceModel.id.in_(workspace_ids)))).all()
    ) if workspace_ids else []
    users = list(
        (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()
    ) if user_ids else []
    workspace_names = {item.id: item.name for item in workspaces}
    usernames = {item.id: item.username for item in users}
    return [
        {
            "id": item.id,
            "workspace_id": item.workspace_id,
            "workspace_name": workspace_names.get(item.workspace_id, "未知工作区"),
            "scene_type": item.scene_type,
            "artifact_id": item.artifact_id,
            "resource_id": item.resource_id,
            "resource_title": item.resource_title,
            "detail_url": item.detail_url,
            "anomaly_types": item.anomaly_types,
            "severity": item.severity,
            "status": item.status,
            "authorization_paused": item.status in ACTIVE_INCIDENT_STATUSES,
            "assigned_to": item.assigned_to,
            "assigned_to_username": usernames.get(item.assigned_to),
            "occurrence_count": item.occurrence_count,
            "resolution_note": item.resolution_note,
            "resolved_by": item.resolved_by,
            "first_detected_at": item.first_detected_at,
            "last_detected_at": item.last_detected_at,
            "resolved_at": item.resolved_at,
            "updated_at": item.updated_at,
        }
        for item in incidents
    ]


async def list_delivery_integrity_incidents(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID | None = None,
    status: str | None = None,
    scene_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    if workspace_id is None:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="Platform administrator required")
    elif not principal.is_admin:
        await require_workspace_role(
            session,
            workspace_id=workspace_id,
            principal=principal,
            required_role=WorkspaceRole.ADMIN,
        )
    query = select(DeliveryIntegrityIncidentModel)
    if workspace_id:
        query = query.where(DeliveryIntegrityIncidentModel.workspace_id == workspace_id)
    if status:
        query = query.where(DeliveryIntegrityIncidentModel.status == status)
    if scene_type:
        query = query.where(DeliveryIntegrityIncidentModel.scene_type == scene_type)
    incidents = list(
        (
            await session.scalars(
                query.order_by(DeliveryIntegrityIncidentModel.updated_at.desc()).limit(limit)
            )
        ).all()
    )
    return await _serialize_incidents(session, incidents)


async def update_delivery_integrity_incident(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    principal: AuthPrincipal,
    status: str | None,
    assigned_to: uuid.UUID | None,
    resolution_note: str | None,
    workspace_id: uuid.UUID | None = None,
) -> dict:
    incident = await session.get(DeliveryIntegrityIncidentModel, incident_id)
    if incident is None or (workspace_id is not None and incident.workspace_id != workspace_id):
        raise HTTPException(status_code=404, detail="Delivery integrity incident not found")
    if not principal.is_admin:
        await require_workspace_role(
            session,
            workspace_id=incident.workspace_id,
            principal=principal,
            required_role=WorkspaceRole.ADMIN,
        )
    if status is not None and status not in INCIDENT_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid delivery integrity incident status")
    if status == "resolved":
        raise HTTPException(
            status_code=409,
            detail="Resolved status requires a successful integrity recheck",
        )
    if assigned_to is not None:
        assignee = await session.scalar(
            select(WorkspaceMemberModel).where(
                WorkspaceMemberModel.workspace_id == incident.workspace_id,
                WorkspaceMemberModel.user_id == assigned_to,
            )
        )
        if assignee is None:
            raise HTTPException(status_code=422, detail="Assignee must be a workspace member")
    if status in CLOSED_INCIDENT_STATUSES and not (resolution_note or "").strip():
        raise HTTPException(status_code=422, detail="Resolution note is required when closing an incident")
    previous_status = incident.status
    if status is not None:
        incident.status = status
    if assigned_to is not None:
        incident.assigned_to = assigned_to
    if resolution_note is not None:
        incident.resolution_note = resolution_note.strip() or None
    now = datetime.now(timezone.utc)
    if incident.status in CLOSED_INCIDENT_STATUSES:
        incident.resolved_at = now
        incident.resolved_by = principal.user_id
    elif previous_status in CLOSED_INCIDENT_STATUSES:
        incident.resolved_at = None
        incident.resolved_by = None
    incident.updated_at = now
    session.add(incident)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=incident.workspace_id,
        action="delivery_integrity.incident_updated",
        resource_type="delivery_integrity_incident",
        resource_id=incident.id,
        metadata={
            "previous_status": previous_status,
            "status": incident.status,
            "assigned_to": str(assigned_to) if assigned_to else None,
            "resolution_note": incident.resolution_note,
        },
    )
    await session.commit()
    return (await _serialize_incidents(session, [incident]))[0]


async def recheck_delivery_integrity_incident(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID | None = None,
) -> dict:
    incident = await session.get(DeliveryIntegrityIncidentModel, incident_id)
    if incident is None or (workspace_id is not None and incident.workspace_id != workspace_id):
        raise HTTPException(status_code=404, detail="Delivery integrity incident not found")
    if not principal.is_admin:
        await require_workspace_role(
            session,
            workspace_id=incident.workspace_id,
            principal=principal,
            required_role=WorkspaceRole.ADMIN,
        )
    from services.enterprise.delivery_center_service import get_delivery_center

    center = await get_delivery_center(
        session,
        workspace_id=incident.workspace_id,
        principal=principal,
        skip_access_check=principal.is_admin,
    )
    item = next(
        (row for row in center["items"] if row["artifact_id"] == incident.artifact_id),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Delivery artifact no longer exists")
    await synchronize_delivery_integrity_incidents(
        session,
        workspace_id=incident.workspace_id,
        items=[item],
        actor_id=principal.user_id,
    )
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=incident.workspace_id,
        action="delivery_integrity.incident_rechecked",
        resource_type="delivery_integrity_incident",
        resource_id=incident.id,
        metadata={"integrity_status": item["integrity_status"]},
    )
    await session.commit()
    refreshed = await session.get(DeliveryIntegrityIncidentModel, incident.id)
    return (await _serialize_incidents(session, [refreshed]))[0]
