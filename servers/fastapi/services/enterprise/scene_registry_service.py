from copy import deepcopy
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import WorkspaceRole
from domains.platform.permissions import role_allows
from models.sql.enterprise.scene_definition import SceneDefinitionModel
from services.enterprise.scene_service import get_active_scene
from services.enterprise.workspace_service import require_workspace_role


SCENE_MANIFESTS: dict[str, dict] = {
    "general": {
        "entry_route": "/workspace",
        "create_schema": "general-presentation-v1",
        "navigation": [
            {"code": "create", "label": "创建 PPT", "route": "/workspace"},
            {"code": "presentations", "label": "文稿", "route": "/workspace"},
            {
                "code": "templates",
                "label": "模板治理",
                "route": "/workspace/templates",
            },
        ],
        "capabilities": {
            "direct_presentation_create": True,
            "requires_scene_resource": False,
        },
        "permission_roles": {
            "presentation.view": WorkspaceRole.VIEWER,
            "presentation.review": WorkspaceRole.REVIEWER,
            "presentation.create": WorkspaceRole.EDITOR,
            "template.use": WorkspaceRole.VIEWER,
            "template.manage": WorkspaceRole.EDITOR,
        },
        "policies": {
            "document_policy": "general-documents-v1",
            "workflow_policy": "general-flexible-v1",
            "quality_policy": "general-v1",
            "assembly_policy": "general-presentation-v1",
        },
    },
    "bid": {
        "entry_route": "/workspace/scenes/bid",
        "create_schema": "bid-project-v1",
        "navigation": [
            {"code": "dashboard", "label": "项目驾驶舱", "route": "dashboard"},
            {"code": "documents", "label": "竞标资料", "route": "documents"},
            {"code": "profile", "label": "项目画像", "route": "profile"},
            {"code": "requirements", "label": "需求矩阵", "route": "requirements"},
            {"code": "strategy", "label": "投标策略", "route": "strategy"},
            {"code": "modules", "label": "专业模块", "route": "modules"},
            {"code": "reviews", "label": "审核门禁", "route": "reviews"},
            {"code": "releases", "label": "交付版本", "route": "releases"},
        ],
        "capabilities": {
            "direct_presentation_create": False,
            "requires_scene_resource": True,
        },
        "permission_roles": {
            "bid.project.view": WorkspaceRole.VIEWER,
            "bid.content.review": WorkspaceRole.REVIEWER,
            "bid.project.create": WorkspaceRole.EDITOR,
            "bid.strategy.confirm": WorkspaceRole.ADMIN,
            "bid.release.publish": WorkspaceRole.ADMIN,
        },
        "policies": {
            "document_policy": "bid-documents-v1",
            "workflow_policy": "bid-gates-v1",
            "quality_policy": "bid-gates-v1",
            "assembly_policy": "bid-modules-v1",
        },
    },
}


def get_scene_manifest(scene_type: str) -> dict | None:
    manifest = SCENE_MANIFESTS.get(scene_type.strip().lower())
    return deepcopy(manifest) if manifest is not None else None


async def resolve_scene_runtime(
    session: AsyncSession,
    *,
    scene_type: str,
    workspace_id: uuid.UUID,
    principal: AuthPrincipal,
) -> dict:
    normalized_scene_type = scene_type.strip().lower()
    scene = await get_active_scene(session, normalized_scene_type)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene is not active")
    manifest = get_scene_manifest(normalized_scene_type)
    if manifest is None:
        raise HTTPException(status_code=503, detail="Scene runtime is not registered")
    _, membership = await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.VIEWER,
    )
    role = WorkspaceRole(membership.role)
    permission_roles = manifest.pop("permission_roles")
    permissions = [
        permission
        for permission, required_role in permission_roles.items()
        if role_allows(role, required_role)
    ]
    policies = manifest["policies"]
    for policy_key in tuple(policies):
        configured = scene.config.get(policy_key)
        if isinstance(configured, str) and configured.strip():
            policies[policy_key] = configured.strip()
    return {
        "scene_type": scene.scene_type,
        "version": scene.version,
        "display_name": scene.display_name,
        "description": scene.description,
        "workspace_id": workspace_id,
        "workspace_role": role,
        "permissions": permissions,
        **manifest,
    }


def require_direct_presentation_creation(scene: SceneDefinitionModel) -> None:
    manifest = get_scene_manifest(scene.scene_type)
    if manifest is None:
        raise HTTPException(status_code=503, detail="Scene runtime is not registered")
    if not manifest["capabilities"]["direct_presentation_create"]:
        raise HTTPException(
            status_code=409,
            detail="This scene requires its dedicated project workflow",
        )
