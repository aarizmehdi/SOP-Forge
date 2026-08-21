"""
SOP Forge — SOP Request & Request History ODM models (Pydantic/MongoDB).
Tracks employee requests through the governed AI evaluation pipeline.
"""

import enum
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field

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


class SOPRequest(BaseModel):
    """
    A governed employee request evaluated by the SOP AI engine.
    Maps directly to the PRD state schema (Section 7).
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    request_type: RequestType
    submitted_data: dict = Field(default_factory=dict)

    # AI evaluation results
    decision: Decision = Decision.PENDING
    confidence: float | None = None
    evaluation_reasoning: str | None = None
    retrieved_policy_refs: list | None = Field(default_factory=list)

    # Lifecycle
    status: RequestStatus = RequestStatus.IN_PROGRESS
    sla_deadline: datetime | None = None
    override_log: list | None = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RequestHistory(BaseModel):
    """
    Tracks every state transition for a request.
    Provides a timeline view of the request lifecycle.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    action: str
    actor_id: str | None = None
    details: dict | None = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
