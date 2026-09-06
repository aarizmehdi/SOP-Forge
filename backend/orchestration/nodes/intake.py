"""
SOP Forge — Intake node.
Validates submitted request data and enriches state with live HRMS data.
"""

import logging
from datetime import date, timedelta

from app.integrations.hrms_mock import get_hrms
from orchestration.state import RequestState

logger = logging.getLogger(__name__)


async def intake(state: RequestState) -> dict:
    """
    Intake node: validate request and fetch live employee data from HRMS.
    
    Steps:
    1. Validate submitted_data has required fields per request_type
    2. Fetch employee profile from HRMS
    3. Fetch leave balance (for leave requests)
    4. Fetch recent attendance data
    5. Return enriched state
    """
    request_type = state["request_type"]
    submitted_data = state["submitted_data"]
    employee_code = state.get("employee_code", "")

    logger.info(f"Intake: Processing {request_type} request for {employee_code}")

    hrms = get_hrms()
    live_data = {}

    try:
        # Fetch employee profile
        profile = await hrms.get_employee_profile(employee_code)
        live_data["employee_profile"] = profile

        # Fetch leave balance (relevant for all request types as context)
        balance = await hrms.get_leave_balance(employee_code)
        live_data["leave_balance"] = balance

        # Fetch recent attendance (last 30 days)
        from app.services.normalization import today_local
        today = today_local()
        start_30 = today - timedelta(days=30)
        attendance = await hrms.get_attendance(employee_code, start_30, today)
        live_data["recent_attendance"] = attendance

        # For leave requests, also fetch team leaves to check overlap
        if request_type == "leave" and profile.get("found"):
            department = profile.get("department", "")
            leave_start = submitted_data.get("start_date", today.isoformat())
            leave_end = submitted_data.get("end_date", today.isoformat())
            team_leaves = await hrms.get_team_leaves(
                department,
                date.fromisoformat(leave_start),
                date.fromisoformat(leave_end),
            )
            live_data["team_leaves_overlap"] = [item for item in team_leaves if item.get("employee_id") != employee_code]

    except Exception as e:
        logger.warning(f"Intake: HRMS fetch partially failed: {e}")
        live_data["hrms_error"] = str(e)

    # Evidence exists only if an authoritative MongoDB record is linked to this request.
    from app.database import get_mongodb_client
    client = get_mongodb_client()
    try:
        db = client.get_default_database()
    except Exception:
        db = client["sopforge"]
    evidence_present = bool(await db.evidence.find_one({"request_id": state["request_id"]}))
    return {
        "evidence_present": evidence_present,
        "live_data": live_data,
        "status": "in_progress",
    }
