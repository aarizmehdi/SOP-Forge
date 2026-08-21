"""
SOP Forge — Audit Log ODM model (Pydantic/MongoDB).
Immutable, append-only audit trail. Corrections are new entries, never overwrites.
"""

import enum
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class AuditEventType(str, enum.Enum):
    """Types of auditable events in the SOP engine."""
    REQUEST_SUBMITTED = "request_submitted"
    POLICY_RETRIEVED = "policy_retrieved"
    VARIABLES_EXTRACTED = "variables_extracted"
    DMN_EVALUATED = "dmn_evaluated"
    AI_EVALUATED = "ai_evaluated"
    AUTO_APPROVED = "auto_approved"
    AUTO_REJECTED = "auto_rejected"
    ESCALATED = "escalated"
    MANAGER_APPROVED = "manager_approved"
    MANAGER_REJECTED = "manager_rejected"
    MORE_INFO_REQUESTED = "more_info_requested"
    EXECUTIVE_OVERRIDE = "executive_override"
    SLA_BREACHED = "sla_breached"
    SOP_UPDATED = "sop_updated"


class AuditLog(BaseModel):
    """
    Immutable audit log entry.
    Every decision, action, and override is recorded here.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str | None = None
    event_type: AuditEventType
    actor_id: str | None = None
    actor_role: str | None = None

    # Decision details
    decision: str | None = None
    confidence: float | None = None
    policy_refs: list | None = Field(default_factory=list)
    evaluation_reasoning: str | None = None

    # Override specifics
    override_justification: str | None = None
    previous_decision: str | None = None

    # Metadata
    details: dict | None = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
