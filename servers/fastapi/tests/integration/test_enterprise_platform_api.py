import asyncio
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.v1.auth.principal import AuthPrincipal, principal_from_request
from api.v1.enterprise.router import API_V1_ENTERPRISE_ROUTER
from api.v1.ppt.endpoints.presentation import PRESENTATION_ROUTER
from domains.platform.enums import SceneStatus
from models.sql.enterprise import (
    AuditEventModel,
    PresentationEntryModel,
    SceneDefinitionModel,
    WorkspaceFolderModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.slide import SlideModel
from models.sql.user import User
from services.database import get_async_session


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
                WorkspaceModel.__table__,
                WorkspaceMemberModel.__table__,
                WorkspaceFolderModel.__table__,
                SceneDefinitionModel.__table__,
                PresentationEntryModel.__table__,
                AuditEventModel.__table__,
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
    client, engine, _, _ = _build_client(tmp_path)
    try:
        scenes = client.get("/api/v1/enterprise/scenes")
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "审计空间", "workspace_type": "team"},
        ).json()
        events = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/audit-events"
        )

        assert scenes.status_code == 200
        assert {scene["scene_type"] for scene in scenes.json()} == {"general", "bid"}
        assert events.status_code == 200
        assert events.json()[0]["action"] == "workspace.created"
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
        assert any(
            event["action"] == "presentation.registered"
            and event["event_metadata"]["creation_mode"] == "blank"
            for event in events.json()
        )
    finally:
        asyncio.run(engine.dispose())
