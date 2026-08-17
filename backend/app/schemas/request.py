"""
SOP Forge — Request schemas.
Pydantic models for request submission and response.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.request import Decision, RequestStatus, RequestType


# ── Submission ──

class LeaveRequestData(BaseModel):
    """Data schema for a leave request."""
    leave_type: str = Field(..., description="annual, sick, casual, unpaid")
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    reason: str = Field(..., min_length=5, max_length=1000)
    half_day: bool = False
    contact_during_leave: str | None = None


class ReimbursementRequestData(BaseModel):
    """Data schema for a reimbursement request."""
    category: str = Field(..., description="travel, medical, equipment, other")
    amount: float = Field(..., gt=0)
    currency: str = "USD"
    description: str = Field(..., min_length=5, max_length=1000)
    receipt_ref: str | None = None


class ITAccessRequestData(BaseModel):
    """Data schema for an IT access request."""
    system_name: str = Field(..., min_length=2)
    access_level: str = Field(..., description="read, write, admin")
    justification: str = Field(..., min_length=10, max_length=1000)
    duration_days: int | None = None


class RequestSubmission(BaseModel):
    """Incoming request submission from an employee."""
    request_type: RequestType
    submitted_data: dict = Field(..., description="Type-specific request data")


# ── Responses ──

class OverrideEntry(BaseModel):
    """An executive override log entry."""
    by: str
    justification: str
    ts: str


class RequestResponse(BaseModel):
    """Full request response with AI evaluation results."""
    id: UUID
    employee_id: UUID
    request_type: RequestType
    submitted_data: dict
    decision: Decision
    confidence: float | None
    evaluation_reasoning: str | None
    retrieved_policy_refs: list[str] | None
    status: RequestStatus
    sla_deadline: datetime | None
    override_log: list[dict] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequestListItem(BaseModel):
    """Compact request item for list views."""
    id: UUID
    request_type: RequestType
    decision: Decision
    status: RequestStatus
    confidence: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestStatusResponse(BaseModel):
    """Quick status check response."""
    id: UUID
    status: RequestStatus
    decision: Decision
    sla_deadline: datetime | None


class ChatMessage(BaseModel):
    """A single turn in the conversation."""
    role: str = Field(..., description="user | assistant")
    content: str


class AssistantChatRequest(BaseModel):
    """Payload for conversational AI assistant."""
    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list, description="Full conversation transcript for multi-turn memory")


class AssistantChatResponse(BaseModel):
    """Response from conversational AI assistant."""
    response_type: str = Field(..., description="chat | request_processed | policy_info")
    message: str
    request_details: RequestResponse | None = None
    suggested_options: list[str] | None = Field(default=None, description="Optional tappable Smart Chip suggestions for the user")
