import asyncio
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.v1.auth.principal import AuthPrincipal, principal_from_request
from api.v1.enterprise.router import API_V1_ENTERPRISE_ROUTER
from api.v1.ppt.endpoints.presentation import PRESENTATION_ROUTER
from api.v1.ppt.endpoints.template import TEMPLATE_ROUTER
from domains.platform.enums import SceneStatus
from models.sql.enterprise import (
    AuditEventModel,
    BidProjectDocumentModel,
    BidProjectMemberModel,
    BidProjectModel,
    BidProjectProfileModel,
    BidRequirementModel,
    BidStrategyModel,
    PresentationEntryModel,
    SceneDefinitionModel,
    TemplatePublicationModel,
    WorkspaceFolderModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.slide import SlideModel
from models.sql.user import User
from models.sql.template_v2 import TemplateV2
from services.database import get_async_session
from services.enterprise.template_publication_service import (
    get_accessible_published_template,
)


def _build_client(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'enterprise-platform.db'}"
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    users = {
        "owner": User(
            id=uuid.uuid4(),
            username="owner",
            hashed_password="unused",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        ),
        "member": User(
            id=uuid.uuid4(),
            username="member",
            hashed_password="unused",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        ),
        "outsider": User(
            id=uuid.uuid4(),
            username="outsider",
            hashed_password="unused",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        ),
    }

    async def initialize():
        async with engine.begin() as connection:
            for table in (
                User.__table__,
                PresentationModel.__table__,
                SlideModel.__table__,
                TemplateV2.__table__,
                WorkspaceModel.__table__,
                WorkspaceMemberModel.__table__,
                WorkspaceFolderModel.__table__,
                SceneDefinitionModel.__table__,
                PresentationEntryModel.__table__,
                AuditEventModel.__table__,
                TemplatePublicationModel.__table__,
                BidProjectModel.__table__,
                BidProjectMemberModel.__table__,
                BidProjectDocumentModel.__table__,
                BidProjectProfileModel.__table__,
                BidRequirementModel.__table__,
                BidStrategyModel.__table__,
            ):
                await connection.run_sync(table.create)
        async with session_maker() as session:
            session.add_all(list(users.values()))
            session.add_all(
                [
                    SceneDefinitionModel(
                        scene_type="general",
                        version="1.0",
                        display_name="通用 PPT 工作台",
                        status=SceneStatus.ACTIVE,
                    ),
                    SceneDefinitionModel(
                        scene_type="bid",
                        version="1.0",
                        display_name="竞标方案工作台",
                        status=SceneStatus.ACTIVE,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(initialize())

    async def override_session():
        async with session_maker() as session:
            yield session

    async def override_principal(request: Request) -> AuthPrincipal:
        username = request.headers.get("x-test-user", "owner")
        user = users.get(username)
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return AuthPrincipal(
            user_id=user.id,
            username=user.username,
            is_admin=user.is_superuser,
            method="jwt",
        )

    app = FastAPI()
    app.include_router(API_V1_ENTERPRISE_ROUTER)
    app.include_router(PRESENTATION_ROUTER, prefix="/api/v1/ppt")
    app.include_router(TEMPLATE_ROUTER, prefix="/api/v1/ppt")
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[principal_from_request] = override_principal
    return TestClient(app), engine, session_maker, users


def test_personal_workspace_is_idempotent_and_isolated(tmp_path):
    client, engine, _, _ = _build_client(tmp_path)
    try:
        first = client.post("/api/v1/enterprise/workspaces/personal")
        second = client.post("/api/v1/enterprise/workspaces/personal")
        outsider = client.get(
            "/api/v1/enterprise/workspaces", headers={"x-test-user": "outsider"}
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        assert first.json()["workspace_type"] == "personal"
        assert first.json()["current_user_role"] == "owner"
        assert outsider.status_code == 200
        assert outsider.json() == []
    finally:
        asyncio.run(engine.dispose())


def test_team_membership_enforces_roles_and_hides_workspace_from_outsider(tmp_path):
    client, engine, _, users = _build_client(tmp_path)
    try:
        created = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "研发团队", "workspace_type": "team"},
        )
        workspace_id = created.json()["id"]
        added = client.put(
            f"/api/v1/enterprise/workspaces/{workspace_id}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "viewer"},
        )
        member_list = client.get(
            "/api/v1/enterprise/workspaces", headers={"x-test-user": "member"}
        )
        denied_folder = client.post(
            f"/api/v1/enterprise/workspaces/{workspace_id}/folders",
            json={"name": "无权创建"},
            headers={"x-test-user": "member"},
        )
        outsider = client.get(
            f"/api/v1/enterprise/workspaces/{workspace_id}",
            headers={"x-test-user": "outsider"},
        )

        assert created.status_code == 201
        assert added.status_code == 200
        assert added.json()["role"] == "viewer"
        assert member_list.status_code == 200
        assert member_list.json()[0]["current_user_role"] == "viewer"
        assert denied_folder.status_code == 404
        assert outsider.status_code == 404
    finally:
        asyncio.run(engine.dispose())


def test_folder_parent_must_belong_to_same_workspace(tmp_path):
    client, engine, _, _ = _build_client(tmp_path)
    try:
        first = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "空间一", "workspace_type": "team"},
        ).json()
        second = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "空间二", "workspace_type": "team"},
        ).json()
        parent = client.post(
            f"/api/v1/enterprise/workspaces/{first['id']}/folders",
            json={"name": "父目录"},
        )
        cross_workspace = client.post(
            f"/api/v1/enterprise/workspaces/{second['id']}/folders",
            json={"name": "子目录", "parent_id": parent.json()["id"]},
        )

        assert parent.status_code == 201
        assert cross_workspace.status_code == 404
    finally:
        asyncio.run(engine.dispose())


def test_presentation_registration_preserves_owner_and_allows_member_listing(tmp_path):
    client, engine, session_maker, users = _build_client(tmp_path)

    presentation_id = uuid.uuid4()

    async def seed_presentation():
        async with session_maker() as session:
            session.add(
                PresentationModel(
                    id=presentation_id,
                    owner_id=users["owner"].id,
                    version=PresentationVersion.V2_STANDARD,
                    content="enterprise architecture",
                    n_slides=10,
                    language="Chinese",
                    title="企业架构汇报",
                )
            )
            await session.commit()

    asyncio.run(seed_presentation())
    try:
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "共享空间", "workspace_type": "team"},
        ).json()
        client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "editor"},
        )
        registered = client.post(
            "/api/v1/enterprise/presentations",
            json={
                "workspace_id": workspace["id"],
                "presentation_id": str(presentation_id),
                "scene_type": "general",
            },
        )
        member_entries = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations",
            headers={"x-test-user": "member"},
        )
        member_cannot_register_owner_presentation = client.post(
            "/api/v1/enterprise/presentations",
            json={
                "workspace_id": workspace["id"],
                "presentation_id": str(presentation_id),
                "scene_type": "general",
            },
            headers={"x-test-user": "member"},
        )

        assert registered.status_code == 201
        assert registered.json()["title"] == "企业架构汇报"
        assert member_entries.status_code == 200
        assert member_entries.json()[0]["presentation_id"] == str(presentation_id)
        assert member_entries.json()[0]["can_open"] is False
        assert registered.json()["can_open"] is True
        assert member_cannot_register_owner_presentation.status_code == 404
    finally:
        asyncio.run(engine.dispose())


def test_scene_registry_and_audit_events_are_available(tmp_path):
    client, engine, _, users = _build_client(tmp_path)
    try:
        scenes = client.get("/api/v1/enterprise/scenes")
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "审计空间", "workspace_type": "team"},
        ).json()
        client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "viewer"},
        )
        general_runtime = client.get(
            "/api/v1/enterprise/scenes/general/runtime",
            params={"workspace_id": workspace["id"]},
            headers={"x-test-user": "member"},
        )
        bid_runtime = client.get(
            "/api/v1/enterprise/scenes/bid/runtime",
            params={"workspace_id": workspace["id"]},
        )
        outsider_runtime = client.get(
            "/api/v1/enterprise/scenes/bid/runtime",
            params={"workspace_id": workspace["id"]},
            headers={"x-test-user": "outsider"},
        )
        blocked_bid_creation = client.post(
            "/api/v1/ppt/presentation/create/blank",
            json={"workspace_id": workspace["id"], "scene_type": "bid"},
        )
        events = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/audit-events"
        )

        assert scenes.status_code == 200
        assert {scene["scene_type"] for scene in scenes.json()} == {"general", "bid"}
        assert general_runtime.status_code == 200
        assert general_runtime.json()["workspace_role"] == "viewer"
        assert general_runtime.json()["capabilities"]["direct_presentation_create"] is True
        assert "presentation.view" in general_runtime.json()["permissions"]
        assert "presentation.create" not in general_runtime.json()["permissions"]
        assert bid_runtime.status_code == 200
        assert bid_runtime.json()["create_schema"] == "bid-project-v1"
        assert bid_runtime.json()["capabilities"]["requires_scene_resource"] is True
        assert outsider_runtime.status_code == 404
        assert blocked_bid_creation.status_code == 409
        assert events.status_code == 200
        assert any(event["action"] == "workspace.created" for event in events.json())
    finally:
        asyncio.run(engine.dispose())


def test_blank_creation_is_atomically_registered_in_workspace(tmp_path):
    client, engine, _, users = _build_client(tmp_path)
    try:
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "通用创作空间", "workspace_type": "team"},
        ).json()

        created = client.post(
            "/api/v1/ppt/presentation/create/blank",
            json={"workspace_id": workspace["id"], "scene_type": "general"},
        )
        client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "viewer"},
        )
        denied = client.post(
            "/api/v1/ppt/presentation/create/blank",
            json={"workspace_id": workspace["id"], "scene_type": "general"},
            headers={"x-test-user": "member"},
        )
        entries = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations"
        )
        events = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/audit-events"
        )

        assert created.status_code == 201
        assert denied.status_code == 404
        assert entries.status_code == 200
        assert len(entries.json()) == 1
        assert entries.json()[0]["presentation_id"] == created.json()["id"]
        assert entries.json()[0]["creation_mode"] == "blank"
        assert entries.json()[0]["scene_version"] == "1.0"
        assert any(
            event["action"] == "presentation.registered"
            and event["event_metadata"]["creation_mode"] == "blank"
            for event in events.json()
        )
    finally:
        asyncio.run(engine.dispose())


def test_template_publication_lifecycle_default_and_immutability(tmp_path):
    client, engine, session_maker, users = _build_client(tmp_path)
    template_id = str(uuid.uuid4())

    async def seed_template():
        async with session_maker() as session:
            session.add(
                TemplateV2(
                    id=template_id,
                    name="管理汇报模板",
                    layouts={"layouts": [{"id": "cover"}]},
                    assets={"slide_image_urls": ["/preview.png"]},
                )
            )
            await session.commit()

    asyncio.run(seed_template())
    try:
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "品牌模板空间", "workspace_type": "team"},
        ).json()
        client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "viewer"},
        )
        created = client.post(
            "/api/v1/enterprise/template-publications",
            json={
                "template_id": template_id,
                "publication_key": "executive-report",
                "version": 1,
                "scope_type": "workspace",
                "workspace_id": workspace["id"],
                "display_name": "企业管理汇报",
                "compatibility": {"pptx": True},
            },
        )
        publication_id = created.json()["id"]
        viewer_drafts = client.get(
            "/api/v1/enterprise/template-publications",
            params={"workspace_id": workspace["id"]},
            headers={"x-test-user": "member"},
        )
        submitted = client.post(
            f"/api/v1/enterprise/template-publications/{publication_id}/submit"
        )
        published = client.post(
            f"/api/v1/enterprise/template-publications/{publication_id}/publish"
        )
        defaulted = client.post(
            f"/api/v1/enterprise/template-publications/{publication_id}/set-default"
        )
        visible = client.get(
            "/api/v1/enterprise/template-publications",
            params={"workspace_id": workspace["id"], "status": "published"},
        )
        viewer_published = client.get(
            "/api/v1/enterprise/template-publications",
            params={"workspace_id": workspace["id"], "status": "published"},
            headers={"x-test-user": "member"},
        )
        blocked_update = client.patch(
            f"/api/v1/ppt/template/{template_id}",
            json={"name": "不应覆盖已发布版本"},
        )
        outsider = client.get(
            "/api/v1/enterprise/template-publications",
            params={"workspace_id": workspace["id"]},
            headers={"x-test-user": "outsider"},
        )

        async def resolve_shared_templates():
            async with session_maker() as session:
                member_template = await get_accessible_published_template(
                    session, template_id, user_id=users["member"].id
                )
                outsider_template = await get_accessible_published_template(
                    session, template_id, user_id=users["outsider"].id
                )
                return member_template, outsider_template

        member_template, outsider_template = asyncio.run(resolve_shared_templates())

        assert created.status_code == 201
        assert created.json()["status"] == "draft"
        assert viewer_drafts.json() == []
        assert submitted.json()["status"] == "in_review"
        assert published.json()["status"] == "published"
        assert defaulted.json()["is_default"] is True
        assert visible.status_code == 200
        assert visible.json()[0]["display_name"] == "企业管理汇报"
        assert viewer_published.json()[0]["template_id"] == template_id
        assert blocked_update.status_code == 409
        assert outsider.json() == []
        assert member_template is not None
        assert member_template.id == template_id
        assert outsider_template is None
    finally:
        asyncio.run(engine.dispose())


def test_bid_understanding_flow_enforces_project_access_and_strategy_gate(tmp_path):
    client, engine, _, users = _build_client(tmp_path)
    try:
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "竞标项目空间", "workspace_type": "team"},
        ).json()
        client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "editor"},
        )
        created = client.post(
            "/api/v1/enterprise/bid/projects",
            json={
                "workspace_id": workspace["id"],
                "bid_code": "BID-2026-001",
                "name": "肿瘤临床研究竞标",
                "sponsor_name": "示例申办方",
                "drug_name": "ABC-101",
                "indication": "肺癌",
            },
        )
        project_id = created.json()["id"]
        member = client.put(
            f"/api/v1/enterprise/bid/projects/{project_id}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "contributor"},
        )
        member_dashboard = client.get(
            f"/api/v1/enterprise/bid/projects/{project_id}",
            headers={"x-test-user": "member"},
        )
        outsider_dashboard = client.get(
            f"/api/v1/enterprise/bid/projects/{project_id}",
            headers={"x-test-user": "outsider"},
        )
        for category, name in (("rfp", "RFP"), ("protocol_summary", "方案摘要")):
            registered = client.post(
                f"/api/v1/enterprise/bid/projects/{project_id}/documents",
                json={
                    "logical_name": name,
                    "category": category,
                    "version_no": 1,
                    "file_ref": f"temp/{category}.pdf",
                },
            )
            assert registered.status_code == 201
        profile = client.put(
            f"/api/v1/enterprise/bid/projects/{project_id}/profile",
            json={
                "facts": {
                    "drug": {"value": "ABC-101", "source": "protocol-summary:p2"},
                    "indication": {"value": "肺癌", "source": "protocol-summary:p2"},
                },
                "conflicts": [],
                "row_version": 1,
            },
        )
        contributor_cannot_confirm = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/profile/confirm",
            headers={"x-test-user": "member"},
        )
        stale_profile = client.put(
            f"/api/v1/enterprise/bid/projects/{project_id}/profile",
            json={"facts": {}, "conflicts": [], "row_version": 1},
        )
        confirmed_profile = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/profile/confirm"
        )
        client.put(
            f"/api/v1/enterprise/bid/projects/{project_id}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "reviewer"},
        )
        reviewer_cannot_create_requirement = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/requirements",
            json={
                "category": "medical",
                "original_text": "审核人不应创建的需求",
                "mandatory": False,
            },
            headers={"x-test-user": "member"},
        )
        requirement = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/requirements",
            json={
                "category": "delivery",
                "original_text": "必须说明中心启动周期",
                "mandatory": True,
                "source_ref": "rfp:p8",
            },
        ).json()
        blocked = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/strategy/confirm"
        )
        answered = client.patch(
            f"/api/v1/enterprise/bid/projects/{project_id}/requirements/{requirement['id']}",
            json={
                "response": "提供分层中心启动计划",
                "status": "answered",
                "owner_department": "运营",
                "target_module": "operations",
                "row_version": 1,
            },
        )
        strategy = client.put(
            f"/api/v1/enterprise/bid/projects/{project_id}/strategy",
            json={
                "row_version": 1,
                "elements": {
                    "project_assessment": ["入组周期是核心挑战"],
                    "client_concerns": ["中心启动速度"],
                    "solutions": ["分层启动与周度监控"],
                    "differentiators": ["同适应症项目经验"],
                    "commitments": ["启动周期需进一步审批"],
                    "joint_decisions": ["共同确认首批中心名单"],
                },
            },
        )
        confirmed = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/strategy/confirm"
        )
        dashboard = client.get(f"/api/v1/enterprise/bid/projects/{project_id}")
        reopened_profile = client.put(
            f"/api/v1/enterprise/bid/projects/{project_id}/profile",
            json={
                "facts": {
                    "drug": {"value": "ABC-101", "source": "protocol-summary:p2"},
                    "indication": {"value": "肺癌", "source": "protocol-summary:p2"},
                    "sites": {"value": 30, "source": "protocol-summary:p4"},
                },
                "conflicts": [],
                "row_version": confirmed_profile.json()["row_version"],
            },
        )
        reopened_dashboard = client.get(
            f"/api/v1/enterprise/bid/projects/{project_id}"
        )

        assert created.status_code == 201
        assert created.json()["current_user_role"] == "bid_manager"
        assert member.status_code == 200
        assert member_dashboard.status_code == 200
        assert member_dashboard.json()["project"]["current_user_role"] == "contributor"
        assert outsider_dashboard.status_code == 404
        assert profile.status_code == 200
        assert stale_profile.status_code == 409
        assert contributor_cannot_confirm.status_code == 404
        assert confirmed_profile.json()["status"] == "confirmed"
        assert reviewer_cannot_create_requirement.status_code == 404
        assert blocked.status_code == 409
        assert "策略六要素未完成" in " ".join(blocked.json()["detail"]["blockers"])
        assert answered.json()["status"] == "answered"
        assert strategy.status_code == 200
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "confirmed"
        assert dashboard.json()["project"]["status"] == "strategy_confirmed"
        assert dashboard.json()["mandatory_requirement_coverage"] == 100.0
        assert dashboard.json()["strategy_blockers"] == []
        assert reopened_profile.status_code == 200
        assert reopened_dashboard.json()["strategy"]["version_no"] == 2
        assert reopened_dashboard.json()["strategy"]["status"] == "draft"
        assert reopened_dashboard.json()["project"]["status"] == "understanding"
    finally:
        asyncio.run(engine.dispose())
