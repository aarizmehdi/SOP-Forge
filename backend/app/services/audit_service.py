"""
SOP Forge — Audit service (MongoDB).
Handles creating and querying immutable audit log entries.
"""

import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.audit import AuditEventType, AuditLog
from app.schemas.audit import AuditLogQuery, AuditSummary


async def create_audit_entry(
    db: AsyncIOMotorDatabase,
    *,
    request_id: str | None = None,
    event_type: AuditEventType,
    actor_id: str | None = None,
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
        id=str(uuid.uuid4()),
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
    await db.audit_logs.insert_one(entry.model_dump(mode="json"))
    return entry


async def query_audit_logs(
    db: AsyncIOMotorDatabase,
    query: AuditLogQuery,
) -> list[AuditLog]:
    """Query audit logs with filters."""
    mongo_query = {}
    
    if query.request_id:
        mongo_query["request_id"] = str(query.request_id)
    if query.event_type:
        mongo_query["event_type"] = query.event_type
    if query.actor_id:
        mongo_query["actor_id"] = str(query.actor_id)
        
    date_filter = {}
    if query.date_from:
        date_filter["$gte"] = query.date_from.isoformat()
    if query.date_to:
        date_filter["$lte"] = query.date_to.isoformat()
        
    if date_filter:
        mongo_query["created_at"] = date_filter

    cursor = db.audit_logs.find(mongo_query).sort("created_at", -1).skip(query.offset).limit(query.limit)
    documents = await cursor.to_list(length=query.limit)
    
    # Normally we would fetch the actor separately, but for speed we just return the logs
    return [AuditLog(**doc) for doc in documents]


async def get_audit_summary(db: AsyncIOMotorDatabase) -> AuditSummary:
    """Get summary statistics across all audit entries."""
    total = await db.audit_logs.count_documents({})

    async def count_event(event_type: AuditEventType) -> int:
        return await db.audit_logs.count_documents({"event_type": event_type.value})

    return AuditSummary(
        total_entries=total,
        auto_approved=await count_event(AuditEventType.AUTO_APPROVED),
        auto_rejected=await count_event(AuditEventType.AUTO_REJECTED),
        escalated=await count_event(AuditEventType.ESCALATED),
        overridden=await count_event(AuditEventType.EXECUTIVE_OVERRIDE),
        sla_breaches=await count_event(AuditEventType.SLA_BREACHED),
    )
