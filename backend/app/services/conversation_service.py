"""Deterministic planner and MongoDB-owned conversation orchestration."""
import logging
import re
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.config import get_settings
from app.models.draft import DraftState, RequestDraft
from app.models.audit import AuditEventType
from app.schemas.request import AssistantChatResponse
from app.services.audit_service import create_audit_entry
from app.services.candidate_extraction import extract_candidates
from app.services.normalization import FIELDS, REQUIRED, coherent_type, normalize_leave_dates, normalize_submission

logger = logging.getLogger(__name__)
GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "salam", "assalamualaikum"}
QUESTIONS = {
    "request_type": "What would you like help with: leave, reimbursement, or system access?",
    "leave_type": "Should I treat this as casual/personal leave, or another leave category?",
    "start_date": "When would you like the leave to start?",
    "duration_days": "How long do you expect to be off?",
    "reason": "What is the reason for your leave?",
    "category": "What category of expense are you claiming?",
    "amount": "What is the expense amount in USD?",
    "description": "What was the expense for?",
    "system_name": "Which system do you need access to?",
    "access_level": "What level of access do you need?",
    "justification": "What do you need this access for?",
}
URDU_QUESTIONS = {
    "request_type": "Aapko leave, reimbursement ya system access mein kis cheez ki madad chahiye?",
    "leave_type": "Kya isay casual/personal leave samjhun, ya koi aur leave category hai?",
    "start_date": "Chutti kab se chahiye?", "duration_days": "Kitne din ki chutti chahiye?",
    "reason": "Chutti ki wajah kya hai?", "category": "Expense kis category ka hai?",
    "amount": "Expense ki raqam USD mein kitni hai?", "description": "Yeh expense kis liye tha?",
    "system_name": "Kis system ka access chahiye?", "access_level": "Kis level ka access chahiye?",
    "justification": "Yeh access kis kaam ke liye chahiye?",
}


def merge_candidates(draft, candidate, message):
    if candidate.language:
        draft.language = candidate.language
    if candidate.intent in {"policy", "general"}:
        return
    facts = {k: v.strip() if isinstance(v, str) else v for k, v in candidate.facts.items()
             if k in set().union(*FIELDS.values()) and v is not None and v != ""}
    family = coherent_type(facts)
    kind = draft.request_type or family or candidate.request_type
    # Explicit branch-switching text cannot change an existing/obvious leave request.
    if re.search(r"\b(?:leave|chutti|chuti)\b", message.lower()) and re.search(r"\b(?:classify|ignore|treat this as it)\b", message.lower()):
        kind = "leave"
    if kind not in FIELDS:
        return
    if (facts and family is None and set(facts) != {"duration_days"}) or set(facts) - FIELDS[kind]:
        draft.ambiguous_fields = ["request_type"]
        return
    if draft.request_type and candidate.request_type and candidate.request_type != draft.request_type:
        draft.ambiguous_fields = ["request_type"]
        return
    draft.request_type = kind
    if kind == "leave":
        # Narrow domain normalization: clear first-person symptoms can imply sick
        # leave. A relative's illness never does. Explicit employee category wins.
        relatives = re.search(r"\b(mother|father|daughter|son|child|wife|husband|family|ammi|abu)\b", message.lower())
        self_reference = re.search(r"\b(i have|i am|i'm|i've got|mujhe|meri tabiyat)\b", message.lower())
        symptoms = re.search(r"\b(fever|bukhar|migraine|flu|unwell|headache|nausea|bimaar|tabiyat kharab)\b", str(facts.get("reason", "")).lower())
        if relatives and facts.get("leave_type") == "sick" and not re.search(r"\bsick leave\b", message.lower()):
            facts.pop("leave_type")
        if not facts.get("leave_type") and not draft.fields.get("leave_type") and self_reference and symptoms and not relatives:
            facts["leave_type"] = "sick"
        if "reason" in facts and "leave_type" not in facts and re.search(r"\b(mother|father|daughter|child|family|ammi|abu)\b", str(facts["reason"]).lower()):
            if draft.fields.get("leave_type") == "sick":
                draft.fields.pop("leave_type", None)
        # Remove stale derived values before applying corrections.
        if "duration_days" in facts and "end_date" not in facts:
            draft.fields.pop("end_date", None)
            draft.date_basis = "duration"
        elif "end_date" in facts and "duration_days" not in facts:
            draft.fields.pop("duration_days", None)
            draft.date_basis = "range"
        elif "start_date" in facts and "end_date" not in facts:
            if draft.date_basis == "duration":
                draft.fields.pop("end_date", None)
            else:
                draft.fields.pop("duration_days", None)
        if "end_date" in facts and "duration_days" in facts:
            draft.date_basis = "range"
    draft.fields.update(facts)
    draft.ambiguous_fields = [name for name in candidate.ambiguities if name not in facts]
    if candidate.evidence_choice != "undecided":
        draft.evidence_choice = candidate.evidence_choice


def plan(draft):
    """Compute missing fields, ambiguity and evidence policy; no model action is trusted."""
    kind = draft.request_type
    if not kind:
        draft.missing_fields = ["request_type"]
        return "ASK_REQUIRED_FIELD", "request_type"
    if draft.ambiguous_fields:
        return "ASK_CLARIFICATION", draft.ambiguous_fields[0]
    if kind == "leave":
        try:
            draft.fields = normalize_leave_dates(draft.fields)
        except (ValueError, TypeError, OverflowError) as exc:
            draft.ambiguous_fields = ["dates"]
            return "ASK_CLARIFICATION", str(exc)
    draft.missing_fields = [key for key in REQUIRED[kind] if draft.fields.get(key) in (None, "")]
    duration = draft.fields.get("duration_days")
    draft.evidence_required = bool(kind == "leave" and draft.fields.get("leave_type") == "sick" and
                                  isinstance(duration, (int, float)) and duration >= get_settings().sick_evidence_threshold_days)
    if not draft.evidence_required:
        draft.evidence_choice = "undecided"
        draft.state = DraftState.COLLECTING
    if draft.missing_fields:
        return "ASK_REQUIRED_FIELD", draft.missing_fields[0]
    try:
        draft.fields = normalize_submission(kind, draft.fields)
    except ValidationError as exc:
        field = str(exc.errors()[0]["loc"][0])
        draft.missing_fields = [field]
        return "ASK_CLARIFICATION", QUESTIONS.get(field, "Please clarify the request details.")
    except (ValueError, TypeError) as exc:
        return "ASK_CLARIFICATION", str(exc)
    if draft.evidence_required and not draft.evidence_present:
        if draft.evidence_choice == "undecided":
            return "ASK_EVIDENCE_PREFERENCE", ""
        if draft.evidence_choice == "upload":
            draft.state = DraftState.AWAITING_EVIDENCE
            return "WAITING_FOR_EVIDENCE", ""
    if draft.preflight.get("decision") == "routed":
        return "ESCALATE_FOR_REVIEW", ""
    return "SUBMIT_REQUEST", ""


def planner_message(draft, action, detail):
    urdu = draft.language == "roman_urdu"
    if action in {"ASK_REQUIRED_FIELD", "ASK_CLARIFICATION"}:
        return (URDU_QUESTIONS if urdu else QUESTIONS).get(detail, detail)
    if action == "WAITING_FOR_EVIDENCE":
        return "File yahan upload kar dein. Isay manager review karega." if urdu else "Please upload your file here. Your manager will review the supporting evidence."
    days = draft.fields.get("duration_days")
    if urdu:
        return f"{days:g} din ki sick leave ke liye supporting evidence darkar hai. Aap abhi upload kar sakte hain, ya baghair evidence manager ko bhejne ka keh sakte hain."
    return f"For {days:g} days of sick leave, supporting evidence is normally required. You can upload it now, or ask me to send the request to your manager without it."


def status_message(request, language="en"):
    """Only persisted enums select employee-facing status. No LLM suffix can contradict it."""
    status, decision = request.status.value, request.decision.value
    if status == "escalated" or decision == "routed":
        return "Aapki request manager review ke liye bhej di hai. Abhi approve nahi hui." if language == "roman_urdu" else "Your request has been sent for manager review. It is not approved yet."
    if status in {"resolved", "overridden"} and decision == "approved":
        return "Aapki request approve ho gayi hai." if language == "roman_urdu" else "Your request has been approved."
    if status in {"resolved", "overridden"} and decision == "rejected":
        return "Aapki request reject ho gayi hai." if language == "roman_urdu" else "Your request has been rejected."
    return "Aapki request process ho rahi hai. Abhi koi final faisla nahi hua." if language == "roman_urdu" else "Your request is being processed. There is no final decision yet."


async def load_draft(db, conversation_id, employee_id):
    doc = await db.request_drafts.find_one({"id": str(conversation_id), "employee_id": str(employee_id)})
    if not doc:
        raise HTTPException(404, "Conversation not found")
    try:
        return RequestDraft.model_validate(doc)
    except ValidationError:
        raise HTTPException(409, "This conversation could not be restored. Please start a new conversation.")


async def save_draft(db, draft):
    revision = draft.revision
    draft.revision += 1
    draft.updated_at = datetime.now(timezone.utc)
    result = await db.request_drafts.update_one(
        {"id": draft.id, "employee_id": draft.employee_id, "revision": revision},
        {"$set": draft.model_dump(mode="json")})
    if not result.matched_count:
        raise HTTPException(409, "Another message changed this conversation. Please retry.")


def response(draft, message, **kwargs):
    return AssistantChatResponse(conversation_id=draft.id, draft_state=draft.state.value,
                                 message=message, **kwargs)


async def processed_response(db, draft):
    from app.services.request_service import get_request_by_id
    request = await get_request_by_id(db, draft.request_id)
    if request is None:
        raise HTTPException(409, "Submission is still being saved. Please retry shortly.")
    request.confidence = None
    request.evaluation_reasoning = None
    request.retrieved_policy_refs = []
    return response(draft, status_message(request, draft.language), response_type="request_processed", request_details=request)


async def handle_message(db, employee, payload, *, attachment_ready=False):
    if payload.conversation_id:
        draft = await load_draft(db, payload.conversation_id, employee.id)
    else:
        draft = RequestDraft(employee_id=str(employee.id))
        await db.request_drafts.insert_one({"_id": draft.id, **draft.model_dump(mode="json")})
        await create_audit_entry(db, request_id=None, event_type=AuditEventType.DRAFT_CREATED,
                                 actor_id=employee.id, actor_role=employee.role.value, details={"draft_id": draft.id})
    if draft.state == DraftState.SUBMITTED:
        return await processed_response(db, draft)
    if draft.state == DraftState.SUBMITTING:
        existing = await db.sop_requests.find_one({"id": draft.request_id})
        stale = datetime.now(timezone.utc) - draft.updated_at > timedelta(minutes=5)
        if existing and (existing["status"] != "in_progress" or stale):
            if stale and existing["status"] == "in_progress":
                await db.sop_requests.update_one({"id": draft.request_id, "status": "in_progress"}, {"$set": {
                    "status": "escalated", "decision": "routed", "evaluation_reasoning": "Interrupted submission recovered for human review."}})
                await create_audit_entry(db, request_id=draft.request_id, event_type=AuditEventType.WORKFLOW_FAILED,
                                         actor_id="system", actor_role="system", details={"reason": "interrupted_submission"})
            draft.state = DraftState.SUBMITTED
            await save_draft(db, draft)
            return await processed_response(db, draft)
        if stale and not existing:
            draft.state, draft.request_id = DraftState.COLLECTING, None
            await save_draft(db, draft)
            return response(draft, "The interrupted submission was not saved. Please send your message again.", response_type="chat")
        return await processed_response(db, draft)
    if draft.state == DraftState.ATTACHING_EVIDENCE:
        if datetime.now(timezone.utc) - draft.updated_at > timedelta(minutes=5):
            draft.state = DraftState.AWAITING_EVIDENCE
            await save_draft(db, draft)
            return response(draft, "The upload was interrupted. Please retry the attachment or send another message.", response_type="chat", upload_available=True)
        raise HTTPException(409, "An attachment is being saved. Please retry shortly.")
    message = payload.message.strip()
    if message.lower().rstrip(".! ") in GREETINGS:
        return response(draft, "Hello! Tell me what you need help with.", response_type="chat")
    try:
        if attachment_ready:
            from app.services.candidate_extraction import Candidates
            candidate = Candidates(intent="general")
        else:
            candidate = await extract_candidates(message, draft)
    except Exception:
        logger.warning("Candidate extraction unavailable or invalid; draft preserved", exc_info=False)
        return response(draft, "I couldn't understand that message reliably. Please try again.", response_type="chat")
    draft.evidence_present = bool(await db.evidence.find_one({"draft_id": draft.id}))
    # A two-option evidence question cannot be answered unambiguously by yes/no.
    # Keep this guard in Python even if the model proposes a preference.
    normalized_message = message.lower().strip().rstrip(".!?")
    if draft.evidence_required and not draft.evidence_present:
        vague_choice = normalized_message in {"yes", "no", "nah", "ok", "okay", "sure", "haan", "nahi"}
        no_document = re.search(r"don't have|do not have|haven't got|nahi hai", normalized_message)
        explicit_send = re.search(r"\b(send|submit|continue|proceed|bhej)\b", normalized_message)
        negative_send = re.search(r"(?:don't|do not) (?:send|submit|proceed)|mat bhej|not yet", normalized_message)
        if vague_choice or negative_send or (no_document and not explicit_send):
            candidate = candidate.model_copy(update={"intent": "general", "facts": {}, "evidence_choice": "undecided"})
            if negative_send or normalized_message in {"no", "nah", "nahi"}:
                draft.evidence_choice = "undecided"
                draft.state = DraftState.COLLECTING
        elif re.search(r"^(can i|may i|could i|kya)\b", normalized_message):
            candidate = candidate.model_copy(update={"intent": "policy", "facts": {}, "evidence_choice": "undecided"})
    policy_message, retrieval_mode = "", None
    if candidate.intent in {"policy", "request_policy"}:
        if draft.evidence_required and re.search(r"without|baghair|bina", message.lower()):
            policy_message = "Yes, you can ask me to send it without evidence. It will need manager review and will not be automatically approved."
        elif re.search(r"\bbalance\b", message.lower()):
            from app.integrations.hrms_mock import get_hrms
            try:
                balance = await get_hrms().get_leave_balance(employee.employee_id)
                if not balance.get("found"):
                    raise ValueError("missing balance")
                policy_message = "Your available leave: " + ", ".join(f"{k}: {v['remaining']:g} days" for k, v in balance["balances"].items()) + "."
            except Exception:
                policy_message = "I couldn't retrieve your leave balance. Please try again."
        else:
            from app.services.sop_service import search_policy
            try:
                chunks = await search_policy(db, message, top_k=2)
                policy_message = "\n\n".join(f"{c['ref']}: {c['chunk_text']}" for c in chunks) if chunks else "I couldn't find a matching company policy. Please check with your manager."
                retrieval_mode = chunks[0]["retrieval_mode"] if chunks else "no_match"
            except Exception:
                policy_message, retrieval_mode = "Policy guidance is unavailable. Please try again or check with your manager.", "unavailable"
        if candidate.intent == "policy":
            return response(draft, policy_message, response_type="policy_info", retrieval_mode=retrieval_mode)
    merge_candidates(draft, candidate, message)
    action, detail = plan(draft)
    if action in {"SUBMIT_REQUEST", "ESCALATE_FOR_REVIEW", "ASK_EVIDENCE_PREFERENCE", "WAITING_FOR_EVIDENCE"}:
        from orchestration.nodes.intake import intake
        from orchestration.nodes.retrieve_policy import retrieve_policy
        from orchestration.nodes.dmn_rule_engine import dmn_rule_engine
        state = {"request_id": draft.id, "employee_id": employee.id, "employee_code": employee.employee_id,
                 "request_type": draft.request_type, "submitted_data": draft.fields}
        try:
            state.update(await intake(state))
            state.update(await retrieve_policy(state))
            state["evidence_present"] = draft.evidence_present
            outcome = await dmn_rule_engine(state)
            draft.preflight = {"decision": outcome["decision"], "reason": outcome["evaluation_reasoning"],
                               "policy_refs": state.get("retrieved_policy_refs", [])}
        except Exception:
            draft.preflight = {"decision": "routed", "reason": "preflight_unavailable"}
        action, detail = plan(draft)
    if action not in {"SUBMIT_REQUEST", "ESCALATE_FOR_REVIEW"}:
        draft.last_question = planner_message(draft, action, detail)
        await save_draft(db, draft)
        return response(draft, (policy_message + "\n\n" if policy_message else "") + draft.last_question,
                        response_type="chat", upload_available=action == "WAITING_FOR_EVIDENCE", retrieval_mode=retrieval_mode)
    # Atomically claim the draft before creating any governed request.
    draft.state, draft.request_id = DraftState.SUBMITTING, str(uuid4())
    await save_draft(db, draft)
    from app.services.request_service import submit_request
    from app.api.request import _run_ai_workflow
    try:
        await submit_request(db, employee=employee, request_type=draft.request_type,
                             submitted_data=draft.fields, request_id=draft.request_id)
        await db.evidence.update_many({"draft_id": draft.id}, {"$set": {"request_id": draft.request_id}})
        attachments = await db.evidence.find({"request_id": draft.request_id}).to_list(length=100)
        from app.api.evidence import public_metadata
        await db.sop_requests.update_one({"id": draft.request_id}, {"$set": {
            "has_evidence": bool(attachments), "evidence_list": [public_metadata(item) for item in attachments]}})
        if draft.evidence_required and not draft.evidence_present:
            await create_audit_entry(db, request_id=draft.request_id, event_type=AuditEventType.EVIDENCE_OMITTED,
                                     actor_id=employee.id, actor_role=employee.role.value,
                                     details={"reason": "required_supporting_evidence_not_provided"})
        await _run_ai_workflow(draft.request_id, employee.id, employee.employee_id, draft.request_type, draft.fields)
    except Exception:
        logger.exception("Conversation submission failed")
        # A partially created request is retained and safely routed, never duplicated.
        existing = await db.sop_requests.find_one({"id": draft.request_id})
        if not existing:
            draft.state, draft.request_id = DraftState.COLLECTING, None
            await save_draft(db, draft)
            raise HTTPException(503, "Your request could not be saved. Please retry.")
        await db.sop_requests.update_one({"id": draft.request_id, "status": "in_progress"}, {"$set": {
            "status": "escalated", "decision": "routed", "evaluation_reasoning": "Submission workflow failed; human review required."}})
        await create_audit_entry(db, request_id=draft.request_id, event_type=AuditEventType.WORKFLOW_FAILED,
                                 actor_id="system", actor_role="system", details={"reason": "submission_failure"})
    draft.state = DraftState.SUBMITTED
    await save_draft(db, draft)
    return await processed_response(db, draft)
