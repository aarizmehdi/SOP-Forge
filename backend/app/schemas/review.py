"""
SOP Forge — Review schemas.
Pydantic models for manager review and executive override.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.request import Decision, RequestStatus, RequestType


class ReviewDecision(BaseModel):
    """Manager's decision on an escalated request."""
    decision: Decision = Field(..., description="approved, rejected, or routed (for more info)")
    comment: str = Field(..., min_length=5, max_length=2000)


class ExecutiveOverride(BaseModel):
    """Executive override with mandatory justification."""
    new_decision: Decision = Field(..., description="The overriding decision")
    justification: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Mandatory justification for the override",
    )


class EscalatedRequestItem(BaseModel):
    """An escalated request visible to managers."""
    id: UUID
    employee_name: str
    employee_id_code: str
    department: str | None
    request_type: RequestType
    submitted_data: dict
    ai_decision: Decision
    ai_confidence: float | None
    evaluation_reasoning: str | None
    policy_refs: list[str] | None
    status: RequestStatus
    sla_deadline: datetime | None
    sla_remaining_minutes: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
