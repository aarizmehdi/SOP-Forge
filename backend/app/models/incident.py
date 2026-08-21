"""
SOP Forge — Incident ODM model (Pydantic/MongoDB).
Dedicated table for flagged/inappropriate chats requiring HR review.
"""

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class HRIncident(BaseModel):
    """
    Dedicated table for flagged incidents, such as inappropriate chat.
    Keeps them strictly separated from standard SOP requests and the audit trail.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    
    incident_type: str  # e.g., 'inappropriate_chat'
    message: str        # The exact message the user typed
    ai_reasoning: str | None = None
    status: str = "open" # 'open' or 'reviewed'
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
