import os
from pathlib import Path
import shutil
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
            app_data = get_app_data_directory_env()
            if not app_data:
                raise RuntimeError("APP_DATA_DIRECTORY is required for asset previews")
            destination_dir = Path(app_data) / "asset-previews"
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"{asset.id}-{asset.payload_hash[:12]}.png"
            shutil.copyfile(result.path, destination)
            os.chmod(destination, 0o644)
            asset.preview_image_path = str(destination)
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


async def get_asset_preview_path(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    principal: AuthPrincipal,
) -> str:
    asset = await _require_asset_access(session, asset_id=asset_id, principal=principal)
    path = asset.preview_image_path
    if asset.preview_status != "ready" or not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Asset preview not found")
    app_data = get_app_data_directory_env()
    if not app_data:
        raise HTTPException(status_code=404, detail="Asset preview not found")
    preview_root = os.path.realpath(os.path.join(app_data, "asset-previews"))
    real_path = os.path.realpath(path)
    if os.path.commonpath([preview_root, real_path]) != preview_root:
        raise HTTPException(status_code=404, detail="Asset preview not found")
    return real_path
