"""
SOP Forge — Admin schemas.
Pydantic models for the no-code SOP management interface.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SOPDocumentCreate(BaseModel):
    """Create a new SOP document."""
    title: str = Field(..., min_length=3, max_length=500)
    category: str = Field(..., min_length=2, max_length=100, description="e.g. leave, reimbursement, it_access")
    content_text: str = Field(..., min_length=50, description="Full SOP policy text")


class SOPDocumentUpdate(BaseModel):
    """Update an existing SOP document (triggers re-embedding)."""
    title: str | None = None
    category: str | None = None
    content_text: str | None = Field(None, min_length=50)


class SOPDocumentResponse(BaseModel):
    """SOP document response for admin views."""
    id: UUID
    title: str
    category: str
    content_text: str
    version: int
    is_active: bool
    chunk_count: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SOPDocumentListItem(BaseModel):
    """Compact SOP document item for list views."""
    id: UUID
    title: str
    category: str
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SOPChunkResponse(BaseModel):
    """A chunk of an embedded SOP document."""
    id: UUID
    chunk_text: str
    chunk_index: int
    has_embedding: bool
    metadata: dict | None

    model_config = {"from_attributes": True}
