"""
SOP Forge — ZKTeco Biometric API Mock.
Simulates fetching real-time punch data from a factory's ZKTeco biometric devices.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def get_punch_data(employee_code: str, target_date: str = None) -> Dict[str, Any]:
    """
    Mock API call to fetch ZKTeco punch data for an employee.
    
    Args:
        employee_code: The employee ID (e.g., EMP001).
        target_date: ISO date string. Defaults to today.
        
    Returns:
        Dict with consecutive_misses, today_punches, and hardware_status.
    """
    logger.info(f"ZKTeco API: Polling punch data for {employee_code}")
    
    # Simulate network latency
    await asyncio.sleep(0.5)
    
    if not target_date:
        target_date = datetime.now().date().isoformat()
    
    # Simple deterministic mock based on employee code
    consecutive_misses = 0
    if employee_code == "EMP002":
        consecutive_misses = 3
    elif employee_code == "EMP003":
        consecutive_misses = 1
        
    return {
        "status": "success",
        "employee_code": employee_code,
        "date": target_date,
        "biometrics": {
            "device": "ZKTeco K40",
            "consecutive_misses": consecutive_misses,
            "today_punches": {
                "in": "08:00:00" if consecutive_misses == 0 else None,
                "out": None
            },
            "hardware_status": "online"
        }
    }
