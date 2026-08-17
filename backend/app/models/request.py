"""
SOP Forge — SOP Request & Request History ORM models.
Tracks employee requests through the governed AI evaluation pipeline.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.database import Base


class RequestType(str, enum.Enum):
    """Types of SOP-governed requests."""
    LEAVE = "leave"
    REIMBURSEMENT = "reimbursement"
    IT_ACCESS = "it_access"
    OTHER = "other"


class RequestStatus(str, enum.Enum):
    """Request lifecycle status."""
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    OVERRIDDEN = "overridden"


class Decision(str, enum.Enum):
    """AI/human decision outcome."""
    APPROVED = "approved"
    REJECTED = "rejected"
    ROUTED = "routed"
    PENDING = "pending"


class SOPRequest(Base):
    """
    A governed employee request evaluated by the SOP AI engine.
    Maps directly to the PRD state schema (Section 7).
    """
    __tablename__ = "sop_requests"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    request_type = Column(Enum(RequestType), nullable=False, index=True)
    submitted_data = Column(JSON, nullable=False, default=dict)

    # AI evaluation results
    decision = Column(Enum(Decision), nullable=False, default=Decision.PENDING)
    confidence = Column(Float, nullable=True)
    evaluation_reasoning = Column(Text, nullable=True)
    retrieved_policy_refs = Column(JSON, nullable=True, default=list)

    # Lifecycle
    status = Column(Enum(RequestStatus), nullable=False, default=RequestStatus.IN_PROGRESS)
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    override_log = Column(JSON, nullable=True, default=list)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    employee = relationship("User", foreign_keys=[employee_id])
    history = relationship("RequestHistory", back_populates="request", order_by="RequestHistory.created_at")

    def __repr__(self) -> str:
        return f"<SOPRequest {self.id} type={self.request_type.value} status={self.status.value}>"


class RequestHistory(Base):
    """
    Tracks every state transition for a request.
    Provides a timeline view of the request lifecycle.
    """
    __tablename__ = "request_history"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("sop_requests.id"),
        nullable=False,
        index=True,
    )
    action = Column(String(100), nullable=False)
    actor_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    details = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    request = relationship("SOPRequest", back_populates="history")
    actor = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<RequestHistory {self.action} on {self.request_id}>"
