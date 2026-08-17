"""
SOP Forge — Incident ORM model.
Dedicated table for flagged/inappropriate chats requiring HR review.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.database import Base


class HRIncident(Base):
    """
    Dedicated table for flagged incidents, such as inappropriate chat.
    Keeps them strictly separated from standard SOP requests and the audit trail.
    """
    __tablename__ = "hr_incidents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    
    incident_type = Column(String(50), nullable=False)  # e.g., 'inappropriate_chat'
    message = Column(Text, nullable=False)              # The exact message the user typed
    ai_reasoning = Column(Text, nullable=True)          # Why the AI flagged it
    status = Column(String(20), default="open")         # 'open' or 'reviewed'
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    employee = relationship("User", foreign_keys=[employee_id])
