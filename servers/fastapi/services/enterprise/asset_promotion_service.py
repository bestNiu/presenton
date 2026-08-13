from datetime import datetime, timezone
import copy
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import AssetPromotionStatus, AssetScopeType, AssetStatus, WorkspaceRole
from models.sql.enterprise.asset_item import AssetItemModel
from models.sql.enterprise.asset_promotion import AssetPromotionRequestModel
from models.sql.enterprise.workspace import WorkspaceMemberModel
from models.sql.user import User
from services.enterprise.audit_service import record_audit_event
from services.enterprise.notification_service import queue_notifications
from services.enterprise.workspace_service import require_workspace_role


_SCOPE_RANK = {
    AssetScopeType.PERSONAL: 0,
    AssetScopeType.WORKSPACE: 1,
    AssetScopeType.ENTERPRISE: 2,
}


def _ensure_asset_is_promotable(asset: AssetItemModel) -> None:
    if AssetStatus(asset.status) in {AssetStatus.OFFLINE, AssetStatus.ARCHIVED}:
        raise HTTPException(status_code=409, detail="Offline or archived asset cannot be promoted")
    if asset.authorization_status == "revoked":
        raise HTTPException(status_code=409, detail="Asset authorization is revoked")
    if asset.expires_at is not None:
        expires_at = asset.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="Asset authorization has expired")


async def create_promotion_request(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    principal: AuthPrincipal,
    values: dict,
) -> AssetPromotionRequestModel:
    asset = await session.get(AssetItemModel, asset_id)
    if asset is None or asset.created_by != principal.user_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    _ensure_asset_is_promotable(asset)
    source_scope = AssetScopeType(asset.scope_type)
    target_scope = AssetScopeType(values["target_scope_type"])
    target_workspace_id = values.get("target_workspace_id")
    if _SCOPE_RANK[target_scope] <= _SCOPE_RANK[source_scope]:
        raise HTTPException(status_code=422, detail="Asset can only be promoted to a broader scope")
    if target_scope == AssetScopeType.WORKSPACE:
        if target_workspace_id is None:
            raise HTTPException(status_code=422, detail="Target workspace is required")
        await require_workspace_role(
            session,
            workspace_id=target_workspace_id,
            principal=principal,
            required_role=WorkspaceRole.EDITOR,
        )
    elif target_scope == AssetScopeType.ENTERPRISE:
        if target_workspace_id is not None:
            raise HTTPException(status_code=422, detail="Enterprise promotion cannot target a workspace")
    else:
        raise HTTPException(status_code=422, detail="Personal scope is not a promotion target")
    if not values.get("authorization_confirmed"):
        raise HTTPException(status_code=422, detail="Asset authorization confirmation is required")
    justification = values["justification"].strip()
    desensitization_notes = values["desensitization_notes"].strip()
    if len(justification) < 5 or len(desensitization_notes) < 5:
        raise HTTPException(status_code=422, detail="Promotion purpose and desensitization notes are required")
    duplicate = await session.scalar(
        select(AssetPromotionRequestModel).where(
            AssetPromotionRequestModel.source_asset_id == asset.id,
            AssetPromotionRequestModel.target_scope_type == target_scope,
            AssetPromotionRequestModel.target_workspace_id == target_workspace_id,
            AssetPromotionRequestModel.status.in_([
                AssetPromotionStatus.PENDING,
                AssetPromotionStatus.APPROVED,
            ]),
        )
    )
    if duplicate is not None:
        detail = "Asset has already been promoted to this scope" if duplicate.status == AssetPromotionStatus.APPROVED else "A promotion request is already pending"
        raise HTTPException(status_code=409, detail=detail)
    request = AssetPromotionRequestModel(
        source_asset_id=asset.id,
        target_scope_type=target_scope,
        target_workspace_id=target_workspace_id,
        requested_by=principal.user_id,
        asset_name_snapshot=asset.name,
        justification=justification,
        desensitization_notes=desensitization_notes,
        authorization_confirmed=True,
    )
    session.add(request)
    if target_scope == AssetScopeType.WORKSPACE:
        reviewer_ids = set((await session.scalars(
            select(WorkspaceMemberModel.user_id).where(
                WorkspaceMemberModel.workspace_id == target_workspace_id,
                WorkspaceMemberModel.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
            )
        )).all())
    else:
        reviewer_ids = set((await session.scalars(select(User.id).where(User.is_superuser.is_(True)))).all())
    queue_notifications(
        session,
        recipient_ids=reviewer_ids,
        actor_id=principal.user_id,
        workspace_id=target_workspace_id,
        notification_type="asset.promotion_requested",
        title="收到资产提升申请",
        body=f"{asset.name} 申请提升为{'空间' if target_scope == AssetScopeType.WORKSPACE else '企业'}资产",
        resource_type="asset_promotion_request",
        resource_id=request.id,
        action_url=f"/workspace/assets{f'?workspace_id={target_workspace_id}' if target_workspace_id else ''}",
        metadata={"asset_id": str(asset.id), "target_scope_type": target_scope.value},
    )
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=target_workspace_id,
        action="asset.promotion_requested",
        resource_type="asset_promotion_request",
        resource_id=request.id,
        metadata={"asset_id": str(asset.id), "target_scope_type": target_scope.value},
    )
    await session.commit()
    await session.refresh(request)
    return request


async def list_promotion_requests(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    workspace_id: uuid.UUID | None,
    view: str,
) -> list[AssetPromotionRequestModel]:
    if workspace_id is not None:
        await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    if view == "mine":
        visibility = AssetPromotionRequestModel.requested_by == principal.user_id
    elif view == "review":
        governed_workspaces = select(WorkspaceMemberModel.workspace_id).where(
            WorkspaceMemberModel.user_id == principal.user_id,
            WorkspaceMemberModel.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
        )
        visibility = (
            (AssetPromotionRequestModel.target_scope_type == AssetScopeType.WORKSPACE)
            & AssetPromotionRequestModel.target_workspace_id.in_(governed_workspaces)
        )
        if principal.is_admin:
            visibility = or_(visibility, AssetPromotionRequestModel.target_scope_type == AssetScopeType.ENTERPRISE)
        visibility = visibility & (AssetPromotionRequestModel.requested_by != principal.user_id)
    else:
        raise HTTPException(status_code=422, detail="Unsupported promotion request view")
    statement = select(AssetPromotionRequestModel).where(visibility)
    if workspace_id is not None:
        statement = statement.where(AssetPromotionRequestModel.target_workspace_id == workspace_id)
    return list((await session.scalars(statement.order_by(AssetPromotionRequestModel.created_at.desc()).limit(200))).all())


async def decide_promotion_request(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    principal: AuthPrincipal,
    action: str,
    comment: str,
) -> AssetPromotionRequestModel:
    request = await session.get(AssetPromotionRequestModel, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Promotion request not found")
    if AssetPromotionStatus(request.status) != AssetPromotionStatus.PENDING:
        raise HTTPException(status_code=409, detail="Promotion request is already decided")
    target_scope = AssetScopeType(request.target_scope_type)
    if target_scope == AssetScopeType.WORKSPACE and request.target_workspace_id is not None:
        await require_workspace_role(
            session,
            workspace_id=request.target_workspace_id,
            principal=principal,
            required_role=WorkspaceRole.ADMIN,
        )
    elif target_scope == AssetScopeType.ENTERPRISE:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="Enterprise asset administrator required")
    if request.requested_by == principal.user_id:
        raise HTTPException(status_code=409, detail="Promotion request requires an independent reviewer")
    source = await session.get(AssetItemModel, request.source_asset_id)
    if source is None:
        raise HTTPException(status_code=409, detail="Source asset no longer exists")
    normalized_comment = comment.strip()
    if len(normalized_comment) < 2:
        raise HTTPException(status_code=422, detail="Decision comment is required")
    if action == "approve":
        _ensure_asset_is_promotable(source)
        promoted = AssetItemModel(
            workspace_id=request.target_workspace_id,
            created_by=request.requested_by,
            scope_type=target_scope,
            asset_type=source.asset_type,
            name=source.name,
            description=source.description,
            scene_type=source.scene_type,
            tags=copy.deepcopy(source.tags),
            payload=copy.deepcopy(source.payload),
            payload_hash=source.payload_hash,
            preview=copy.deepcopy(source.preview),
            preview_image_path=source.preview_image_path if source.preview_status == "ready" else None,
            preview_object_key=source.preview_object_key if source.preview_status == "ready" else None,
            preview_sha256=source.preview_sha256 if source.preview_status == "ready" else None,
            preview_status=source.preview_status if source.preview_status in {"ready", "error"} else "structured",
            preview_error=source.preview_error if source.preview_status == "error" else None,
            source_presentation_entry_id=source.source_presentation_entry_id,
            source_slide_id=source.source_slide_id,
            parent_asset_id=source.id,
            authorization_status=source.authorization_status,
            expires_at=source.expires_at,
            compatibility=copy.deepcopy(source.compatibility),
            status=AssetStatus.PUBLISHED,
            published_by=principal.user_id,
            published_at=datetime.now(timezone.utc),
        )
        session.add(promoted)
        request.promoted_asset_id = promoted.id
        request.status = AssetPromotionStatus.APPROVED
    elif action == "reject":
        request.status = AssetPromotionStatus.REJECTED
    else:
        raise HTTPException(status_code=422, detail="Unsupported promotion decision")
    request.decided_by = principal.user_id
    request.decision_comment = normalized_comment
    request.decided_at = datetime.now(timezone.utc)
    session.add(request)
    decision_event = "approved" if action == "approve" else "rejected"
    queue_notifications(
        session,
        recipient_ids={request.requested_by},
        actor_id=principal.user_id,
        workspace_id=request.target_workspace_id,
        notification_type=f"asset.promotion_{decision_event}",
        title="资产提升申请已通过" if action == "approve" else "资产提升申请被驳回",
        body=f"{source.name}：{normalized_comment}",
        resource_type="asset_promotion_request",
        resource_id=request.id,
        action_url=f"/workspace/assets{f'?workspace_id={request.target_workspace_id}' if request.target_workspace_id else ''}",
        metadata={"asset_id": str(source.id), "promoted_asset_id": str(request.promoted_asset_id) if request.promoted_asset_id else None},
    )
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=request.target_workspace_id,
        action=f"asset.promotion_{decision_event}",
        resource_type="asset_promotion_request",
        resource_id=request.id,
        metadata={"asset_id": str(source.id), "promoted_asset_id": str(request.promoted_asset_id) if request.promoted_asset_id else None},
    )
    await session.commit()
    await session.refresh(request)
    return request
