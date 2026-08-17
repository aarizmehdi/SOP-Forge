"""
SOP Forge — Incident schemas.
Pydantic schemas for the HRIncident models.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional


class IncidentCreate(BaseModel):
    employee_id: UUID
    incident_type: str
    message: str
    ai_reasoning: Optional[str] = None
    status: str = "open"


class IncidentResponse(BaseModel):
    id: UUID
    employee_id: UUID
    incident_type: str
    message: str
    ai_reasoning: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
