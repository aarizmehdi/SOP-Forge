"""
SOP Forge — Audit Log node.
Terminal node — writes complete, immutable audit log entry (MongoDB).
Every path through the graph ends here.
"""

import logging
import uuid
from datetime import datetime, timezone

from orchestration.state import RequestState

logger = logging.getLogger(__name__)


async def audit_log(state: RequestState) -> dict:
    """
    Terminal audit log node — writes a complete audit entry to MongoDB.
    """
    request_id = state.get("request_id", "unknown")
    status = state.get("status", "unknown")
    decision = state.get("decision", "pending")
    confidence = state.get("confidence", 0.0)

    logger.info(
        f"Audit Log: Recording decision for request {request_id}. "
        f"Status: {status}, Decision: {decision}, Confidence: {confidence:.2f}"
    )

    try:
        from app.database import get_mongodb_client
        from app.models.audit import AuditEventType, AuditLog as AuditLogModel

        if status == "resolved" and decision == "approved":
            event_type = AuditEventType.AUTO_APPROVED
        elif status == "resolved" and decision == "rejected":
            event_type = AuditEventType.AUTO_REJECTED
        elif status == "escalated":
            event_type = AuditEventType.ESCALATED
        elif status == "overridden":
            event_type = AuditEventType.EXECUTIVE_OVERRIDE
        else:
            event_type = AuditEventType.AI_EVALUATED

        client = get_mongodb_client()
        db = client.get_database()
        if not db.name:
            db = client["sopforge"]

        try:
            req_uuid = uuid.UUID(request_id) if request_id != "unknown" else None
        except ValueError:
            req_uuid = None

        entry = AuditLogModel(
            id=uuid.uuid4(),
            request_id=req_uuid,
            event_type=event_type,
            actor_role="system",
            decision=decision,
            confidence=confidence,
            policy_refs=state.get("retrieved_policy_refs", []),
            evaluation_reasoning=state.get("evaluation_reasoning", ""),
            details={
                "request_type": state.get("request_type", "unknown"),
                "employee_code": state.get("employee_code", "unknown"),
                "sla_deadline": state.get("sla_deadline"),
                "override_count": len(state.get("override_log", [])),
            },
        )
        
        await db.audit_logs.insert_one(entry.model_dump(mode="json"))
        logger.info(f"Audit Log: Entry recorded for request {request_id}")

    except Exception as e:
        logger.error(f"Audit Log: Failed to write audit entry: {e}")

    return {
        "status": status,
    }
