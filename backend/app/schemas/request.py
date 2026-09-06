"""
SOP Forge — Request schemas.
Pydantic models for request submission and response.
"""

from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.request import Decision, RequestStatus, RequestType


# ── Submission ──

class LeaveRequestData(BaseModel):
    """Data schema for a leave request."""
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    leave_type: Literal["annual", "sick", "casual", "unpaid"]
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    reason: str = Field(..., min_length=2, max_length=1000)
    half_day: bool = False
    duration_days: float = Field(..., gt=0, le=366, allow_inf_nan=False)
    contact_during_leave: str | None = None


class ReimbursementRequestData(BaseModel):
    """Data schema for a reimbursement request."""
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    category: Literal["travel", "medical", "equipment", "other"]
    amount: float = Field(..., gt=0, allow_inf_nan=False)
    currency: Literal["USD"] = "USD"
    description: str = Field(..., min_length=5, max_length=1000)
    receipt_ref: str | None = None


class ITAccessRequestData(BaseModel):
    """Data schema for an IT access request."""
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    system_name: str = Field(..., min_length=2, max_length=200)
    access_level: Literal["read", "write", "admin"]
    justification: str = Field(..., min_length=10, max_length=1000)
    duration_days: int | None = Field(default=None, gt=0)


class RequestSubmission(BaseModel):
    """Incoming request submission from an employee."""
    request_type: RequestType
    submitted_data: dict = Field(..., description="Type-specific request data")

    @model_validator(mode="after")
    def validate_data(self):
        from app.services.normalization import normalize_submission
        self.submitted_data = normalize_submission(self.request_type.value, self.submitted_data)
        return self


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
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    history: list[ChatMessage] = Field(default_factory=list, description="Full conversation transcript for multi-turn memory")


class AssistantChatResponse(BaseModel):
    """Response from conversational AI assistant."""
    response_type: str = Field(..., description="chat | request_processed | policy_info")
    message: str
    request_details: RequestResponse | None = None
    conversation_id: str | None = None
    draft_state: str | None = None
    upload_available: bool = False
    retrieval_mode: str | None = None
