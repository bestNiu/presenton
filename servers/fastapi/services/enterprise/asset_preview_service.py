import os
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from enums.async_task_status import AsyncTaskStatus
from models.sql.async_task import AsyncTaskModel
from models.sql.enterprise.asset_item import AssetItemModel
from services.database import async_session_maker
from services.enterprise.asset_library_service import _require_asset_access
from services.enterprise.audit_service import record_audit_event
from services.enterprise.object_storage_service import (
    StoredObjectLocation,
    get_enterprise_object_storage,
)
from services.export_task_service import EXPORT_TASK_SERVICE
from utils.get_env import get_app_data_directory_env


ASSET_PREVIEW_TASK_TYPE = "enterprise.asset-preview"


async def queue_asset_preview(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    principal: AuthPrincipal,
) -> AsyncTaskModel:
    asset = await _require_asset_access(session, asset_id=asset_id, principal=principal)
    if asset.asset_type != "page" or asset.payload.get("format") != "presentation-page-v1":
        raise HTTPException(status_code=422, detail="Only reusable page assets support rendered previews")
    if asset.preview_status in {"queued", "rendering"} and asset.preview_task_id:
        existing = await session.get(AsyncTaskModel, asset.preview_task_id)
        if existing is not None:
            return existing
    task = AsyncTaskModel(
        owner_id=principal.user_id,
        type=ASSET_PREVIEW_TASK_TYPE,
        status=AsyncTaskStatus.PENDING,
        message="Queued for asset preview rendering",
        data={"asset_id": str(asset.id), "attempt": 1},
    )
    previous_task_id = asset.preview_task_id
    if previous_task_id:
        previous = await session.get(AsyncTaskModel, previous_task_id)
        attempt = int((previous.data or {}).get("attempt", 1)) + 1 if previous else 2
        task.data = {"asset_id": str(asset.id), "attempt": attempt}
    session.add(task)
    asset.preview_task_id = task.id
    asset.preview_status = "queued"
    asset.preview_error = None
    session.add(asset)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=asset.workspace_id,
        action="asset.preview_queued",
        resource_type="asset_item",
        resource_id=asset.id,
        metadata={"task_id": task.id, "retry": bool(previous_task_id)},
    )
    await session.commit()
    await session.refresh(task)
    return task


async def run_asset_preview_task(asset_id: uuid.UUID, task_id: str) -> None:
    async with async_session_maker() as session:
        asset = await session.get(AssetItemModel, asset_id)
        task = await session.get(AsyncTaskModel, task_id)
        if asset is None or task is None or asset.preview_task_id != task_id:
            return
        asset.preview_status = "rendering"
        task.message = "Rendering asset preview"
        session.add_all([asset, task])
        await session.commit()
        try:
            payload = asset.payload or {}
            html = payload.get("html_content")
            ui = payload.get("ui") or {}
            components = ui.get("components") if isinstance(ui, dict) else None
            if isinstance(html, str) and html.strip():
                result = await EXPORT_TASK_SERVICE.render_html_to_image(html, 1280, 720)
            elif isinstance(components, list):
                result = await EXPORT_TASK_SERVICE.render_json_to_image(components, 1280, 720)
            else:
                raise HTTPException(status_code=422, detail="Asset snapshot has no renderable HTML or UI components")
            stored = await get_enterprise_object_storage().put_file(
                result.path,
                f"asset-previews/{asset.id}/{asset.payload_hash[:12]}.png",
                content_type="image/png",
            )
            asset.preview_object_key = stored.object_key
            asset.preview_sha256 = stored.sha256
            asset.preview_image_path = None
            asset.preview_status = "ready"
            asset.preview_error = None
            task.status = AsyncTaskStatus.COMPLETED
            task.message = "Asset preview is ready"
            task.data = {**(task.data or {}), "preview_url": f"/api/v1/enterprise/assets/{asset.id}/thumbnail"}
            record_audit_event(
                session,
                actor_id=task.owner_id,
                workspace_id=asset.workspace_id,
                action="asset.preview_ready",
                resource_type="asset_item",
                resource_id=asset.id,
                metadata={"task_id": task.id},
            )
        except Exception as exc:
            detail = str(getattr(exc, "detail", exc))[:1000]
            asset.preview_status = "error"
            asset.preview_error = detail
            task.status = AsyncTaskStatus.ERROR
            task.message = "Asset preview rendering failed"
            task.error = {"detail": detail}
            record_audit_event(
                session,
                actor_id=task.owner_id,
                workspace_id=asset.workspace_id,
                action="asset.preview_failed",
                resource_type="asset_item",
                resource_id=asset.id,
                metadata={"task_id": task.id, "error": detail},
            )
        session.add_all([asset, task])
        await session.commit()


async def get_asset_preview_location(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    principal: AuthPrincipal,
) -> StoredObjectLocation:
    asset = await _require_asset_access(session, asset_id=asset_id, principal=principal)
    location = StoredObjectLocation(
        object_key=asset.preview_object_key,
        legacy_path=asset.preview_image_path,
    )
    if asset.preview_status != "ready" or not (location.object_key or location.legacy_path):
        raise HTTPException(status_code=404, detail="Asset preview not found")
    if not location.object_key:
        app_data = get_app_data_directory_env()
        if not app_data:
            raise HTTPException(status_code=404, detail="Asset preview not found")
        preview_root = os.path.realpath(os.path.join(app_data, "asset-previews"))
        legacy_path = os.path.realpath(location.legacy_path or "")
        if os.path.commonpath([preview_root, legacy_path]) != preview_root:
            raise HTTPException(status_code=404, detail="Asset preview not found")
    try:
        await get_enterprise_object_storage().verify(
            location, expected_sha256=asset.preview_sha256
        )
    except HTTPException as exc:
        raise HTTPException(status_code=404, detail="Asset preview not found")
    return location
