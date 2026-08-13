from datetime import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from utils.datetime_utils import get_current_utc_datetime


class EnterpriseDocumentChunkModel(SQLModel, table=True):
    __tablename__ = "enterprise_document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_enterprise_document_chunk_index"
        ),
    )

    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    document_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("enterprise_documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    chunk_index: int = Field(sa_column=Column(Integer, nullable=False))
    heading: str | None = Field(default=None, sa_column=Column(String(500)))
    content: str = Field(sa_column=Column(Text, nullable=False))
    content_hash: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    character_count: int = Field(sa_column=Column(Integer, nullable=False))
    start_line: int = Field(sa_column=Column(Integer, nullable=False))
    end_line: int = Field(sa_column=Column(Integer, nullable=False))
    locator: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=get_current_utc_datetime,
            index=True,
        )
    )
