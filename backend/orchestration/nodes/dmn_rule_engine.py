"""
SOP Forge — DMN Rule Engine Node.
Deterministic evaluation of rules without LLM hallucination.
Receives request state, calculates server-side date duration, performs math bounds checks, outputs pass/fail.
"""

import logging
from datetime import date
from orchestration.state import RequestState

logger = logging.getLogger(__name__)

VALID_LEAVE_CATEGORIES = {"annual", "sick", "casual", "unpaid"}


async def dmn_rule_engine(state: RequestState) -> dict:
    """
    Evaluates the request using a strict rules engine (Decision Model and Notation approach).
    Guarantees zero hallucination for policy limit math.
    """
    logger.info("DMN Engine: Starting deterministic rule evaluation")
    
    extracted = state.get("extracted_variables", {})
    submitted_data = state.get("submitted_data", {})
    live_data = state.get("live_data", {})

    from app.services.normalization import normalize_submission
    try:
        submitted_data = normalize_submission(state.get("request_type"), submitted_data)
    except (ValueError, TypeError):
        return {"dmn_result": False, "decision": "routed", "status": "escalated",
                "evaluation_reasoning": "Request data is invalid or incoherent; human review required."}
    if live_data.get("hrms_error") or not live_data.get("employee_profile", {}).get("found") or state.get("policy_unavailable") or state.get("error"):
        return {"dmn_result": False, "decision": "routed", "status": "escalated",
                "evaluation_reasoning": "Authoritative HRMS or policy guidance unavailable; human review required."}

    # P0-2: Trusted Request Type (State request_type is authoritative, NOT LLM intent)
    trusted_request_type = state.get("request_type", "leave").lower()
    llm_intent = extracted.get("intent", "").lower()

    if llm_intent and llm_intent != trusted_request_type:
        logger.warning(
            f"DMN Engine: LLM intent '{llm_intent}' differs from trusted request_type '{trusted_request_type}'. "
            f"Enforcing trusted request_type branch."
        )
    
    if trusted_request_type == "leave":
        return _evaluate_leave_dmn(submitted_data, extracted, live_data, state)
    elif trusted_request_type == "missed_punch":
        return _evaluate_biometric_dmn(submitted_data, extracted, live_data)
    elif trusted_request_type == "overtime":
        return _evaluate_overtime_dmn(submitted_data, extracted, live_data)
    elif trusted_request_type in ("reimbursement", "expense"):
        return _evaluate_reimbursement_dmn(submitted_data, extracted)
    elif trusted_request_type == "it_access":
        return _evaluate_it_access_dmn(submitted_data, extracted)
    
    # Fallback if unknown request type
    return {
        "dmn_result": False,
        "decision": "routed",
        "evaluation_reasoning": f"DMN Engine: Unrecognized request type '{trusted_request_type}'. Escalating for manager review."
    }


def _evaluate_leave_dmn(submitted_data: dict, extracted: dict, live_data: dict, state: RequestState) -> dict:
    reasons = []
    passed = True
    decision = "approved"

    # P0-3: Validate & Normalize Leave Category
    submitted_category = (submitted_data.get("leave_type") or "").strip().lower()
    if submitted_category not in VALID_LEAVE_CATEGORIES:
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": f"DMN Failure: Unknown leave category '{submitted_category}'. Category must be one of {sorted(list(VALID_LEAVE_CATEGORIES))}. Escalated for human review."
        }

    # P0-1 & P0-7: Server-side Date Validation & Duration Calculation
    start_str = submitted_data.get("start_date")
    end_str = submitted_data.get("end_date")

    if not start_str:
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": "DMN Failure: Missing start_date in request. Escalated for human review."
        }

    try:
        start_dt = date.fromisoformat(start_str)
        end_dt = date.fromisoformat(end_str)
    except (ValueError, TypeError):
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": f"DMN Failure: Invalid date format (start_date='{start_str}', end_date='{end_str}'). Dates must be in YYYY-MM-DD format. Escalated for human review."
        }

    # Date range validation (end_date >= start_date)
    if end_dt < start_dt:
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": f"DMN Failure: Invalid date range (end_date '{end_str}' is before start_date '{start_str}'). Escalated for human review."
        }

    # Deterministic duration calculation (inclusive)
    days_req = (end_dt - start_dt).days + 1
    if submitted_data.get("half_day"):
        if start_dt != end_dt:
            return {"dmn_result": False, "decision": "routed", "status": "escalated",
                    "evaluation_reasoning": "Half-day leave must cover a single date."}
        days_req = 0.5

    if days_req <= 0:
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": f"DMN Failure: Invalid calculated duration ({days_req} days). Escalated for human review."
        }

    # STRICT ZERO BACKDATE RULE: start_date MUST be >= today
    from app.services.normalization import today_local
    today_dt = today_local()
    if start_dt < today_dt:
        return {
            "dmn_result": False,
            "decision": "rejected",
            "status": "resolved",
            "evaluation_reasoning": f"DMN Policy Rejection: Backdated leave requests are strictly prohibited. Requested start date '{start_str}' is in the past. Leave requests must start today ({today_dt.isoformat()}) or a future date."
        }

    # Extreme advance leave (> 365 days) requires manager review
    from datetime import timedelta
    if start_dt > (today_dt + timedelta(days=365)):
        passed = False
        decision = "routed"
        reasons.append(
            f"Advance planning threshold exceeded: Leave requested more than 365 days in advance ({start_str}) requires manager review."
        )

    # Fetch HRMS Leave Balance for normalized category
    balance_dict = live_data.get("leave_balance", {}).get("balances", {}).get(submitted_category, {})
    remaining_balance = balance_dict.get("remaining", 0)

    # Balance check
    if remaining_balance < days_req:
        passed = False
        decision = "routed"
        reasons.append(
            f"Requested leave duration ({days_req} days) exceeds available {submitted_category.capitalize()} leave balance ({remaining_balance} days remaining)."
        )

    # Check Blackout dates
    blackout_dates = live_data.get("leave_balance", {}).get("blackout_dates", [])
    for bo_start, bo_end in blackout_dates:
        try:
            bs = date.fromisoformat(bo_start)
            be = date.fromisoformat(bo_end)
            if start_dt <= be and end_dt >= bs:
                passed = False
                decision = "routed"
                reasons.append(f"Requested dates overlap with company blackout period ({bo_start} to {bo_end}).")
                break
        except (ValueError, TypeError):
            pass

    # Team Overlap Check
    team_overlap = live_data.get("team_leaves_overlap", [])
    approved_overlaps = [t for t in team_overlap if t.get("status") == "approved"]
    if len(approved_overlaps) >= 2:
        passed = False
        decision = "routed"
        reasons.append(f"Multiple team members ({len(approved_overlaps)}) have overlapping approved leave during this period.")

    from app.config import get_settings
    threshold = get_settings().sick_evidence_threshold_days
    if submitted_category == "sick" and days_req >= threshold:
        passed, decision = False, "routed"
        if state.get("evidence_present"):
            reasons.append("Supporting evidence attached; human evidence review is required. File presence is not verification.")
        else:
            reasons.append("Required supporting evidence was not provided; manager review is required.")

    if passed:
        reasons.append(
            f"SOP Compliance Verified: Employee has {remaining_balance} days of {submitted_category.capitalize()} leave available for {days_req} requested day(s)."
        )

    calc_status = "escalated" if not passed else "in_progress"

    return {
        "dmn_result": passed,
        "decision": decision,
        "status": calc_status,
        "evaluation_reasoning": " | ".join(reasons),
    }


def _evaluate_biometric_dmn(submitted_data: dict, extracted: dict, live_data: dict) -> dict:
    consecutive_misses = live_data.get("biometrics", {}).get("consecutive_misses", 0)
    if consecutive_misses >= 3:
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": f"Multiple consecutive missed punch entries ({consecutive_misses}) detected. Escalated to HR Manager per attendance SOP."
        }
    return {
        "dmn_result": True,
        "decision": "approved",
        "evaluation_reasoning": "Missed punch request verified against attendance records. Within standard policy threshold."
    }


def _evaluate_overtime_dmn(submitted_data: dict, extracted: dict, live_data: dict) -> dict:
    try:
        hours_req = float(submitted_data.get("hours_requested") or extracted.get("hours_requested") or 0)
    except (ValueError, TypeError):
        hours_req = 0.0

    if hours_req <= 0 or hours_req > 2:
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


def _evaluate_reimbursement_dmn(submitted_data: dict, extracted: dict) -> dict:
    try:
        amount = float(submitted_data.get("amount") or extracted.get("amount") or 0)
    except (ValueError, TypeError):
        amount = 0.0

    category = (submitted_data.get("category") or extracted.get("category") or "other").lower()
    limits = {"travel": 500.0, "medical": 1000.0, "equipment": 300.0, "other": 150.0}
    limit = limits.get(category, 150.0)

    if amount <= 0 or amount > limit:
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": f"Reimbursement claim of ${amount:.2f} for {category} exceeds the auto-approval limit of ${limit:.2f}. Escalated to manager for review."
        }
    return {
        "dmn_result": True,
        "decision": "approved",
        "evaluation_reasoning": f"Reimbursement claim of ${amount:.2f} for {category} is within auto-approval limit of ${limit:.2f}."
    }


def _evaluate_it_access_dmn(submitted_data: dict, extracted: dict) -> dict:
    access_level = (submitted_data.get("access_level") or extracted.get("access_level") or "read").lower()
    if access_level in ("admin", "root", "write"):
        return {
            "dmn_result": False,
            "decision": "routed",
            "evaluation_reasoning": f"IT Access level '{access_level}' requires manual IT manager approval per security SOP."
        }
    return {
        "dmn_result": True,
        "decision": "approved",
        "evaluation_reasoning": f"Standard read-only IT access request approved per security SOP."
    }
