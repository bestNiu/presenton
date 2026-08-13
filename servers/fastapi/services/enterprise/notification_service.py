from datetime import datetime, timedelta, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from models.sql.enterprise.notification import EnterpriseNotificationModel
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.presentation_governance import PresentationCommentThreadModel
from domains.platform.enums import PresentationCommentStatus
from services.enterprise.workspace_service import require_workspace_role


def queue_notifications(
    session: AsyncSession,
    *,
    recipient_ids: set[uuid.UUID],
    actor_id: uuid.UUID | None,
    workspace_id: uuid.UUID | None,
    notification_type: str,
    title: str,
    body: str,
    resource_type: str,
    resource_id: uuid.UUID | str,
    action_url: str | None = None,
    metadata: dict | None = None,
) -> list[EnterpriseNotificationModel]:
    notifications = [
        EnterpriseNotificationModel(
            recipient_id=recipient_id,
            actor_id=actor_id,
            workspace_id=workspace_id,
            notification_type=notification_type,
            title=title,
            body=body,
            resource_type=resource_type,
            resource_id=str(resource_id),
            action_url=action_url,
            event_metadata=metadata or {},
        )
        for recipient_id in recipient_ids
        if recipient_id != actor_id
    ]
    session.add_all(notifications)
    return notifications


async def refresh_due_notifications(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID | None,
) -> int:
    if workspace_id is not None:
        await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    now = datetime.now(timezone.utc)
    due_limit = now + timedelta(hours=24)
    predicates = [
        PresentationCommentThreadModel.assigned_to == principal.user_id,
        PresentationCommentThreadModel.status == PresentationCommentStatus.OPEN,
        PresentationCommentThreadModel.due_at.is_not(None),
        PresentationCommentThreadModel.due_at <= due_limit,
    ]
    if workspace_id is not None:
        predicates.append(PresentationEntryModel.workspace_id == workspace_id)
    rows = list((await session.execute(
        select(PresentationCommentThreadModel, PresentationEntryModel)
        .join(PresentationEntryModel, PresentationEntryModel.id == PresentationCommentThreadModel.presentation_entry_id)
        .where(*predicates)
    )).all())
    if not rows:
        return 0
    existing = set((await session.execute(
        select(EnterpriseNotificationModel.notification_type, EnterpriseNotificationModel.resource_id).where(
            EnterpriseNotificationModel.recipient_id == principal.user_id,
            EnterpriseNotificationModel.resource_type == "presentation_comment_thread",
            EnterpriseNotificationModel.resource_id.in_([str(thread.id) for thread, _ in rows]),
            EnterpriseNotificationModel.notification_type.in_(["presentation.comment_due_soon", "presentation.comment_overdue"]),
        )
    )).all())
    created = 0
    for thread, entry in rows:
        due_at = thread.due_at
        if due_at is None:
            continue
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        notification_type = "presentation.comment_overdue" if due_at < now else "presentation.comment_due_soon"
        if (notification_type, str(thread.id)) in existing:
            continue
        queue_notifications(
            session,
            recipient_ids={principal.user_id},
            actor_id=None,
            workspace_id=entry.workspace_id,
            notification_type=notification_type,
            title="演示整改任务已逾期" if due_at < now else "演示整改任务即将到期",
            body=f"{entry.title or '演示文稿'}：{thread.title}",
            resource_type="presentation_comment_thread",
            resource_id=thread.id,
            action_url=f"/workspace/presentations/{entry.id}/review?workspace_id={entry.workspace_id}",
            metadata={"due_at": due_at.isoformat()},
        )
        created += 1
    if created:
        await session.commit()
    return created


async def list_notifications(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID | None,
    unread_only: bool,
    limit: int,
) -> dict:
    if workspace_id is not None:
        await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    predicates = [EnterpriseNotificationModel.recipient_id == principal.user_id]
    if workspace_id is not None:
        predicates.append(EnterpriseNotificationModel.workspace_id == workspace_id)
    if unread_only:
        predicates.append(EnterpriseNotificationModel.is_read.is_(False))
    notifications = list((await session.scalars(
        select(EnterpriseNotificationModel)
        .where(*predicates)
        .order_by(EnterpriseNotificationModel.created_at.desc())
        .limit(limit)
    )).all())
    unread_count = int(await session.scalar(
        select(func.count(EnterpriseNotificationModel.id)).where(
            EnterpriseNotificationModel.recipient_id == principal.user_id,
            EnterpriseNotificationModel.is_read.is_(False),
            *([EnterpriseNotificationModel.workspace_id == workspace_id] if workspace_id else []),
        )
    ) or 0)
    return {"unread_count": unread_count, "notifications": notifications}


async def mark_notification_read(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    notification_id: uuid.UUID,
) -> EnterpriseNotificationModel:
    notification = await session.get(EnterpriseNotificationModel, notification_id)
    if notification is None or notification.recipient_id != principal.user_id:
        raise HTTPException(status_code=404, detail="Notification not found")
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
    return notification


async def mark_all_notifications_read(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID | None,
) -> int:
    if workspace_id is not None:
        await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    predicates = [
        EnterpriseNotificationModel.recipient_id == principal.user_id,
        EnterpriseNotificationModel.is_read.is_(False),
    ]
    if workspace_id is not None:
        predicates.append(EnterpriseNotificationModel.workspace_id == workspace_id)
    result = await session.execute(
        update(EnterpriseNotificationModel)
        .where(*predicates)
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await session.commit()
    return result.rowcount or 0
