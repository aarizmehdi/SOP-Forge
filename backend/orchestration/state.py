"""
SOP Forge — LangGraph state schema.
Defines the RequestState TypedDict matching the PRD Section 7 state schema.
"""

from typing import TypedDict


class RequestState(TypedDict, total=False):
    """
    Shared state schema for the SOP request evaluation workflow.
    Flows through all LangGraph nodes, accumulating data at each step.
    
    Maps directly to PRD Section 7:
    - request_id, employee_id, request_type, submitted_data
    - retrieved_policy_refs, decision, confidence, status
    - sla_deadline, override_log
    
    Extended with:
    - live_data: fetched from HRMS bridge
    - evaluation_reasoning: concise deterministic evaluation reasons
    - error: any error encountered during processing
    """

    # ── Request Identity ──
    request_id: str
    employee_id: str
    employee_code: str  # Human-readable employee ID (e.g., EMP001)
    request_type: str  # leave | reimbursement | it_access | other
    submitted_data: dict

    # ── RAG Retrieval ──
    retrieved_policy_refs: list[str]
    retrieved_policy_text: str  # Full retrieved policy context
    retrieval_status: str  # match | no_match | degraded | error

    # ── AI Evaluation ──
    decision: str  # approved | rejected | routed | pending
    confidence: float
    evaluation_reasoning: str
    extracted_variables: dict
    evidence_present: bool
    dmn_result: bool

    # ── Lifecycle ──
    status: str  # in_progress | escalated | resolved | overridden
    sla_deadline: str | None
    override_log: list[dict]

    # ── Live Data (from HRMS) ──
    live_data: dict

    # ── Error Handling ──
    error: str | None
