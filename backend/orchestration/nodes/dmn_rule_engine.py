"""
SOP Forge — DMN Rule Engine Node.
Deterministic evaluation of rules without LLM hallucination.
Receives extracted variables, performs math bounds checks, outputs pass/fail.
"""

import logging
from orchestration.state import RequestState

logger = logging.getLogger(__name__)


async def dmn_rule_engine(state: RequestState) -> dict:
    """
    Evaluates the request using a strict rules engine (Decision Model and Notation approach).
    Guarantees zero hallucination for policy limit math.
    """
    logger.info("DMN Engine: Starting deterministic rule evaluation")
    
    extracted = state.get("extracted_variables", {})
    live_data = state.get("live_data", {})
    intent = extracted.get("intent", state.get("request_type", ""))
    
    if intent == "leave":
        return _evaluate_leave_dmn(extracted, live_data)
    elif intent == "missed_punch":
        return _evaluate_biometric_dmn(extracted, live_data)
    elif intent == "overtime":
        return _evaluate_overtime_dmn(extracted, live_data)
    
    # Fallback if unknown
    return {
        "dmn_result": False,
        "decision": "routed",
        "evaluation_reasoning": f"DMN Engine: No deterministic rules configured for intent '{intent}'. Routing to manager."
    }


def _evaluate_leave_dmn(extracted: dict, live_data: dict) -> dict:
    category = extracted.get("category", "annual").lower()
    days_req = extracted.get("days_requested", 1)
    if days_req <= 0:
        days_req = 1
    
    # Live Data Mocks
    balance = live_data.get("leave_balance", {}).get("balances", {}).get(category, {}).get("remaining", 0)
    team_overlap = live_data.get("team_leaves_overlap", [])
    overlap_count = len([t for t in team_overlap if t.get("status") == "approved"])
    
    reasons = []
    passed = True
    decision = "approved"

    # Math Checks
    if days_req <= 0:
        passed = False
        decision = "rejected"
        reasons.append("Invalid leave duration requested.")
    
    if balance < days_req:
        passed = False
        decision = "routed"  # Route to manager for discretionary approval rather than harsh auto-reject
        reasons.append(f"Requested leave duration ({days_req} days) exceeds available {category.capitalize()} leave balance ({balance} days remaining). Escalate to manager for review.")
    
    if overlap_count >= 2:
        passed = False
        decision = "routed"
        reasons.append("Multiple department team members have overlapping leave during this period. Escalated to manager for scheduling review.")
        
    if passed:
        reasons.append(f"SOP Compliance Verified: Employee has {balance} days of {category.capitalize()} leave available for {days_req} requested days.")
    
    return {
        "dmn_result": passed,
        "decision": decision,
        "evaluation_reasoning": " ".join(reasons)
    }


def _evaluate_biometric_dmn(extracted: dict, live_data: dict) -> dict:
    consecutive_misses = live_data.get("biometrics", {}).get("consecutive_misses", 0)
    
    if consecutive_misses >= 3:
        return {
            "dmn_result": True,
            "decision": "routed",
            "evaluation_reasoning": f"Multiple consecutive missed punch entries ({consecutive_misses}) detected. Escalated to HR Manager for review per company attendance SOP."
        }
    else:
        return {
            "dmn_result": True,
            "decision": "approved",
            "evaluation_reasoning": "Missed punch request verified against attendance records. Within standard policy threshold."
        }


def _evaluate_overtime_dmn(extracted: dict, live_data: dict) -> dict:
    hours_req = extracted.get("hours_requested", 0)
    
    if hours_req > 2:
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": f"Requested overtime ({hours_req} hours) exceeds the 2-hour daily auto-approval limit. Escalated to manager for review."
        }
    
    return {
        "dmn_result": True,
        "decision": "approved",
        "evaluation_reasoning": f"Overtime request ({hours_req} hours) is within daily auto-approval limit."
    }
