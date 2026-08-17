"""
SOP Forge — Override Check node.
Human-in-the-loop interrupt point for executive overrides.
"""

import logging

from orchestration.state import RequestState

logger = logging.getLogger(__name__)


async def override_check(state: RequestState) -> dict:
    """
    Override check point — allows executive override at any stage.
    
    In the actual workflow, this node acts as a pass-through unless
    an executive override has been submitted via the API.
    The API endpoint handles the actual override logic and state mutation.
    
    This node exists in the graph to represent the override checkpoint
    in the deterministic workflow and to ensure the audit trail captures
    that the override opportunity was presented.
    """
    request_id = state.get("request_id", "unknown")
    override_log = state.get("override_log", [])

    if override_log:
        latest = override_log[-1]
        logger.info(
            f"Override Check: Request {request_id} has {len(override_log)} override(s). "
            f"Latest by: {latest.get('by', 'unknown')}"
        )
        return {
            "status": "overridden",
        }

    logger.info(f"Override Check: No overrides for request {request_id}")
    return {}
