"""
SOP Forge — Incident ODM model (Pydantic/MongoDB).
Dedicated table for flagged/inappropriate chats requiring HR review.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class IncidentType(str, Enum):
    POLICY_BYPASS = "policy_bypass_attempt"
    AUTHORITY_IMPERSONATION = "authority_impersonation"
    FRAUDULENT_AUTHORITY_CLAIM = "fraudulent_authoritative_claim"
    SECURITY_CONTROL_MANIPULATION = "security_control_manipulation"
    SERIOUS_THREAT_HARASSMENT = "serious_threat_or_harassment"

class HRIncident(BaseModel):
    """
    Dedicated table for flagged incidents, such as inappropriate chat.
    Keeps them strictly separated from standard SOP requests and the audit trail.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    
    incident_type: IncidentType
    message: str        # The exact message the user typed
    ai_reasoning: str | None = None
    status: Literal["open", "reviewed"] = "open"
    confidence: float = Field(default=1.0, ge=0, le=1)
    conversation_id: str | None = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
