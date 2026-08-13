from datetime import datetime, timedelta, timezone
import copy
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import AssetScopeType, AssetStatus, PresentationEntryStatus, WorkspaceRole
from models.sql.enterprise.asset_item import AssetItemModel
from models.sql.enterprise.asset_usage import AssetUsageEventModel
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.workspace import WorkspaceMemberModel
from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from services.enterprise.audit_service import record_audit_event
from services.enterprise.workspace_service import require_workspace_role


ALLOWED_ASSET_TYPES = {"page", "chart", "image", "logo", "copy", "component"}


def _preview_text(value: object, keys: tuple[str, ...]) -> str | None:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()[:160]
        for candidate in value.values():
            found = _preview_text(candidate, keys)
            if found:
                return found
    elif isinstance(value, list):
        for candidate in value:
            found = _preview_text(candidate, keys)
            if found:
                return found
    return None


def _count_preview_elements(value: object) -> int:
    if isinstance(value, dict):
        own = len(value.get("elements", [])) if isinstance(value.get("elements"), list) else 0
        return own + sum(_count_preview_elements(candidate) for candidate in value.values())
    if isinstance(value, list):
        return sum(_count_preview_elements(candidate) for candidate in value)
    return 0


def _build_preview(*, name: str, payload: dict, asset_type: str) -> dict:
    content = payload.get("content") or {}
    ui = payload.get("ui") or {}
    digest = _canonical_hash(payload)
    palette = ["#635BFF", "#0E7490", "#B54708", "#175CD3", "#067647", "#C11574"]
    return {
        "kind": "structured-v1",
        "title": _preview_text(content, ("title", "heading", "name", "text")) or name,
        "subtitle": _preview_text(content, ("subtitle", "description", "summary")),
        "layout": payload.get("layout") or asset_type,
        "element_count": _count_preview_elements(ui),
        "accent": palette[int(digest[:2], 16) % len(palette)],
    }


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _validate_scope(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    scope_type: AssetScopeType,
    workspace_id: uuid.UUID | None,
    required_role: WorkspaceRole,
) -> uuid.UUID | None:
    if scope_type == AssetScopeType.ENTERPRISE:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="Enterprise asset administrator required")
        if workspace_id is not None:
            raise HTTPException(status_code=422, detail="Enterprise asset cannot belong to a workspace")
        return None
    if scope_type == AssetScopeType.PERSONAL:
        return None
    if workspace_id is None:
        raise HTTPException(status_code=422, detail="Workspace is required for workspace asset")
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=required_role)
    return workspace_id


async def create_asset(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    values: dict,
) -> AssetItemModel:
    scope_type = AssetScopeType(values.pop("scope_type"))
    workspace_id = await _validate_scope(
        session,
        principal=principal,
        scope_type=scope_type,
        workspace_id=values.pop("workspace_id", None),
        required_role=WorkspaceRole.EDITOR,
    )
    asset_type = values.get("asset_type")
    if asset_type not in ALLOWED_ASSET_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported asset type")
    payload = values.get("payload") or {}
    values.setdefault("preview", _build_preview(name=values["name"], payload=payload, asset_type=asset_type))
    asset = AssetItemModel(
        workspace_id=workspace_id,
        created_by=principal.user_id,
        scope_type=scope_type,
        payload_hash=_canonical_hash(payload),
        **values,
    )
    session.add(asset)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="asset.created",
        resource_type="asset_item",
        resource_id=asset.id,
        metadata={"asset_type": asset.asset_type, "scope_type": scope_type.value},
    )
    await session.commit()
    await session.refresh(asset)
    return asset


async def save_slide_as_asset(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    slide_id: uuid.UUID,
    values: dict,
) -> AssetItemModel:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.EDITOR)
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    slide = await session.scalar(
        select(SlideModel).execution_options(skip_owner_scope=True).where(
            SlideModel.id == slide_id,
            SlideModel.presentation == entry.presentation_id,
        )
    )
    if slide is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    payload = {
        "format": "presentation-page-v1",
        "layout_group": slide.layout_group,
        "layout": slide.layout,
        "content": copy.deepcopy(slide.content),
        "html_content": slide.html_content,
        "speaker_note": slide.speaker_note,
        "properties": copy.deepcopy(slide.properties),
        "ui": copy.deepcopy(slide.ui),
    }
    scope_type = AssetScopeType(values.get("scope_type", AssetScopeType.PERSONAL))
    values.update({
        "scope_type": scope_type,
        "workspace_id": workspace_id if scope_type == AssetScopeType.WORKSPACE else None,
        "asset_type": "page",
        "payload": payload,
        "source_presentation_entry_id": entry.id,
        "source_slide_id": slide.id,
        "scene_type": values.get("scene_type") or entry.scene_type,
        "compatibility": {"presentation_version": "v2-standard", "editable": True},
    })
    return await create_asset(session, principal=principal, values=values)


async def list_assets(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID | None,
    asset_type: str | None,
    status: AssetStatus | None,
    query: str | None,
    tags: list[str],
) -> list[AssetItemModel]:
    if workspace_id is not None:
        await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    member_workspace_ids = select(WorkspaceMemberModel.workspace_id).where(WorkspaceMemberModel.user_id == principal.user_id)
    governed_workspace_ids = select(WorkspaceMemberModel.workspace_id).where(
        WorkspaceMemberModel.user_id == principal.user_id,
        WorkspaceMemberModel.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
    )
    visibility = or_(
        (AssetItemModel.scope_type == AssetScopeType.PERSONAL) & (AssetItemModel.created_by == principal.user_id),
        (AssetItemModel.scope_type == AssetScopeType.WORKSPACE) & AssetItemModel.workspace_id.in_(member_workspace_ids) & (AssetItemModel.status == AssetStatus.PUBLISHED),
        (AssetItemModel.scope_type == AssetScopeType.WORKSPACE) & (AssetItemModel.created_by == principal.user_id),
        (AssetItemModel.scope_type == AssetScopeType.WORKSPACE) & AssetItemModel.workspace_id.in_(governed_workspace_ids),
        (AssetItemModel.scope_type == AssetScopeType.ENTERPRISE) & (AssetItemModel.status == AssetStatus.PUBLISHED),
    )
    if principal.is_admin:
        visibility = or_(visibility, AssetItemModel.scope_type == AssetScopeType.ENTERPRISE)
    statement = select(AssetItemModel).where(visibility)
    if workspace_id is not None:
        statement = statement.where(or_(
            AssetItemModel.scope_type.in_([AssetScopeType.PERSONAL, AssetScopeType.ENTERPRISE]),
            AssetItemModel.workspace_id == workspace_id,
        ))
    if asset_type:
        statement = statement.where(AssetItemModel.asset_type == asset_type)
    if status:
        statement = statement.where(AssetItemModel.status == status)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(or_(AssetItemModel.name.ilike(pattern), AssetItemModel.description.ilike(pattern)))
    assets = list((await session.scalars(statement.order_by(AssetItemModel.updated_at.desc()).limit(200))).all())
    if tags:
        required = set(tags)
        assets = [asset for asset in assets if required.issubset(set(asset.tags or []))]
    return assets


async def _require_asset_access(session: AsyncSession, *, asset_id: uuid.UUID, principal: AuthPrincipal) -> AssetItemModel:
    asset = await session.get(AssetItemModel, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    visible = asset.created_by == principal.user_id or (asset.status == AssetStatus.PUBLISHED and asset.scope_type == AssetScopeType.ENTERPRISE)
    if asset.scope_type == AssetScopeType.WORKSPACE and asset.workspace_id:
        try:
            await require_workspace_role(session, workspace_id=asset.workspace_id, principal=principal)
            visible = visible or asset.status == AssetStatus.PUBLISHED
        except HTTPException:
            pass
    if not visible and not principal.is_admin:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


async def transition_asset(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    principal: AuthPrincipal,
    action: str,
) -> AssetItemModel:
    asset, target = await _resolve_asset_transition(
        session, asset_id=asset_id, principal=principal, action=action
    )
    _apply_asset_transition(asset, target=target, principal=principal)
    session.add(asset)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=asset.workspace_id, action=f"asset.{action}", resource_type="asset_item", resource_id=asset.id)
    await session.commit()
    await session.refresh(asset)
    return asset


async def _resolve_asset_transition(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    principal: AuthPrincipal,
    action: str,
) -> tuple[AssetItemModel, AssetStatus]:
    asset = await session.get(AssetItemModel, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    scope = AssetScopeType(asset.scope_type)
    if scope == AssetScopeType.PERSONAL:
        if asset.created_by != principal.user_id:
            raise HTTPException(status_code=404, detail="Asset not found")
    else:
        await _validate_scope(session, principal=principal, scope_type=scope, workspace_id=asset.workspace_id, required_role=WorkspaceRole.ADMIN)
    transitions = {
        (AssetStatus.DRAFT, "publish"): AssetStatus.PUBLISHED,
        (AssetStatus.DRAFT, "archive"): AssetStatus.ARCHIVED,
        (AssetStatus.PUBLISHED, "offline"): AssetStatus.OFFLINE,
        (AssetStatus.OFFLINE, "publish"): AssetStatus.PUBLISHED,
        (AssetStatus.OFFLINE, "archive"): AssetStatus.ARCHIVED,
    }
    target = transitions.get((AssetStatus(asset.status), action))
    if target is None:
        raise HTTPException(status_code=409, detail="Invalid asset transition")
    return asset, target


def _apply_asset_transition(
    asset: AssetItemModel,
    *,
    target: AssetStatus,
    principal: AuthPrincipal,
) -> None:
    asset.status = target
    if target == AssetStatus.PUBLISHED:
        asset.published_by = principal.user_id
        asset.published_at = datetime.now(timezone.utc)


async def bulk_transition_assets(
    session: AsyncSession,
    *,
    asset_ids: list[uuid.UUID],
    principal: AuthPrincipal,
    action: str,
) -> list[AssetItemModel]:
    if len(set(asset_ids)) != len(asset_ids):
        raise HTTPException(status_code=422, detail="Asset ids must be unique")
    resolved = [
        await _resolve_asset_transition(
            session, asset_id=asset_id, principal=principal, action=action
        )
        for asset_id in asset_ids
    ]
    assets: list[AssetItemModel] = []
    for asset, target in resolved:
        _apply_asset_transition(asset, target=target, principal=principal)
        session.add(asset)
        assets.append(asset)
        record_audit_event(
            session,
            actor_id=principal.user_id,
            workspace_id=asset.workspace_id,
            action=f"asset.bulk_{action}",
            resource_type="asset_item",
            resource_id=asset.id,
            metadata={"batch_size": len(resolved)},
        )
    await session.commit()
    for asset in assets:
        await session.refresh(asset)
    return assets


async def insert_asset_page(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
    after_index: int | None,
) -> SlideModel:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.EDITOR)
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    if PresentationEntryStatus(entry.status) != PresentationEntryStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft presentation accepts reusable assets")
    asset = await _require_asset_access(session, asset_id=asset_id, principal=principal)
    if AssetStatus(asset.status) in (AssetStatus.OFFLINE, AssetStatus.ARCHIVED):
        raise HTTPException(status_code=409, detail="Asset is not available")
    if asset.status != AssetStatus.PUBLISHED and asset.created_by != principal.user_id:
        raise HTTPException(status_code=409, detail="Asset is not published")
    if asset.authorization_status == "revoked":
        raise HTTPException(status_code=409, detail="Asset authorization is revoked")
    if asset.asset_type != "page" or asset.payload.get("format") != "presentation-page-v1":
        raise HTTPException(status_code=422, detail="Asset cannot be inserted as a page")
    expires_at = asset.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="Asset authorization has expired")
    presentation = await session.scalar(select(PresentationModel).execution_options(skip_owner_scope=True).where(PresentationModel.id == entry.presentation_id))
    if presentation is None:
        raise HTTPException(status_code=409, detail="Presentation is missing")
    max_index = await session.scalar(select(SlideModel.index).execution_options(skip_owner_scope=True).where(SlideModel.presentation == presentation.id).order_by(SlideModel.index.desc()).limit(1))
    insert_index = (max_index + 1 if max_index is not None else 0) if after_index is None else min(max(after_index + 1, 0), (max_index + 1 if max_index is not None else 0))
    await session.execute(update(SlideModel).where(SlideModel.presentation == presentation.id, SlideModel.index >= insert_index).values(index=SlideModel.index + 1))
    payload = asset.payload
    slide = SlideModel(
        owner_id=presentation.owner_id,
        presentation=presentation.id,
        layout_group=payload.get("layout_group") or "asset",
        layout=payload.get("layout") or "asset-page",
        index=insert_index,
        content=copy.deepcopy(payload.get("content") or {}),
        html_content=payload.get("html_content"),
        speaker_note=payload.get("speaker_note"),
        properties=copy.deepcopy(payload.get("properties")),
        ui=copy.deepcopy(payload.get("ui")),
    )
    presentation.n_slides = (max_index + 2) if max_index is not None else 1
    asset.usage_count += 1
    usage_event = AssetUsageEventModel(
        asset_id=asset.id,
        workspace_id=workspace_id,
        presentation_entry_id=entry.id,
        slide_id=slide.id,
        reused_by=principal.user_id,
        insert_index=insert_index,
    )
    session.add_all([slide, presentation, asset, usage_event])
    record_audit_event(session, actor_id=principal.user_id, workspace_id=workspace_id, action="asset.reused", resource_type="asset_item", resource_id=asset.id, metadata={"entry_id": str(entry.id), "slide_id": str(slide.id), "insert_index": insert_index})
    await session.commit()
    await session.refresh(slide)
    return slide


async def get_asset_analytics(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
) -> dict:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    assets = await list_assets(
        session,
        principal=principal,
        workspace_id=workspace_id,
        asset_type=None,
        status=None,
        query=None,
        tags=[],
    )
    asset_ids = [asset.id for asset in assets]
    now = datetime.now(timezone.utc)
    due_limit = now + timedelta(days=7)
    by_scope: dict[str, int] = {}
    by_type: dict[str, int] = {}
    expiring = 0
    expired = 0
    for asset in assets:
        scope = AssetScopeType(asset.scope_type).value
        by_scope[scope] = by_scope.get(scope, 0) + 1
        by_type[asset.asset_type] = by_type.get(asset.asset_type, 0) + 1
        expires_at = asset.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                expired += 1
            elif expires_at <= due_limit:
                expiring += 1
    if asset_ids:
        events = list((await session.scalars(
            select(AssetUsageEventModel).where(
                AssetUsageEventModel.workspace_id == workspace_id,
                AssetUsageEventModel.asset_id.in_(asset_ids),
            )
        )).all())
    else:
        events = []
    reuse_counts: dict[uuid.UUID, int] = {}
    for event in events:
        reuse_counts[event.asset_id] = reuse_counts.get(event.asset_id, 0) + 1
    top_assets = sorted(assets, key=lambda item: reuse_counts.get(item.id, 0), reverse=True)[:5]
    return {
        "total_assets": len(assets),
        "published_assets": sum(1 for asset in assets if AssetStatus(asset.status) == AssetStatus.PUBLISHED),
        "expiring_within_7_days": expiring,
        "expired_assets": expired,
        "total_reuses": len(events),
        "reuses_last_30_days": sum(1 for event in events if (event.created_at.replace(tzinfo=timezone.utc) if event.created_at.tzinfo is None else event.created_at) >= now - timedelta(days=30)),
        "unique_presentations": len({event.presentation_entry_id for event in events}),
        "unique_users": len({event.reused_by for event in events if event.reused_by is not None}),
        "by_scope": by_scope,
        "by_type": by_type,
        "top_assets": [
            {
                "asset_id": asset.id,
                "name": asset.name,
                "asset_type": asset.asset_type,
                "scope_type": asset.scope_type,
                "reuse_count": reuse_counts.get(asset.id, 0),
            }
            for asset in top_assets
        ],
    }
