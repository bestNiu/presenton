import json
import re
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import AssetScopeType, WorkspaceRole
from models.sql.enterprise.asset_item import AssetItemModel
from services.enterprise.asset_library_service import _require_asset_access, list_assets
from services.enterprise.audit_service import record_audit_event
from services.enterprise.workspace_service import require_workspace_role


def _terms(value: object) -> set[str]:
    text = json.dumps(value, ensure_ascii=False).lower() if not isinstance(value, str) else value.lower()
    chunks = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text)
    terms: set[str] = set()
    for chunk in chunks:
        terms.add(chunk)
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk) and len(chunk) > 1:
            terms.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return terms


def _asset_terms(asset: AssetItemModel) -> set[str]:
    return _terms({"name": asset.name, "description": asset.description, "tags": asset.tags, "preview": asset.preview, "payload": asset.payload})


def _score(query_terms: set[str], asset: AssetItemModel) -> tuple[float, list[str]]:
    if not query_terms:
        return 0.0, []
    name_terms = _terms(asset.name)
    tag_terms = _terms(asset.tags)
    all_terms = _asset_terms(asset)
    name_overlap = query_terms & name_terms
    tag_overlap = query_terms & tag_terms
    overlap = query_terms & all_terms
    coverage = len(overlap) / len(query_terms)
    score = coverage * 60 + len(name_overlap) * 12 + len(tag_overlap) * 8
    reasons = []
    if name_overlap:
        reasons.append("名称匹配")
    if tag_overlap:
        reasons.append("标签匹配")
    if overlap - name_overlap - tag_overlap:
        reasons.append("内容语义匹配")
    return round(min(score, 100), 3), reasons


async def search_assets(session: AsyncSession, *, principal: AuthPrincipal, workspace_id: uuid.UUID, query: str, asset_type: str | None, limit: int) -> list[dict]:
    assets = await list_assets(session, principal=principal, workspace_id=workspace_id, asset_type=asset_type, status=None, query=None, tags=[])
    query_terms = _terms(query.strip())
    ranked = []
    for asset in assets:
        score, reasons = _score(query_terms, asset)
        if score > 0:
            ranked.append({"asset": asset, "score": score, "reasons": reasons, "exact_duplicate": asset.duplicate_status == "suspected"})
    ranked.sort(key=lambda item: (item["score"], item["asset"].usage_count, item["asset"].updated_at), reverse=True)
    return ranked[:limit]


async def find_similar_assets(session: AsyncSession, *, principal: AuthPrincipal, asset_id: uuid.UUID, workspace_id: uuid.UUID, limit: int) -> list[dict]:
    source = await _require_asset_access(session, asset_id=asset_id, principal=principal)
    candidates = await list_assets(session, principal=principal, workspace_id=workspace_id, asset_type=source.asset_type, status=None, query=None, tags=[])
    source_terms = _asset_terms(source)
    results = []
    for candidate in candidates:
        if candidate.id == source.id:
            continue
        exact = candidate.payload_hash == source.payload_hash
        candidate_terms = _asset_terms(candidate)
        union = source_terms | candidate_terms
        similarity = 1.0 if exact else (len(source_terms & candidate_terms) / len(union) if union else 0.0)
        if exact or similarity >= 0.18:
            results.append({"asset": candidate, "score": round(similarity * 100, 3), "reasons": ["内容完全相同" if exact else "名称、标签或内容相似"], "exact_duplicate": exact})
    results.sort(key=lambda item: (item["exact_duplicate"], item["score"]), reverse=True)
    return results[:limit]


async def decide_asset_duplicate(session: AsyncSession, *, principal: AuthPrincipal, asset_id: uuid.UUID, action: str, canonical_asset_id: uuid.UUID | None) -> dict:
    asset = await _require_asset_access(session, asset_id=asset_id, principal=principal)
    if AssetScopeType(asset.scope_type) == AssetScopeType.WORKSPACE and asset.workspace_id:
        await require_workspace_role(session, workspace_id=asset.workspace_id, principal=principal, required_role=WorkspaceRole.ADMIN)
    elif AssetScopeType(asset.scope_type) == AssetScopeType.ENTERPRISE and not principal.is_admin:
        raise HTTPException(status_code=403, detail="Enterprise asset administrator required")
    elif AssetScopeType(asset.scope_type) == AssetScopeType.PERSONAL and asset.created_by != principal.user_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    if action == "confirm":
        if canonical_asset_id is None or canonical_asset_id == asset.id:
            raise HTTPException(status_code=422, detail="Canonical asset is required")
        canonical = await _require_asset_access(session, asset_id=canonical_asset_id, principal=principal)
        if canonical.asset_type != asset.asset_type:
            raise HTTPException(status_code=422, detail="Canonical asset type differs")
        if canonical.scope_type != asset.scope_type or canonical.workspace_id != asset.workspace_id:
            raise HTTPException(status_code=422, detail="Canonical asset must belong to the same asset library")
        asset.duplicate_status = "confirmed"
        asset.duplicate_of_asset_id = canonical.id
    elif action == "distinct":
        asset.duplicate_status = "distinct"
        asset.duplicate_of_asset_id = None
    else:
        raise HTTPException(status_code=422, detail="Unsupported duplicate decision")
    session.add(asset)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=asset.workspace_id, action=f"asset.duplicate_{action}", resource_type="asset_item", resource_id=asset.id, metadata={"canonical_asset_id": str(asset.duplicate_of_asset_id) if asset.duplicate_of_asset_id else None})
    await session.commit()
    return {"asset_id": asset.id, "duplicate_status": asset.duplicate_status, "duplicate_of_asset_id": asset.duplicate_of_asset_id}
