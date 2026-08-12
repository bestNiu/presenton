from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from api.v1.auth.context import get_current_owner_id
from domains.platform.enums import (
    TemplatePublicationStatus,
    TemplateScopeType,
    WorkspaceRole,
)
from models.sql.enterprise.template_publication import TemplatePublicationModel
from models.sql.enterprise.workspace import WorkspaceMemberModel
from models.sql.template_v2 import TemplateV2
from services.enterprise.audit_service import record_audit_event
from services.enterprise.workspace_service import require_workspace_role


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _require_scope_role(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    scope_type: TemplateScopeType,
    workspace_id: uuid.UUID | None,
    required_role: WorkspaceRole,
) -> None:
    if scope_type == TemplateScopeType.ENTERPRISE:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="Enterprise template admin required")
        if workspace_id is not None:
            raise HTTPException(
                status_code=422,
                detail="Enterprise templates cannot belong to a workspace",
            )
        return
    if workspace_id is None:
        raise HTTPException(
            status_code=422, detail="Workspace is required for this template scope"
        )
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=required_role,
    )


async def create_template_publication(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    template_id: str,
    publication_key: str,
    version: int,
    scope_type: TemplateScopeType,
    workspace_id: uuid.UUID | None,
    scene_type: str | None,
    display_name: str | None,
    description: str | None,
    rules: dict,
    compatibility: dict,
    preview_url: str | None,
    recommended_order: int,
) -> TemplatePublicationModel:
    await _require_scope_role(
        session,
        principal=principal,
        scope_type=scope_type,
        workspace_id=workspace_id,
        required_role=WorkspaceRole.EDITOR,
    )
    if scope_type == TemplateScopeType.SCENE and not (scene_type or "").strip():
        raise HTTPException(status_code=422, detail="Scene type is required")
    if scope_type != TemplateScopeType.SCENE and scene_type is not None:
        raise HTTPException(
            status_code=422, detail="Scene type is valid only for scene templates"
        )
    template = await session.get(TemplateV2, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if not isinstance(template.layouts, dict) or not template.layouts:
        raise HTTPException(
            status_code=422, detail="Template must contain generated layouts"
        )
    normalized_key = publication_key.strip()
    if not normalized_key:
        raise HTTPException(status_code=422, detail="Publication key is required")
    if preview_url is None and isinstance(template.assets, dict):
        preview_urls = template.assets.get("slide_image_urls")
        if isinstance(preview_urls, list) and preview_urls:
            first_preview = preview_urls[0]
            if isinstance(first_preview, str) and first_preview.strip():
                preview_url = first_preview.strip()
    publication = TemplatePublicationModel(
        publication_key=normalized_key,
        template_id=template.id,
        workspace_id=workspace_id,
        created_by=principal.user_id,
        scope_type=scope_type,
        scene_type=scene_type.strip().lower() if scene_type else None,
        version=version,
        display_name=(display_name or template.name).strip(),
        description=(description or template.description),
        rules=rules,
        compatibility=compatibility,
        preview_url=preview_url,
        recommended_order=recommended_order,
    )
    session.add(publication)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="template.publication_created",
        resource_type="template_publication",
        resource_id=publication.id,
        metadata={
            "template_id": template.id,
            "scope_type": scope_type.value,
            "version": version,
        },
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Template or publication version is already registered",
        ) from exc
    await session.refresh(publication)
    return publication


async def get_manageable_publication(
    session: AsyncSession,
    *,
    publication_id: uuid.UUID,
    principal: AuthPrincipal,
    required_role: WorkspaceRole = WorkspaceRole.EDITOR,
) -> TemplatePublicationModel:
    publication = await session.get(TemplatePublicationModel, publication_id)
    if publication is None:
        raise HTTPException(status_code=404, detail="Template publication not found")
    await _require_scope_role(
        session,
        principal=principal,
        scope_type=TemplateScopeType(publication.scope_type),
        workspace_id=publication.workspace_id,
        required_role=required_role,
    )
    return publication


async def list_visible_publications(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID | None,
    status: TemplatePublicationStatus | None,
) -> list[TemplatePublicationModel]:
    member_workspace_ids = select(WorkspaceMemberModel.workspace_id).where(
        WorkspaceMemberModel.user_id == principal.user_id
    )
    manageable_workspace_ids = select(WorkspaceMemberModel.workspace_id).where(
        WorkspaceMemberModel.user_id == principal.user_id,
        WorkspaceMemberModel.role != WorkspaceRole.VIEWER,
    )
    visibility = or_(
        TemplatePublicationModel.status == TemplatePublicationStatus.PUBLISHED,
        (
            TemplatePublicationModel.workspace_id.in_(manageable_workspace_ids)
            & (
                TemplatePublicationModel.status
                != TemplatePublicationStatus.PUBLISHED
            )
        ),
    )
    visibility = visibility & or_(
        TemplatePublicationModel.scope_type == TemplateScopeType.ENTERPRISE,
        TemplatePublicationModel.workspace_id.in_(member_workspace_ids),
        TemplatePublicationModel.workspace_id.in_(manageable_workspace_ids),
    )
    if principal.is_admin:
        visibility = or_(
            visibility,
            TemplatePublicationModel.scope_type == TemplateScopeType.ENTERPRISE,
        )
    query = select(TemplatePublicationModel).where(visibility)
    if workspace_id is not None:
        query = query.where(
            or_(
                TemplatePublicationModel.workspace_id == workspace_id,
                TemplatePublicationModel.scope_type == TemplateScopeType.ENTERPRISE,
            )
        )
    if status is not None:
        query = query.where(TemplatePublicationModel.status == status)
    return list(
        (
            await session.scalars(
                query.order_by(
                    TemplatePublicationModel.recommended_order.desc(),
                    TemplatePublicationModel.updated_at.desc(),
                )
            )
        ).all()
    )


async def transition_publication(
    session: AsyncSession,
    *,
    publication_id: uuid.UUID,
    principal: AuthPrincipal,
    action: str,
) -> TemplatePublicationModel:
    required_role = (
        WorkspaceRole.ADMIN
        if action in {"publish", "reject", "offline", "archive"}
        else WorkspaceRole.EDITOR
    )
    publication = await get_manageable_publication(
        session,
        publication_id=publication_id,
        principal=principal,
        required_role=required_role,
    )
    transitions = {
        "submit": (
            {TemplatePublicationStatus.DRAFT},
            TemplatePublicationStatus.IN_REVIEW,
        ),
        "publish": (
            {TemplatePublicationStatus.IN_REVIEW},
            TemplatePublicationStatus.PUBLISHED,
        ),
        "reject": (
            {TemplatePublicationStatus.IN_REVIEW},
            TemplatePublicationStatus.DRAFT,
        ),
        "offline": (
            {TemplatePublicationStatus.PUBLISHED},
            TemplatePublicationStatus.OFFLINE,
        ),
        "archive": (
            {TemplatePublicationStatus.DRAFT, TemplatePublicationStatus.OFFLINE},
            TemplatePublicationStatus.ARCHIVED,
        ),
    }
    allowed, target = transitions[action]
    current = TemplatePublicationStatus(publication.status)
    if current not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot {action} template publication from {current.value}",
        )
    if action == "publish":
        if not publication.preview_url:
            raise HTTPException(
                status_code=422,
                detail="Template preview is required before publication",
            )
        if publication.compatibility.get("pptx") is not True:
            raise HTTPException(
                status_code=422,
                detail="PPTX compatibility must be validated before publication",
            )
    publication.status = target
    if action == "submit":
        publication.submitted_at = _now()
    elif action == "publish":
        publication.published_at = _now()
    elif action == "offline":
        publication.offline_at = _now()
        publication.is_default = False
    session.add(publication)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=publication.workspace_id,
        action=f"template.{action}",
        resource_type="template_publication",
        resource_id=publication.id,
        metadata={"from": current.value, "to": target.value},
    )
    await session.commit()
    await session.refresh(publication)
    return publication


async def set_default_publication(
    session: AsyncSession,
    *,
    publication_id: uuid.UUID,
    principal: AuthPrincipal,
) -> TemplatePublicationModel:
    publication = await get_manageable_publication(
        session,
        publication_id=publication_id,
        principal=principal,
        required_role=WorkspaceRole.ADMIN,
    )
    if TemplatePublicationStatus(publication.status) != TemplatePublicationStatus.PUBLISHED:
        raise HTTPException(status_code=409, detail="Only published templates can be default")
    await session.execute(
        update(TemplatePublicationModel)
        .where(
            TemplatePublicationModel.scope_type == publication.scope_type,
            TemplatePublicationModel.workspace_id == publication.workspace_id,
            TemplatePublicationModel.scene_type == publication.scene_type,
            TemplatePublicationModel.is_default.is_(True),
        )
        .values(is_default=False)
    )
    publication.is_default = True
    session.add(publication)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=publication.workspace_id,
        action="template.default_set",
        resource_type="template_publication",
        resource_id=publication.id,
    )
    await session.commit()
    await session.refresh(publication)
    return publication


async def template_is_published(session: AsyncSession, template_id: str) -> bool:
    rows = await session.scalars(
        select(TemplatePublicationModel.id)
        .where(
            TemplatePublicationModel.template_id == template_id,
            TemplatePublicationModel.published_at.is_not(None),
        )
        .limit(1)
    )
    if hasattr(rows, "first"):
        return rows.first() is not None
    return next(iter(rows), None) is not None


async def get_accessible_published_template(
    session: AsyncSession,
    template_id: str,
    *,
    user_id: uuid.UUID | None = None,
) -> TemplateV2 | None:
    """Resolve a published template without widening normal template ownership rules."""
    effective_user_id = user_id or get_current_owner_id()
    if effective_user_id is None:
        return None

    member_workspace_ids = select(WorkspaceMemberModel.workspace_id).where(
        WorkspaceMemberModel.user_id == effective_user_id
    )
    publication_rows = await session.scalars(
        select(TemplatePublicationModel.id)
        .where(
            TemplatePublicationModel.template_id == template_id,
            TemplatePublicationModel.status == TemplatePublicationStatus.PUBLISHED,
            or_(
                TemplatePublicationModel.scope_type == TemplateScopeType.ENTERPRISE,
                TemplatePublicationModel.workspace_id.in_(member_workspace_ids),
            ),
        )
        .limit(1)
    )
    publication_id = publication_rows.first()
    if publication_id is None:
        return None

    template_rows = await session.scalars(
        select(TemplateV2)
        .where(TemplateV2.id == template_id)
        .execution_options(skip_owner_scope=True)
    )
    return template_rows.first()
