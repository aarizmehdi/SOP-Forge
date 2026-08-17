"""
SOP Forge — SOP Document & Chunk ORM models.
Stores digitized SOP policy text with pgvector embeddings for RAG retrieval.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SOPDocument(Base):
    """
    A digitized SOP policy document.
    HR/Compliance manages these via the no-code admin interface.
    """
    __tablename__ = "sop_documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    content_text = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    chunks = relationship(
        "SOPChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<SOPDocument '{self.title}' v{self.version}>"


class SOPChunk(Base):
    """
    An embedded chunk of an SOP document.
    Used for RAG retrieval via pgvector cosine similarity search.
    """
    __tablename__ = "sop_chunks"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("sop_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(JSON, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    document = relationship("SOPDocument", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<SOPChunk doc={self.document_id} idx={self.chunk_index}>"
