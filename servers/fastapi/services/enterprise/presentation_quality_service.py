from datetime import datetime, timezone
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from domains.platform.enums import (
    PresentationQualitySeverity,
    PresentationQualityStatus,
    WorkspaceRole,
)
from models.sql.enterprise.presentation_entry import PresentationEntryModel
from models.sql.enterprise.document_chunk import EnterpriseDocumentChunkModel
from models.sql.enterprise.document import EnterpriseDocumentModel
from models.sql.enterprise.presentation_governance import (
    PresentationQualityIssueModel,
    PresentationQualityRunModel,
    PresentationSourceCitationModel,
)
from models.sql.slide import SlideModel
from services.enterprise.audit_service import record_audit_event
from services.enterprise.document_service import get_enterprise_document
from services.enterprise.presentation_governance_service import _presentation_snapshot
from services.enterprise.workspace_service import require_workspace_role


PLACEHOLDER_PATTERN = re.compile(
    r"\b(?:lorem ipsum|placeholder|todo|tbd)\b|待补充|待确认|占位文本",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:%|％|万|亿|年|月|日|天|例|家|个)?")
DOCUMENT_LOCATOR_PATTERN = re.compile(
    r"^lines:(?P<start>\d+)-(?P<end>\d+)#chunk=(?P<chunk>\d+)$"
)


async def _citation_detail(
    session: AsyncSession, citation: PresentationSourceCitationModel
) -> tuple[dict, EnterpriseDocumentChunkModel | None]:
    detail = {
        "status": "valid",
        "status_message": "来源有效",
        "source_name": None,
        "source_category": None,
        "current_version": citation.source_version,
        "source_available": False,
    }
    if citation.source_type != "enterprise_document":
        return detail, None
    try:
        document_id = uuid.UUID(citation.source_id)
    except (TypeError, ValueError):
        detail.update(status="missing", status_message="来源标识无效")
        return detail, None
    document = await session.get(EnterpriseDocumentModel, document_id)
    if document is None:
        detail.update(status="missing", status_message="来源资料已删除")
        return detail, None
    detail.update(
        source_name=document.logical_name,
        source_category=document.category,
        current_version=str(document.version_no),
        source_available=True,
    )
    expires_at = document.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if document.authorization_status == "revoked" or document.status == "revoked":
        detail.update(status="revoked", status_message="来源授权已撤销")
        return detail, None
    if document.status == "archived":
        detail.update(status="archived", status_message="来源资料已归档")
        return detail, None
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        detail.update(status="expired", status_message="来源资料已过期")
        return detail, None
    if document.parse_status != "ready":
        detail.update(status="unavailable", status_message="来源资料尚不可用")
        return detail, None
    if str(document.version_no) != citation.source_version:
        detail.update(status="source_updated", status_message="来源资料已有新版本")
        return detail, None
    locator_match = DOCUMENT_LOCATOR_PATTERN.fullmatch(citation.locator or "")
    if locator_match is None:
        detail.update(status="locator_changed", status_message="来源定位信息无效")
        return detail, None
    chunk = await session.scalar(
        select(EnterpriseDocumentChunkModel).where(
            EnterpriseDocumentChunkModel.document_id == document.id,
            EnterpriseDocumentChunkModel.chunk_index
            == int(locator_match.group("chunk")),
        )
    )
    if (
        chunk is None
        or chunk.start_line != int(locator_match.group("start"))
        or chunk.end_line != int(locator_match.group("end"))
    ):
        detail.update(status="locator_changed", status_message="来源段落位置已变化")
        return detail, chunk
    excerpt_body = (citation.excerpt or "").strip().strip("…").strip()
    if not excerpt_body or excerpt_body not in chunk.content:
        detail.update(status="excerpt_changed", status_message="引用摘录与来源不一致")
        return detail, chunk
    return detail, chunk


async def invalid_source_citations(
    session: AsyncSession, *, entry_id: uuid.UUID
) -> list[PresentationSourceCitationModel]:
    citations = list(
        (
            await session.scalars(
                select(PresentationSourceCitationModel).where(
                    PresentationSourceCitationModel.presentation_entry_id == entry_id
                )
            )
        ).all()
    )
    invalid = []
    for citation in citations:
        detail, _ = await _citation_detail(session, citation)
        if detail["status"] != "valid":
            invalid.append(citation)
    return invalid


def _walk(value: object, path: str = ""):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _text_from_node(node: dict) -> str:
    runs = node.get("runs")
    if isinstance(runs, list):
        return "".join(str(run.get("text", "")) for run in runs if isinstance(run, dict))
    return str(node.get("text", "")) if node.get("text") is not None else ""


def _slide_issues(slide: SlideModel, *, require_numeric_citations: bool, cited: bool) -> list[dict]:
    issues: list[dict] = []
    ui = slide.ui
    if not isinstance(ui, dict):
        return [{"rule_code": "slide_ui_missing", "severity": PresentationQualitySeverity.BLOCKING, "slide_id": slide.id, "slide_index": slide.index, "message": "页面缺少可编辑 UI 数据", "details": {}}]
    numeric_texts: list[str] = []
    for path, node in _walk(ui):
        if not isinstance(node, dict):
            continue
        position, size = node.get("position"), node.get("size")
        if isinstance(position, dict) and isinstance(size, dict):
            try:
                x, y = float(position.get("x", 0)), float(position.get("y", 0))
                width, height = float(size.get("width", 0)), float(size.get("height", 0))
                if x < 0 or y < 0 or x + width > 1280 or y + height > 720:
                    issues.append({"rule_code": "element_out_of_bounds", "severity": PresentationQualitySeverity.BLOCKING, "slide_id": slide.id, "slide_index": slide.index, "element_ref": path, "message": "页面元素超出 1280×720 画布", "details": {"x": x, "y": y, "width": width, "height": height}})
            except (TypeError, ValueError):
                pass
        text = _text_from_node(node).strip()
        if text and PLACEHOLDER_PATTERN.search(text):
            issues.append({"rule_code": "placeholder_residue", "severity": PresentationQualitySeverity.BLOCKING, "slide_id": slide.id, "slide_index": slide.index, "element_ref": path, "message": "页面包含占位或待补充文本", "details": {"text": text[:200]}})
        if text and NUMBER_PATTERN.search(text):
            numeric_texts.append(text[:200])
    if require_numeric_citations and numeric_texts and not cited:
        issues.append({"rule_code": "numeric_citation_missing", "severity": PresentationQualitySeverity.BLOCKING, "slide_id": slide.id, "slide_index": slide.index, "message": "页面包含关键数字但没有来源引用", "details": {"samples": numeric_texts[:5]}})
    return issues


async def run_quality_check(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    entry_id: uuid.UUID,
    principal: AuthPrincipal,
    policy_override: dict | None = None,
) -> tuple[PresentationQualityRunModel, list[PresentationQualityIssueModel]]:
    workspace, _ = await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.EDITOR)
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    policy = {**(workspace.governance_policy or {}), **(policy_override or {})}
    if entry.scene_type == "bid":
        policy["require_numeric_citations"] = True
    slide_hash, _ = await _presentation_snapshot(session, entry)
    slides = list((await session.scalars(select(SlideModel).execution_options(skip_owner_scope=True).where(SlideModel.presentation == entry.presentation_id).order_by(SlideModel.index))).all())
    citations = list((await session.scalars(select(PresentationSourceCitationModel).where(PresentationSourceCitationModel.presentation_entry_id == entry.id))).all())
    cited_slide_ids = {
        item.slide_id
        for item in citations
        if item.slide_id is not None and item.source_type != "enterprise_document"
    }
    raw_issues: list[dict] = []
    for citation in citations:
        if citation.source_type != "enterprise_document" or citation.slide_id is None:
            continue
        citation_detail, _ = await _citation_detail(session, citation)
        if citation_detail["status"] == "valid":
            cited_slide_ids.add(citation.slide_id)
        else:
            raw_issues.append(
                {
                    "rule_code": "citation_source_invalid",
                    "severity": PresentationQualitySeverity.BLOCKING,
                    "slide_id": citation.slide_id,
                    "message": "页面引用的企业资料已失效、撤销或版本不一致",
                    "details": {
                        "citation_id": str(citation.id),
                        "source_id": citation.source_id,
                        "source_version": citation.source_version,
                        "status": citation_detail["status"],
                    },
                }
            )
    if not slides:
        raw_issues.append({"rule_code": "presentation_empty", "severity": PresentationQualitySeverity.BLOCKING, "message": "演示文稿没有页面", "details": {}})
    for slide in slides:
        raw_issues.extend(_slide_issues(slide, require_numeric_citations=bool(policy.get("require_numeric_citations")), cited=slide.id in cited_slide_ids))
    blocking_count = sum(item["severity"] == PresentationQualitySeverity.BLOCKING for item in raw_issues)
    warning_count = len(raw_issues) - blocking_count
    run = PresentationQualityRunModel(
        presentation_entry_id=entry.id,
        slide_snapshot_hash=slide_hash,
        status=PresentationQualityStatus.FAILED if blocking_count else PresentationQualityStatus.PASSED,
        blocking_count=blocking_count,
        warning_count=warning_count,
        policy_snapshot=policy,
        created_by=principal.user_id,
    )
    session.add(run)
    issues = [PresentationQualityIssueModel(quality_run_id=run.id, **item) for item in raw_issues]
    session.add_all(issues)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=workspace_id, action="presentation.quality_checked", resource_type="presentation_quality_run", resource_id=run.id, metadata={"entry_id": str(entry.id), "status": run.status.value, "blocking_count": blocking_count, "warning_count": warning_count})
    await session.commit()
    await session.refresh(run)
    return run, issues


async def latest_quality_report(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal) -> tuple[PresentationQualityRunModel | None, list[PresentationQualityIssueModel]]:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    run = await session.scalar(select(PresentationQualityRunModel).where(PresentationQualityRunModel.presentation_entry_id == entry.id).order_by(PresentationQualityRunModel.created_at.desc()).limit(1))
    issues = [] if run is None else list((await session.scalars(select(PresentationQualityIssueModel).where(PresentationQualityIssueModel.quality_run_id == run.id))).all())
    return run, issues


async def create_source_citation(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal, values: dict) -> PresentationSourceCitationModel:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.EDITOR)
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    slide_id = values.get("slide_id")
    if slide_id is not None:
        slide = await session.scalar(select(SlideModel).execution_options(skip_owner_scope=True).where(SlideModel.id == slide_id, SlideModel.presentation == entry.presentation_id))
        if slide is None:
            raise HTTPException(status_code=404, detail="Slide not found")
    if values.get("source_type") == "enterprise_document":
        try:
            document_id = uuid.UUID(values.get("source_id", ""))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="Invalid enterprise document citation"
            ) from exc
        document = await get_enterprise_document(
            session, document_id=document_id, principal=principal
        )
        if document.scope_type != "enterprise" and document.workspace_id != workspace_id:
            raise HTTPException(
                status_code=422,
                detail="Enterprise document belongs to another workspace",
            )
        if (
            document.parse_status != "ready"
            or document.authorization_status == "revoked"
            or document.status in {"archived", "revoked"}
            or (
                document.expires_at is not None
                and (
                    document.expires_at
                    if document.expires_at.tzinfo
                    else document.expires_at.replace(tzinfo=timezone.utc)
                )
                <= datetime.now(timezone.utc)
            )
        ):
            raise HTTPException(
                status_code=409, detail="Enterprise document cannot be cited"
            )
        if values.get("source_version") != str(document.version_no):
            raise HTTPException(
                status_code=409, detail="Enterprise document citation version changed"
            )
        locator_match = DOCUMENT_LOCATOR_PATTERN.fullmatch(values.get("locator") or "")
        if locator_match is None:
            raise HTTPException(
                status_code=422, detail="Invalid enterprise document locator"
            )
        chunk = await session.scalar(
            select(EnterpriseDocumentChunkModel).where(
                EnterpriseDocumentChunkModel.document_id == document.id,
                EnterpriseDocumentChunkModel.chunk_index
                == int(locator_match.group("chunk")),
            )
        )
        if (
            chunk is None
            or chunk.start_line != int(locator_match.group("start"))
            or chunk.end_line != int(locator_match.group("end"))
        ):
            raise HTTPException(
                status_code=409, detail="Enterprise document citation locator changed"
            )
        excerpt = (values.get("excerpt") or "").strip()
        excerpt_body = excerpt.strip("…").strip()
        if not excerpt_body or excerpt_body not in chunk.content:
            raise HTTPException(
                status_code=422, detail="Enterprise document citation excerpt is invalid"
            )
    citation = PresentationSourceCitationModel(presentation_entry_id=entry.id, created_by=principal.user_id, **values)
    session.add(citation)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=workspace_id, action="presentation.citation_created", resource_type="presentation_source_citation", resource_id=citation.id, metadata={"entry_id": str(entry.id), "source_type": citation.source_type, "source_id": citation.source_id})
    await session.commit()
    await session.refresh(citation)
    return citation


async def list_source_citations(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal) -> list[PresentationSourceCitationModel]:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal)
    entry = await session.get(PresentationEntryModel, entry_id)
    if entry is None or entry.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Presentation entry not found")
    return list((await session.scalars(select(PresentationSourceCitationModel).where(PresentationSourceCitationModel.presentation_entry_id == entry.id).order_by(PresentationSourceCitationModel.created_at))).all())


async def list_source_citation_details(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal) -> list[dict]:
    citations = await list_source_citations(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)
    result = []
    for citation in citations:
        detail, _ = await _citation_detail(session, citation)
        result.append({**citation.model_dump(), **detail})
    return result


async def source_citation_summary(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, principal: AuthPrincipal) -> dict:
    details = await list_source_citation_details(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)
    invalid = [item for item in details if item["status"] != "valid"]
    return {
        "total_citations": len(details),
        "valid_citations": len(details) - len(invalid),
        "invalid_citations": len(invalid),
        "cited_slide_ids": sorted({item["slide_id"] for item in details if item["status"] == "valid" and item["slide_id"] is not None}, key=str),
        "invalid_citation_ids": [item["id"] for item in invalid],
    }


async def get_source_citation_preview(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, citation_id: uuid.UUID, principal: AuthPrincipal) -> dict:
    details = await list_source_citation_details(session, workspace_id=workspace_id, entry_id=entry_id, principal=principal)
    item = next((row for row in details if row["id"] == citation_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Citation not found")
    citation = await session.get(PresentationSourceCitationModel, citation_id)
    if citation is None:
        raise HTTPException(status_code=404, detail="Citation not found")
    _, chunk = await _citation_detail(session, citation)
    if citation.source_type == "enterprise_document":
        try:
            document_id = uuid.UUID(citation.source_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Citation source not found") from exc
        await get_enterprise_document(session, document_id=document_id, principal=principal)
    return {"citation": item, "heading": chunk.heading if chunk else None, "content": chunk.content if chunk else None}


async def delete_source_citation(session: AsyncSession, *, workspace_id: uuid.UUID, entry_id: uuid.UUID, citation_id: uuid.UUID, principal: AuthPrincipal) -> None:
    await require_workspace_role(session, workspace_id=workspace_id, principal=principal, required_role=WorkspaceRole.EDITOR)
    entry = await session.get(PresentationEntryModel, entry_id)
    citation = await session.get(PresentationSourceCitationModel, citation_id)
    if entry is None or entry.workspace_id != workspace_id or citation is None or citation.presentation_entry_id != entry_id:
        raise HTTPException(status_code=404, detail="Citation not found")
    await session.delete(citation)
    record_audit_event(session, actor_id=principal.user_id, workspace_id=workspace_id, action="presentation.citation_deleted", resource_type="presentation_source_citation", resource_id=citation.id, metadata={"entry_id": str(entry.id), "source_id": citation.source_id})
    await session.commit()
