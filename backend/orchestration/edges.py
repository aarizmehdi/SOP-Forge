"""
SOP Forge — Conditional edge logic for LangGraph.
Determines workflow routing based on AI evaluation confidence.
"""

import logging

from app.config import get_settings
from orchestration.state import RequestState

logger = logging.getLogger(__name__)
settings = get_settings()


def check_confidence(state: RequestState) -> str:
    """
    Conditional edge: routes to auto_decide or escalate based on DMN and confidence.
    
    High confidence AND DMN pass → auto_decide → audit_log
    Low confidence OR DMN fail  → escalate → override_check → audit_log
    """
    confidence = state.get("confidence", 0.0)
    decision = state.get("decision", "pending")
    dmn_result = state.get("dmn_result", False)
    threshold = settings.confidence_threshold

    if decision == "routed" or not dmn_result:
        logger.info(f"Edge: DMN failed or explicitly routed — escalating")
        return "escalate"

    if confidence >= threshold:
        logger.info(
            f"Edge: DMN Passed and Confidence {confidence:.2f} >= {threshold} — auto-deciding"
        )
        return "auto_decide"
    else:
        logger.info(
            f"Edge: Confidence {confidence:.2f} < threshold {threshold} — escalating"
        )
        return "escalate"
