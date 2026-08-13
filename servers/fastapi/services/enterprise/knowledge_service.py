from datetime import datetime, timezone
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from models.sql.enterprise.document import EnterpriseDocumentModel
from models.sql.enterprise.document_chunk import EnterpriseDocumentChunkModel
from services.enterprise.document_service import authorize_document_scope


def _terms(value: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", value.casefold())
    terms: set[str] = set()
    for token in tokens:
        terms.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 1:
            terms.update(token[index : index + 2] for index in range(len(token) - 1))
    return terms


def _excerpt(content: str, matched_terms: set[str], limit: int = 500) -> str:
    if len(content) <= limit:
        return content
    lowered = content.casefold()
    positions = [lowered.find(term) for term in matched_terms if lowered.find(term) >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - limit // 4)
    end = min(len(content), start + limit)
    prefix = "…" if start else ""
    suffix = "…" if end < len(content) else ""
    return f"{prefix}{content[start:end].strip()}{suffix}"


def _rank_chunk(
    query: str,
    query_terms: set[str],
    chunk: EnterpriseDocumentChunkModel,
    document: EnterpriseDocumentModel,
) -> tuple[float, set[str]]:
    content_terms = _terms(chunk.content)
    heading_terms = _terms(chunk.heading or "")
    document_terms = _terms(f"{document.logical_name} {document.category}")
    all_terms = content_terms | heading_terms | document_terms
    matched = query_terms & all_terms
    if not matched:
        return 0.0, set()
    coverage = len(matched) / len(query_terms)
    score = coverage * 60
    score += len(query_terms & heading_terms) * 10
    score += len(query_terms & document_terms) * 8
    if query.casefold() in chunk.content.casefold():
        score += 20
    return round(min(score, 100.0), 3), matched


async def search_enterprise_knowledge(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    query: str,
    scope_type: str,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    categories: list[str],
    latest_only: bool,
    limit: int,
) -> list[dict]:
    workspace_id, project_id = await authorize_document_scope(
        session,
        principal=principal,
        scope_type=scope_type,
        workspace_id=workspace_id,
        project_id=project_id,
        write=False,
    )
    normalized_query = query.strip()
    query_terms = _terms(normalized_query)
    if not query_terms:
        raise HTTPException(status_code=422, detail="Knowledge search query is required")

    predicates = [
        EnterpriseDocumentModel.scope_type == scope_type,
        EnterpriseDocumentModel.workspace_id == workspace_id
        if workspace_id is not None
        else EnterpriseDocumentModel.workspace_id.is_(None),
        EnterpriseDocumentModel.project_id == project_id
        if project_id is not None
        else EnterpriseDocumentModel.project_id.is_(None),
        EnterpriseDocumentModel.parse_status == "ready",
        EnterpriseDocumentModel.status.in_(["active", "superseded"]),
        EnterpriseDocumentModel.authorization_status != "revoked",
        or_(
            EnterpriseDocumentModel.expires_at.is_(None),
            EnterpriseDocumentModel.expires_at > datetime.now(timezone.utc),
        ),
    ]
    if latest_only:
        predicates.append(EnterpriseDocumentModel.is_latest.is_(True))
    normalized_categories = [item.strip() for item in categories if item.strip()]
    if normalized_categories:
        predicates.append(EnterpriseDocumentModel.category.in_(normalized_categories))

    candidate_limit = min(max(limit * 100, 500), 5000)
    rows = (
        await session.execute(
            select(EnterpriseDocumentChunkModel, EnterpriseDocumentModel)
            .join(
                EnterpriseDocumentModel,
                EnterpriseDocumentModel.id
                == EnterpriseDocumentChunkModel.document_id,
            )
            .where(*predicates)
            .limit(candidate_limit)
        )
    ).all()
    ranked: list[dict] = []
    for chunk, document in rows:
        score, matched_terms = _rank_chunk(
            normalized_query, query_terms, chunk, document
        )
        if score <= 0:
            continue
        locator = {
            **(chunk.locator or {}),
            "document_id": str(document.id),
            "version_no": document.version_no,
        }
        ranked.append(
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "document_version": document.version_no,
                "logical_name": document.logical_name,
                "category": document.category,
                "heading": chunk.heading,
                "excerpt": _excerpt(chunk.content, matched_terms),
                "locator": locator,
                "score": score,
                "matched_terms": sorted(matched_terms),
                "citation": {
                    "source_type": "enterprise_document",
                    "source_id": str(document.id),
                    "source_version": str(document.version_no),
                    "locator": (
                        f"lines:{chunk.start_line}-{chunk.end_line}"
                        f"#chunk={chunk.chunk_index}"
                    ),
                    "excerpt": _excerpt(chunk.content, matched_terms, limit=1000),
                },
                "updated_at": document.updated_at,
                "chunk_index": chunk.chunk_index,
            }
        )
    ranked.sort(
        key=lambda item: (
            item["score"],
            item["updated_at"],
            -item["chunk_index"],
        ),
        reverse=True,
    )
    for item in ranked:
        item.pop("updated_at")
        item.pop("chunk_index")
    return ranked[:limit]
