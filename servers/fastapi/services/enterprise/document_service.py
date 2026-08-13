from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth.principal import AuthPrincipal
from constants.documents import UPLOAD_ACCEPTED_EXTENSIONS
from domains.platform.enums import BidProjectRole, WorkspaceRole
from enums.async_task_status import AsyncTaskStatus
from models.sql.async_task import AsyncTaskModel
from models.sql.enterprise.document import EnterpriseDocumentModel
from services.database import async_session_maker
from services.documents_loader import DocumentsLoader
from services.enterprise.audit_service import record_audit_event
from services.enterprise.bid_project_service import require_project_role
from services.enterprise.document_index_service import replace_document_chunks
from services.enterprise.object_storage_service import (
    StoredObjectLocation,
    get_enterprise_object_storage,
)
from services.enterprise.workspace_service import require_workspace_role
from services.temp_file_service import TEMP_FILE_SERVICE


DOCUMENT_PARSE_TASK_TYPE = "enterprise.document-parse"
DOCUMENT_SCOPES = {"enterprise", "workspace", "project"}
DOCUMENT_AUTHORIZATION_STATUSES = {"internal", "authorized", "revoked"}
DOCUMENT_CONFIDENTIALITY_LEVELS = {"L1", "L2", "L3", "L4"}


def _scope_predicates(
    scope_type: str,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
):
    predicates = [EnterpriseDocumentModel.scope_type == scope_type]
    predicates.append(
        EnterpriseDocumentModel.workspace_id == workspace_id
        if workspace_id is not None
        else EnterpriseDocumentModel.workspace_id.is_(None)
    )
    predicates.append(
        EnterpriseDocumentModel.project_id == project_id
        if project_id is not None
        else EnterpriseDocumentModel.project_id.is_(None)
    )
    return predicates


async def authorize_document_scope(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    scope_type: str,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    write: bool,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    if scope_type not in DOCUMENT_SCOPES:
        raise HTTPException(status_code=422, detail="Invalid document scope")
    if scope_type == "enterprise":
        if write and not principal.is_admin:
            raise HTTPException(status_code=403, detail="Platform administrator required")
        return None, None
    if scope_type == "workspace":
        if workspace_id is None or project_id is not None:
            raise HTTPException(
                status_code=422,
                detail="Workspace scope requires workspace_id only",
            )
        await require_workspace_role(
            session,
            workspace_id=workspace_id,
            principal=principal,
            required_role=WorkspaceRole.EDITOR if write else WorkspaceRole.VIEWER,
        )
        return workspace_id, None
    if project_id is None:
        raise HTTPException(status_code=422, detail="Project scope requires project_id")
    project, _ = await require_project_role(
        session,
        project_id=project_id,
        principal=principal,
        required_role=BidProjectRole.CONTRIBUTOR if write else BidProjectRole.VIEWER,
    )
    if workspace_id is not None and workspace_id != project.workspace_id:
        raise HTTPException(status_code=422, detail="Project does not belong to workspace")
    return project.workspace_id, project_id


async def _require_document_access(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    principal: AuthPrincipal,
    write: bool = False,
) -> EnterpriseDocumentModel:
    document = await session.get(EnterpriseDocumentModel, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Enterprise document not found")
    await authorize_document_scope(
        session,
        principal=principal,
        scope_type=document.scope_type,
        workspace_id=document.workspace_id,
        project_id=document.project_id,
        write=write,
    )
    return document


async def upload_enterprise_document(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    file: UploadFile,
    scope_type: str,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    logical_name: str | None,
    category: str,
    authorization_status: str,
    confidentiality: str,
) -> tuple[EnterpriseDocumentModel, AsyncTaskModel]:
    workspace_id, project_id = await authorize_document_scope(
        session,
        principal=principal,
        scope_type=scope_type,
        workspace_id=workspace_id,
        project_id=project_id,
        write=True,
    )
    if authorization_status not in DOCUMENT_AUTHORIZATION_STATUSES:
        raise HTTPException(
            status_code=422, detail="Invalid document authorization status"
        )
    if confidentiality not in DOCUMENT_CONFIDENTIALITY_LEVELS:
        raise HTTPException(status_code=422, detail="Invalid confidentiality level")
    file_name = TEMP_FILE_SERVICE.sanitize_upload_filename(file.filename)
    extension = Path(file_name).suffix.lower()
    if extension not in UPLOAD_ACCEPTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported enterprise document type")
    normalized_name = (logical_name or Path(file_name).stem).strip()
    if not normalized_name or len(normalized_name) > 300:
        raise HTTPException(status_code=422, detail="Document logical name is required")
    normalized_category = category.strip() or "general"
    if len(normalized_category) > 64:
        raise HTTPException(
            status_code=422,
            detail="Document category cannot exceed 64 characters",
        )

    temp_dir = TEMP_FILE_SERVICE.create_temp_dir(f"enterprise-upload-{uuid.uuid4()}")
    temp_path = TEMP_FILE_SERVICE.create_temp_file_path(file_name, temp_dir)
    digest = hashlib.sha256()
    size_bytes = 0
    max_bytes = (
        int(os.getenv("ENTERPRISE_DOCUMENT_MAX_UPLOAD_MB", "100")) * 1024 * 1024
    )
    try:
        with open(temp_path, "wb") as handle:
            while chunk := await file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Enterprise document exceeds upload limit",
                    )
                digest.update(chunk)
                handle.write(chunk)
        if size_bytes == 0:
            raise HTTPException(status_code=422, detail="Enterprise document is empty")
        sha256 = digest.hexdigest()
        scope_predicates = _scope_predicates(scope_type, workspace_id, project_id)
        duplicate = await session.scalar(
            select(EnterpriseDocumentModel).where(
                *scope_predicates,
                EnterpriseDocumentModel.sha256 == sha256,
                EnterpriseDocumentModel.status.in_(["active", "superseded"]),
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Duplicate enterprise document",
                    "document_id": str(duplicate.id),
                },
            )

        previous = await session.scalar(
            select(EnterpriseDocumentModel)
            .where(
                *scope_predicates,
                EnterpriseDocumentModel.logical_name == normalized_name,
                EnterpriseDocumentModel.is_latest.is_(True),
            )
            .order_by(EnterpriseDocumentModel.version_no.desc())
        )
        document = EnterpriseDocumentModel(
            version_group_id=previous.version_group_id if previous else uuid.uuid4(),
            version_no=(previous.version_no + 1) if previous else 1,
            supersedes_document_id=previous.id if previous else None,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by=principal.user_id,
            scope_type=scope_type,
            logical_name=normalized_name,
            category=normalized_category,
            file_name=file_name,
            mime_type=file.content_type or "application/octet-stream",
            object_key="pending",
            sha256=sha256,
            size_bytes=size_bytes,
            authorization_status=authorization_status,
            confidentiality=confidentiality,
        )
        object_key = "/".join(
            part
            for part in (
                "documents",
                scope_type,
                str(workspace_id) if workspace_id else "enterprise",
                str(project_id) if project_id else None,
                str(document.id),
                f"v{document.version_no}",
                file_name,
            )
            if part
        )
        stored = await get_enterprise_object_storage().put_file(
            temp_path, object_key, content_type=document.mime_type
        )
        document.object_key = stored.object_key
        document.sha256 = stored.sha256
        document.size_bytes = stored.size_bytes
        if previous:
            previous.is_latest = False
            previous.status = "superseded"
            session.add(previous)
        task = AsyncTaskModel(
            owner_id=principal.user_id,
            type=DOCUMENT_PARSE_TASK_TYPE,
            status=AsyncTaskStatus.PENDING,
            message="Queued for enterprise document parsing",
            data={"document_id": str(document.id), "attempt": 1},
        )
        document.parse_task_id = task.id
        session.add_all([document, task])
        record_audit_event(
            session,
            actor_id=principal.user_id,
            workspace_id=workspace_id,
            action="document.uploaded",
            resource_type="enterprise_document",
            resource_id=document.id,
            metadata={
                "scope_type": scope_type,
                "project_id": str(project_id) if project_id else None,
                "version_no": document.version_no,
                "sha256": document.sha256,
            },
        )
        await session.commit()
        await session.refresh(document)
        return document, task
    finally:
        await file.close()
        TEMP_FILE_SERVICE.cleanup_temp_dir(temp_dir)


async def run_document_parse_task(document_id: uuid.UUID, task_id: str) -> None:
    async with async_session_maker() as session:
        document = await session.get(EnterpriseDocumentModel, document_id)
        task = await session.get(AsyncTaskModel, task_id)
        if document is None or task is None or document.parse_task_id != task_id:
            return
        document.parse_status = "parsing"
        task.message = "Parsing enterprise document"
        session.add_all([document, task])
        await session.commit()
        temp_dir = TEMP_FILE_SERVICE.create_temp_dir(f"enterprise-parse-{document.id}")
        temp_path = TEMP_FILE_SERVICE.create_temp_file_path(document.file_name, temp_dir)
        try:
            await get_enterprise_object_storage().download_to_file(document.object_key, temp_path)
            loader = DocumentsLoader([temp_path])
            await loader.load_documents(load_text=True, load_images=False)
            extracted_text = loader.documents[0] if loader.documents else ""
            chunks = await replace_document_chunks(
                session, document=document, extracted_text=extracted_text
            )
            document.extracted_text = extracted_text
            document.extracted_metadata = {
                "character_count": len(extracted_text),
                "line_count": len(extracted_text.splitlines()),
                "heading_count": sum(
                    line.lstrip().startswith("#")
                    for line in extracted_text.splitlines()
                ),
                "chunk_count": len(chunks),
                "parsed_at": datetime.now(timezone.utc).isoformat(),
                "parser": "documents-loader",
                "index_version": "lexical-v1",
            }
            document.parse_status = "ready"
            document.parse_error = None
            task.status = AsyncTaskStatus.COMPLETED
            task.message = "Enterprise document is ready"
            record_audit_event(
                session,
                actor_id=task.owner_id,
                workspace_id=document.workspace_id,
                action="document.parsed",
                resource_type="enterprise_document",
                resource_id=document.id,
                metadata={
                    "character_count": len(extracted_text),
                    "chunk_count": len(chunks),
                    "task_id": task.id,
                },
            )
        except Exception as exc:
            detail = str(getattr(exc, "detail", exc))[:2000]
            document.parse_status = "error"
            document.parse_error = detail
            task.status = AsyncTaskStatus.ERROR
            task.message = "Enterprise document parsing failed"
            task.error = {"detail": detail}
            record_audit_event(
                session,
                actor_id=task.owner_id,
                workspace_id=document.workspace_id,
                action="document.parse_failed",
                resource_type="enterprise_document",
                resource_id=document.id,
                metadata={"task_id": task.id, "error": detail},
            )
        finally:
            TEMP_FILE_SERVICE.cleanup_temp_dir(temp_dir)
        session.add_all([document, task])
        await session.commit()


async def retry_document_parse(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    principal: AuthPrincipal,
) -> tuple[EnterpriseDocumentModel, AsyncTaskModel]:
    document = await _require_document_access(
        session, document_id=document_id, principal=principal, write=True
    )
    if document.parse_status in {"queued", "parsing"}:
        raise HTTPException(
            status_code=409, detail="Enterprise document parsing is already in progress"
        )
    previous_task = (
        await session.get(AsyncTaskModel, document.parse_task_id)
        if document.parse_task_id
        else None
    )
    attempt = (
        int((previous_task.data or {}).get("attempt", 1)) + 1
        if previous_task
        else 1
    )
    task = AsyncTaskModel(
        owner_id=principal.user_id,
        type=DOCUMENT_PARSE_TASK_TYPE,
        status=AsyncTaskStatus.PENDING,
        message="Queued for enterprise document parsing",
        data={"document_id": str(document.id), "attempt": attempt},
    )
    document.parse_task_id = task.id
    document.parse_status = "queued"
    document.parse_error = None
    session.add_all([document, task])
    record_audit_event(
        session,
        actor_id=principal.user_id,
        workspace_id=document.workspace_id,
        action="document.parse_retried",
        resource_type="enterprise_document",
        resource_id=document.id,
        metadata={"task_id": task.id, "attempt": attempt},
    )
    await session.commit()
    return document, task


async def list_enterprise_documents(
    session: AsyncSession,
    *,
    principal: AuthPrincipal,
    scope_type: str,
    workspace_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    include_versions: bool,
) -> list[EnterpriseDocumentModel]:
    workspace_id, project_id = await authorize_document_scope(
        session,
        principal=principal,
        scope_type=scope_type,
        workspace_id=workspace_id,
        project_id=project_id,
        write=False,
    )
    predicates = _scope_predicates(scope_type, workspace_id, project_id)
    if not include_versions:
        predicates.append(EnterpriseDocumentModel.is_latest.is_(True))
    return list(
        (
            await session.scalars(
                select(EnterpriseDocumentModel)
                .where(*predicates)
                .order_by(EnterpriseDocumentModel.updated_at.desc())
            )
        ).all()
    )


async def get_enterprise_document(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    principal: AuthPrincipal,
) -> EnterpriseDocumentModel:
    return await _require_document_access(
        session, document_id=document_id, principal=principal
    )


async def get_document_download_location(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    principal: AuthPrincipal,
) -> tuple[EnterpriseDocumentModel, StoredObjectLocation]:
    document = await _require_document_access(
        session, document_id=document_id, principal=principal
    )
    if (
        document.status in {"archived", "revoked"}
        or document.authorization_status == "revoked"
    ):
        raise HTTPException(status_code=409, detail="Enterprise document is unavailable")
    location = StoredObjectLocation(object_key=document.object_key)
    await get_enterprise_object_storage().verify(
        location,
        expected_sha256=document.sha256,
        expected_size=document.size_bytes,
    )
    return document, location
