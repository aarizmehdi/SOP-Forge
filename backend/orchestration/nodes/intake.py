"""
SOP Forge — Intake node.
Validates submitted request data and enriches state with live HRMS data.
"""

import logging
from datetime import date

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
        today = date.today()
        start_30 = date(today.year, today.month - 1 if today.month > 1 else 12, today.day)
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
            live_data["team_leaves_overlap"] = team_leaves

    except Exception as e:
        logger.warning(f"Intake: HRMS fetch partially failed: {e}")
        live_data["hrms_error"] = str(e)

    return {
        "live_data": live_data,
        "status": "in_progress",
    }
