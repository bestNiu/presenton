import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.platform.enums import AuditResult
from models.sql.enterprise.audit_event import AuditEventModel


def record_audit_event(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | str,
    workspace_id: uuid.UUID | None = None,
    result: AuditResult = AuditResult.SUCCESS,
    metadata: dict[str, Any] | None = None,
) -> AuditEventModel:
    event = AuditEventModel(
        actor_id=actor_id,
        workspace_id=workspace_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        result=result,
        event_metadata=metadata or {},
    )
    session.add(event)
    return event
