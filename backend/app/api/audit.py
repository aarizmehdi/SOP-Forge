"""
SOP Forge — Audit API router (MongoDB).
Read-only access to the immutable audit trail.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.rbac import require_manager
from app.database import get_db
from app.models.audit import AuditEventType
from app.models.user import User
from app.schemas.audit import AuditLogQuery, AuditLogResponse, AuditSummary
from app.services.audit_service import get_audit_summary, query_audit_logs

router = APIRouter(prefix="/api/audit", tags=["Audit"])


@router.get("/logs", response_model=list[AuditLogResponse])
async def get_audit_logs(
    request_id: UUID | None = None,
    event_type: AuditEventType | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Query the audit trail with filters. Read-only."""
    query = AuditLogQuery(
        request_id=request_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )

    logs = await query_audit_logs(db, query)

    # Note: Actor name is mocked here for speed since MongoDB doesn't JOIN natively
    return [
        AuditLogResponse(
            id=log.id,
            request_id=log.request_id,
            event_type=log.event_type,
            actor_id=log.actor_id,
            actor_name="System/User", 
            actor_role=log.actor_role,
            decision=log.decision,
            confidence=log.confidence,
            policy_refs=log.policy_refs,
            evaluation_reasoning=log.evaluation_reasoning,
            override_justification=log.override_justification,
            previous_decision=log.previous_decision,
            details=log.details,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/logs/{request_id}", response_model=list[AuditLogResponse])
async def get_request_audit_trail(
    request_id: UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Get full audit history for a specific request."""
    query = AuditLogQuery(request_id=request_id, limit=500)
    logs = await query_audit_logs(db, query)

    return [
        AuditLogResponse(
            id=log.id,
            request_id=log.request_id,
            event_type=log.event_type,
            actor_id=log.actor_id,
            actor_name="System/User",
            actor_role=log.actor_role,
            decision=log.decision,
            confidence=log.confidence,
            policy_refs=log.policy_refs,
            evaluation_reasoning=log.evaluation_reasoning,
            override_justification=log.override_justification,
            previous_decision=log.previous_decision,
            details=log.details,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/summary", response_model=AuditSummary)
async def get_summary(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Get aggregate audit statistics."""
    return await get_audit_summary(db)
