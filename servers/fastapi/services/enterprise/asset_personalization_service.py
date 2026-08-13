from datetime import datetime, timezone
import math
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import AssetStatus
from models.sql.enterprise.asset_favorite import AssetFavoriteModel
from models.sql.enterprise.asset_item import AssetItemModel
from models.sql.enterprise.asset_usage import AssetUsageEventModel
from services.enterprise.asset_library_service import _require_asset_access, list_assets
from services.enterprise.audit_service import record_audit_event
from services.enterprise.workspace_service import require_workspace_role


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _available(asset: AssetItemModel) -> bool:
    if AssetStatus(asset.status) in {AssetStatus.OFFLINE, AssetStatus.ARCHIVED}:
        return False
    if asset.authorization_status == "revoked":
        return False
    return asset.expires_at is None or _aware(asset.expires_at) > datetime.now(timezone.utc)


async def set_asset_favorite(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    principal: AuthPrincipal,
    favorite: bool,
) -> dict:
    asset = await _require_asset_access(session, asset_id=asset_id, principal=principal)
    if not _available(asset):
        raise HTTPException(status_code=409, detail="Unavailable asset cannot be favorited")
    existing = await session.scalar(
        select(AssetFavoriteModel).where(
            AssetFavoriteModel.asset_id == asset.id,
            AssetFavoriteModel.user_id == principal.user_id,
        )
    )
    if favorite and existing is None:
        session.add(AssetFavoriteModel(asset_id=asset.id, user_id=principal.user_id))
    elif not favorite and existing is not None:
        await session.delete(existing)
    else:
        return {"asset_id": asset.id, "is_favorite": favorite}
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=asset.workspace_id,
        action="asset.favorited" if favorite else "asset.unfavorited",
        resource_type="asset_item",
        resource_id=asset.id,
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
    return {"asset_id": asset.id, "is_favorite": favorite}


async def list_personalized_assets(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID,
    view: str,
    scene_type: str | None,
    tags: list[str],
    limit: int,
) -> list[dict]:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    visible_assets = await list_assets(
        session,
        principal=principal,
        workspace_id=workspace_id,
        asset_type=None,
        status=None,
        query=None,
        tags=[],
    )
    available = {asset.id: asset for asset in visible_assets if _available(asset)}
    if not available:
        return []
    favorites = list((await session.scalars(
        select(AssetFavoriteModel).where(
            AssetFavoriteModel.user_id == principal.user_id,
            AssetFavoriteModel.asset_id.in_(available),
        ).order_by(AssetFavoriteModel.created_at.desc())
    )).all())
    favorite_ids = {favorite.asset_id for favorite in favorites}
    usage_events = list((await session.scalars(
        select(AssetUsageEventModel).where(
            AssetUsageEventModel.reused_by == principal.user_id,
            AssetUsageEventModel.asset_id.in_(available),
        ).order_by(AssetUsageEventModel.created_at.desc())
    )).all())
    last_used: dict[uuid.UUID, datetime] = {}
    for event in usage_events:
        last_used.setdefault(event.asset_id, event.created_at)
    if view == "favorites":
        assets = [available[item.asset_id] for item in favorites if item.asset_id in available][:limit]
        return [{"asset": asset, "is_favorite": True, "last_used_at": last_used.get(asset.id)} for asset in assets]
    if view == "recent":
        assets = [available[asset_id] for asset_id in list(last_used)[:limit]]
        return [{"asset": asset, "is_favorite": asset.id in favorite_ids, "last_used_at": last_used[asset.id]} for asset in assets]
    if view != "recommended":
        raise HTTPException(status_code=422, detail="Unsupported personalized asset view")
    history_tags: set[str] = set()
    history_scenes: set[str] = set()
    for asset_id in list(last_used)[:20]:
        asset = available[asset_id]
        history_tags.update(asset.tags or [])
        if asset.scene_type:
            history_scenes.add(asset.scene_type)
    requested_tags = {tag.strip() for tag in tags if tag.strip()}
    scored: list[tuple[float, AssetItemModel, list[str]]] = []
    for asset in available.values():
        if AssetStatus(asset.status) != AssetStatus.PUBLISHED and asset.created_by != principal.user_id:
            continue
        score = math.log1p(asset.usage_count)
        reasons: list[str] = []
        asset_tags = set(asset.tags or [])
        if scene_type and asset.scene_type == scene_type:
            score += 6
            reasons.append("适配当前场景")
        elif asset.scene_type and asset.scene_type in history_scenes:
            score += 2
            reasons.append("符合最近使用场景")
        requested_overlap = asset_tags & requested_tags
        if requested_overlap:
            score += 3 * len(requested_overlap)
            reasons.append(f"匹配标签：{'、'.join(sorted(requested_overlap)[:3])}")
        history_overlap = asset_tags & history_tags
        if history_overlap:
            score += min(3, len(history_overlap))
            reasons.append("与你最近使用的资产相似")
        if asset.id in favorite_ids:
            score += 2
            reasons.append("你已收藏")
        if asset.usage_count:
            reasons.append(f"已被复用 {asset.usage_count} 次")
        if not reasons:
            reasons.append("工作空间可用资产")
        scored.append((score, asset, reasons))
    scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
    return [
        {
            "asset": asset,
            "is_favorite": asset.id in favorite_ids,
            "last_used_at": last_used.get(asset.id),
            "recommendation_score": round(score, 3),
            "recommendation_reasons": reasons,
        }
        for score, asset, reasons in scored[:limit]
    ]
