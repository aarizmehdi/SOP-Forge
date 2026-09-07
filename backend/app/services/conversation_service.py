"""Server-owned conversational orchestration with bounded LLM responsibilities."""
import logging
import re
from datetime import date, datetime, timezone, timedelta
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.config import get_settings
from app.models.audit import AuditEventType
from app.models.draft import (
    ConversationDomain,
    ConversationLanguage,
    ConversationTurn,
    ConversationUIState,
    DraftState,
    RequestDraft,
)
from app.models.incident import HRIncident
from app.schemas.request import AssistantChatResponse, TerminalResult
from app.services.audit_service import create_audit_entry
from app.services.candidate_extraction import Candidates, development_candidates, extract_candidates
from app.services.normalization import (
    FIELDS, REQUIRED, normalize_leave_dates, normalize_submission, resolve_date,
    today_local,
)
from app.services.response_composition import (
    EvidenceResponseContext,
    IncompleteResponseContext,
    ResponsePlan,
    TerminalResponseContext,
    compose_response,
)

logger = logging.getLogger(__name__)

DOMAIN_REQUEST_TYPE = {
    ConversationDomain.LEAVE_HR: "leave",
    ConversationDomain.EXPENSES_FINANCE: "reimbursement",
    ConversationDomain.IT_SYSTEM_ACCESS: "it_access",
    ConversationDomain.POLICIES_GENERAL: None,
}
DOMAIN_LABELS = {
    ConversationDomain.LEAVE_HR: "Leave & HR",
    ConversationDomain.EXPENSES_FINANCE: "Expenses & Finance",
    ConversationDomain.IT_SYSTEM_ACCESS: "IT & System Access",
    ConversationDomain.POLICIES_GENERAL: "Policies & General",
}
REQUEST_DOMAIN = {value: key for key, value in DOMAIN_REQUEST_TYPE.items() if value}


def ui_contract(draft):
    if draft.state in {DraftState.CLOSED, DraftState.SUBMITTED}:
        if draft.terminal and draft.terminal.get("outcome") == "incomplete_conversation":
            return ConversationUIState.TERMINAL, ["start_new_conversation"]
        return ConversationUIState.TERMINAL, ["view_request", "start_new_conversation"]
    if draft.state in {DraftState.AWAITING_EVIDENCE, DraftState.ATTACHING_EVIDENCE}:
        return ConversationUIState.EVIDENCE_GATE, ["upload_evidence", "skip_evidence"]
    return ConversationUIState.ACTIVE_CHAT, ["send_message", "use_microphone"]


def response(draft, message, **kwargs):
    ui_state, actions = ui_contract(draft)
    return AssistantChatResponse(
        conversation_id=draft.id,
        draft_state=draft.state.value,
        ui_state=ui_state,
        allowed_actions=actions,
        message=message,
        **kwargs,
    )


def append_turns(draft, user_message, assistant_message):
    if user_message:
        draft.recent_turns.append(ConversationTurn(role="user", content=user_message))
    draft.recent_turns.append(ConversationTurn(role="assistant", content=assistant_message))
    maximum = get_settings().conversation_history_turns
    draft.recent_turns = draft.recent_turns[-maximum:]


async def start_conversation(db, employee, domain, language):
    domain = ConversationDomain(domain)
    language = ConversationLanguage(language)
    draft = RequestDraft(
        employee_id=str(employee.id),
        domain=domain,
        request_type=DOMAIN_REQUEST_TYPE[domain],
        language=language,
    )
    welcome = await compose_response(draft, ResponsePlan(purpose="welcome"))
    append_turns(draft, None, welcome)
    await db.request_drafts.insert_one({"_id": draft.id, **draft.model_dump(mode="json")})
    await create_audit_entry(
        db, request_id=None, event_type=AuditEventType.DRAFT_CREATED,
        actor_id=employee.id, actor_role=employee.role.value,
        details={"draft_id": draft.id, "domain": domain.value, "language": language.value},
    )
    return response(draft, welcome, response_type="conversation_started")


async def load_draft(db, conversation_id, employee_id):
    doc = await db.request_drafts.find_one({"id": str(conversation_id), "employee_id": str(employee_id)})
    if not doc:
        raise HTTPException(404, detail={"code": "conversation_not_found", "message": "Conversation not found."})
    try:
        return RequestDraft.model_validate(doc)
    except ValidationError:
        raise HTTPException(409, detail={
            "code": "conversation_restore_failed",
            "message": "This conversation could not be restored. Please start a new conversation.",
        })


async def save_draft(db, draft):
    revision = draft.revision
    draft.revision += 1
    draft.updated_at = datetime.now(timezone.utc)
    result = await db.request_drafts.update_one(
        {"id": draft.id, "employee_id": draft.employee_id, "revision": revision},
        {"$set": draft.model_dump(mode="json")},
    )
    if not result.matched_count:
        raise HTTPException(409, detail={
            "code": "conversation_conflict",
            "message": "Another action changed this conversation. Please retry.",
        })


def closed_error(draft):
    incomplete = draft.terminal and draft.terminal.get("outcome") == "incomplete_conversation"
    urdu = draft.language == ConversationLanguage.ROMAN_URDU
    raise HTTPException(409, detail={
        "code": "conversation_closed",
        "message": (
            "Yeh conversation band ho chuki hai. Naye kaam ke liye Start New Conversation chunein."
            if urdu else "This conversation is closed. Start a new conversation for another task."
        ),
        "ui_state": ConversationUIState.TERMINAL.value,
        "allowed_actions": ["start_new_conversation"] if incomplete else ["view_request", "start_new_conversation"],
        "terminal": draft.terminal,
    })


def evidence_gate_error(draft):
    urdu = draft.language == ConversationLanguage.ROMAN_URDU
    raise HTTPException(409, detail={
        "code": "evidence_action_required",
        "message": (
            "Aage barhne ke liye Upload Evidence ya Skip Evidence chunein."
            if urdu else "Choose Upload Evidence or Skip Evidence to continue."
        ),
        "ui_state": ConversationUIState.EVIDENCE_GATE.value,
        "allowed_actions": ["upload_evidence", "skip_evidence"],
    })


async def record_incident(db, draft, employee, candidate, message):
    threshold = get_settings().incident_confidence_threshold
    if not candidate.governance_signal or candidate.governance_confidence < threshold:
        return
    incident = HRIncident(
        employee_id=str(employee.id),
        incident_type=candidate.governance_signal,
        message=message,
        ai_reasoning="Structured conversational governance signal met the configured threshold.",
        confidence=candidate.governance_confidence,
        conversation_id=draft.id,
    )
    await db.hr_incidents.insert_one({"_id": incident.id, **incident.model_dump(mode="json")})


def merge_candidates(draft, candidate, message=""):
    """Apply only in-domain, allow-listed candidate facts to the authoritative draft."""
    expected = DOMAIN_REQUEST_TYPE[draft.domain]
    if expected is None or candidate.intent in {"policy", "balance", "help", "general"}:
        return
    if candidate.request_type and candidate.request_type != expected:
        return
    values = {**candidate.recovered_facts, **candidate.facts, **candidate.corrections}
    rejected_shapes = [
        key for key, value in values.items()
        if key in FIELDS[expected] and not isinstance(value, (str, int, float, bool))
    ]
    values = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in values.items()
        if key in FIELDS[expected]
        and isinstance(value, (str, int, float, bool))
        and value not in (None, "")
    }
    if expected == "leave":
        inferred = candidate.inferred_leave_category
        if (
            "leave_type" not in values
            and inferred
            and candidate.inference_confidence >= get_settings().category_inference_confidence_threshold
        ):
            values["leave_type"] = inferred
        if values.get("leave_type") not in {None, "annual", "sick", "casual", "unpaid"}:
            values.pop("leave_type", None)
            rejected_shapes.append("leave_type")
        if "duration_days" in values and "end_date" not in values:
            draft.fields.pop("end_date", None)
            draft.date_basis = "duration"
        elif "end_date" in values and "duration_days" not in values:
            draft.fields.pop("duration_days", None)
            draft.date_basis = "range"
        elif "start_date" in values and "end_date" not in values:
            if draft.date_basis == "duration":
                draft.fields.pop("end_date", None)
            else:
                draft.fields.pop("duration_days", None)
        if "end_date" in values and "duration_days" in values:
            draft.date_basis = "range"
    draft.fields.update(values)
    explicit_ambiguities = [
        name for name in candidate.ambiguities
        if name in FIELDS[expected]
        and (
            name in values
            or (name in {"start_date", "end_date"} and bool(re.search(
                r"(?<!\d)\d{1,2}/\d{1,2}(?:/\d{2,4})?(?!\d)", message,
            )))
        )
    ]
    draft.ambiguous_fields = list(dict.fromkeys(explicit_ambiguities + rejected_shapes))


def plan(draft):
    """Return a safe response descriptor; never expose internal identifiers to the employee."""
    kind = draft.request_type
    if not kind:
        return "GENERAL", None
    if draft.ambiguous_fields:
        if draft.ambiguous_fields[0] in {"start_date", "end_date"}:
            return "AMBIGUOUS_DATE", None
        return "ASK", draft.ambiguous_fields[0]
    if kind == "leave":
        raw_start = draft.fields.get("start_date")
        if raw_start:
            try:
                if resolve_date(raw_start) < today_local():
                    draft.fields.pop("start_date", None)
                    draft.fields.pop("end_date", None)
                    draft.ambiguous_fields = []
                    draft.missing_fields = ["start_date"]
                    return "PAST_DATE", None
            except (ValueError, TypeError, OverflowError):
                pass
        try:
            draft.fields = normalize_leave_dates(draft.fields)
        except (ValueError, TypeError, OverflowError) as exc:
            code = str(exc)
            if code == "ambiguous_numeric_date":
                return "AMBIGUOUS_DATE", None
            if code == "unrecognized_date":
                return "INVALID_DATE", None
            return "DATE_CONFLICT", None
        start = draft.fields.get("start_date")
        if start and date.fromisoformat(start) < today_local():
            draft.fields.pop("start_date", None)
            draft.fields.pop("end_date", None)
            draft.ambiguous_fields = []
            draft.missing_fields = ["start_date"]
            return "PAST_DATE", None
    draft.missing_fields = [field for field in REQUIRED[kind] if draft.fields.get(field) in (None, "")]
    duration = draft.fields.get("duration_days")
    draft.evidence_required = bool(
        kind == "leave"
        and draft.fields.get("leave_type") == "sick"
        and isinstance(duration, (int, float))
        and duration >= get_settings().sick_evidence_threshold_days
    )
    if draft.missing_fields:
        draft.state = DraftState.COLLECTING
        return "ASK", draft.missing_fields[0]
    try:
        draft.fields = normalize_submission(kind, draft.fields)
    except ValidationError as exc:
        field = str(exc.errors()[0]["loc"][0])
        draft.missing_fields = [field]
        return "ASK", field
    except (ValueError, TypeError):
        return "HELP", None
    if draft.evidence_required and not draft.evidence_present:
        draft.state = DraftState.AWAITING_EVIDENCE
        return "EVIDENCE_GATE", None
    return "SUBMIT", None


def question_context(
    draft, field, *, attempt=1, employee_message=None,
    reference_acknowledged=False, purpose="ask",
):
    """Describe the unresolved concept; the LLM chooses the ordinary wording."""
    concepts = {
        "leave_type": (
            "Could you describe what the time off is for so I can use the right leave category?",
            "Meherbani karke batayein chutti kis wajah se chahiye taake sahi category use ho sake.",
            "The governed request needs one allowed leave category.",
            "For example, your own health, planned vacation, an urgent family matter, or unpaid time.",
        ),
        "start_date": (
            "Could you please tell me when you would like the leave to start?",
            "Meherbani karke batayein chutti kab se shuru karni hai.",
            "A start date is needed to validate the request and calculate working days.",
            "For example, today, tomorrow, or next Monday.",
        ),
        "duration_days": (
            "Could you please tell me how many working days you expect to be away?",
            "Meherbani karke batayein kitne working days ki chutti chahiye.",
            "The working-day duration is needed for policy and balance checks.",
            "For example, 3 working days; an end date can be given instead.",
        ),
        "reason": (
            "Could you briefly explain the reason for the time off?",
            "Meherbani karke chutti ki wajah mukhtasar taur par batayein.",
            "A short employee-provided reason is required for the request.",
            "A brief explanation in your own words is enough.",
        ),
        "category": (
            "Could you describe the kind of expense you are claiming?",
            "Meherbani karke batayein yeh kis qisam ka expense hai.",
            "The expense category determines the applicable reimbursement rules.",
            "For example, travel, medical, equipment, or another expense.",
        ),
        "amount": (
            "Could you please tell me the amount you are claiming in USD?",
            "Meherbani karke USD mein claim ki raqam batayein.",
            "The amount is required for deterministic reimbursement checks.",
            "For example, USD 60.",
        ),
        "description": (
            "Could you briefly explain what the expense was for?",
            "Meherbani karke mukhtasar batayein expense kis liye hua tha.",
            "A short business description is required for the claim.",
            "For example, a train ride to the client office.",
        ),
        "system_name": (
            "Could you please tell me which system you need access to?",
            "Meherbani karke batayein kis system ka access chahiye.",
            "The governed access request must identify its target system.",
            "For example, GitHub, Jira, or another named system.",
        ),
        "access_level": (
            "Could you please tell me which level of access you need?",
            "Meherbani karke batayein kis level ka access chahiye.",
            "The access level is required for the security review path.",
            "The allowed levels are read, write, and admin.",
        ),
        "justification": (
            "Could you briefly explain what you need this access for?",
            "Meherbani karke mukhtasar batayein yeh access kis kaam ke liye chahiye.",
            "A work-related justification is required for the access request.",
            "For example, the task or issue the access will let you complete.",
        ),
    }
    question, urdu, why_needed, example = concepts.get(field, (
        "Could you please share the remaining detail?",
        "Meherbani karke baqi detail batayein.",
        "The request cannot continue safely without this information.",
        "A short answer in your own words is enough.",
    ))
    return ResponsePlan(
        purpose=purpose, expected_concept=field,
        fallback_question=question, fallback_urdu_question=urdu,
        known_context=dict(draft.fields), why_needed=why_needed, example=example,
        clarification_attempt=attempt, prior_question=draft.last_question,
        employee_message=employee_message,
        reference_acknowledged=reference_acknowledged,
    )


def next_clarification_attempt(draft, concept):
    previous = draft.clarification_attempts.get(concept, 0)
    if draft.last_question_field == concept and previous >= 3:
        return None
    attempt = previous + 1 if draft.last_question_field == concept else 1
    draft.clarification_attempts[concept] = attempt
    return attempt


async def policy_answer(db, draft, message):
    from app.services.policy_retrieval import PolicyRetrievalStatus, get_policy_retrieval_adapter
    retrieval = await get_policy_retrieval_adapter().retrieve(
        db, message, top_k=3, category=draft.request_type or None
    )
    if retrieval.status in {PolicyRetrievalStatus.MATCH, PolicyRetrievalStatus.DEGRADED}:
        answer = "\n\n".join(chunk["chunk_text"] for chunk in retrieval.chunks)
    elif retrieval.status == PolicyRetrievalStatus.NO_MATCH:
        answer = "I couldn't find a matching company policy. Please check with your manager."
    else:
        answer = "Policy guidance is unavailable right now. Please try again or check with your manager."
    return answer, retrieval.status.value, retrieval.chunks


async def category_policy_context(db):
    from app.services.policy_retrieval import PolicyRetrievalStatus, get_policy_retrieval_adapter
    retrieval = await get_policy_retrieval_adapter().retrieve(
        db,
        "leave category definitions sick annual casual unpaid illness vacation personal family emergency",
        top_k=3,
        category="leave",
    )
    return retrieval.chunks if retrieval.status in {
        PolicyRetrievalStatus.MATCH, PolicyRetrievalStatus.DEGRADED
    } else []


async def turn_policy_context(db, draft, message):
    """Supply bounded active-policy context for semantic interpretation."""
    if draft.domain == ConversationDomain.LEAVE_HR and not draft.fields.get("leave_type"):
        return await category_policy_context(db)
    if not draft.request_type:
        return []
    from app.services.policy_retrieval import PolicyRetrievalStatus, get_policy_retrieval_adapter
    retrieval = await get_policy_retrieval_adapter().retrieve(
        db,
        f"{message} Known request facts: {draft.fields}. Missing: {draft.missing_fields}",
        top_k=2,
        category=draft.request_type,
    )
    return retrieval.chunks if retrieval.status in {
        PolicyRetrievalStatus.MATCH, PolicyRetrievalStatus.DEGRADED,
    } else []


def repair_candidate(message, draft, candidate):
    """Supplement provider output with non-conflicting, bounded explicit facts."""
    fallback = development_candidates(message, draft)
    facts = {**fallback.facts, **candidate.facts}
    recovered_facts = {**fallback.recovered_facts, **candidate.recovered_facts}
    corrections = {**fallback.corrections, **candidate.corrections}
    for corrected_field in candidate.corrections:
        facts.pop(corrected_field, None)
    use_fallback_intent = (
        fallback.intent in {"policy", "balance", "help"}
        or (
            candidate.intent == "general" and fallback.intent == "request"
            and bool(fallback.facts or draft.last_question_field)
        )
    )
    fallback_inference = (
        fallback.inferred_leave_category
        if not candidate.inferred_leave_category else candidate.inferred_leave_category
    )
    inference_confidence = (
        fallback.inference_confidence
        if not candidate.inferred_leave_category else candidate.inference_confidence
    )
    return candidate.model_copy(update={
        "intent": fallback.intent if use_fallback_intent else candidate.intent,
        "request_type": candidate.request_type or fallback.request_type,
        "requested_domain": candidate.requested_domain or fallback.requested_domain,
        "facts": facts,
        "recovered_facts": recovered_facts,
        "corrections": corrections,
        "field_sources": {**fallback.field_sources, **candidate.field_sources},
        "inferred_leave_category": fallback_inference,
        "inference_confidence": inference_confidence,
        "language_signal": candidate.language_signal or fallback.language_signal,
        "language_confidence": max(candidate.language_confidence, fallback.language_confidence),
        "governance_signal": candidate.governance_signal or fallback.governance_signal,
        "governance_confidence": max(candidate.governance_confidence, fallback.governance_confidence),
        "ambiguities": list(dict.fromkeys([*candidate.ambiguities, *fallback.ambiguities])),
        "references_prior_context": candidate.references_prior_context or fallback.references_prior_context,
    })


def recover_prior_reference(draft, candidate):
    """Recover the requested concept from bounded, server-owned employee turns."""
    if not candidate.references_prior_context or candidate.recovered_facts:
        return candidate
    concept = draft.last_question_field or (draft.missing_fields[0] if draft.missing_fields else None)
    expected = draft.request_type
    if not concept or not expected or concept not in FIELDS[expected]:
        return candidate
    recovered = None
    for turn in draft.recent_turns:
        if turn.role != "user":
            continue
        prior = development_candidates(turn.content, draft)
        values = {**prior.facts, **prior.corrections}
        if concept == "leave_type" and concept not in values and (
            prior.inferred_leave_category
            and prior.inference_confidence >= get_settings().category_inference_confidence_threshold
        ):
            values[concept] = prior.inferred_leave_category
        if values.get(concept) not in (None, ""):
            recovered = values[concept]
    if recovered is None:
        return candidate
    sources = dict(candidate.field_sources)
    sources[concept] = "recovered"
    return candidate.model_copy(update={
        "recovered_facts": {concept: recovered},
        "field_sources": sources,
    })


def enforce_date_ambiguity(message, draft, candidate):
    """Numeric slash dates remain ambiguous unless a future locale policy resolves them."""
    if draft.domain != ConversationDomain.LEAVE_HR:
        return candidate
    if not re.search(r"(?<!\d)\d{1,2}/\d{1,2}(?:/\d{2,4})?(?!\d)", message):
        return candidate
    facts, corrections = dict(candidate.facts), dict(candidate.corrections)
    for field in ("start_date", "end_date"):
        facts.pop(field, None)
        corrections.pop(field, None)
    return candidate.model_copy(update={
        "facts": facts,
        "corrections": corrections,
        "ambiguities": list(dict.fromkeys([*candidate.ambiguities, "start_date"])),
    })


def preserve_last_required_explanation(message, draft, candidate):
    """Retain a substantive free-form answer to the server's explanation question."""
    field = {
        "leave": "reason", "reimbursement": "description", "it_access": "justification",
    }.get(draft.request_type)
    if (
        not field or candidate.references_prior_context or draft.fields.get(field)
        or field in candidate.facts or field in candidate.recovered_facts
        or field in candidate.corrections
    ):
        return candidate
    was_requested = draft.last_question_field == field or draft.missing_fields == [field]
    text = message.strip()
    if (
        not was_requested or candidate.intent != "request" or "?" in text
        or len(re.findall(r"\b\w+\b", text)) < 2
    ):
        return candidate
    facts = dict(candidate.facts)
    facts[field] = text
    sources = dict(candidate.field_sources)
    sources[field] = "explicit"
    return candidate.model_copy(update={"facts": facts, "field_sources": sources})


async def balance_answer(employee, language):
    from app.integrations.hrms_mock import get_hrms
    try:
        balance = await get_hrms().get_leave_balance(employee.employee_id)
        if not balance.get("found"):
            raise ValueError("missing")
        values = ", ".join(
            f"{name}: {data['remaining']:g} {'din' if language == ConversationLanguage.ROMAN_URDU else 'days'}"
            for name, data in balance["balances"].items()
        )
        return (
            f"Aapki available leave yeh hai: {values}."
            if language == ConversationLanguage.ROMAN_URDU
            else f"Your available leave is {values}."
        )
    except Exception:
        return (
            "Aapki leave balance abhi hasil nahi ho saki. Dobara koshish karein."
            if language == ConversationLanguage.ROMAN_URDU
            else "I couldn't retrieve your leave balance right now. Please try again."
        )


async def save_conversational_response(db, draft, user_message, message, **kwargs):
    append_turns(draft, user_message, message)
    await save_draft(db, draft)
    return response(draft, message, **kwargs)


async def close_incomplete_conversation(db, draft, user_message, concept):
    """Close after three unsuccessful clarifications without creating a request."""
    terminal = TerminalResult(
        outcome="incomplete_conversation", missing_concept=concept,
    )
    draft.state = DraftState.CLOSED
    draft.terminal = terminal.model_dump(mode="json")
    message = await compose_response(draft, ResponsePlan(
        purpose="incomplete_conversation",
        employee_message=user_message,
        known_context=dict(draft.fields),
        incomplete=IncompleteResponseContext(missing_concept=concept),
    ))
    append_turns(draft, user_message, message)
    await save_draft(db, draft)
    return response(
        draft, message, response_type="conversation_incomplete", terminal=terminal,
    )


def terminal_from_request(request):
    destination = None
    if request.status.value == "escalated" or request.decision.value == "routed":
        destination = "manager_review"
    return TerminalResult(
        request_id=request.id,
        status=request.status,
        decision=request.decision,
        destination=destination,
    )


def status_message(request, language="en"):
    """Compatibility helper for non-conversational status surfaces."""
    if request.status.value == "escalated" or request.decision.value == "routed":
        return "Aapki request manager review ke liye bhej di hai. Abhi approve nahi hui." if language == "roman_urdu" else "Your request has been sent for manager review. It is not approved yet."
    if request.decision.value == "approved":
        return "Aapki request approve ho gayi hai." if language == "roman_urdu" else "Your request has been approved."
    if request.decision.value == "rejected":
        return "Aapki request reject ho gayi hai." if language == "roman_urdu" else "Your request has been rejected."
    return "Aapki request process ho rahi hai." if language == "roman_urdu" else "Your request is being processed."


async def processed_response(db, draft, *, compose=True):
    from app.services.request_service import get_request_by_id
    request = await get_request_by_id(db, draft.request_id)
    if request is None:
        raise HTTPException(409, detail={"code": "submission_incomplete", "message": "Submission is still being saved."})
    request.confidence = None
    request.evaluation_reasoning = None
    request.retrieved_policy_refs = []
    terminal = terminal_from_request(request)
    draft.terminal = terminal.model_dump(mode="json")
    terminal_plan = ResponsePlan(purpose="terminal", terminal=TerminalResponseContext(
        status=terminal.status.value,
        decision=terminal.decision.value,
        destination=terminal.destination,
    ))
    message = await compose_response(draft, terminal_plan) if compose else status_message(request, draft.language)
    return response(
        draft, message, response_type="request_processed",
        request_details=request, terminal=terminal,
    )


async def run_preflight(draft, employee):
    from orchestration.nodes.intake import intake
    from orchestration.nodes.retrieve_policy import retrieve_policy
    from orchestration.nodes.dmn_rule_engine import dmn_rule_engine
    state = {
        "request_id": draft.id,
        "employee_id": employee.id,
        "employee_code": employee.employee_id,
        "request_type": draft.request_type,
        "submitted_data": draft.fields,
    }
    try:
        state.update(await intake(state))
        state.update(await retrieve_policy(state))
        state["evidence_present"] = draft.evidence_present
        outcome = await dmn_rule_engine(state)
        draft.preflight = {
            "decision": outcome["decision"],
            "reason": outcome["evaluation_reasoning"],
            "policy_refs": state.get("retrieved_policy_refs", []),
        }
    except Exception:
        draft.preflight = {"decision": "routed", "reason": "preflight_unavailable"}


async def finalize_draft(db, employee, draft, *, evidence_skipped=False):
    """Persist one complete governed request, execute DMN, and close its conversation."""
    draft.evidence_present = bool(await db.evidence.find_one({"draft_id": draft.id}))
    if draft.evidence_required and not draft.evidence_present and not evidence_skipped:
        draft.state = DraftState.AWAITING_EVIDENCE
        await save_draft(db, draft)
        evidence_gate_error(draft)
    if evidence_skipped:
        draft.evidence_choice = "continue_without"
    await run_preflight(draft, employee)
    draft.state, draft.request_id = DraftState.SUBMITTING, str(uuid4())
    await save_draft(db, draft)
    from app.services.request_service import submit_request
    from app.api.request import _run_ai_workflow
    try:
        await submit_request(
            db, employee=employee, request_type=draft.request_type,
            submitted_data=draft.fields, request_id=draft.request_id,
        )
        await db.evidence.update_many(
            {"draft_id": draft.id}, {"$set": {"request_id": draft.request_id}}
        )
        attachments = await db.evidence.find({"request_id": draft.request_id}).to_list(length=100)
        from app.api.evidence import public_metadata
        await db.sop_requests.update_one({"id": draft.request_id}, {"$set": {
            "has_evidence": bool(attachments),
            "evidence_list": [public_metadata(item) for item in attachments],
        }})
        if draft.evidence_required and not draft.evidence_present:
            await create_audit_entry(
                db, request_id=draft.request_id, event_type=AuditEventType.EVIDENCE_OMITTED,
                actor_id=employee.id, actor_role=employee.role.value,
                details={"reason": "required_supporting_evidence_not_provided"},
            )
        await _run_ai_workflow(
            draft.request_id, employee.id, employee.employee_id,
            draft.request_type, draft.fields,
        )
    except Exception:
        logger.exception("Conversation submission failed")
        existing = await db.sop_requests.find_one({"id": draft.request_id})
        if not existing:
            draft.state, draft.request_id = DraftState.COLLECTING, None
            await save_draft(db, draft)
            raise HTTPException(503, detail={
                "code": "submission_failed",
                "message": "Your request could not be saved. Please retry.",
            })
        await db.sop_requests.update_one(
            {"id": draft.request_id, "status": "in_progress"},
            {"$set": {
                "status": "escalated", "decision": "routed",
                "evaluation_reasoning": "Submission workflow failed; human review required.",
            }},
        )
        await create_audit_entry(
            db, request_id=draft.request_id, event_type=AuditEventType.WORKFLOW_FAILED,
            actor_id="system", actor_role="system", details={"reason": "submission_failure"},
        )
    draft.state = DraftState.CLOSED
    result = await processed_response(db, draft)
    append_turns(draft, None, result.message)
    await save_draft(db, draft)
    return result.model_copy(update={"draft_state": draft.state.value})


async def skip_evidence(db, employee, conversation_id):
    draft = await load_draft(db, conversation_id, employee.id)
    if draft.state in {DraftState.CLOSED, DraftState.SUBMITTED}:
        closed_error(draft)
    if draft.state != DraftState.AWAITING_EVIDENCE:
        raise HTTPException(409, detail={
            "code": "evidence_gate_inactive",
            "message": "This conversation is not waiting for an evidence choice.",
        })
    return await finalize_draft(db, employee, draft, evidence_skipped=True)


async def handle_message(db, employee, payload):
    draft = await load_draft(db, payload.conversation_id, employee.id)
    if draft.state in {DraftState.CLOSED, DraftState.SUBMITTED}:
        closed_error(draft)
    if draft.state in {DraftState.AWAITING_EVIDENCE, DraftState.ATTACHING_EVIDENCE}:
        evidence_gate_error(draft)
    if draft.state == DraftState.SUBMITTING:
        stale = datetime.now(timezone.utc) - draft.updated_at > timedelta(minutes=5)
        existing = await db.sop_requests.find_one({"id": draft.request_id})
        if stale and existing:
            await db.sop_requests.update_one({"id": draft.request_id}, {"$set": {
                "status": "escalated", "decision": "routed",
                "evaluation_reasoning": "Interrupted submission recovered for human review.",
            }})
            draft.state = DraftState.CLOSED
            result = await processed_response(db, draft)
            append_turns(draft, None, result.message)
            await save_draft(db, draft)
            closed_error(draft)
        raise HTTPException(409, detail={
            "code": "submission_in_progress",
            "message": "This request is being submitted. Please wait.",
        })

    message = payload.message.strip()
    policy_chunks = await turn_policy_context(db, draft, message)
    try:
        candidate = await extract_candidates(message, draft, policy_chunks)
    except Exception:
        logger.warning("Turn understanding unavailable or invalid; using bounded fallback", exc_info=False)
        candidate = development_candidates(message, draft)
    else:
        candidate = repair_candidate(message, draft, candidate)
    candidate = recover_prior_reference(draft, candidate)
    candidate = enforce_date_ambiguity(message, draft, candidate)
    candidate = preserve_last_required_explanation(message, draft, candidate)
    await record_incident(db, draft, employee, candidate, message)

    if candidate.intent in {"policy", "request_policy"} or draft.domain == ConversationDomain.POLICIES_GENERAL:
        if candidate.intent == "request_policy":
            merge_candidates(draft, candidate, message)
        answer, retrieval_mode, _ = await policy_answer(db, draft, message)
        resume = draft.ambiguous_fields[0] if draft.ambiguous_fields else (
            draft.missing_fields[0] if draft.missing_fields else None
        )
        response_plan = question_context(
            draft, resume, employee_message=message, purpose="policy",
        ) if resume else ResponsePlan(purpose="policy", employee_message=message)
        response_plan = response_plan.model_copy(update={
            "answer": answer, "draft_preserved": bool(draft.fields),
            "resume_concept": resume,
        })
        composed = await compose_response(draft, response_plan)
        return await save_conversational_response(
            db, draft, message, composed, response_type="policy_info",
            retrieval_mode=retrieval_mode,
        )
    if candidate.intent == "balance":
        answer = await balance_answer(employee, draft.language)
        resume = draft.ambiguous_fields[0] if draft.ambiguous_fields else (
            draft.missing_fields[0] if draft.missing_fields else None
        )
        response_plan = question_context(
            draft, resume, employee_message=message, purpose="balance",
        ) if resume else ResponsePlan(purpose="balance", employee_message=message)
        response_plan = response_plan.model_copy(update={
            "answer": answer, "draft_preserved": bool(draft.fields),
            "resume_concept": resume,
        })
        composed = await compose_response(draft, response_plan)
        return await save_conversational_response(
            db, draft, message, composed, response_type="policy_info"
        )
    if candidate.intent == "help":
        field = draft.missing_fields[0] if draft.missing_fields else None
        if field:
            attempt = next_clarification_attempt(draft, field)
            if attempt is None:
                return await close_incomplete_conversation(db, draft, message, field)
            response_plan = question_context(
                draft, field, attempt=attempt, employee_message=message,
                reference_acknowledged=candidate.references_prior_context,
                purpose="help",
            )
        else:
            response_plan = ResponsePlan(purpose="help", employee_message=message)
        response_plan = response_plan.model_copy(update={
            "guidance": "I understand the confusion. I will summarize what is already known and explain the one detail still needed.",
            "urdu_guidance": "Main aapki pareshani samajhta hoon. Jo maloomat maujood hai usay rakh kar sirf baqi zaroori detail wazeh karta hoon.",
        })
        composed = await compose_response(draft, response_plan)
        if field:
            draft.last_question = composed
            draft.last_question_field = field
        return await save_conversational_response(
            db, draft, message, composed, response_type="chat"
        )

    expected_domain = REQUEST_DOMAIN.get(candidate.request_type)
    if expected_domain and expected_domain != draft.domain:
        composed = await compose_response(draft, ResponsePlan(
            purpose="out_of_domain", current_domain=DOMAIN_LABELS[draft.domain],
            requested_domain=DOMAIN_LABELS[expected_domain], employee_message=message,
        ))
        return await save_conversational_response(
            db, draft, message, composed, response_type="chat"
        )

    merge_candidates(draft, candidate, message)
    action, detail = plan(draft)
    if action == "SUBMIT":
        return await finalize_draft(db, employee, draft)
    purpose = {
        "ASK": "ask",
        "AMBIGUOUS_DATE": "ambiguous_date",
        "INVALID_DATE": "invalid_date",
        "PAST_DATE": "past_date",
        "DATE_CONFLICT": "date_conflict",
        "EVIDENCE_GATE": "evidence_gate",
        "HELP": "help",
        "GENERAL": "general",
    }[action]
    clarification_concept = detail if action == "ASK" else (
        "start_date" if action in {
            "AMBIGUOUS_DATE", "INVALID_DATE", "PAST_DATE", "DATE_CONFLICT",
        } else None
    )
    if clarification_concept:
        attempt = next_clarification_attempt(draft, clarification_concept)
        if attempt is None:
            return await close_incomplete_conversation(
                db, draft, message, clarification_concept,
            )
    else:
        attempt = None
    reference_acknowledged = bool(
        candidate.references_prior_context and (candidate.recovered_facts or draft.fields)
    )
    if action == "ASK":
        response_plan = question_context(
            draft, detail, attempt=attempt, employee_message=message,
            reference_acknowledged=reference_acknowledged,
        )
    elif action == "EVIDENCE_GATE":
        response_plan = ResponsePlan(purpose=purpose, evidence=EvidenceResponseContext(
            category=draft.fields["leave_type"], duration_days=draft.fields["duration_days"],
        ))
    else:
        response_plan = ResponsePlan(
            purpose=purpose, expected_concept=clarification_concept,
            known_context=dict(draft.fields), clarification_attempt=attempt,
            prior_question=draft.last_question, employee_message=message,
            reference_acknowledged=reference_acknowledged,
        )
    composed = await compose_response(draft, response_plan)
    if action in {"ASK", "AMBIGUOUS_DATE", "INVALID_DATE", "PAST_DATE", "DATE_CONFLICT"}:
        draft.last_question = composed
        draft.last_question_field = detail if action == "ASK" else "start_date"
    return await save_conversational_response(
        db, draft, message, composed, response_type="chat",
        upload_available=action == "EVIDENCE_GATE",
    )
