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


async def start_conversation(db, employee, domain):
    domain = ConversationDomain(domain)
    draft = RequestDraft(
        employee_id=str(employee.id),
        domain=domain,
        request_type=DOMAIN_REQUEST_TYPE[domain],
    )
    welcome = await compose_response(draft, ResponsePlan(purpose="welcome"))
    append_turns(draft, None, welcome)
    await db.request_drafts.insert_one({"_id": draft.id, **draft.model_dump(mode="json")})
    await create_audit_entry(
        db, request_id=None, event_type=AuditEventType.DRAFT_CREATED,
        actor_id=employee.id, actor_role=employee.role.value,
        details={"draft_id": draft.id, "domain": domain.value},
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
    raise HTTPException(409, detail={
        "code": "conversation_closed",
        "message": "This conversation is complete. Start a new conversation for another task.",
        "ui_state": ConversationUIState.TERMINAL.value,
        "allowed_actions": ["view_request", "start_new_conversation"],
        "terminal": draft.terminal,
    })


def evidence_gate_error(draft):
    raise HTTPException(409, detail={
        "code": "evidence_action_required",
        "message": "Choose Upload Evidence or Skip Evidence to continue.",
        "ui_state": ConversationUIState.EVIDENCE_GATE.value,
        "allowed_actions": ["upload_evidence", "skip_evidence"],
    })


def update_language(draft, candidate):
    legacy_language = candidate.__dict__.get("language")
    signal = candidate.language_signal or legacy_language
    confidence = candidate.language_confidence or (0.9 if legacy_language else 0)
    if signal == "mixed":
        return
    if not signal:
        return
    if draft.language_confidence == 0 or signal == draft.language:
        if confidence >= 0.75:
            draft.language, draft.language_confidence = signal, confidence
    elif confidence >= 0.92:
        draft.language, draft.language_confidence = signal, confidence


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
    update_language(draft, candidate)
    expected = DOMAIN_REQUEST_TYPE[draft.domain]
    if expected is None or candidate.intent in {"policy", "balance", "help", "general"}:
        return
    if candidate.request_type and candidate.request_type != expected:
        return
    values = {**candidate.facts, **candidate.corrections}
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


def question_context(draft, field):
    questions = {
        "leave_type": ("Would this time off be for illness, vacation, a personal or family matter, or unpaid leave?",
                       "Yeh chutti bemari, vacation, personal ya family matter, ya unpaid leave ke liye hai?"),
        "start_date": ("When would you like the leave to begin?", "Chutti kab se shuru karni hai?"),
        "duration_days": ("How much time off do you need?", "Kitne din ki chutti chahiye?"),
        "reason": ("What is the reason for the time off?", "Chutti ki wajah kya hai?"),
        "category": ("What type of expense was this, such as travel, medical, or equipment?",
                     "Yeh kis qisam ka expense tha, jaise travel, medical ya equipment?"),
        "amount": ("What amount are you claiming in USD?", "USD mein kitni raqam claim karni hai?"),
        "description": ("What was the expense for?", "Yeh expense kis liye tha?"),
        "system_name": ("Which system do you need access to?", "Kis system ka access chahiye?"),
        "access_level": ("Do you need read, write, or admin access?", "Read, write ya admin access chahiye?"),
        "justification": ("What work do you need this access for?", "Yeh access kis kaam ke liye chahiye?"),
    }
    question, urdu = questions.get(field, ("What detail can you provide next?", "Agli detail kya de sakte hain?"))
    return ResponsePlan(
        purpose="ask", expected_concept=field, question=question,
        urdu_question=urdu, known_context=draft.fields,
    )


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


def repair_candidate(message, draft, candidate):
    """Supplement provider output with non-conflicting, bounded explicit facts."""
    fallback = development_candidates(message, draft)
    facts = {**fallback.facts, **candidate.facts}
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
        "corrections": corrections,
        "field_sources": {**fallback.field_sources, **candidate.field_sources},
        "inferred_leave_category": fallback_inference,
        "inference_confidence": inference_confidence,
        "language_signal": candidate.language_signal or fallback.language_signal,
        "language_confidence": max(candidate.language_confidence, fallback.language_confidence),
        "governance_signal": candidate.governance_signal or fallback.governance_signal,
        "governance_confidence": max(candidate.governance_confidence, fallback.governance_confidence),
        "ambiguities": list(dict.fromkeys([*candidate.ambiguities, *fallback.ambiguities])),
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
    if not field or draft.fields.get(field) or field in candidate.facts or field in candidate.corrections:
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


async def balance_answer(employee):
    from app.integrations.hrms_mock import get_hrms
    try:
        balance = await get_hrms().get_leave_balance(employee.employee_id)
        if not balance.get("found"):
            raise ValueError("missing")
        return "Your available leave is " + ", ".join(
            f"{name}: {data['remaining']:g} days" for name, data in balance["balances"].items()
        ) + "."
    except Exception:
        return "I couldn't retrieve your leave balance right now. Please try again."


async def save_conversational_response(db, draft, user_message, message, **kwargs):
    append_turns(draft, user_message, message)
    await save_draft(db, draft)
    return response(draft, message, **kwargs)


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
    policy_chunks = []
    if draft.domain == ConversationDomain.LEAVE_HR and not draft.fields.get("leave_type"):
        policy_chunks = await category_policy_context(db)
    try:
        candidate = await extract_candidates(message, draft, policy_chunks)
    except Exception:
        logger.warning("Turn understanding unavailable or invalid; using bounded fallback", exc_info=False)
        candidate = development_candidates(message, draft)
    else:
        candidate = repair_candidate(message, draft, candidate)
    candidate = enforce_date_ambiguity(message, draft, candidate)
    candidate = preserve_last_required_explanation(message, draft, candidate)
    update_language(draft, candidate)
    await record_incident(db, draft, employee, candidate, message)

    if candidate.intent in {"policy", "request_policy"} or draft.domain == ConversationDomain.POLICIES_GENERAL:
        if candidate.intent == "request_policy":
            merge_candidates(draft, candidate, message)
        answer, retrieval_mode, _ = await policy_answer(db, draft, message)
        composed = await compose_response(draft, ResponsePlan(
            purpose="policy", answer=answer, draft_preserved=bool(draft.fields),
        ))
        return await save_conversational_response(
            db, draft, message, composed, response_type="policy_info",
            retrieval_mode=retrieval_mode,
        )
    if candidate.intent == "balance":
        answer = await balance_answer(employee)
        composed = await compose_response(draft, ResponsePlan(
            purpose="balance", answer=answer, draft_preserved=bool(draft.fields),
        ))
        return await save_conversational_response(
            db, draft, message, composed, response_type="policy_info"
        )
    if candidate.intent == "help":
        field = draft.missing_fields[0] if draft.missing_fields else None
        question_plan = question_context(draft, field) if field else None
        guidance = (
            "Tell me the part you know in your own words. "
            + (question_plan.question if question_plan else "I can explain the next step.")
        )
        urdu_guidance = (
            "Jo detail aap jaante hain apne alfaaz mein bata dein. "
            + (question_plan.urdu_question if question_plan else "Main agla step samjha deta hoon.")
        )
        composed = await compose_response(draft, ResponsePlan(
            purpose="help", expected_concept=field,
            question=question_plan.question if question_plan else None,
            urdu_question=question_plan.urdu_question if question_plan else None,
            known_context=draft.fields, guidance=guidance, urdu_guidance=urdu_guidance,
        ))
        return await save_conversational_response(
            db, draft, message, composed, response_type="chat"
        )

    expected_domain = REQUEST_DOMAIN.get(candidate.request_type)
    if expected_domain and expected_domain != draft.domain:
        composed = await compose_response(draft, ResponsePlan(
            purpose="out_of_domain", current_domain=DOMAIN_LABELS[draft.domain],
            requested_domain=DOMAIN_LABELS[expected_domain],
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
    if action == "ASK":
        response_plan = question_context(draft, detail)
    elif action == "EVIDENCE_GATE":
        response_plan = ResponsePlan(purpose=purpose, evidence=EvidenceResponseContext(
            category=draft.fields["leave_type"], duration_days=draft.fields["duration_days"],
        ))
    else:
        response_plan = ResponsePlan(purpose=purpose, known_context=draft.fields)
    composed = await compose_response(draft, response_plan)
    if action in {"ASK", "AMBIGUOUS_DATE", "INVALID_DATE", "PAST_DATE", "DATE_CONFLICT"}:
        draft.last_question = composed
        draft.last_question_field = detail if action == "ASK" else "start_date"
    return await save_conversational_response(
        db, draft, message, composed, response_type="chat",
        upload_available=action == "EVIDENCE_GATE",
    )
