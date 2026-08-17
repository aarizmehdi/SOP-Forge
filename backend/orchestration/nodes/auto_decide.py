"""
SOP Forge — Auto-Decide node.
Finalizes the decision when AI confidence meets the threshold.
"""

import logging

from orchestration.state import RequestState

logger = logging.getLogger(__name__)


async def auto_decide(state: RequestState) -> dict:
    """
    Finalize the AI decision when confidence is high enough.
    Updates request status to resolved with the auto-decided outcome.
    """
    decision = state.get("decision", "pending")
    confidence = state.get("confidence", 0.0)
    request_id = state.get("request_id", "unknown")

    logger.info(
        f"Auto-Decide: Request {request_id} auto-{decision} "
        f"with confidence {confidence:.2f}"
    )

    return {
        "status": "resolved",
        "decision": decision,
    }
