"""
SOP Forge — Admin API router.
SOP document CRUD for the no-code policy management interface.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_admin
from app.database import get_db
from app.models.sop import SOPChunk, SOPDocument
from app.models.user import User
from app.schemas.admin import (
    SOPChunkResponse,
    SOPDocumentCreate,
    SOPDocumentListItem,
    SOPDocumentResponse,
    SOPDocumentUpdate,
)
from app.services.sop_service import (
    get_all_documents,
    get_document_chunks,
    ingest_sop_document,
    update_sop_document,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/sop", response_model=list[SOPDocumentListItem])
async def list_sop_documents(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all SOP documents."""
    documents = await get_all_documents(db, active_only=active_only)
    return documents


@router.post("/sop", response_model=SOPDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_sop_document(
    doc: SOPDocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new SOP document — auto-embeds into pgvector."""
    document = await ingest_sop_document(
        db,
        title=doc.title,
        category=doc.category,
        content_text=doc.content_text,
        created_by=current_user.id,
    )

    # Get chunk count
    chunk_count = await db.scalar(
        select(func.count(SOPChunk.id)).where(SOPChunk.document_id == document.id)
    )

    return SOPDocumentResponse(
        id=document.id,
        title=document.title,
        category=document.category,
        content_text=document.content_text,
        version=document.version,
        is_active=document.is_active,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/sop/{document_id}", response_model=SOPDocumentResponse)
async def get_sop_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get a specific SOP document with chunk count."""
    result = await db.execute(
        select(SOPDocument).where(SOPDocument.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="SOP document not found")

    chunk_count = await db.scalar(
        select(func.count(SOPChunk.id)).where(SOPChunk.document_id == document.id)
    )

    return SOPDocumentResponse(
        id=document.id,
        title=document.title,
        category=document.category,
        content_text=document.content_text,
        version=document.version,
        is_active=document.is_active,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.put("/sop/{document_id}", response_model=SOPDocumentResponse)
async def update_sop(
    document_id: UUID,
    update: SOPDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an SOP document. If content changes, triggers re-embedding."""
    try:
        document = await update_sop_document(
            db,
            document_id,
            title=update.title,
            category=update.category,
            content_text=update.content_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    chunk_count = await db.scalar(
        select(func.count(SOPChunk.id)).where(SOPChunk.document_id == document.id)
    )

    return SOPDocumentResponse(
        id=document.id,
        title=document.title,
        category=document.category,
        content_text=document.content_text,
        version=document.version,
        is_active=document.is_active,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.delete("/sop/{document_id}")
async def deactivate_sop(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Soft-delete (deactivate) an SOP document."""
    result = await db.execute(
        select(SOPDocument).where(SOPDocument.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="SOP document not found")

    document.is_active = False
    await db.flush()

    return {"status": "success", "message": f"SOP '{document.title}' deactivated"}


@router.get("/sop/{document_id}/chunks", response_model=list[SOPChunkResponse])
async def get_sop_chunks(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """View embedded chunks for a document."""
    chunks = await get_document_chunks(db, document_id)

    return [
        SOPChunkResponse(
            id=chunk.id,
            chunk_text=chunk.chunk_text,
            chunk_index=chunk.chunk_index,
            has_embedding=chunk.embedding is not None,
            metadata=chunk.extra_metadata,
        )
        for chunk in chunks
    ]
