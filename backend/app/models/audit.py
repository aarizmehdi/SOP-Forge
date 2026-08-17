"""
SOP Forge — Audit Log ORM model.
Immutable, append-only audit trail. Corrections are new entries, never overwrites.
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


class AuditLog(Base):
    """
    Immutable audit log entry.
    
    Every decision, action, and override is recorded here.
    This table is APPEND-ONLY — no UPDATE or DELETE operations
    are exposed through any API endpoint.
    """
    __tablename__ = "audit_logs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("sop_requests.id"),
        nullable=True,
        index=True,
    )
    event_type = Column(Enum(AuditEventType), nullable=False, index=True)
    actor_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    actor_role = Column(String(50), nullable=True)

    # Decision details
    decision = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    policy_refs = Column(JSON, nullable=True, default=list)
    evaluation_reasoning = Column(Text, nullable=True)

    # Override specifics
    override_justification = Column(Text, nullable=True)
    previous_decision = Column(String(50), nullable=True)

    # Metadata
    details = Column(JSON, nullable=True, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    request = relationship("SOPRequest", foreign_keys=[request_id])
    actor = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type.value} request={self.request_id}>"

from sqlalchemy import event

@event.listens_for(AuditLog, 'before_update')
def receive_before_update(mapper, connection, target):
    raise NotImplementedError("AuditLog records are immutable and cannot be updated.")

@event.listens_for(AuditLog, 'before_delete')
def receive_before_delete(mapper, connection, target):
    raise NotImplementedError("AuditLog records are immutable and cannot be deleted.")
