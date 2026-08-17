"""
SOP Forge — Audit schemas.
Pydantic models for the immutable audit trail viewer.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.audit import AuditEventType


class AuditLogResponse(BaseModel):
    """A single audit log entry."""
    id: UUID
    request_id: UUID | None
    event_type: AuditEventType
    actor_id: UUID | None
    actor_name: str | None = None
    actor_role: str | None
    decision: str | None
    confidence: float | None
    policy_refs: list[str] | None
    evaluation_reasoning: str | None
    override_justification: str | None
    previous_decision: str | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogQuery(BaseModel):
    """Query parameters for filtering audit logs."""
    request_id: UUID | None = None
    event_type: AuditEventType | None = None
    actor_id: UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class AuditSummary(BaseModel):
    """Summary statistics for audit logs."""
    total_entries: int
    auto_approved: int
    auto_rejected: int
    escalated: int
    overridden: int
    sla_breaches: int
