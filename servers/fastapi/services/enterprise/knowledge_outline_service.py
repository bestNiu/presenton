import os
import uuid
import hashlib
import json

import dirtyjson
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from constants.presentation import MAX_NUMBER_OF_SLIDES
from enums.async_task_status import AsyncTaskStatus
from models.presentation_outline_model import PresentationOutlineModel
from models.sql.async_task import AsyncTaskModel
from models.sql.enterprise.document import EnterpriseDocumentModel
from models.sql.enterprise.knowledge_outline import EnterpriseKnowledgeOutlineModel
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.presentation_governance import PresentationSourceCitationModel
from models.sql.presentation import PresentationModel
from models.sql.presentation import PresentationVersion
from models.sql.slide import SlideModel
from services.database import async_session_maker
from services.enterprise.audit_service import record_audit_event
from services.enterprise.document_service import authorize_document_scope
from services.enterprise.document_service import get_enterprise_document
from services.enterprise.knowledge_service import _terms, search_enterprise_knowledge
from services.enterprise.workspace_service import require_workspace_role
from services.enterprise.presentation_workspace_service import attach_presentation_to_workspace
from domains.platform.enums import PresentationCreationMode, WorkspaceRole
from utils.llm_calls.generate_presentation_outlines import generate_ppt_outline
from utils.outline_limits import normalize_outline_payload


KNOWLEDGE_OUTLINE_TASK_TYPE = "enterprise.knowledge-outline"


async def build_knowledge_context(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    query: str,
    scope_type: str,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    document_ids: list[uuid.UUID],
    max_characters: int | None = None,
) -> tuple[str, list[dict]]:
    budget = max_characters or int(
        os.getenv("ENTERPRISE_KNOWLEDGE_CONTEXT_MAX_CHARACTERS", "16000")
    )
    budget = max(2000, min(budget, 60000))
    results = await search_enterprise_knowledge(
        session,
        principal=principal,
        query=query,
        scope_type=scope_type,
        workspace_id=workspace_id,
        project_id=project_id,
        categories=[],
        latest_only=True,
        limit=50,
        document_ids=document_ids,
        retrieval_mode="hybrid",
    )
    blocks: list[str] = []
    manifest: list[dict] = []
    used = 0
    for index, item in enumerate(results, start=1):
        reference = f"K{index}"
        block = (
            f"[{reference}] 文档：{item['logical_name']}；版本：{item['document_version']}；"
            f"位置：{item['citation']['locator']}\n{item['citation']['excerpt']}"
        )
        if blocks and used + len(block) > budget:
            break
        block = block[:budget] if not blocks else block
        blocks.append(block)
        used += len(block)
        manifest.append(
            {
                "ref": reference,
                "chunk_id": str(item["chunk_id"]),
                "document_id": str(item["document_id"]),
                "document_version": item["document_version"],
                "logical_name": item["logical_name"],
                "heading": item["heading"],
                "citation": item["citation"],
                "score": item["score"],
            }
        )
    if not manifest:
        raise HTTPException(
            status_code=422, detail="No authorized knowledge matched the outline topic"
        )
    return "\n\n".join(blocks), manifest


def attach_outline_citations(outline: dict, manifest: list[dict]) -> dict:
    cited_slides: list[dict] = []
    for slide in outline.get("slides", []):
        content = str(slide.get("content", ""))
        content_terms = _terms(content)
        ranked = []
        for item in manifest:
            source_terms = _terms(
                f"{item['logical_name']} {item.get('heading') or ''} "
                f"{item['citation']['excerpt']}"
            )
            overlap = len(content_terms & source_terms)
            if overlap:
                ranked.append((overlap, item["ref"]))
        ranked.sort(reverse=True)
        refs = [ref for _, ref in ranked[:3]]
        if not refs and manifest:
            refs = [manifest[0]["ref"]]
        cited_slides.append({"content": content, "citation_refs": refs})
    return {"slides": cited_slides}


async def create_knowledge_outline(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    values: dict,
) -> tuple[EnterpriseKnowledgeOutlineModel, AsyncTaskModel]:
    workspace_id, project_id = await authorize_document_scope(
        session,
        principal=principal,
        scope_type=values["scope_type"],
        workspace_id=values.get("workspace_id"),
        project_id=values.get("project_id"),
        write=True,
    )
    topic = values["topic"].strip()
    query = (values.get("query") or topic).strip()
    outline = EnterpriseKnowledgeOutlineModel(
        workspace_id=workspace_id,
        project_id=project_id,
        created_by=principal.user_id,
        scope_type=values["scope_type"],
        topic=topic,
        query=query,
        audience=(values.get("audience") or "").strip() or None,
        language=values.get("language") or "Chinese",
        n_slides=values["n_slides"],
        document_ids=[str(item) for item in values.get("document_ids", [])],
        presentation_entry_id=values.get("presentation_entry_id"),
        idempotency_key=values.get("idempotency_key"),
        input_manifest_hash=values.get("input_manifest_hash"),
        input_manifest=values.get("input_manifest", []),
    )
    task = AsyncTaskModel(
        owner_id=principal.user_id,
        type=KNOWLEDGE_OUTLINE_TASK_TYPE,
        status=AsyncTaskStatus.PENDING,
        message="Queued for knowledge-backed outline generation",
        data={
            "outline_id": str(outline.id),
            "instructions": values.get("instructions"),
            "request_fingerprint": values.get("request_fingerprint"),
        },
    )
    outline.task_id = task.id
    session.add_all([outline, task])
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="knowledge_outline.created",
        resource_type="enterprise_knowledge_outline",
        resource_id=outline.id,
        metadata={"scope_type": outline.scope_type, "n_slides": outline.n_slides},
    )
    await session.commit()
    await session.refresh(outline)
    return outline, task


async def run_knowledge_outline_task(outline_id: uuid.UUID, task_id: str) -> None:
    async with async_session_maker() as session:
        outline = await session.get(EnterpriseKnowledgeOutlineModel, outline_id)
        task = await session.get(AsyncTaskModel, task_id)
        if outline is None or task is None or outline.task_id != task_id:
            return
        outline.status = "generating"
        task.message = "Building authorized knowledge context"
        await session.commit()
        principal = AuthPrincipal(
            user_id=outline.created_by,
            username="knowledge-outline-worker",
            is_admin=outline.scope_type == "enterprise",
            method="task",
        )
        try:
            context, manifest = await build_knowledge_context(
                session,
                principal=principal,
                query=outline.query,
                scope_type=outline.scope_type,
                workspace_id=outline.workspace_id,
                project_id=outline.project_id,
                document_ids=[uuid.UUID(item) for item in outline.document_ids],
            )
            instructions = (task.data or {}).get("instructions")
            governed_instructions = "\n".join(
                part
                for part in (
                    instructions,
                    "Only use the supplied enterprise knowledge. Do not invent facts. "
                    "Do not print source identifiers in slide text.",
                    f"Target audience: {outline.audience}" if outline.audience else None,
                )
                if part
            )
            generated = ""
            async for chunk in generate_ppt_outline(
                outline.topic,
                outline.n_slides,
                outline.language,
                context,
                instructions=governed_instructions,
                include_title_slide=True,
                web_search=False,
                include_table_of_contents=False,
            ):
                if isinstance(chunk, HTTPException):
                    raise chunk
                if isinstance(chunk, str):
                    generated += chunk
            payload = dict(dirtyjson.loads(generated))
            normalized = PresentationOutlineModel(
                **normalize_outline_payload(payload, MAX_NUMBER_OF_SLIDES)
            ).model_dump(mode="json")
            if len(normalized["slides"]) != outline.n_slides:
                raise ValueError("Model returned an unexpected number of outline slides")
            outline.context_manifest = manifest
            outline.outline = attach_outline_citations(normalized, manifest)
            outline.status = "ready"
            outline.error = None
            task.status = AsyncTaskStatus.COMPLETED
            task.message = "Knowledge-backed outline is ready"
            if outline.presentation_entry_id is not None:
                entry = await session.get(
                    PresentationEntryModel, outline.presentation_entry_id
                )
                presentation = (
                    await session.scalar(
                        select(PresentationModel)
                        .execution_options(skip_owner_scope=True)
                        .where(PresentationModel.id == entry.presentation_id)
                    )
                    if entry is not None
                    else None
                )
                if presentation is None:
                    raise ValueError("Linked enterprise presentation no longer exists")
                presentation.outlines = {
                    "slides": [
                        {"content": item["content"]}
                        for item in outline.outline["slides"]
                    ]
                }
                presentation.n_slides = len(presentation.outlines["slides"])
                presentation.title = outline.topic
                entry.title = outline.topic
                entry.creation_mode = PresentationCreationMode.DOCUMENT
                entry.row_version += 1
                session.add_all([presentation, entry])
            record_audit_event(
                session,
                actor_id=outline.created_by,
                workspace_id=outline.workspace_id,
                action="knowledge_outline.generated",
                resource_type="enterprise_knowledge_outline",
                resource_id=outline.id,
                metadata={"slide_count": outline.n_slides, "source_count": len(manifest)},
            )
        except Exception as exc:
            detail = str(getattr(exc, "detail", exc))[:4000]
            outline.status = "error"
            outline.error = detail
            task.status = AsyncTaskStatus.ERROR
            task.message = "Knowledge-backed outline generation failed"
            task.error = {"detail": detail}
        session.add_all([outline, task])
        await session.commit()


async def get_knowledge_outline(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    outline_id: uuid.UUID,
) -> EnterpriseKnowledgeOutlineModel:
    outline = await session.get(EnterpriseKnowledgeOutlineModel, outline_id)
    if outline is None:
        raise HTTPException(status_code=404, detail="Knowledge outline not found")
    await authorize_document_scope(
        session,
        principal=principal,
        scope_type=outline.scope_type,
        workspace_id=outline.workspace_id,
        project_id=outline.project_id,
        write=False,
    )
    return outline


async def create_knowledge_presentation(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    values: dict,
    idempotency_key: str | None,
) -> tuple[PresentationModel, PresentationEntryModel, EnterpriseKnowledgeOutlineModel, AsyncTaskModel, bool]:
    normalized_key = (idempotency_key or "").strip() or None
    if normalized_key and len(normalized_key) > 200:
        raise HTTPException(status_code=422, detail="Idempotency-Key is too long")
    request_fingerprint = hashlib.sha256(
        json.dumps(values, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    if normalized_key:
        existing = await session.scalar(
            select(EnterpriseKnowledgeOutlineModel).where(
                EnterpriseKnowledgeOutlineModel.created_by == principal.user_id,
                EnterpriseKnowledgeOutlineModel.idempotency_key == normalized_key,
            )
        )
        if existing is not None and existing.presentation_entry_id is not None:
            entry = await session.get(
                PresentationEntryModel, existing.presentation_entry_id
            )
            presentation = await session.scalar(
                select(PresentationModel)
                .execution_options(skip_owner_scope=True)
                .where(PresentationModel.id == entry.presentation_id)
            )
            task = await session.get(AsyncTaskModel, existing.task_id)
            if (task.data or {}).get("request_fingerprint") != request_fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was already used with another request",
                )
            return presentation, entry, existing, task, True

    workspace_id = values["workspace_id"]
    await authorize_document_scope(
        session,
        principal=principal,
        scope_type="workspace",
        workspace_id=workspace_id,
        project_id=None,
        write=True,
    )
    snapshots = []
    for document_id in values["document_ids"]:
        document = await get_enterprise_document(
            session, document_id=document_id, principal=principal
        )
        if document.scope_type != "workspace" or document.workspace_id != workspace_id:
            raise HTTPException(
                status_code=422, detail="Selected document belongs to another scope"
            )
        if (
            document.parse_status != "ready"
            or document.authorization_status == "revoked"
            or not document.is_latest
        ):
            raise HTTPException(
                status_code=409, detail="Selected document is not ready or current"
            )
        snapshots.append(
            {
                "document_id": str(document.id),
                "version_group_id": str(document.version_group_id),
                "version_no": document.version_no,
                "sha256": document.sha256,
            }
        )
    manifest_hash = hashlib.sha256(
        json.dumps(snapshots, sort_keys=True).encode("utf-8")
    ).hexdigest()
    presentation = PresentationModel(
        owner_id=principal.user_id,
        version=PresentationVersion.V2_STANDARD,
        content=values["topic"].strip(),
        n_slides=values["n_slides"],
        language=values.get("language") or "Chinese",
        title=values["topic"].strip(),
        instructions=values.get("instructions"),
        include_title_slide=True,
        include_table_of_contents=False,
        web_search=False,
    )
    session.add(presentation)
    entry = await attach_presentation_to_workspace(
        session,
        principal=principal,
        workspace_id=workspace_id,
        presentation=presentation,
        folder_id=values.get("folder_id"),
        scene_type="general",
        creation_mode=PresentationCreationMode.DOCUMENT,
    )
    outline_values = {
        "topic": values["topic"],
        "query": values.get("query") or values["topic"],
        "scope_type": "workspace",
        "workspace_id": workspace_id,
        "project_id": None,
        "document_ids": values["document_ids"],
        "audience": values.get("audience"),
        "language": values.get("language") or "Chinese",
        "n_slides": values["n_slides"],
        "instructions": values.get("instructions"),
        "presentation_entry_id": entry.id,
        "idempotency_key": normalized_key,
        "input_manifest_hash": manifest_hash,
        "input_manifest": snapshots,
        "request_fingerprint": request_fingerprint,
    }
    try:
        outline, task = await create_knowledge_outline(
            session, principal=principal, values=outline_values
        )
    except IntegrityError:
        await session.rollback()
        if normalized_key is None:
            raise
        existing = await session.scalar(
            select(EnterpriseKnowledgeOutlineModel).where(
                EnterpriseKnowledgeOutlineModel.created_by == principal.user_id,
                EnterpriseKnowledgeOutlineModel.idempotency_key == normalized_key,
            )
        )
        if existing is None or existing.presentation_entry_id is None:
            raise
        task = await session.get(AsyncTaskModel, existing.task_id)
        if (task.data or {}).get("request_fingerprint") != request_fingerprint:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used with another request",
            )
        entry = await session.get(PresentationEntryModel, existing.presentation_entry_id)
        presentation = await session.scalar(
            select(PresentationModel)
            .execution_options(skip_owner_scope=True)
            .where(PresentationModel.id == entry.presentation_id)
        )
        return presentation, entry, existing, task, True
    return presentation, entry, outline, task, False


async def apply_knowledge_outline_to_presentation(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    outline_id: uuid.UUID,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> EnterpriseKnowledgeOutlineModel:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    outline = await get_knowledge_outline(
        session, principal=principal, outline_id=outline_id
    )
    if outline.status != "ready":
        raise HTTPException(status_code=409, detail="Knowledge outline is not ready")
    if outline.workspace_id is not None and outline.workspace_id != workspace_id:
        raise HTTPException(status_code=422, detail="Knowledge outline belongs to another workspace")
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    presentation = await session.scalar(
        select(PresentationModel)
        .execution_options(skip_owner_scope=True)
        .where(PresentationModel.id == entry.presentation_id)
    )
    if presentation is None:
        raise HTTPException(status_code=404, detail="Presentation not found")
    presentation.outlines = {
        "slides": [
            {"content": item["content"]}
            for item in outline.outline.get("slides", [])
        ]
    }
    presentation.n_slides = len(presentation.outlines["slides"])
    presentation.title = outline.topic
    outline.presentation_entry_id = entry.id
    entry.creation_mode = PresentationCreationMode.DOCUMENT
    entry.title = outline.topic
    entry.row_version += 1
    session.add_all([presentation, entry, outline])
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="knowledge_outline.applied",
        resource_type="enterprise_knowledge_outline",
        resource_id=outline.id,
        metadata={"presentation_entry_id": str(entry.id)},
    )
    await session.commit()
    return outline


async def materialize_knowledge_outline_citations(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    outline_id: uuid.UUID,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> list[PresentationSourceCitationModel]:
    await require_workspace_role(
        session,
        workspace_id=workspace_id,
        principal=principal,
        required_role=WorkspaceRole.EDITOR,
    )
    outline = await get_knowledge_outline(
        session, principal=principal, outline_id=outline_id
    )
    if outline.status != "ready" or outline.presentation_entry_id != entry_id:
        raise HTTPException(status_code=409, detail="Knowledge outline is not applied")
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    for item in outline.input_manifest:
        latest = await session.scalar(
            select(EnterpriseDocumentModel).where(
                EnterpriseDocumentModel.version_group_id
                == uuid.UUID(item["version_group_id"]),
                EnterpriseDocumentModel.is_latest.is_(True),
            )
        )
        if latest is None or str(latest.id) != item["document_id"]:
            outline.input_status = "stale"
            session.add(outline)
            break
    slides = list(
        (
            await session.scalars(
                select(SlideModel)
                .execution_options(skip_owner_scope=True)
                .where(SlideModel.presentation == entry.presentation_id)
                .order_by(SlideModel.index)
            )
        ).all()
    )
    manifest = {item["ref"]: item for item in outline.context_manifest}
    created: list[PresentationSourceCitationModel] = []
    for slide_index, outline_slide in enumerate(outline.outline.get("slides", [])):
        if slide_index >= len(slides):
            break
        for ref in outline_slide.get("citation_refs", []):
            source = manifest.get(ref)
            if source is None:
                continue
            citation = source["citation"]
            document = await get_enterprise_document(
                session,
                document_id=uuid.UUID(citation["source_id"]),
                principal=principal,
            )
            if (
                document.parse_status != "ready"
                or document.authorization_status == "revoked"
                or str(document.version_no) != citation["source_version"]
            ):
                raise HTTPException(
                    status_code=409, detail="Knowledge citation source changed"
                )
            existing = await session.scalar(
                select(PresentationSourceCitationModel).where(
                    PresentationSourceCitationModel.presentation_entry_id == entry.id,
                    PresentationSourceCitationModel.slide_id == slides[slide_index].id,
                    PresentationSourceCitationModel.source_type
                    == citation["source_type"],
                    PresentationSourceCitationModel.source_id == citation["source_id"],
                    PresentationSourceCitationModel.source_version
                    == citation["source_version"],
                    PresentationSourceCitationModel.locator == citation["locator"],
                )
            )
            if existing is not None:
                created.append(existing)
                continue
            row = PresentationSourceCitationModel(
                presentation_entry_id=entry.id,
                slide_id=slides[slide_index].id,
                source_type=citation["source_type"],
                source_id=citation["source_id"],
                source_version=citation["source_version"],
                locator=citation["locator"],
                excerpt=citation["excerpt"],
                created_by=principal.user_id,
            )
            session.add(row)
            created.append(row)
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=workspace_id,
        action="knowledge_outline.citations_materialized",
        resource_type="enterprise_knowledge_outline",
        resource_id=outline.id,
        metadata={"presentation_entry_id": str(entry.id), "citation_count": len(created)},
    )
    await session.commit()
    return created


async def materialize_linked_knowledge_citations_for_presentation(
    session: AsyncSession,
    *,
    presentation_id: uuid.UUID,
) -> list[PresentationSourceCitationModel]:
    entry = await session.scalar(
        select(PresentationEntryModel).where(
            PresentationEntryModel.presentation_id == presentation_id
        )
    )
    if entry is None:
        return []
    outline = await session.scalar(
        select(EnterpriseKnowledgeOutlineModel)
        .where(
            EnterpriseKnowledgeOutlineModel.presentation_entry_id == entry.id,
            EnterpriseKnowledgeOutlineModel.status == "ready",
        )
        .order_by(EnterpriseKnowledgeOutlineModel.updated_at.desc())
    )
    if outline is None or outline.created_by is None:
        return []
    principal = AuthPrincipal(
        user_id=outline.created_by,
        username="knowledge-presentation-worker",
        is_admin=outline.scope_type == "enterprise",
        method="jwt",
    )
    return await materialize_knowledge_outline_citations(
        session,
        principal=principal,
        outline_id=outline.id,
        workspace_id=entry.workspace_id,
        entry_id=entry.id,
    )
