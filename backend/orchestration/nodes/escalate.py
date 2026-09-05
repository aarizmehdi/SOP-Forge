"""
SOP Forge — Escalate node.
Routes low-confidence requests to the department head with SLA enforcement.
"""

import logging
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from orchestration.state import RequestState

logger = logging.getLogger(__name__)
settings = get_settings()


async def escalate(state: RequestState) -> dict:
    """
    Escalate a request to the department head when AI confidence is low.
    
    Sets an SLA deadline (default 2 hours, configurable) per PRD requirement.
    The request is cached in Redis for fast retrieval by the manager's review panel.
    """
    request_id = state.get("request_id", "unknown")
    confidence = state.get("confidence", 0.0)
    decision = state.get("decision", "pending")
    status = state.get("status", "in_progress")

    # Calculate SLA deadline
    sla_deadline = datetime.now(timezone.utc) + timedelta(hours=settings.sla_default_hours)

    # Check if request is awaiting evidence
    if decision == "awaiting_evidence" or status == "awaiting_evidence":
        logger.info(
            f"Escalate node: Request {request_id} is awaiting evidence. "
            f"Preserving awaiting_evidence status."
        )
        return {
            "status": "awaiting_evidence",
            "decision": "awaiting_evidence",
            "sla_deadline": sla_deadline.isoformat(),
        }

    logger.info(
        f"Escalate: Request {request_id} escalated "
        f"(AI decision: {decision}, confidence: {confidence:.2f}). "
        f"SLA deadline: {sla_deadline.isoformat()}"
    )

    # Cache escalation state in Redis for fast manager retrieval
    try:
        import json
        from app.database import get_redis

        redis = get_redis()
        await redis.setex(
            f"request:{request_id}:escalated",
            int(settings.sla_default_hours * 3600) + 3600,  # TTL = SLA + 1 hour buffer
            json.dumps({
                "request_id": request_id,
                "ai_decision": decision,
                "ai_confidence": confidence,
                "sla_deadline": sla_deadline.isoformat(),
                "escalated_at": datetime.now(timezone.utc).isoformat(),
            }),
        )
    except Exception as e:
        logger.warning(f"Escalate: Redis cache failed (non-critical): {e}")

    return {
        "status": "escalated",
        "decision": "routed",
        "sla_deadline": sla_deadline.isoformat(),
    }
