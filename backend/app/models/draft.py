"""Server-owned conversation state; never deserialize this from a browser payload."""
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from typing import Literal

from pydantic import BaseModel, Field


class DraftState(str, Enum):
    COLLECTING = "collecting"
    AWAITING_EVIDENCE = "awaiting_evidence"
    ATTACHING_EVIDENCE = "attaching_evidence"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    CLOSED = "closed"


class ConversationDomain(str, Enum):
    LEAVE_HR = "leave_hr"
    EXPENSES_FINANCE = "expenses_finance"
    IT_SYSTEM_ACCESS = "it_system_access"
    POLICIES_GENERAL = "policies_general"


class ConversationLanguage(str, Enum):
    ENGLISH = "en"
    ROMAN_URDU = "roman_urdu"


class ConversationUIState(str, Enum):
    ACTIVE_CHAT = "ACTIVE_CHAT"
    EVIDENCE_GATE = "EVIDENCE_GATE"
    TERMINAL = "TERMINAL"


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class RequestDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    employee_id: str
    domain: ConversationDomain = ConversationDomain.LEAVE_HR
    request_type: Literal["leave", "reimbursement", "it_access"] | None = None
    fields: dict = Field(default_factory=dict)
    date_basis: str | None = None
    evidence_required: bool = False
    evidence_present: bool = False
    evidence_choice: Literal["undecided", "upload", "continue_without"] = "undecided"
    missing_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[str] = Field(default_factory=list)
    state: DraftState = DraftState.COLLECTING
    language: ConversationLanguage = ConversationLanguage.ENGLISH
    revision: int = 0
    request_id: str | None = None
    preflight: dict = Field(default_factory=dict)
    last_question: str | None = None
    last_question_field: str | None = None
    clarification_attempts: dict[str, int] = Field(default_factory=dict)
    recent_turns: list[ConversationTurn] = Field(default_factory=list)
    language_confidence: float = Field(default=1.0, deprecated=True)
    terminal: dict | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
