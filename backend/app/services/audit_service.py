"""
SOP Forge — Audit service.
Handles creating and querying immutable audit log entries.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.audit import AuditEventType, AuditLog
from app.models.request import SOPRequest
from app.schemas.audit import AuditLogQuery, AuditSummary


async def create_audit_entry(
    db: AsyncSession,
    *,
    request_id: uuid.UUID | None = None,
    event_type: AuditEventType,
    actor_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    decision: str | None = None,
    confidence: float | None = None,
    policy_refs: list[str] | None = None,
    evaluation_reasoning: str | None = None,
    override_justification: str | None = None,
    previous_decision: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Create an immutable audit log entry. This is append-only."""
    entry = AuditLog(
        id=uuid.uuid4(),
        request_id=request_id,
        event_type=event_type,
        actor_id=actor_id,
        actor_role=actor_role,
        decision=decision,
        confidence=confidence,
        policy_refs=policy_refs,
        evaluation_reasoning=evaluation_reasoning,
        override_justification=override_justification,
        previous_decision=previous_decision,
        details=details,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.flush()
    return entry


async def query_audit_logs(
    db: AsyncSession,
    query: AuditLogQuery,
) -> list[AuditLog]:
    """Query audit logs with filters."""
    stmt = select(AuditLog).options(joinedload(AuditLog.actor))

    if query.request_id:
        stmt = stmt.where(AuditLog.request_id == query.request_id)
    if query.event_type:
        stmt = stmt.where(AuditLog.event_type == query.event_type)
    if query.actor_id:
        stmt = stmt.where(AuditLog.actor_id == query.actor_id)
    if query.date_from:
        stmt = stmt.where(AuditLog.created_at >= query.date_from)
    if query.date_to:
        stmt = stmt.where(AuditLog.created_at <= query.date_to)

    stmt = stmt.order_by(AuditLog.created_at.desc())
    stmt = stmt.offset(query.offset).limit(query.limit)

    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_audit_summary(db: AsyncSession) -> AuditSummary:
    """Get summary statistics across all audit entries."""
    total = await db.scalar(select(func.count(AuditLog.id)))

    async def count_event(event_type: AuditEventType) -> int:
        result = await db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.event_type == event_type)
        )
        return result or 0

    return AuditSummary(
        total_entries=total or 0,
        auto_approved=await count_event(AuditEventType.AUTO_APPROVED),
        auto_rejected=await count_event(AuditEventType.AUTO_REJECTED),
        escalated=await count_event(AuditEventType.ESCALATED),
        overridden=await count_event(AuditEventType.EXECUTIVE_OVERRIDE),
        sla_breaches=await count_event(AuditEventType.SLA_BREACHED),
    )
