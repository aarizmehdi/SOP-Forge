"""
SOP Forge — HRMS Bridge abstract interface.
Defines the contract for integrating with any HRMS/payroll/biometric system.
Per PRD: build the bridge against the real system once confirmed, not assumed.
"""

from abc import ABC, abstractmethod
from datetime import date


class HRMSBridge(ABC):
    """Abstract interface for HRMS system integration."""

    @abstractmethod
    async def get_employee_profile(self, employee_id: str) -> dict:
        """Fetch employee profile data from HRMS."""
        ...

    @abstractmethod
    async def get_leave_balance(self, employee_id: str) -> dict:
        """Fetch current leave balances for an employee."""
        ...

    @abstractmethod
    async def get_attendance(
        self, employee_id: str, start_date: date, end_date: date
    ) -> dict:
        """Fetch attendance records for a date range."""
        ...

    @abstractmethod
    async def get_team_leaves(
        self, department_id: str, start_date: date, end_date: date
    ) -> list[dict]:
        """Fetch approved/pending leaves for a team in a date range."""
        ...
