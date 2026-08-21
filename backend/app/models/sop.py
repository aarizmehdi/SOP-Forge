"""
SOP Forge — SOP Document & Chunk ODM models (Pydantic/MongoDB).
"""

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class SOPDocument(BaseModel):
    """
    A digitized SOP policy document.
    HR/Compliance manages these via the no-code admin interface.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    category: str
    content_text: str
    version: int = 1
    is_active: bool = True
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SOPChunk(BaseModel):
    """
    An embedded chunk of an SOP document.
    Used for RAG retrieval via cosine similarity search.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    chunk_text: str
    chunk_index: int
    embedding: list[float] | None = None
    metadata: dict | None = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
