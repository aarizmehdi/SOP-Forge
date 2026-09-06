"""
SOP Forge — Incident schemas.
Pydantic schemas for the HRIncident models.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional, Literal
from app.models.incident import IncidentType


class IncidentCreate(BaseModel):
    employee_id: UUID
    incident_type: IncidentType
    message: str
    ai_reasoning: Optional[str] = None
    status: Literal["open", "reviewed"] = "open"
    confidence: float = 1.0
    conversation_id: Optional[str] = None


class IncidentResponse(BaseModel):
    id: UUID
    employee_id: UUID
    incident_type: IncidentType
    message: str
    ai_reasoning: Optional[str] = None
    status: Literal["open", "reviewed"]
    confidence: float = 1.0
    conversation_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
