from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import PresentationCommentStatus, WorkspaceRole
from models.sql.enterprise.presentation_governance import (
    PresentationCommentReplyModel,
    PresentationCommentThreadModel,
)
from models.sql.enterprise.workspace import WorkspaceMemberModel
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.slide import SlideModel
from models.sql.user import User
from services.enterprise.audit_service import record_audit_event
from services.enterprise.notification_service import queue_notifications
from services.enterprise.presentation_governance_service import (
    _presentation_snapshot,
    _require_entry,
)
from services.enterprise.workspace_service import require_workspace_role


async def _require_thread(
    session: AsyncSession, *, entry_id: uuid.UUID, thread_id: uuid.UUID
) -> PresentationCommentThreadModel:
    thread = await session.get(PresentationCommentThreadModel, thread_id)
    if thread is None or thread.presentation_entry_id != entry_id:
        raise HTTPException(status_code=404, detail="Comment thread not found")
    return thread


async def _validate_assignee(
    session: AsyncSession, *, workspace_id: uuid.UUID, assigned_to: uuid.UUID | None
) -> None:
    if assigned_to is None:
        return
    membership = await session.scalar(
        select(WorkspaceMemberModel).where(
            WorkspaceMemberModel.workspace_id == workspace_id,
            WorkspaceMemberModel.user_id == assigned_to,
        )
    )
    if membership is None:
        raise HTTPException(status_code=422, detail="Assignee must be a workspace member")


async def create_comment_thread(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
    values: dict,
) -> PresentationCommentThreadModel:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.REVIEWER
    )
    entry = await _require_entry(session, workspace_id=workspace_id, entry_id=entry_id)
    await _validate_assignee(session, workspace_id=workspace_id, assigned_to=values.get("assigned_to"))
    slide_id = values.get("slide_id")
    slide_index = values.get("slide_index")
    if slide_id is not None or slide_index is not None:
        slide = await session.scalar(
            select(SlideModel)
            .execution_options(skip_owner_scope=True)
            .where(
                SlideModel.presentation == entry.presentation_id,
                SlideModel.id == slide_id if slide_id is not None else SlideModel.index == slide_index,
            )
        )
        if slide is None:
            raise HTTPException(status_code=422, detail="Slide does not belong to presentation")
        values["slide_id"] = slide.id
        values["slide_index"] = slide.index
    slide_hash, _ = await _presentation_snapshot(session, entry)
    thread = PresentationCommentThreadModel(
        presentation_entry_id=entry.id,
        slide_snapshot_hash=slide_hash,
        created_by=principal.user_id,
        **values,
    )
    session.add(thread)
    if thread.assigned_to:
        queue_notifications(
            session,
            recipient_ids={thread.assigned_to},
            actor_id=principal.user_id,
            workspace_id=workspace_id,
            notification_type="presentation.comment_assigned",
            title="收到新的演示整改任务",
            body=f"{entry.title or '演示文稿'}：{thread.title}",
            resource_type="presentation_comment_thread",
            resource_id=thread.id,
            action_url=f"/workspace/presentations/{entry.id}/review?workspace_id={workspace_id}",
            metadata={"entry_id": str(entry.id), "due_at": thread.due_at.isoformat() if thread.due_at else None},
        )
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="presentation.comment_created",
        resource_type="presentation_comment_thread",
        resource_id=thread.id,
        metadata={"entry_id": str(entry.id), "is_blocking": thread.is_blocking},
    )
    await session.commit()
    await session.refresh(thread)
    return thread


async def list_comment_threads(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
) -> list[dict]:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    await _require_entry(session, workspace_id=workspace_id, entry_id=entry_id)
    threads = list(
        (await session.scalars(
            select(PresentationCommentThreadModel)
            .where(PresentationCommentThreadModel.presentation_entry_id == entry_id)
            .order_by(PresentationCommentThreadModel.created_at.desc())
        )).all()
    )
    if not threads:
        return []
    replies = list(
        (await session.scalars(
            select(PresentationCommentReplyModel)
            .where(PresentationCommentReplyModel.thread_id.in_([thread.id for thread in threads]))
            .order_by(PresentationCommentReplyModel.created_at.asc())
        )).all()
    )
    replies_by_thread: dict[uuid.UUID, list[PresentationCommentReplyModel]] = {}
    for reply in replies:
        replies_by_thread.setdefault(reply.thread_id, []).append(reply)
    return [{"thread": thread, "replies": replies_by_thread.get(thread.id, [])} for thread in threads]


async def add_comment_reply(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    thread_id: uuid.UUID,
    principal: AuthPrincipal,
    body: str,
) -> PresentationCommentReplyModel:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.REVIEWER
    )
    entry = await _require_entry(session, workspace_id=workspace_id, entry_id=entry_id)
    thread = await _require_thread(session, entry_id=entry_id, thread_id=thread_id)
    reply = PresentationCommentReplyModel(thread_id=thread.id, body=body.strip(), created_by=principal.user_id)
    session.add(reply)
    queue_notifications(
        session,
        recipient_ids={recipient for recipient in (thread.created_by, thread.assigned_to) if recipient},
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        notification_type="presentation.comment_replied",
        title="演示整改任务有新回复",
        body=f"{entry.title or '演示文稿'}：{thread.title}",
        resource_type="presentation_comment_thread",
        resource_id=thread.id,
        action_url=f"/workspace/presentations/{entry.id}/review?workspace_id={workspace_id}",
    )
    await session.commit()
    await session.refresh(reply)
    return reply


async def transition_comment_thread(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    thread_id: uuid.UUID,
    principal: AuthPrincipal,
    action: str,
) -> PresentationCommentThreadModel:
    await require_workspace_role(
        session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.REVIEWER
    )
    entry = await _require_entry(session, workspace_id=workspace_id, entry_id=entry_id)
    thread = await _require_thread(session, entry_id=entry_id, thread_id=thread_id)
    resolved = action == "resolve"
    thread.status = PresentationCommentStatus.RESOLVED if resolved else PresentationCommentStatus.OPEN
    thread.resolved_by = principal.user_id if resolved else None
    thread.resolved_at = datetime.now(timezone.utc) if resolved else None
    session.add(thread)
    queue_notifications(
        session,
        recipient_ids={recipient for recipient in (thread.created_by, thread.assigned_to) if recipient},
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        notification_type=f"presentation.comment_{'resolved' if resolved else 'reopened'}",
        title="演示整改任务已解决" if resolved else "演示整改任务已重新打开",
        body=f"{entry.title or '演示文稿'}：{thread.title}",
        resource_type="presentation_comment_thread",
        resource_id=thread.id,
        action_url=f"/workspace/presentations/{entry.id}/review?workspace_id={workspace_id}",
    )
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action=("presentation.comment_reopened" if action == "reopen" else "presentation.comment_resolved"),
        resource_type="presentation_comment_thread",
        resource_id=thread.id,
        metadata={"entry_id": str(entry_id)},
    )
    await session.commit()
    await session.refresh(thread)
    return thread


async def count_open_blocking_comments(session: AsyncSession, *, entry_id: uuid.UUID) -> int:
    return int(await session.scalar(
        select(func.count(PresentationCommentThreadModel.id)).where(
            PresentationCommentThreadModel.presentation_entry_id == entry_id,
            PresentationCommentThreadModel.status == PresentationCommentStatus.OPEN,
            PresentationCommentThreadModel.is_blocking.is_(True),
        )
    ) or 0)


def _is_overdue(thread: PresentationCommentThreadModel, now: datetime) -> bool:
    if thread.status != PresentationCommentStatus.OPEN or thread.due_at is None:
        return False
    due_at = thread.due_at
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    return due_at < now


async def get_workspace_review_inbox(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
    scope: str,
    status: str,
    overdue_only: bool,
) -> dict:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    rows = list((await session.execute(
        select(PresentationCommentThreadModel, PresentationEntryModel)
        .join(PresentationEntryModel, PresentationEntryModel.id == PresentationCommentThreadModel.presentation_entry_id)
        .where(PresentationEntryModel.workspace_id == workspace_id)
        .order_by(
            PresentationCommentThreadModel.is_blocking.desc(),
            PresentationCommentThreadModel.due_at.asc(),
            PresentationCommentThreadModel.created_at.desc(),
        )
    )).all())
    now = datetime.now(timezone.utc)
    open_rows = [row for row in rows if row[0].status == PresentationCommentStatus.OPEN]
    assignee_ids = {thread.assigned_to for thread, _ in rows if thread.assigned_to}
    assignees = {}
    if assignee_ids:
        users = list((await session.scalars(select(User).where(User.id.in_(assignee_ids)))).all())
        assignees = {user.id: user.username for user in users}
    reply_counts = dict((await session.execute(
        select(PresentationCommentReplyModel.thread_id, func.count(PresentationCommentReplyModel.id))
        .join(PresentationCommentThreadModel, PresentationCommentThreadModel.id == PresentationCommentReplyModel.thread_id)
        .join(PresentationEntryModel, PresentationEntryModel.id == PresentationCommentThreadModel.presentation_entry_id)
        .where(PresentationEntryModel.workspace_id == workspace_id)
        .group_by(PresentationCommentReplyModel.thread_id)
    )).all())
    filtered = rows
    if scope == "mine":
        filtered = [row for row in filtered if row[0].assigned_to == principal.user_id]
    if status != "all":
        wanted = PresentationCommentStatus(status)
        filtered = [row for row in filtered if row[0].status == wanted]
    if overdue_only:
        filtered = [row for row in filtered if _is_overdue(row[0], now)]
    tasks = [
        {
            "thread": thread,
            "presentation_title": entry.title or "Untitled presentation",
            "scene_type": entry.scene_type,
            "presentation_status": entry.status,
            "assigned_to_username": assignees.get(thread.assigned_to),
            "reply_count": int(reply_counts.get(thread.id, 0)),
            "is_overdue": _is_overdue(thread, now),
        }
        for thread, entry in filtered[:200]
    ]
    return {
        "summary": {
            "open_count": len(open_rows),
            "blocking_count": sum(thread.is_blocking for thread, _ in open_rows),
            "overdue_count": sum(_is_overdue(thread, now) for thread, _ in open_rows),
            "assigned_to_me_count": sum(thread.assigned_to == principal.user_id for thread, _ in open_rows),
        },
        "tasks": tasks,
    }
