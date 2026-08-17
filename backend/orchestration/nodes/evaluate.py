"""
SOP Forge — Evaluate node.
LLM-based decision evaluation with confidence scoring.
Uses DeepSeek V4 Pro via langchain-deepseek, with a mock fallback.
"""

import json
import logging
import re

from app.config import get_settings
from orchestration.state import RequestState

logger = logging.getLogger(__name__)
settings = get_settings()


EVALUATION_PROMPT = """You are an SOP (Standard Operating Procedure) compliance evaluator for an organization.
Your task is to evaluate an employee request against the organization's SOP policy and live data.

## Request Details
- **Type:** {request_type}
- **Employee:** {employee_code}
- **Submitted Data:** {submitted_data}

## Retrieved SOP Policy
{policy_text}

## Live Employee Data
{live_data}

## Your Task
Evaluate this request against the SOP policy and live data. You MUST respond with ONLY a JSON object (no markdown, no extra text):

{{
    "decision": "approved" | "rejected" | "routed",
    "confidence": <float between 0.0 and 1.0>,
    "reasoning": "<detailed explanation referencing specific policy sections and data>"
}}

## Decision Guidelines
- **approved**: Request clearly meets all policy requirements. High confidence (>= 0.85).
- **rejected**: Request clearly violates policy. High confidence (>= 0.85).
- **routed**: Ambiguous case, needs human review. Any confidence level.

## Confidence Guidelines
- 0.90-1.00: Clear-cut case, policy unambiguously applies
- 0.75-0.89: Likely correct but some nuance exists
- 0.50-0.74: Uncertain, should be escalated
- 0.00-0.49: Very uncertain, definitely escalate

Be conservative. When in doubt, route for human review rather than making an incorrect automated decision.
"""


async def evaluate(state: RequestState) -> dict:
    """
    Evaluate the request using the LLM against retrieved policy and live data.
    Falls back to a rule-based mock if no LLM is configured.
    """
    request_type = state["request_type"]
    employee_code = state.get("employee_code", "unknown")
    submitted_data = state["submitted_data"]
    policy_text = state.get("retrieved_policy_text", "No policy retrieved")
    live_data = state.get("live_data", {})

    logger.info(f"Evaluate: Running AI evaluation for {request_type} request")

    if settings.is_llm_configured:
        try:
            return await _evaluate_with_llm(
                request_type, employee_code, submitted_data, policy_text, live_data
            )
        except Exception as e:
            logger.error(f"Evaluate: LLM evaluation failed, falling back to rules: {e}")

    # Fallback: rule-based evaluation for development
    return await _evaluate_with_rules(request_type, submitted_data, live_data)


async def _evaluate_with_llm(
    request_type: str,
    employee_code: str,
    submitted_data: dict,
    policy_text: str,
    live_data: dict,
) -> dict:
    """Evaluate using DeepSeek via LangChain OpenAI compatible client."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.1,
        max_tokens=1000,
        openai_api_key=settings.deepseek_api_key,
        openai_api_base="https://api.deepseek.com/v1",
    )

    prompt = EVALUATION_PROMPT.format(
        request_type=request_type,
        employee_code=employee_code,
        submitted_data=json.dumps(submitted_data, indent=2),
        policy_text=policy_text,
        live_data=json.dumps(live_data, indent=2, default=str),
    )

    response = await llm.ainvoke(prompt)
    response_text = response.content.strip()

    # Parse the JSON response
    # Try to extract JSON from the response (handle markdown code blocks)
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        result = json.loads(json_match.group())
    else:
        result = json.loads(response_text)

    return {
        "decision": result.get("decision", "routed"),
        "confidence": float(result.get("confidence", 0.5)),
        "evaluation_reasoning": result.get("reasoning", "Evaluated per SOP policies"),
    }


async def _evaluate_with_rules(
    request_type: str,
    submitted_data: dict,
    live_data: dict,
) -> dict:
    """
    Rule-based fallback evaluation for development/testing.
    Provides deterministic behavior when no LLM is configured.
    """
    if request_type == "leave":
        return await _evaluate_leave_rules(submitted_data, live_data)
    elif request_type == "reimbursement":
        return _evaluate_reimbursement_rules(submitted_data)
    else:
        return {
            "decision": "routed",
            "confidence": 0.5,
            "evaluation_reasoning": f"No automated rules for {request_type}. Escalating for manual review.",
        }


async def _evaluate_leave_rules(submitted_data: dict, live_data: dict) -> dict:
    """Rule-based leave evaluation matching common SOP policies."""
    leave_type = submitted_data.get("leave_type", "annual")
    start_date = submitted_data.get("start_date", "")
    end_date = submitted_data.get("end_date", "")
    reason = submitted_data.get("reason", "")

    # Calculate requested days
    try:
        from datetime import date as date_cls
        start = date_cls.fromisoformat(start_date)
        end = date_cls.fromisoformat(end_date)
        requested_days = (end - start).days + 1
        if submitted_data.get("half_day"):
            requested_days = 0.5
    except (ValueError, TypeError):
        return {
            "decision": "routed",
            "confidence": 0.4,
            "evaluation_reasoning": "Invalid date format in request. Cannot evaluate automatically.",
        }

    # Check leave balance
    balance_data = live_data.get("leave_balance", {}).get("balances", {})
    leave_balance = balance_data.get(leave_type, {})
    remaining = leave_balance.get("remaining", 0)

    reasons = []

    # Rule 1: Sufficient balance
    if remaining < requested_days:
        reasons.append(
            f"Insufficient {leave_type} leave balance. "
            f"Requested: {requested_days} days, Remaining: {remaining} days."
        )
        return {
            "decision": "rejected",
            "confidence": 0.95,
            "evaluation_reasoning": " ".join(reasons) + " Request exceeds available balance per leave policy.",
        }

    # Rule 2: Check blackout dates
    blackout_dates = live_data.get("leave_balance", {}).get("blackout_dates", [])
    for blackout_start, blackout_end in blackout_dates:
        try:
            from datetime import date as date_cls
            bs = date_cls.fromisoformat(blackout_start)
            be = date_cls.fromisoformat(blackout_end)
            if start <= be and end >= bs:
                reasons.append(
                    f"Requested dates overlap with blackout period ({blackout_start} to {blackout_end})."
                )
                return {
                    "decision": "rejected",
                    "confidence": 0.92,
                    "evaluation_reasoning": " ".join(reasons) + " Company policy prohibits leave during blackout periods.",
                }
        except (ValueError, TypeError):
            pass

    # Rule 3: Check team overlap
    team_leaves = live_data.get("team_leaves_overlap", [])
    overlapping_team = [tl for tl in team_leaves if tl.get("status") == "approved"]
    if len(overlapping_team) >= 2:
        reasons.append(
            f"Multiple team members ({len(overlapping_team)}) already have approved leave during this period. "
            "Team coverage may be insufficient."
        )
        return {
            "decision": "routed",
            "confidence": 0.6,
            "evaluation_reasoning": " ".join(reasons) + " Escalating for manager review due to team coverage concerns.",
        }

    # Rule 4: Check notice period (7 days for annual, 0 for sick)
    from datetime import date as date_cls
    today = date_cls.today()
    days_notice = (start - today).days if isinstance(start, date_cls) else 0

    if leave_type == "annual" and days_notice < 7 and requested_days > 2:
        reasons.append(
            f"Annual leave with only {days_notice} days notice (policy requires 7 days for >2 day leave)."
        )
        return {
            "decision": "routed",
            "confidence": 0.65,
            "evaluation_reasoning": " ".join(reasons) + " Short notice leave. Escalating for manager discretion.",
        }

    # Rule 5: Check attendance rate
    attendance = live_data.get("recent_attendance", {})
    attendance_rate = attendance.get("attendance_rate", 100)
    if attendance_rate < 80 and leave_type != "sick":
        reasons.append(
            f"Employee attendance rate ({attendance_rate}%) is below threshold (80%). "
            "Request needs manager review."
        )
        return {
            "decision": "routed",
            "confidence": 0.55,
            "evaluation_reasoning": " ".join(reasons) + " Low attendance rate warrants manager review.",
        }

    # All checks passed — auto-approve
    reasons.append(
        f"Leave request meets all policy requirements. "
        f"Balance sufficient ({remaining} remaining after {requested_days} day request). "
        f"No blackout conflicts. Adequate notice period."
    )
    return {
        "decision": "approved",
        "confidence": 0.92,
        "evaluation_reasoning": " ".join(reasons),
    }


def _evaluate_reimbursement_rules(submitted_data: dict) -> dict:
    """Rule-based reimbursement evaluation."""
    amount = submitted_data.get("amount", 0)
    category = submitted_data.get("category", "other")

    # Simple limit-based rules
    limits = {"travel": 5000, "medical": 10000, "equipment": 2000, "other": 1000}
    limit = limits.get(category, 1000)

    if amount <= limit * 0.5:
        return {
            "decision": "approved",
            "confidence": 0.90,
            "evaluation_reasoning": f"Amount ${amount} is well within the ${limit} limit for {category} reimbursements.",
        }
    elif amount <= limit:
        return {
            "decision": "routed",
            "confidence": 0.7,
            "evaluation_reasoning": f"Amount ${amount} is within limit but close to the ${limit} cap for {category}. Manager review recommended.",
        }
    else:
        return {
            "decision": "rejected",
            "confidence": 0.93,
            "evaluation_reasoning": f"Amount ${amount} exceeds the ${limit} limit for {category} reimbursements per policy.",
        }
