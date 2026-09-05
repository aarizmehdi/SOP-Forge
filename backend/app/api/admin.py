"""
SOP Forge — Admin API router (MongoDB).
SOP document CRUD for the no-code policy management interface.
"""

import logging
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

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
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all SOP documents."""
    documents = await get_all_documents(db, active_only=active_only)
    return documents


@router.post("/sop", response_model=SOPDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_sop_document(
    doc: SOPDocumentCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new SOP document — auto-embeds into DB."""
    document = await ingest_sop_document(
        db,
        title=doc.title,
        category=doc.category,
        content_text=doc.content_text,
        created_by=str(current_user.id),
    )

    chunk_count = await db.sop_chunks.count_documents({"document_id": document.id})

    # Record Audit Entry for SOP creation
    try:
        from app.models.audit import AuditEventType
        from app.services.request_service import create_audit_entry
        await create_audit_entry(
            db,
            request_id=document.id,
            event_type=AuditEventType.SOP_UPDATED,
            actor_id=str(current_user.id),
            actor_role=current_user.role.value,
            details={
                "action": "sop_created",
                "document_id": document.id,
                "document_title": document.title,
                "category": document.category,
                "version": document.version,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to record SOP creation audit event: {e}")

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
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get a specific SOP document with chunk count."""
    doc_dict = await db.sop_documents.find_one({"id": str(document_id)})
    if doc_dict is None:
        raise HTTPException(status_code=404, detail="SOP document not found")

    document = SOPDocument(**doc_dict)
    chunk_count = await db.sop_chunks.count_documents({"document_id": document.id})

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
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an SOP document. If content changes, triggers re-embedding."""
    try:
        document = await update_sop_document(
            db,
            str(document_id),
            title=update.title,
            category=update.category,
            content_text=update.content_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    chunk_count = await db.sop_chunks.count_documents({"document_id": document.id})

    # Record Audit Entry for SOP update
    try:
        from app.models.audit import AuditEventType
        from app.services.request_service import create_audit_entry
        await create_audit_entry(
            db,
            request_id=document.id,
            event_type=AuditEventType.SOP_UPDATED,
            actor_id=str(current_user.id),
            actor_role=current_user.role.value,
            details={
                "action": "sop_updated",
                "document_id": document.id,
                "document_title": document.title,
                "category": document.category,
                "version": document.version,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to record SOP update audit event: {e}")

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
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Soft-delete (deactivate) an SOP document."""
    doc_id = str(document_id)
    doc_dict = await db.sop_documents.find_one({"id": doc_id})
    if doc_dict is None:
        raise HTTPException(status_code=404, detail="SOP document not found")

    await db.sop_documents.update_one(
        {"id": doc_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
    )

    # Record Audit Entry for SOP deactivation
    try:
        from app.models.audit import AuditEventType
        from app.services.request_service import create_audit_entry
        await create_audit_entry(
            db,
            request_id=doc_id,
            event_type=AuditEventType.SOP_UPDATED,
            actor_id=str(current_user.id),
            actor_role=current_user.role.value,
            details={
                "action": "sop_deactivated",
                "document_id": doc_id,
                "document_title": doc_dict.get("title"),
            },
        )
    except Exception as e:
        logger.warning(f"Failed to record SOP deactivation audit event: {e}")

    return {"status": "success", "message": f"SOP '{doc_dict.get('title')}' deactivated"}


@router.get("/sop/{document_id}/chunks", response_model=list[SOPChunkResponse])
async def get_sop_chunks(
    document_id: UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """View embedded chunks for a document."""
    chunks = await get_document_chunks(db, str(document_id))

    return [
        SOPChunkResponse(
            id=chunk.id,
            chunk_text=chunk.chunk_text,
            chunk_index=chunk.chunk_index,
            has_embedding=chunk.embedding is not None,
            metadata=chunk.metadata,
        )
        for chunk in chunks
    ]
