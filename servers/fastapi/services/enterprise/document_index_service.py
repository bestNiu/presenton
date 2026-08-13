import hashlib
import os

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.sql.enterprise.document import EnterpriseDocumentModel
from models.sql.enterprise.document_chunk import EnterpriseDocumentChunkModel


def build_document_chunks(
    text: str, *, max_characters: int | None = None
) -> list[dict]:
    max_characters = max_characters or int(
        os.getenv("ENTERPRISE_DOCUMENT_CHUNK_MAX_CHARACTERS", "1200")
    )
    max_characters = max(200, min(max_characters, 5000))
    chunks: list[dict] = []
    heading: str | None = None
    heading_line: int | None = None
    content_lines: list[str] = []
    start_line: int | None = None
    end_line: int | None = None

    def flush() -> None:
        nonlocal content_lines, start_line, end_line
        content = "\n".join(content_lines).strip()
        if content:
            chunk_index = len(chunks)
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "heading": heading,
                    "content": content,
                    "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    "character_count": len(content),
                    "start_line": heading_line or start_line or 1,
                    "end_line": end_line or start_line or heading_line or 1,
                    "locator": {
                        "chunk_index": chunk_index,
                        "start_line": heading_line or start_line or 1,
                        "end_line": end_line or start_line or heading_line or 1,
                        "heading": heading,
                    },
                }
            )
        content_lines = []
        start_line = None
        end_line = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            flush()
            heading = stripped.lstrip("#").strip() or stripped
            heading_line = line_number
            continue
        if not stripped:
            continue
        fragments = [
            stripped[offset : offset + max_characters]
            for offset in range(0, len(stripped), max_characters)
        ]
        for fragment in fragments:
            projected = len(fragment) + sum(len(item) + 1 for item in content_lines)
            if content_lines and projected > max_characters:
                flush()
            if start_line is None:
                start_line = line_number
            content_lines.append(fragment)
            end_line = line_number
            if len(fragment) >= max_characters:
                flush()
    flush()
    return chunks


async def replace_document_chunks(
    session: AsyncSession,
    *,
    document: EnterpriseDocumentModel,
    extracted_text: str,
) -> list[EnterpriseDocumentChunkModel]:
    await session.execute(
        delete(EnterpriseDocumentChunkModel).where(
            EnterpriseDocumentChunkModel.document_id == document.id
        )
    )
    chunks = [
        EnterpriseDocumentChunkModel(document_id=document.id, **values)
        for values in build_document_chunks(extracted_text)
    ]
    session.add_all(chunks)
    return chunks
