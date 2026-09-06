"""
SOP Forge — Mock HRMS integration.
Provides realistic mock data for Phase 1 development.
Per PRD: cross-references live enterprise data (real leave balance, real attendance).
"""

import asyncio
import random
from datetime import date, timedelta

from app.integrations.hrms_bridge import HRMSBridge


# ── Mock Employee Data ──
MOCK_EMPLOYEES = {
    "EMP001": {
        "employee_id": "EMP001",
        "name": "Aisha Khan",
        "email": "aisha.khan@company.com",
        "department": "Engineering",
        "designation": "Senior Software Engineer",
        "join_date": "2022-03-15",
        "manager_id": "EMP006",
    },
    "EMP002": {
        "employee_id": "EMP002",
        "name": "Omar Farooq",
        "email": "omar.farooq@company.com",
        "department": "Engineering",
        "designation": "Software Engineer",
        "join_date": "2023-06-01",
        "manager_id": "EMP006",
    },
    "EMP003": {
        "employee_id": "EMP003",
        "name": "Sara Ahmed",
        "email": "sara.ahmed@company.com",
        "department": "Marketing",
        "designation": "Marketing Specialist",
        "join_date": "2023-01-10",
        "manager_id": "EMP007",
    },
    "EMP004": {
        "employee_id": "EMP004",
        "name": "Hassan Ali",
        "email": "hassan.ali@company.com",
        "department": "Engineering",
        "designation": "Junior Developer",
        "join_date": "2024-09-01",
        "manager_id": "EMP006",
    },
    "EMP005": {
        "employee_id": "EMP005",
        "name": "Fatima Zahra",
        "email": "fatima.zahra@company.com",
        "department": "Marketing",
        "designation": "Content Creator",
        "join_date": "2024-02-15",
        "manager_id": "EMP007",
    },
    "EMP006": {
        "employee_id": "EMP006",
        "name": "Bilal Hussain",
        "email": "bilal.hussain@company.com",
        "department": "Engineering",
        "designation": "Engineering Manager",
        "join_date": "2020-01-05",
        "manager_id": "EMP008",
    },
    "EMP007": {
        "employee_id": "EMP007",
        "name": "Zainab Malik",
        "email": "zainab.malik@company.com",
        "department": "Marketing",
        "designation": "Marketing Manager",
        "join_date": "2021-06-15",
        "manager_id": "EMP008",
    },
    "EMP008": {
        "employee_id": "EMP008",
        "name": "Tariq Rashid",
        "email": "tariq.rashid@company.com",
        "department": "Executive",
        "designation": "VP Operations",
        "join_date": "2019-01-01",
        "manager_id": None,
    },
    "EMP009": {
        "employee_id": "EMP009",
        "name": "Nadia Bukhari",
        "email": "nadia.bukhari@company.com",
        "department": "HR",
        "designation": "HR & Compliance Lead",
        "join_date": "2020-08-20",
        "manager_id": "EMP008",
    },
}

# ── Mock Leave Balances ──
MOCK_LEAVE_BALANCES = {
    "EMP001": {"annual": 12, "sick": 8, "casual": 5, "unpaid": 0, "used_annual": 3, "used_sick": 1, "used_casual": 2},
    "EMP002": {"annual": 10, "sick": 8, "casual": 5, "unpaid": 0, "used_annual": 8, "used_sick": 2, "used_casual": 3},
    "EMP003": {"annual": 12, "sick": 8, "casual": 5, "unpaid": 0, "used_annual": 4, "used_sick": 0, "used_casual": 1},
    "EMP004": {"annual": 8, "sick": 8, "casual": 5, "unpaid": 0, "used_annual": 7, "used_sick": 3, "used_casual": 4},
    "EMP005": {"annual": 10, "sick": 8, "casual": 5, "unpaid": 0, "used_annual": 2, "used_sick": 1, "used_casual": 0},
    "EMP006": {"annual": 18, "sick": 10, "casual": 7, "unpaid": 0, "used_annual": 5, "used_sick": 0, "used_casual": 2},
    "EMP007": {"annual": 18, "sick": 10, "casual": 7, "unpaid": 0, "used_annual": 6, "used_sick": 1, "used_casual": 3},
    "EMP008": {"annual": 25, "sick": 12, "casual": 10, "unpaid": 0, "used_annual": 10, "used_sick": 0, "used_casual": 2},
    "EMP009": {"annual": 15, "sick": 10, "casual": 7, "unpaid": 0, "used_annual": 3, "used_sick": 2, "used_casual": 1},
}

# ── Blackout dates (company-wide) ──
BLACKOUT_DATES = [
    ("2026-12-28", "2026-12-31"),  # Year-end freeze
    ("2026-03-31", "2026-04-02"),  # Quarter-end close
    ("2026-06-30", "2026-07-02"),  # Quarter-end close
]


class MockHRMSBridge(HRMSBridge):
    """
    Mock HRMS implementation with realistic sample data.
    Simulates async behavior with configurable latency.
    """

    def __init__(self, latency_ms: int = 50):
        self.latency_ms = latency_ms

    async def _simulate_latency(self):
        """Simulate network latency for realistic behavior."""
        await asyncio.sleep(self.latency_ms / 1000)

    async def get_employee_profile(self, employee_id: str) -> dict:
        """Fetch mock employee profile."""
        await self._simulate_latency()
        profile = MOCK_EMPLOYEES.get(employee_id)
        if not profile:
            return {"error": f"Employee {employee_id} not found", "found": False}
        return {**profile, "found": True}

    async def get_leave_balance(self, employee_id: str) -> dict:
        """Fetch mock leave balances with remaining calculations."""
        await self._simulate_latency()
        balances = MOCK_LEAVE_BALANCES.get(employee_id)
        if not balances:
            return {"error": f"No balance data for {employee_id}", "found": False}

        return {
            "employee_id": employee_id,
            "found": True,
            "balances": {
                "annual": {
                    "total": balances["annual"],
                    "used": balances["used_annual"],
                    "remaining": balances["annual"] - balances["used_annual"],
                },
                "sick": {
                    "total": balances["sick"],
                    "used": balances["used_sick"],
                    "remaining": balances["sick"] - balances["used_sick"],
                },
                "casual": {
                    "total": balances["casual"],
                    "used": balances["used_casual"],
                    "remaining": balances["casual"] - balances["used_casual"],
                },
                "unpaid": {
                    "total": 0,
                    "used": balances["unpaid"],
                    "remaining": 0,
                },
            },
            "blackout_dates": BLACKOUT_DATES,
        }

    async def get_attendance(
        self, employee_id: str, start_date: date, end_date: date
    ) -> dict:
        """Generate deterministic mock attendance data for the date range."""
        await self._simulate_latency()

        records = []
        current = start_date
        day_idx = 0
        while current <= end_date:
            if current.weekday() < 5:  # Mon-Fri
                # Deterministic pattern: absent on 10th working day, present otherwise
                is_present = (day_idx % 10) != 9
                records.append({
                    "date": current.isoformat(),
                    "status": "present" if is_present else "absent",
                    "check_in": "09:05" if is_present else None,
                    "check_out": "18:10" if is_present else None,
                    "hours_worked": 8.0 if is_present else 0,
                })
                day_idx += 1
            current += timedelta(days=1)

        total_days = len(records)
        present_days = sum(1 for r in records if r["status"] == "present")

        return {
            "employee_id": employee_id,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_working_days": total_days,
            "present_days": present_days,
            "absent_days": total_days - present_days,
            "attendance_rate": round(present_days / total_days * 100, 1) if total_days > 0 else 100.0,
            "records": records,
        }

    async def get_team_leaves(
        self, department_id: str, start_date: date, end_date: date
    ) -> list[dict]:
        """Get deterministic approved/pending leaves for a team in a date range."""
        await self._simulate_latency()

        team_leaves = []
        # Fixed scenario: If Engineering department and dates overlap with Hassan Ali (EMP004) scenario
        # generate 2 approved team leaves to demonstrate team overlap threshold rule
        dept_lower = department_id.lower()
        if dept_lower in ("engineering", "eng") and start_date <= date(2026, 10, 14) and end_date >= date(2026, 10, 12):
            # EMP004 (Hassan Ali) triggers overlap escalation scenario
            # If start_date month is same or range includes active dates, return 2 fixed overlapping leaves
            team_leaves = [
                {
                    "employee_id": "EMP002",
                    "employee_name": "Omar Farooq",
                    "leave_type": "annual",
                    "start_date": "2026-10-12",
                    "end_date": "2026-10-14",
                    "status": "approved",
                },
                {
                    "employee_id": "EMP006",
                    "employee_name": "Bilal Hussain",
                    "leave_type": "casual",
                    "start_date": "2026-10-12",
                    "end_date": "2026-10-14",
                    "status": "approved",
                },
            ]
        return team_leaves


# ── Singleton ──
_hrms_instance: MockHRMSBridge | None = None


def get_hrms() -> MockHRMSBridge:
    """Get the HRMS bridge instance."""
    global _hrms_instance
    if _hrms_instance is None:
        _hrms_instance = MockHRMSBridge()
    return _hrms_instance
