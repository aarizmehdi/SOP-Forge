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
    days: int | None = Query(default=None, ge=1),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Query the audit trail with filters. Read-only."""
    date_from = None
    if days is not None:
        from datetime import datetime, timezone, timedelta
        date_from = datetime.now(timezone.utc) - timedelta(days=days)

    query = AuditLogQuery(
        request_id=request_id,
        event_type=event_type,
        date_from=date_from,
        limit=limit,
        offset=offset,
    )

    logs = await query_audit_logs(db, query)
    return await resolve_audit_actors(db, logs)


@router.get("/logs/{request_id}", response_model=list[AuditLogResponse])
async def get_request_audit_trail(
    request_id: UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Get full audit history for a specific request."""
    query = AuditLogQuery(request_id=request_id, limit=500)
    logs = await query_audit_logs(db, query)
    return await resolve_audit_actors(db, logs)


async def resolve_audit_actors(db: AsyncIOMotorDatabase, logs: list) -> list[AuditLogResponse]:
    """Helper to resolve actor names from DB users collection for audit response."""
    actor_ids = {str(log.actor_id) for log in logs if log.actor_id and not str(log.actor_id).startswith("system")}
    users_map = {}
    if actor_ids:
        users_cursor = db.users.find({"id": {"$in": list(actor_ids)}})
        users = await users_cursor.to_list(length=len(actor_ids))
        for u in users:
            users_map[str(u["id"])] = f"{u.get('name', 'User')}"

    responses = []
    for log in logs:
        actor_id_str = str(log.actor_id) if log.actor_id else None
        if not actor_id_str or actor_id_str.startswith("system"):
            actor_name = "AI Engine (System)"
        else:
            actor_name = users_map.get(actor_id_str, log.actor_role or "User")

        responses.append(
            AuditLogResponse(
                id=log.id,
                request_id=log.request_id,
                event_type=log.event_type,
                actor_id=log.actor_id,
                actor_name=actor_name,
                actor_role=log.actor_role or ("system" if not actor_id_str or actor_id_str.startswith("system") else "user"),
                decision=log.decision,
                confidence=log.confidence,
                policy_refs=log.policy_refs,
                evaluation_reasoning=log.evaluation_reasoning,
                override_justification=log.override_justification,
                previous_decision=log.previous_decision,
                details=log.details,
                created_at=log.created_at,
            )
        )
    return responses


@router.get("/summary", response_model=AuditSummary)
async def get_summary(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Get aggregate audit statistics."""
    return await get_audit_summary(db)
