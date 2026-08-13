import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.v1.auth.principal import AuthPrincipal, principal_from_request
from api.v1.enterprise.router import API_V1_ENTERPRISE_ROUTER
from api.v1.ppt.endpoints.presentation import PRESENTATION_ROUTER
from api.v1.ppt.endpoints.template import TEMPLATE_ROUTER
from domains.platform.enums import SceneStatus
from models.sql.enterprise import (
    AssetItemModel,
    AssetFavoriteModel,
    AssetPromotionRequestModel,
    AssetUsageEventModel,
    AuditEventModel,
    EnterpriseNotificationModel,
    EnterpriseDocumentModel,
    EnterpriseDocumentChunkModel,
    EnterpriseKnowledgeOutlineModel,
    BidDeliveryArtifactModel,
    BidDownloadGrantModel,
    BidProjectDocumentModel,
    BidCommitmentModel,
    BidProfessionalModuleModel,
    BidPresentationReleaseModel,
    BidProjectMemberModel,
    BidProjectModel,
    BidProjectProfileModel,
    BidRequirementModel,
    BidReviewGateModel,
    BidReviewIssueModel,
    BidStrategyModel,
    PresentationEntryModel,
    PresentationDeliveryArtifactModel,
    PresentationDownloadGrantModel,
    PresentationCommentReplyModel,
    PresentationCommentThreadModel,
    PresentationQualityIssueModel,
    PresentationQualityRunModel,
    PresentationReviewModel,
    PresentationSourceCitationModel,
    PresentationSnapshotModel,
    SceneDefinitionModel,
    StorageLifecycleRunModel,
    TemplatePublicationModel,
    WorkspaceFolderModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.async_task import AsyncTaskModel
from models.sql.slide import SlideModel
from models.sql.user import User
from models.sql.template_v2 import TemplateV2
from services.database import get_async_session
from services.enterprise.template_publication_service import (
    get_accessible_published_template,
)
import services.enterprise.asset_preview_service as asset_preview_service
import services.enterprise.document_service as document_service
import services.enterprise.knowledge_outline_service as knowledge_outline_service
import services.enterprise.storage_lifecycle_service as storage_lifecycle_service


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
        "admin": User(
            id=uuid.uuid4(),
            username="admin",
            hashed_password="unused",
            is_active=True,
            is_superuser=True,
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
                AsyncTaskModel.__table__,
                EnterpriseDocumentModel.__table__,
                EnterpriseDocumentChunkModel.__table__,
                EnterpriseKnowledgeOutlineModel.__table__,
                AssetItemModel.__table__,
                AssetFavoriteModel.__table__,
                AssetPromotionRequestModel.__table__,
                AssetUsageEventModel.__table__,
                PresentationCommentThreadModel.__table__,
                PresentationCommentReplyModel.__table__,
                PresentationReviewModel.__table__,
                PresentationSnapshotModel.__table__,
                PresentationDeliveryArtifactModel.__table__,
                PresentationDownloadGrantModel.__table__,
                PresentationQualityRunModel.__table__,
                PresentationQualityIssueModel.__table__,
                PresentationSourceCitationModel.__table__,
                EnterpriseNotificationModel.__table__,
                AuditEventModel.__table__,
                StorageLifecycleRunModel.__table__,
                TemplatePublicationModel.__table__,
                BidProjectModel.__table__,
                BidProjectMemberModel.__table__,
                BidProjectDocumentModel.__table__,
                BidProjectProfileModel.__table__,
                BidRequirementModel.__table__,
                BidStrategyModel.__table__,
                BidProfessionalModuleModel.__table__,
                BidCommitmentModel.__table__,
                BidReviewGateModel.__table__,
                BidReviewIssueModel.__table__,
                BidPresentationReleaseModel.__table__,
                BidDeliveryArtifactModel.__table__,
                BidDownloadGrantModel.__table__,
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


def test_storage_lifecycle_requires_admin_and_cleans_aged_orphan(tmp_path, monkeypatch):
    client, engine, session_maker, _ = _build_client(tmp_path)
    storage_root = tmp_path / "enterprise-objects"
    orphan = storage_root / "orphaned" / "old.bin"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"unreferenced-object")
    aged = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
    os.utime(orphan, (aged, aged))
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_LOCAL_ROOT", str(storage_root))
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_ORPHAN_GRACE_DAYS", "1")
    try:
        denied = client.post(
            "/api/v1/enterprise/admin/storage/lifecycle-runs",
            json={"execute": False},
        )
        dry_run = client.post(
            "/api/v1/enterprise/admin/storage/lifecycle-runs",
            json={"execute": False},
            headers={"x-test-user": "admin"},
        )
        assert denied.status_code == 403
        assert dry_run.status_code == 200
        assert dry_run.json()["candidate_count"] == 1
        assert dry_run.json()["stored_bytes"] == len(b"unreferenced-object")
        assert dry_run.json()["orphan_candidate_count"] == 1
        assert dry_run.json()["revoked_candidate_count"] == 0
        assert dry_run.json()["deleted_count"] == 0
        assert orphan.exists()

        executed = client.post(
            "/api/v1/enterprise/admin/storage/lifecycle-runs",
            json={"execute": True, "max_delete": 10},
            headers={"x-test-user": "admin"},
        )
        history = client.get(
            "/api/v1/enterprise/admin/storage/lifecycle-runs",
            headers={"x-test-user": "admin"},
        )

        assert executed.json()["deleted_count"] == 1
        assert executed.json()["deleted_bytes"] == len(b"unreferenced-object")
        assert not orphan.exists()
        assert history.status_code == 200
        assert [item["mode"] for item in history.json()] == ["execute", "dry_run"]
        assert history.json()[0]["health"] == "healthy"
        assert history.json()[1]["health"] == "warning"
        assert history.json()[0]["deleted_count"] == 1

        class FailingStorage:
            backend = "local"

            async def list_objects(self):
                raise RuntimeError("storage inventory unavailable")

        monkeypatch.setattr(
            storage_lifecycle_service,
            "get_enterprise_object_storage",
            lambda: FailingStorage(),
        )
        with pytest.raises(RuntimeError, match="storage inventory unavailable"):
            client.post(
                "/api/v1/enterprise/admin/storage/lifecycle-runs",
                json={"execute": False},
                headers={"x-test-user": "admin"},
            )
        failed_history = client.get(
            "/api/v1/enterprise/admin/storage/lifecycle-runs",
            headers={"x-test-user": "admin"},
        ).json()

        async def count_health_alerts():
            async with session_maker() as session:
                return await session.scalar(
                    select(func.count(EnterpriseNotificationModel.id)).where(
                        EnterpriseNotificationModel.notification_type
                        == "storage.lifecycle_health_alert"
                    )
                )

        assert failed_history[0]["status"] == "failed"
        assert failed_history[0]["health"] == "critical"
        assert "inventory unavailable" in failed_history[0]["failure_detail"]
        assert asyncio.run(count_health_alerts()) == 1
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


def test_enterprise_document_upload_versions_parse_access_and_storage_protection(
    tmp_path, monkeypatch
):
    client, engine, session_maker, users = _build_client(tmp_path)
    storage_root = tmp_path / "enterprise-objects"
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_LOCAL_ROOT", str(storage_root))
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_ORPHAN_GRACE_DAYS", "1")
    monkeypatch.setattr(document_service, "async_session_maker", session_maker)
    monkeypatch.setattr(
        knowledge_outline_service, "async_session_maker", session_maker
    )

    class FakeDocumentsLoader:
        def __init__(self, file_paths):
            self.file_paths = file_paths
            self.documents = []

        async def load_documents(self, **_):
            self.documents = ["# 企业介绍\n可信、可追溯的产品能力。"]

    monkeypatch.setattr(document_service, "DocumentsLoader", FakeDocumentsLoader)

    async def fake_generate_outline(*_args, **_kwargs):
        yield json.dumps(
            {
                "slides": [
                    {"content": "# 企业能力\n可信产品能力"},
                    {"content": "# 交付经验\n可追溯的交付体系"},
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(
        knowledge_outline_service,
        "generate_ppt_outline",
        fake_generate_outline,
    )
    try:
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "企业资料空间", "workspace_type": "team"},
        ).json()
        client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "viewer"},
        )
        form = {
            "scope_type": "workspace",
            "workspace_id": workspace["id"],
            "logical_name": "企业介绍",
            "category": "公司资料",
            "confidentiality": "L2",
        }
        first = client.post(
            "/api/v1/enterprise/documents",
            data=form,
            files={"file": ("company.md", b"first version", "text/markdown")},
        )
        duplicate = client.post(
            "/api/v1/enterprise/documents",
            data={**form, "logical_name": "另一个名称"},
            files={"file": ("duplicate.md", b"first version", "text/markdown")},
        )
        second = client.post(
            "/api/v1/enterprise/documents",
            data=form,
            files={"file": ("company.md", b"second version", "text/markdown")},
        )
        owner_cannot_publish_enterprise = client.post(
            "/api/v1/enterprise/documents",
            data={"scope_type": "enterprise", "logical_name": "集团标准"},
            files={"file": ("standard.txt", b"enterprise standard", "text/plain")},
        )
        enterprise_document = client.post(
            "/api/v1/enterprise/documents",
            data={"scope_type": "enterprise", "logical_name": "集团标准"},
            files={"file": ("standard.txt", b"enterprise standard", "text/plain")},
            headers={"x-test-user": "admin"},
        )

        assert first.status_code == 201, first.text
        assert first.json()["version_no"] == 1
        assert first.json()["parse_status"] == "queued"
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["document_id"] == first.json()["id"]
        assert second.status_code == 201, second.text
        assert second.json()["version_no"] == 2
        assert second.json()["supersedes_document_id"] == first.json()["id"]
        assert owner_cannot_publish_enterprise.status_code == 403
        assert enterprise_document.status_code == 201
        enterprise_list = client.get(
            "/api/v1/enterprise/documents",
            params={"scope_type": "enterprise"},
        )
        assert [item["id"] for item in enterprise_list.json()] == [
            enterprise_document.json()["id"]
        ]

        latest = client.get(
            "/api/v1/enterprise/documents",
            params={"scope_type": "workspace", "workspace_id": workspace["id"]},
        )
        versions = client.get(
            "/api/v1/enterprise/documents",
            params={
                "scope_type": "workspace",
                "workspace_id": workspace["id"],
                "include_versions": True,
            },
        )
        detail = client.get(
            f"/api/v1/enterprise/documents/{second.json()['id']}",
            headers={"x-test-user": "member"},
        )
        downloaded = client.get(
            f"/api/v1/enterprise/documents/{second.json()['id']}/download",
            headers={"x-test-user": "member"},
        )
        viewer_upload = client.post(
            "/api/v1/enterprise/documents",
            data=form,
            files={"file": ("denied.md", b"denied", "text/markdown")},
            headers={"x-test-user": "member"},
        )
        outsider = client.get(
            "/api/v1/enterprise/documents",
            params={"scope_type": "workspace", "workspace_id": workspace["id"]},
            headers={"x-test-user": "outsider"},
        )
        retried = client.post(
            f"/api/v1/enterprise/documents/{second.json()['id']}/parse-tasks"
        )
        searched = client.post(
            "/api/v1/enterprise/knowledge/search",
            json={
                "query": "产品能力",
                "scope_type": "workspace",
                "workspace_id": workspace["id"],
            },
            headers={"x-test-user": "member"},
        )
        searched_versions = client.post(
            "/api/v1/enterprise/knowledge/search",
            json={
                "query": "产品能力",
                "scope_type": "workspace",
                "workspace_id": workspace["id"],
                "latest_only": False,
            },
        )
        category_filtered = client.post(
            "/api/v1/enterprise/knowledge/search",
            json={
                "query": "产品能力",
                "scope_type": "workspace",
                "workspace_id": workspace["id"],
                "categories": ["不存在"],
            },
        )
        outsider_search = client.post(
            "/api/v1/enterprise/knowledge/search",
            json={
                "query": "产品能力",
                "scope_type": "workspace",
                "workspace_id": workspace["id"],
            },
            headers={"x-test-user": "outsider"},
        )

        assert [item["id"] for item in latest.json()] == [second.json()["id"]]
        assert len(versions.json()) == 2
        assert detail.status_code == 200
        assert detail.json()["parse_status"] == "ready"
        assert detail.json()["extracted_text"].startswith("# 企业介绍")
        assert detail.json()["extracted_metadata"]["heading_count"] == 1
        assert downloaded.content == b"second version"
        assert viewer_upload.status_code == 404
        assert outsider.status_code == 404
        assert retried.status_code == 202
        assert retried.json()["document_id"] == second.json()["id"]
        assert retried.json()["status"] == "pending"
        assert searched.status_code == 200
        assert len(searched.json()) == 1
        assert searched.json()[0]["document_id"] == second.json()["id"]
        assert searched.json()[0]["heading"] == "企业介绍"
        assert searched.json()[0]["locator"]["start_line"] == 1
        assert searched.json()[0]["citation"] == {
            "source_type": "enterprise_document",
            "source_id": second.json()["id"],
            "source_version": "2",
            "locator": "lines:1-2#chunk=0",
            "excerpt": "可信、可追溯的产品能力。",
        }
        assert len(searched_versions.json()) == 2
        assert category_filtered.json() == []
        assert outsider_search.status_code == 404

        presentation_id = uuid.uuid4()
        slide_id = uuid.uuid4()

        async def seed_citation_target():
            async with session_maker() as session:
                session.add(
                    PresentationModel(
                        id=presentation_id,
                        owner_id=users["owner"].id,
                        version=PresentationVersion.V2_STANDARD,
                        content="knowledge-backed presentation",
                        n_slides=1,
                        language="Chinese",
                        title="知识引用演示",
                    )
                )
                session.add(
                    SlideModel(
                        id=slide_id,
                        owner_id=users["owner"].id,
                        presentation=presentation_id,
                        layout_group="general",
                        layout="general-1",
                        index=0,
                        content={"title": "企业能力"},
                        ui={"id": "slide-knowledge", "elements": []},
                    )
                )
                await session.commit()

        asyncio.run(seed_citation_target())
        entry = client.post(
            "/api/v1/enterprise/presentations",
            json={
                "workspace_id": workspace["id"],
                "presentation_id": str(presentation_id),
                "scene_type": "general",
            },
        ).json()
        citation_payload = {
            **searched.json()[0]["citation"],
            "slide_id": str(slide_id),
        }
        citation = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/citations",
            json=citation_payload,
        )
        tampered_citation = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/citations",
            json={**citation_payload, "excerpt": "资料中不存在的内容"},
        )

        assert citation.status_code == 201, citation.text
        assert citation.json()["source_id"] == second.json()["id"]
        assert tampered_citation.status_code == 422
        removable_citation = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/citations",
            json=citation_payload,
        )
        removed_citation = client.delete(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/citations/{removable_citation.json()['id']}"
        )
        assert removable_citation.status_code == 201
        assert removed_citation.status_code == 204
        citation_list = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/citations"
        )
        citation_summary = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/citations/summary"
        )
        citation_preview = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/citations/{citation.json()['id']}/source"
        )
        assert citation_list.status_code == 200
        assert citation_list.json()[0]["status"] == "valid"
        assert citation_list.json()[0]["source_name"] == "企业介绍"
        assert citation_summary.json()["valid_citations"] == 1
        assert citation_summary.json()["cited_slide_ids"] == [str(slide_id)]
        assert citation_preview.status_code == 200
        assert "可信、可追溯的产品能力" in citation_preview.json()["content"]

        outline_created = client.post(
            "/api/v1/enterprise/knowledge/outlines",
            json={
                "topic": "企业能力汇报",
                "query": "产品能力",
                "scope_type": "workspace",
                "workspace_id": workspace["id"],
                "document_ids": [second.json()["id"]],
                "audience": "管理层",
                "n_slides": 2,
            },
        )
        assert outline_created.status_code == 202, outline_created.text
        outline = client.get(
            f"/api/v1/enterprise/knowledge/outlines/{outline_created.json()['id']}"
        )
        assert outline.status_code == 200
        assert outline.json()["status"] == "ready"
        assert len(outline.json()["context_manifest"]) == 1
        assert outline.json()["outline"]["slides"][0]["citation_refs"] == ["K1"]

        applied = client.post(
            f"/api/v1/enterprise/knowledge/outlines/{outline.json()['id']}/workspaces/{workspace['id']}/presentations/{entry['id']}/apply"
        )
        materialized = client.post(
            f"/api/v1/enterprise/knowledge/outlines/{outline.json()['id']}/workspaces/{workspace['id']}/presentations/{entry['id']}/citations"
        )
        materialized_again = client.post(
            f"/api/v1/enterprise/knowledge/outlines/{outline.json()['id']}/workspaces/{workspace['id']}/presentations/{entry['id']}/citations"
        )
        assert applied.status_code == 200
        assert applied.json()["presentation_entry_id"] == entry["id"]
        assert materialized.status_code == 200
        assert len(materialized.json()) == 1
        assert materialized_again.json()[0]["id"] == materialized.json()[0]["id"]

        knowledge_presentation_payload = {
            "workspace_id": workspace["id"],
            "topic": "资料驱动企业汇报",
            "query": "产品能力",
            "document_ids": [second.json()["id"]],
            "audience": "管理层",
            "language": "Chinese",
            "n_slides": 2,
        }
        knowledge_presentation = client.post(
            "/api/v1/enterprise/knowledge/presentations",
            json=knowledge_presentation_payload,
            headers={"Idempotency-Key": "knowledge-presentation-case-1"},
        )
        knowledge_presentation_replayed = client.post(
            "/api/v1/enterprise/knowledge/presentations",
            json=knowledge_presentation_payload,
            headers={"Idempotency-Key": "knowledge-presentation-case-1"},
        )
        knowledge_presentation_conflict = client.post(
            "/api/v1/enterprise/knowledge/presentations",
            json={**knowledge_presentation_payload, "topic": "另一个主题"},
            headers={"Idempotency-Key": "knowledge-presentation-case-1"},
        )
        assert knowledge_presentation.status_code == 202, knowledge_presentation.text
        assert knowledge_presentation.json()["outline"]["status"] == "queued"
        assert knowledge_presentation.json()["outline"]["input_status"] == "current"
        assert len(knowledge_presentation.json()["outline"]["input_manifest"]) == 1
        assert len(knowledge_presentation.json()["outline"]["input_manifest_hash"]) == 64
        assert knowledge_presentation_replayed.status_code == 202
        assert knowledge_presentation_conflict.status_code == 409
        assert knowledge_presentation_replayed.headers["Idempotency-Replayed"] == "true"
        assert knowledge_presentation_replayed.json()["presentation_id"] == knowledge_presentation.json()["presentation_id"]
        generated_outline = client.get(
            f"/api/v1/enterprise/knowledge/outlines/{knowledge_presentation.json()['outline']['id']}"
        )
        async def load_generated_core_outline():
            async with session_maker() as session:
                presentation = await session.get(
                    PresentationModel,
                    uuid.UUID(knowledge_presentation.json()["presentation_id"]),
                )
                return presentation.outlines

        generated_core_outline = asyncio.run(load_generated_core_outline())
        assert generated_outline.json()["status"] == "ready"
        assert generated_outline.json()["presentation_entry_id"] == knowledge_presentation.json()["presentation_entry_id"]
        assert len(generated_core_outline["slides"]) == 2

        async def seed_generated_slides_and_materialize():
            async with session_maker() as session:
                generated_presentation_id = uuid.UUID(
                    knowledge_presentation.json()["presentation_id"]
                )
                session.add_all(
                    [
                        SlideModel(
                            owner_id=users["owner"].id,
                            presentation=generated_presentation_id,
                            layout_group="general",
                            layout="general-1",
                            index=index,
                            content={"title": f"知识页面 {index + 1}"},
                            ui={"id": f"knowledge-slide-{index}", "elements": []},
                        )
                        for index in range(2)
                    ]
                )
                await session.commit()
                return await knowledge_outline_service.materialize_linked_knowledge_citations_for_presentation(
                    session, presentation_id=generated_presentation_id
                )

        auto_citations = asyncio.run(seed_generated_slides_and_materialize())
        assert len(auto_citations) == 2

        third = client.post(
            "/api/v1/enterprise/documents",
            data=form,
            files={"file": ("company.md", b"third version", "text/markdown")},
        )
        assert third.status_code == 201

        async def refresh_input_status():
            async with session_maker() as session:
                await knowledge_outline_service.materialize_linked_knowledge_citations_for_presentation(
                    session,
                    presentation_id=uuid.UUID(
                        knowledge_presentation.json()["presentation_id"]
                    ),
                )
                refreshed = await session.get(
                    EnterpriseKnowledgeOutlineModel,
                    uuid.UUID(knowledge_presentation.json()["outline"]["id"]),
                )
                return refreshed.input_status

        assert asyncio.run(refresh_input_status()) == "stale"

        evaluation_denied = client.post(
            "/api/v1/enterprise/knowledge/evaluations",
            json={"cases": [{"case_id": "c1", "expected_document_ids": [second.json()["id"]], "ranked_document_ids": [second.json()["id"]]}]},
        )
        evaluation = client.post(
            "/api/v1/enterprise/knowledge/evaluations",
            json={"cases": [{"case_id": "c1", "expected_document_ids": [second.json()["id"]], "ranked_document_ids": [second.json()["id"]]}]},
            headers={"x-test-user": "admin"},
        )
        assert evaluation_denied.status_code == 403
        assert evaluation.status_code == 200
        assert evaluation.json()["hit_rate"] == 1.0
        assert evaluation.json()["mean_reciprocal_rank"] == 1.0
        governance_policy = client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/governance-policy",
            json={
                "review_mode": "none",
                "quality_gate_enabled": False,
                "require_numeric_citations": False,
                "revoked_delivery_retention_days": 30,
            },
        )
        assert governance_policy.status_code == 200

        async def revoke_cited_document():
            async with session_maker() as session:
                document = await session.get(
                    EnterpriseDocumentModel, uuid.UUID(second.json()["id"])
                )
                document.authorization_status = "revoked"
                session.add(document)
                await session.commit()

        asyncio.run(revoke_cited_document())
        revoked_citations = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/citations"
        )
        assert revoked_citations.json()[0]["status"] == "revoked"
        assert revoked_citations.json()[0]["status_message"] == "来源授权已撤销"
        freeze_with_revoked_source = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/freeze"
        )
        assert freeze_with_revoked_source.status_code == 409
        assert freeze_with_revoked_source.json()["detail"]["message"] == "Resolve invalid source citations before freeze"
        stale_citation_quality = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/quality-runs"
        )
        assert stale_citation_quality.status_code == 201
        assert stale_citation_quality.json()["status"] == "failed"
        assert "citation_source_invalid" in {
            item["rule_code"] for item in stale_citation_quality.json()["issues"]
        }

        for path in storage_root.rglob("*.md"):
            aged = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
            os.utime(path, (aged, aged))
        lifecycle = client.post(
            "/api/v1/enterprise/admin/storage/lifecycle-runs",
            json={"execute": False},
            headers={"x-test-user": "admin"},
        )
        assert lifecycle.status_code == 200
        assert lifecycle.json()["candidate_count"] == 0
        assert lifecycle.json()["protected_count"] == 4
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


def test_presentation_registration_preserves_owner_and_allows_member_listing(tmp_path, monkeypatch):
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
            session.add(
                SlideModel(
                    owner_id=users["owner"].id,
                    presentation=presentation_id,
                    layout_group="general",
                    layout="general-1",
                    index=0,
                    content={"title": "企业架构"},
                    ui={"id": "slide-1", "elements": []},
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
            json={"user_id": str(users["member"].id), "role": "reviewer"},
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
        entry_id = registered.json()["id"]
        submitted = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/review/submit"
        )
        self_review_denied = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/review/decision",
            json={"action": "approve"},
        )
        approval_quality_blocked = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/review/decision",
            json={"action": "approve"},
            headers={"x-test-user": "member"},
        )
        quality = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/quality-runs"
        )
        blocking_comment = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/comment-threads",
            json={"slide_index": 0, "title": "补充数据口径", "body": "明确架构收益的统计口径", "is_blocking": True, "assigned_to": str(users["member"].id), "due_at": "2020-01-01T00:00:00Z"},
        )
        member_notifications = client.get(
            "/api/v1/enterprise/notifications",
            params={"workspace_id": workspace["id"], "unread_only": True},
            headers={"x-test-user": "member"},
        )
        marked_notification = client.post(
            f"/api/v1/enterprise/notifications/{member_notifications.json()['notifications'][0]['id']}/read",
            headers={"x-test-user": "member"},
        )
        outsider_notification_denied = client.post(
            f"/api/v1/enterprise/notifications/{member_notifications.json()['notifications'][0]['id']}/read",
            headers={"x-test-user": "outsider"},
        )
        member_read_all = client.post(
            "/api/v1/enterprise/notifications/read-all",
            params={"workspace_id": workspace["id"]},
            headers={"x-test-user": "member"},
        )
        review_inbox = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/review-inbox"
        )
        member_review_inbox = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/review-inbox",
            params={"scope": "mine", "overdue_only": True},
            headers={"x-test-user": "member"},
        )
        approval_comment_blocked = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/review/decision",
            json={"action": "approve"},
            headers={"x-test-user": "member"},
        )
        comment_reply = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/comment-threads/{blocking_comment.json()['id']}/replies",
            json={"body": "已按统一口径补充说明"},
            headers={"x-test-user": "member"},
        )
        resolved_comment = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/comment-threads/{blocking_comment.json()['id']}/resolve",
            headers={"x-test-user": "member"},
        )
        approved = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/review/decision",
            json={"action": "approve", "comment": "内容与品牌规范检查通过"},
            headers={"x-test-user": "member"},
        )
        freeze_preflight = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/freeze-preflight"
        )
        frozen = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/freeze"
        )
        assert freeze_preflight.status_code == 200
        assert freeze_preflight.json()["can_freeze"] is True
        assert {item["code"] for item in freeze_preflight.json()["checks"]} == {"review", "quality", "comments", "citations"}
        assert frozen.json()["manifest"]["citation_manifest"] == []
        assert len(frozen.json()["manifest"]["citation_manifest_hash"]) == 64
        snapshot_evidence = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/snapshots/{frozen.json()['id']}/evidence"
        )
        assert snapshot_evidence.status_code == 200
        assert snapshot_evidence.json()["manifest_integrity"] is True
        assert snapshot_evidence.json()["citation_integrity"] is True
        assert snapshot_evidence.json()["citations"] == []
        frozen_update_denied = client.patch(
            "/api/v1/ppt/presentation/update",
            json={"id": str(presentation_id), "title": "不应覆盖的标题"},
        )
        delivery_path = tmp_path / "general-delivery.pdf"
        delivery_path.write_bytes(b"governed-general-pdf")

        async def fake_general_export(*_args, **_kwargs):
            return SimpleNamespace(path=str(delivery_path))

        monkeypatch.setattr(
            "services.enterprise.presentation_delivery_service.export_presentation",
            fake_general_export,
        )
        delivery = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/deliveries",
            json={"snapshot_id": frozen.json()["id"], "format": "pdf"},
        )
        delivery_evidence = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/deliveries/{delivery.json()['id']}/evidence"
        )
        delivery_grant = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/deliveries/{delivery.json()['id']}/grants",
            json={"expires_in_minutes": 30, "max_downloads": 1},
        )
        delivery_download = client.get(delivery_grant.json()["download_url"])
        revocable_delivery_grant = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/deliveries/{delivery.json()['id']}/grants",
            json={"expires_in_minutes": 30, "max_downloads": 1},
        )
        revoked_delivery = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/deliveries/{delivery.json()['id']}/revoke"
        )
        revoked_delivery_download = client.get(
            revocable_delivery_grant.json()["download_url"]
        )
        revoked_delivery_grant_denied = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/deliveries/{delivery.json()['id']}/grants",
            json={"expires_in_minutes": 30, "max_downloads": 1},
        )
        delivery_activity = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/deliveries/{delivery.json()['id']}/activity"
        )
        delivery_activity_denied = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/deliveries/{delivery.json()['id']}/activity",
            headers={"x-test-user": "member"},
        )
        governance = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/governance",
            headers={"x-test-user": "member"},
        )
        comments = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/comment-threads",
            headers={"x-test-user": "member"},
        )
        snapshot_diff = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/snapshot-diff",
            params={"from_snapshot_id": frozen.json()["id"], "to_snapshot_id": frozen.json()["id"]},
            headers={"x-test-user": "member"},
        )
        shared_read = client.get(
            f"/api/v1/ppt/presentation/{presentation_id}",
            headers={"x-test-user": "member"},
        )

        assert registered.status_code == 201
        assert registered.json()["title"] == "企业架构汇报"
        assert member_entries.status_code == 200
        assert member_entries.json()[0]["presentation_id"] == str(presentation_id)
        assert member_entries.json()[0]["can_open"] is True
        assert registered.json()["can_open"] is True
        assert member_cannot_register_owner_presentation.status_code == 404
        assert submitted.json()["status"] == "pending"
        assert self_review_denied.status_code == 409
        assert approval_quality_blocked.status_code == 409
        assert quality.json()["status"] == "passed"
        assert blocking_comment.status_code == 201
        assert blocking_comment.json()["slide_index"] == 0
        assert member_notifications.json()["unread_count"] >= 1
        assert {item["notification_type"] for item in member_notifications.json()["notifications"]} >= {"presentation.comment_assigned", "presentation.comment_overdue", "presentation.review_submitted"}
        assert marked_notification.json()["is_read"] is True
        assert outsider_notification_denied.status_code == 404
        assert member_read_all.status_code == 200
        assert review_inbox.json()["summary"] == {"open_count": 1, "blocking_count": 1, "overdue_count": 1, "assigned_to_me_count": 0}
        assert member_review_inbox.json()["summary"]["assigned_to_me_count"] == 1
        assert member_review_inbox.json()["tasks"][0]["presentation_title"] == "企业架构汇报"
        assert member_review_inbox.json()["tasks"][0]["is_overdue"] is True
        assert approval_comment_blocked.status_code == 409
        assert comment_reply.status_code == 201
        assert resolved_comment.json()["status"] == "resolved"
        assert approved.json()["status"] == "approved"
        assert frozen.status_code == 200
        assert frozen_update_denied.status_code == 409
        assert delivery.status_code == 201
        assert delivery_evidence.status_code == 200
        assert delivery_evidence.json()["file_integrity"] is True
        assert delivery_evidence.json()["snapshot_integrity"] is True
        assert delivery_evidence.json()["citation_integrity"] is True
        assert len(delivery_evidence.json()["credential_hash"]) == 64
        assert delivery.json()["watermark_text"] == "共享空间 · L2 · owner"
        assert "file_path" not in delivery.json()
        assert delivery_download.content == b"governed-general-pdf"
        assert revoked_delivery.json()["status"] == "revoked"
        assert revoked_delivery.json()["revoked_at"]
        assert revoked_delivery_download.status_code == 404
        assert revoked_delivery_grant_denied.status_code == 409
        assert delivery_activity.status_code == 200
        assert {item["action"] for item in delivery_activity.json()} >= {
            "presentation.delivery_exported",
            "presentation.download_grant_issued",
            "presentation.delivery_downloaded",
            "presentation.delivery_revoked",
        }
        assert delivery_activity_denied.status_code == 404
        assert frozen.json()["version_no"] == 1
        assert frozen.json()["manifest"]["scene"]["type"] == "general"
        assert governance.json()["entry"]["status"] == "frozen"
        assert len(governance.json()["reviews"]) == 1
        assert len(governance.json()["snapshots"]) == 1
        assert comments.json()[0]["replies"][0]["body"] == "已按统一口径补充说明"
        assert snapshot_diff.json()["unchanged"] == 1
        assert shared_read.status_code == 200
        assert shared_read.json()["slides"][0]["ui"]["id"] == "slide-1"
    finally:
        asyncio.run(engine.dispose())


def test_asset_library_page_snapshot_lifecycle_and_reuse(tmp_path, monkeypatch):
    client, engine, session_maker, users = _build_client(tmp_path)
    preview_source = tmp_path / "rendered-preview.png"
    preview_source.write_bytes(b"rendered-enterprise-asset-preview")

    async def fake_render_json_to_image(_components, _width, _height):
        return SimpleNamespace(path=str(preview_source))

    monkeypatch.setenv("APP_DATA_DIRECTORY", str(tmp_path / "app-data"))
    monkeypatch.setattr(asset_preview_service, "async_session_maker", session_maker)
    monkeypatch.setattr(
        asset_preview_service.EXPORT_TASK_SERVICE,
        "render_json_to_image",
        fake_render_json_to_image,
    )
    presentation_id = uuid.uuid4()
    slide_id = uuid.uuid4()

    async def seed_presentation():
        async with session_maker() as session:
            session.add(
                PresentationModel(
                    id=presentation_id,
                    owner_id=users["owner"].id,
                    version=PresentationVersion.V2_STANDARD,
                    content="quarterly business review",
                    n_slides=1,
                    language="Chinese",
                    title="季度经营复盘",
                )
            )
            session.add(
                SlideModel(
                    id=slide_id,
                    owner_id=users["owner"].id,
                    presentation=presentation_id,
                    layout_group="general",
                    layout="metrics",
                    index=0,
                    content={"title": "核心经营指标", "value": "42%"},
                    ui={"id": "asset-source", "components": []},
                )
            )
            await session.commit()

    asyncio.run(seed_presentation())
    try:
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "经营分析空间", "workspace_type": "team"},
        ).json()
        client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "reviewer"},
        )
        entry = client.post(
            "/api/v1/enterprise/presentations",
            json={
                "workspace_id": workspace["id"],
                "presentation_id": str(presentation_id),
                "scene_type": "general",
            },
        ).json()

        saved = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/slides/{slide_id}/assets",
            json={
                "scope_type": "workspace",
                "name": "经营指标页",
                "tags": ["经营", "指标"],
            },
        )
        asset_id = saved.json()["id"]
        owner_thumbnail = client.get(
            f"/api/v1/enterprise/assets/{asset_id}/thumbnail"
        )
        member_draft_thumbnail_denied = client.get(
            f"/api/v1/enterprise/assets/{asset_id}/thumbnail",
            headers={"x-test-user": "member"},
        )
        hidden_draft = client.get(
            "/api/v1/enterprise/assets",
            params={"workspace_id": workspace["id"], "asset_type": "page"},
            headers={"x-test-user": "member"},
        )
        published = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/transitions/publish"
        )
        visible_published = client.get(
            "/api/v1/enterprise/assets",
            params={"workspace_id": workspace["id"], "asset_type": "page", "tags": "经营"},
            headers={"x-test-user": "member"},
        )
        member_thumbnail = client.get(
            f"/api/v1/enterprise/assets/{asset_id}/thumbnail",
            headers={"x-test-user": "member"},
        )
        outsider_thumbnail_denied = client.get(
            f"/api/v1/enterprise/assets/{asset_id}/thumbnail",
            headers={"x-test-user": "outsider"},
        )
        preview_retry = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/preview-tasks"
        )
        member_favorite = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/favorite",
            headers={"x-test-user": "member"},
        )
        member_favorites = client.get(
            "/api/v1/enterprise/assets/personalized",
            params={"workspace_id": workspace["id"], "view": "favorites"},
            headers={"x-test-user": "member"},
        )
        member_recommendations = client.get(
            "/api/v1/enterprise/assets/personalized",
            params={
                "workspace_id": workspace["id"],
                "view": "recommended",
                "scene_type": "general",
                "tags": "经营",
            },
            headers={"x-test-user": "member"},
        )
        reviewer_insert_denied = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/insert-page",
            json={
                "workspace_id": workspace["id"],
                "presentation_entry_id": entry["id"],
                "after_index": 0,
            },
            headers={"x-test-user": "member"},
        )
        personal_asset = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/slides/{slide_id}/assets",
            json={
                "scope_type": "personal",
                "name": "个人经营指标页",
                "tags": ["经营", "待提升"],
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            },
        ).json()
        second_personal_asset = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/slides/{slide_id}/assets",
            json={
                "scope_type": "personal",
                "name": "个人经营指标页二",
                "tags": ["经营", "批量治理"],
            },
        ).json()
        similar_personal_assets = client.get(
            f"/api/v1/enterprise/assets/{personal_asset['id']}/similar",
            params={"workspace_id": workspace["id"]},
        )
        confirmed_duplicate = client.post(
            f"/api/v1/enterprise/assets/{second_personal_asset['id']}/duplicate-decision",
            json={"action": "confirm", "canonical_asset_id": personal_asset["id"]},
        )
        client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "admin"},
        )
        unconfirmed_promotion = client.post(
            f"/api/v1/enterprise/assets/{personal_asset['id']}/promotion-requests",
            json={
                "target_scope_type": "workspace",
                "target_workspace_id": workspace["id"],
                "justification": "供经营复盘团队统一复用",
                "desensitization_notes": "已移除客户名称和敏感经营明细",
                "authorization_confirmed": False,
            },
        )
        promotion = client.post(
            f"/api/v1/enterprise/assets/{personal_asset['id']}/promotion-requests",
            json={
                "target_scope_type": "workspace",
                "target_workspace_id": workspace["id"],
                "justification": "供经营复盘团队统一复用",
                "desensitization_notes": "已移除客户名称和敏感经营明细",
                "authorization_confirmed": True,
            },
        )
        duplicate_promotion = client.post(
            f"/api/v1/enterprise/assets/{personal_asset['id']}/promotion-requests",
            json={
                "target_scope_type": "workspace",
                "target_workspace_id": workspace["id"],
                "justification": "供经营复盘团队统一复用",
                "desensitization_notes": "已移除客户名称和敏感经营明细",
                "authorization_confirmed": True,
            },
        )
        self_approval_denied = client.post(
            f"/api/v1/enterprise/asset-promotion-requests/{promotion.json()['id']}/decision",
            json={"action": "approve", "comment": "申请人自行审批"},
        )
        review_queue = client.get(
            "/api/v1/enterprise/asset-promotion-requests",
            params={"workspace_id": workspace["id"], "view": "review"},
            headers={"x-test-user": "member"},
        )
        approved_promotion = client.post(
            f"/api/v1/enterprise/asset-promotion-requests/{promotion.json()['id']}/decision",
            json={"action": "approve", "comment": "脱敏与授权检查通过"},
            headers={"x-test-user": "member"},
        )
        promoted_assets = client.get(
            "/api/v1/enterprise/assets",
            params={"workspace_id": workspace["id"]},
            headers={"x-test-user": "member"},
        )
        requester_notifications = client.get(
            "/api/v1/enterprise/notifications",
            params={"workspace_id": workspace["id"]},
        )
        bulk_published = client.post(
            "/api/v1/enterprise/assets/bulk-transition",
            json={
                "asset_ids": [personal_asset["id"], second_personal_asset["id"]],
                "action": "publish",
            },
        )
        enterprise_promotion = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/promotion-requests",
            json={
                "target_scope_type": "enterprise",
                "justification": "供企业经营汇报场景统一复用",
                "desensitization_notes": "已移除空间成员、客户和内部经营明细",
                "authorization_confirmed": True,
            },
        )
        enterprise_review_queue = client.get(
            "/api/v1/enterprise/asset-promotion-requests",
            params={"view": "review"},
            headers={"x-test-user": "admin"},
        )
        enterprise_approved = client.post(
            f"/api/v1/enterprise/asset-promotion-requests/{enterprise_promotion.json()['id']}/decision",
            json={"action": "approve", "comment": "企业范围授权与脱敏检查通过"},
            headers={"x-test-user": "admin"},
        )
        enterprise_assets = client.get(
            "/api/v1/enterprise/assets",
            params={"workspace_id": workspace["id"]},
        )

        async def change_target_theme():
            async with session_maker() as session:
                target = await session.get(PresentationModel, presentation_id)
                target.theme = {"colors": {"primary": "#0052CC"}}
                session.add(target)
                await session.commit()

        asyncio.run(change_target_theme())
        compatibility = client.get(
            f"/api/v1/enterprise/assets/{asset_id}/compatibility",
            params={
                "workspace_id": workspace["id"],
                "presentation_entry_id": entry["id"],
            },
        )
        inserted = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/insert-page",
            json={
                "workspace_id": workspace["id"],
                "presentation_entry_id": entry["id"],
                "after_index": 0,
            },
        )
        chart_asset = client.post(
            "/api/v1/enterprise/assets",
            json={
                "workspace_id": workspace["id"],
                "scope_type": "workspace",
                "asset_type": "chart",
                "name": "季度趋势图",
                "tags": ["经营", "图表"],
                "payload": {
                    "format": "presentation-element-v1",
                    "element": {
                        "type": "chart",
                        "chart_type": "bar",
                        "data": {
                            "labels": ["Q1", "Q2"],
                            "datasets": [{"label": "收入", "data": [12, 18]}],
                        },
                        "size": {"width": 520, "height": 280},
                    },
                },
                "compatibility": {"presentation_version": "v2-standard", "editable": True},
            },
        )
        chart_asset_id = chart_asset.json()["id"]
        client.post(f"/api/v1/enterprise/assets/{chart_asset_id}/transitions/publish")
        inserted_chart = client.post(
            f"/api/v1/enterprise/assets/{chart_asset_id}/insert-element",
            json={
                "workspace_id": workspace["id"],
                "presentation_entry_id": entry["id"],
                "slide_id": str(slide_id),
            },
        )
        semantic_search = client.get(
            "/api/v1/enterprise/assets/search",
            params={"workspace_id": workspace["id"], "q": "季度趋势收入", "asset_type": "chart"},
        )
        element_asset_specs = [
            ("image", "品牌主视觉", {"format": "presentation-element-v1", "element": {"type": "image", "data": "/app_data/images/brand.png", "size": {"width": 320, "height": 180}}}),
            ("copy", "标准结论文案", {"format": "presentation-element-v1", "element": {"type": "text", "runs": [{"text": "经营质量持续改善"}], "size": {"width": 420, "height": 80}}}),
            ("component", "结论组合组件", {"format": "presentation-component-v1", "component": {"id": "insight", "description": "Reusable insight component", "elements": [{"type": "text", "runs": [{"text": "关键洞察"}], "size": {"width": 300, "height": 60}}]}}),
        ]
        additional_insertions = []
        for asset_type, asset_name, payload in element_asset_specs:
            created_element_asset = client.post(
                "/api/v1/enterprise/assets",
                json={
                    "workspace_id": workspace["id"],
                    "scope_type": "workspace",
                    "asset_type": asset_type,
                    "name": asset_name,
                    "payload": payload,
                    "compatibility": {"presentation_version": "v2-standard", "editable": True},
                },
            ).json()
            client.post(f"/api/v1/enterprise/assets/{created_element_asset['id']}/transitions/publish")
            additional_insertions.append(client.post(
                f"/api/v1/enterprise/assets/{created_element_asset['id']}/insert-element",
                json={"workspace_id": workspace["id"], "presentation_entry_id": entry["id"], "slide_id": str(slide_id)},
            ))
        saved_selected_chart = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/slides/{slide_id}/element-assets",
            json={
                "scope_type": "personal",
                "asset_type": "chart",
                "name": "从编辑器保存的趋势图",
                "tags": ["选中元素"],
                "component_index": 0,
                "element_index": 0,
            },
        )
        reused_assets = client.get(
            "/api/v1/enterprise/assets",
            params={"workspace_id": workspace["id"]},
        )
        analytics = client.get(
            "/api/v1/enterprise/assets/analytics",
            params={"workspace_id": workspace["id"]},
        )
        recent_assets = client.get(
            "/api/v1/enterprise/assets/personalized",
            params={"workspace_id": workspace["id"], "view": "recent"},
        )
        owner_favorite = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/favorite"
        )
        owner_unfavorite = client.delete(
            f"/api/v1/enterprise/assets/{asset_id}/favorite"
        )
        new_version = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry['id']}/slides/{slide_id}/assets/{asset_id}/versions",
            json={},
        )
        version_history = client.get(
            f"/api/v1/enterprise/assets/{asset_id}/versions"
        )
        published_new_version = client.post(
            f"/api/v1/enterprise/assets/{new_version.json()['id']}/transitions/publish"
        )
        old_version_after_publish = next(
            version for version in client.get(
                f"/api/v1/enterprise/assets/{asset_id}/versions"
            ).json() if version["id"] == asset_id
        )

        async def change_target_presentation_version():
            async with session_maker() as session:
                target = await session.get(PresentationModel, presentation_id)
                target.version = PresentationVersion.V1_STANDARD
                session.add(target)
                await session.commit()

        asyncio.run(change_target_presentation_version())
        blocked_compatibility = client.get(
            f"/api/v1/enterprise/assets/{new_version.json()['id']}/compatibility",
            params={
                "workspace_id": workspace["id"],
                "presentation_entry_id": entry["id"],
            },
        )
        blocked_insert = client.post(
            f"/api/v1/enterprise/assets/{new_version.json()['id']}/insert-page",
            json={
                "workspace_id": workspace["id"],
                "presentation_entry_id": entry["id"],
                "after_index": 1,
            },
        )
        presentation = client.get(f"/api/v1/ppt/presentation/{presentation_id}")
        offline = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/transitions/offline"
        )
        offline_insert_denied = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/insert-page",
            json={
                "workspace_id": workspace["id"],
                "presentation_entry_id": entry["id"],
                "after_index": 1,
            },
        )
        outsider_list_denied = client.get(
            "/api/v1/enterprise/assets",
            params={"workspace_id": workspace["id"]},
            headers={"x-test-user": "outsider"},
        )

        async def fail_render_json_to_image(_components, _width, _height):
            raise RuntimeError("preview renderer unavailable")

        monkeypatch.setattr(
            asset_preview_service.EXPORT_TASK_SERVICE,
            "render_json_to_image",
            fail_render_json_to_image,
        )
        failed_preview = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/preview-tasks"
        )
        failed_preview_asset = next(
            item
            for item in client.get(
                f"/api/v1/enterprise/assets/{asset_id}/versions"
            ).json()
            if item["id"] == asset_id
        )
        monkeypatch.setattr(
            asset_preview_service.EXPORT_TASK_SERVICE,
            "render_json_to_image",
            fake_render_json_to_image,
        )
        recovered_preview = client.post(
            f"/api/v1/enterprise/assets/{asset_id}/preview-tasks"
        )
        recovered_preview_asset = next(
            item
            for item in client.get(
                f"/api/v1/enterprise/assets/{asset_id}/versions"
            ).json()
            if item["id"] == asset_id
        )
        events = client.get(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/audit-events"
        ).json()

        assert saved.status_code == 201
        assert saved.json()["status"] == "draft"
        assert saved.json()["payload_hash"]
        assert saved.json()["preview_status"] == "queued"
        assert saved.json()["preview_task_id"]
        assert owner_thumbnail.status_code == 200
        assert owner_thumbnail.content == b"rendered-enterprise-asset-preview"
        assert member_draft_thumbnail_denied.status_code == 404
        assert hidden_draft.json() == []
        assert published.json()["status"] == "published"
        assert [item["id"] for item in visible_published.json()] == [asset_id]
        assert visible_published.json()[0]["preview_status"] == "ready"
        assert visible_published.json()[0]["preview_url"].endswith(f"/{asset_id}/thumbnail")
        assert member_thumbnail.content == b"rendered-enterprise-asset-preview"
        assert outsider_thumbnail_denied.status_code == 404
        assert preview_retry.status_code == 202
        assert preview_retry.json()["task_id"] != saved.json()["preview_task_id"]
        assert member_favorite.json() == {"asset_id": asset_id, "is_favorite": True}
        assert member_favorites.json()[0]["asset"]["id"] == asset_id
        assert member_favorites.json()[0]["is_favorite"] is True
        assert member_recommendations.json()[0]["asset"]["id"] == asset_id
        assert any("标签" in reason for reason in member_recommendations.json()[0]["recommendation_reasons"])
        assert reviewer_insert_denied.status_code == 404
        assert second_personal_asset["duplicate_status"] == "suspected"
        assert second_personal_asset["duplicate_of_asset_id"] == personal_asset["id"]
        assert similar_personal_assets.json()[0]["asset"]["id"] == second_personal_asset["id"]
        assert similar_personal_assets.json()[0]["exact_duplicate"] is True
        assert confirmed_duplicate.json()["duplicate_status"] == "confirmed"
        assert unconfirmed_promotion.status_code == 422
        assert promotion.status_code == 201
        assert promotion.json()["status"] == "pending"
        assert duplicate_promotion.status_code == 409
        assert self_approval_denied.status_code == 409
        assert review_queue.json()[0]["id"] == promotion.json()["id"]
        assert approved_promotion.json()["status"] == "approved"
        promoted_asset = next(item for item in promoted_assets.json() if item["id"] == approved_promotion.json()["promoted_asset_id"])
        assert promoted_asset["scope_type"] == "workspace"
        assert promoted_asset["status"] == "published"
        assert promoted_asset["parent_asset_id"] == personal_asset["id"]
        assert any(item["notification_type"] == "asset.promotion_approved" for item in requester_notifications.json()["notifications"])
        assert any(item["notification_type"] == "asset.authorization_expiring" for item in requester_notifications.json()["notifications"])
        assert bulk_published.status_code == 200
        assert {item["status"] for item in bulk_published.json()} == {"published"}
        assert enterprise_promotion.status_code == 201
        assert enterprise_review_queue.json()[0]["id"] == enterprise_promotion.json()["id"]
        assert enterprise_approved.json()["status"] == "approved"
        promoted_enterprise_asset = next(item for item in enterprise_assets.json() if item["id"] == enterprise_approved.json()["promoted_asset_id"])
        assert promoted_enterprise_asset["scope_type"] == "enterprise"
        assert promoted_enterprise_asset["parent_asset_id"] == asset_id
        assert promoted_enterprise_asset["preview_status"] == "ready"
        assert promoted_enterprise_asset["preview_url"]
        assert compatibility.status_code == 200
        assert compatibility.json()["status"] == "warning"
        assert compatibility.json()["can_insert"] is True
        assert any(issue["code"] == "theme_mismatch" for issue in compatibility.json()["issues"])
        assert inserted.status_code == 201
        assert inserted.json()["slide_index"] == 1
        assert inserted.json()["compatibility"]["status"] == "warning"
        assert chart_asset.status_code == 201
        assert inserted_chart.status_code == 201
        assert inserted_chart.json()["asset_type"] == "chart"
        assert inserted_chart.json()["component_index"] == 0
        assert semantic_search.status_code == 200
        assert semantic_search.json()[0]["asset"]["id"] == chart_asset_id
        assert "内容语义匹配" in semantic_search.json()[0]["reasons"]
        assert [response.status_code for response in additional_insertions] == [201, 201, 201]
        assert [response.json()["component_index"] for response in additional_insertions] == [1, 2, 3]
        assert saved_selected_chart.status_code == 201
        assert saved_selected_chart.json()["asset_type"] == "chart"
        assert saved_selected_chart.json()["source_slide_id"] == str(slide_id)
        assert next(item for item in reused_assets.json() if item["id"] == asset_id)["usage_count"] == 1
        assert analytics.status_code == 200
        assert analytics.json()["total_reuses"] == 5
        assert analytics.json()["unique_presentations"] == 1
        assert analytics.json()["unique_users"] == 1
        assert {item["asset_id"] for item in analytics.json()["top_assets"]} >= {asset_id, chart_asset_id}
        assert saved.json()["preview"]["title"] == "核心经营指标"
        assert {item["asset"]["id"] for item in recent_assets.json()} >= {asset_id, chart_asset_id}
        assert all(item["last_used_at"] for item in recent_assets.json())
        assert owner_favorite.json()["is_favorite"] is True
        assert owner_unfavorite.json()["is_favorite"] is False
        assert new_version.status_code == 201
        assert new_version.json()["version_no"] == 2
        assert new_version.json()["supersedes_asset_id"] == asset_id
        assert new_version.json()["is_latest"] is False
        assert [version["version_no"] for version in version_history.json()] == [2, 1]
        assert published_new_version.json()["is_latest"] is True
        assert old_version_after_publish["is_latest"] is False
        assert blocked_compatibility.json()["status"] == "blocked"
        assert blocked_compatibility.json()["can_insert"] is False
        assert any(issue["code"] == "presentation_version_mismatch" for issue in blocked_compatibility.json()["issues"])
        assert blocked_insert.status_code == 409
        assert blocked_insert.json()["detail"]["compatibility"]["status"] == "blocked"
        assert len(presentation.json()["slides"]) == 2
        assert presentation.json()["slides"][1]["content"]["title"] == "核心经营指标"
        assert presentation.json()["slides"][0]["ui"]["components"][0]["elements"][0]["type"] == "chart"
        assert [component["elements"][0]["type"] for component in presentation.json()["slides"][0]["ui"]["components"]] == ["chart", "image", "text", "text"]
        assert offline.json()["status"] == "offline"
        assert offline_insert_denied.status_code == 409
        assert outsider_list_denied.status_code == 404
        assert failed_preview.status_code == 202
        assert failed_preview_asset["preview_status"] == "error"
        assert failed_preview_asset["preview_url"] is None
        assert failed_preview_asset["preview"]["title"] == "核心经营指标"
        assert "renderer unavailable" in failed_preview_asset["preview_error"]
        assert recovered_preview.status_code == 202
        assert recovered_preview_asset["preview_status"] == "ready"
        assert recovered_preview_asset["preview_error"] is None
        assert {event["action"] for event in events} >= {
            "asset.created", "asset.publish", "asset.reused", "asset.offline",
            "asset.promotion_requested", "asset.promotion_approved",
            "asset.favorited", "asset.unfavorited",
            "asset.preview_queued", "asset.preview_ready", "asset.preview_failed",
            "asset.version_created",
            "asset.element_reused",
        }
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
        entry_id = entries.json()[0]["id"]
        no_review_policy = client.put(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/governance-policy",
            json={"review_mode": "none", "quality_gate_enabled": True, "require_numeric_citations": False},
        )
        blank_quality = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/quality-runs"
        )
        direct_freeze = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{entry_id}/freeze"
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
        assert no_review_policy.json()["governance_policy"]["review_mode"] == "none"
        assert blank_quality.json()["status"] == "passed"
        assert direct_freeze.status_code == 200
        assert direct_freeze.json()["review_id"]
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


def test_bid_understanding_flow_enforces_project_access_and_strategy_gate(tmp_path, monkeypatch):
    client, engine, session_maker, users = _build_client(tmp_path)
    try:
        workspace = client.post(
            "/api/v1/enterprise/workspaces",
            json={"name": "竞标项目空间", "workspace_type": "team"},
        ).json()
        template_id = str(uuid.uuid4())
        publication_id = uuid.uuid4()

        async def seed_bid_template():
            async with session_maker() as session:
                session.add(TemplateV2(id=template_id, name="竞标摘要模板", layouts={"layouts": [{"id": "summary"}]}, assets={"slide_image_urls": ["/bid-preview.png"]}))
                session.add(TemplatePublicationModel(id=publication_id, publication_key="bid-summary", template_id=template_id, workspace_id=uuid.UUID(workspace["id"]), created_by=users["owner"].id, scope_type="scene", scene_type="bid", version=1, status="published", display_name="竞标摘要模板", compatibility={"pptx": True}, preview_url="/bid-preview.png", published_at=datetime.now(timezone.utc)))
                await session.commit()

        asyncio.run(seed_bid_template())
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
        collaboration = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/modules/initialize"
        )
        gate1_blocked = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/gates/gate_1/action",
            json={"action": "pass"},
            headers={"x-test-user": "member"},
        )
        reviewed_modules = []
        for module in collaboration.json()["modules"]:
            updated_module = client.put(
                f"/api/v1/enterprise/bid/projects/{project_id}/modules/{module['id']}",
                json={
                    "content": {
                        "summary": f"{module['module_type']} 专业方案",
                        "sources": ["protocol-summary:p2"],
                    },
                    "row_version": module["row_version"],
                },
            ).json()
            submitted_module = client.post(
                f"/api/v1/enterprise/bid/projects/{project_id}/modules/{module['id']}/submit"
            ).json()
            reviewed_modules.append(
                client.post(
                    f"/api/v1/enterprise/bid/projects/{project_id}/modules/{module['id']}/review",
                    json={"action": "approve", "comment": "专业审核通过"},
                    headers={"x-test-user": "member"},
                )
            )
            assert updated_module["status"] == "draft"
            assert submitted_module["status"] == "in_review"
        gate1_opened = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/gates/gate_1/action",
            json={"action": "open"},
            headers={"x-test-user": "member"},
        )
        gate1_passed = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/gates/gate_1/action",
            json={"action": "pass"},
            headers={"x-test-user": "member"},
        )
        commitment = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/commitments",
            json={
                "content": "承诺在约定条件下完成首批中心启动",
                "commitment_type": "timeline",
                "conditions": "客户按时确认中心名单",
                "evidence_ref": "historical-case:001",
                "risk_level": "high",
            },
        ).json()
        client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/commitments/{commitment['id']}/action",
            json={"action": "submit"},
        )
        self_approval_denied = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/commitments/{commitment['id']}/action",
            json={"action": "approve"},
        )
        client.put(
            f"/api/v1/enterprise/bid/projects/{project_id}/members/{users['member'].id}",
            json={"user_id": str(users["member"].id), "role": "bid_manager"},
        )
        commitment_approved = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/commitments/{commitment['id']}/action",
            json={"action": "approve", "comment": "依据充分"},
            headers={"x-test-user": "member"},
        )
        gate2_opened = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/gates/gate_2/action",
            json={"action": "open"},
            headers={"x-test-user": "member"},
        )
        gate2_passed = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/gates/gate_2/action",
            json={"action": "pass"},
            headers={"x-test-user": "member"},
        )
        assembled = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/releases/assemble",
            json={"template_publication_id": str(publication_id)},
        )
        release = assembled.json()
        freeze_blocked = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/releases/{release['id']}/freeze"
        )
        release_presentation = client.get(
            f"/api/v1/ppt/presentation/{release['manifest']['presentation_id']}"
        ).json()
        for slide in release_presentation["slides"]:
            citation = client.post(
                f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{release['presentation_entry_id']}/citations",
                json={"slide_id": slide["id"], "source_type": "bid_document", "source_id": "protocol-summary:v1", "locator": "p2"},
            )
            assert citation.status_code == 201
        bid_quality = client.post(
            f"/api/v1/enterprise/workspaces/{workspace['id']}/presentations/{release['presentation_entry_id']}/quality-runs"
        )
        gate3_opened = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/gates/gate_3/action",
            json={"action": "open"},
            headers={"x-test-user": "member"},
        )
        gate3_passed = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/gates/gate_3/action",
            json={"action": "pass"},
            headers={"x-test-user": "member"},
        )
        frozen = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/releases/{release['id']}/freeze"
        )
        delivery_path = tmp_path / "bid-delivery.pptx"
        delivery_path.write_bytes(b"watermarked-pptx-delivery")

        async def fake_export_presentation(*_args, **_kwargs):
            return SimpleNamespace(path=str(delivery_path))

        monkeypatch.setattr(
            "services.enterprise.bid_delivery_service.export_presentation",
            fake_export_presentation,
        )
        delivery = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/releases/{release['id']}/deliveries",
            json={"format": "pptx"},
        )
        outsider_deliveries = client.get(
            f"/api/v1/enterprise/bid/projects/{project_id}/releases/{release['id']}/deliveries",
            headers={"x-test-user": "outsider"},
        )
        grant = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/deliveries/{delivery.json()['id']}/grants",
            json={"expires_in_minutes": 30, "max_downloads": 1},
        )
        downloaded = client.get(grant.json()["download_url"])
        exhausted = client.get(grant.json()["download_url"])
        archived = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/releases/{release['id']}/archive"
        )
        revocable_grant = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/deliveries/{delivery.json()['id']}/grants",
            json={"expires_in_minutes": 30, "max_downloads": 1},
        )
        revoked_delivery = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/deliveries/{delivery.json()['id']}/revoke"
        )
        revoked_download = client.get(revocable_grant.json()["download_url"])
        revoked_grant_denied = client.post(
            f"/api/v1/enterprise/bid/projects/{project_id}/deliveries/{delivery.json()['id']}/grants",
            json={"expires_in_minutes": 30, "max_downloads": 1},
        )
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
        assert collaboration.status_code == 200
        assert len(collaboration.json()["modules"]) == 3
        assert gate1_blocked.status_code == 409
        assert all(response.json()["status"] == "approved" for response in reviewed_modules)
        assert gate1_opened.json()["status"] == "open"
        assert gate1_passed.json()["status"] == "passed"
        assert self_approval_denied.status_code == 409
        assert commitment_approved.json()["status"] == "approved"
        assert gate2_opened.json()["status"] == "open"
        assert gate2_passed.json()["status"] == "passed"
        assert assembled.status_code == 201
        expected_manifest_hash = hashlib.sha256(
            json.dumps(release["manifest"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert release["manifest_hash"] == expected_manifest_hash
        assert len(release["manifest"]["sources"]) == 4
        assert freeze_blocked.status_code == 409
        assert bid_quality.json()["status"] == "passed"
        assert gate3_opened.json()["status"] == "open"
        assert gate3_passed.json()["status"] == "passed"
        assert frozen.json()["status"] == "frozen"
        assert delivery.status_code == 201
        assert delivery.json()["watermark_text"] == "BID-2026-001 · L3 · owner"
        assert delivery.json()["sha256"] == hashlib.sha256(b"watermarked-pptx-delivery").hexdigest()
        assert "file_path" not in delivery.json()
        assert outsider_deliveries.status_code == 404
        assert grant.status_code == 201
        assert downloaded.content == b"watermarked-pptx-delivery"
        assert exhausted.status_code == 410
        assert archived.json()["status"] == "archived"
        assert revoked_delivery.json()["status"] == "revoked"
        assert revoked_delivery.json()["revoked_at"]
        assert revoked_download.status_code == 404
        assert revoked_grant_denied.status_code == 409
        assert reopened_profile.status_code == 200
        assert reopened_dashboard.json()["strategy"]["version_no"] == 2
        assert reopened_dashboard.json()["strategy"]["status"] == "draft"
        assert reopened_dashboard.json()["project"]["status"] == "understanding"
    finally:
        asyncio.run(engine.dispose())
