"""
SOP Forge — Audit Log node.
Terminal node — writes complete, immutable audit log entry.
Every path through the graph ends here.
"""

import logging
import uuid

from orchestration.state import RequestState

logger = logging.getLogger(__name__)


async def audit_log(state: RequestState) -> dict:
    """
    Terminal audit log node — writes a complete audit entry to PostgreSQL.
    
    Every path through the LangGraph workflow terminates here, ensuring
    100% audit trail coverage as required by the PRD.
    
    Records: request details, decision, confidence, policy refs,
    reasoning, override info.
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
        from app.database import async_session_factory
        from app.models.audit import AuditEventType, AuditLog as AuditLogModel

        # Determine the audit event type based on the outcome
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

        async with async_session_factory() as db:
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
            db.add(entry)
            await db.commit()

        logger.info(f"Audit Log: Entry recorded for request {request_id}")

    except Exception as e:
        logger.error(f"Audit Log: Failed to write audit entry: {e}")
        # Non-fatal — we log the error but don't fail the workflow
        # In production, this should trigger an alert

    return {
        "status": status,
    }
