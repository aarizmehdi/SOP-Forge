"""
SOP Forge — Request API router (MongoDB).
Employee request submission and status tracking.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.jwt import get_current_user
from app.auth.rbac import require_employee
from app.database import get_db, get_mongodb_client
from app.models.request import Decision, RequestStatus, SOPRequest
from app.models.user import User
from app.schemas.request import (
    AssistantChatRequest,
    AssistantChatResponse,
    RequestListItem,
    RequestResponse,
    RequestStatusResponse,
    RequestSubmission,
)
from app.services.request_service import (
    get_employee_requests,
    get_request_by_id,
    submit_request,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/request", tags=["Requests"])


async def _run_ai_workflow(request_id: str, employee_id: str, employee_code: str, request_type: str, submitted_data: dict):
    """Background task to run the LangGraph AI evaluation workflow."""
    try:
        from orchestration.graph import run_request_workflow
        
        result = await run_request_workflow(
            request_id=request_id,
            employee_id=employee_id,
            employee_code=employee_code,
            request_type=request_type,
            submitted_data=submitted_data,
        )

        # Update the request with AI results
        client = get_mongodb_client()
        try:
            db = client.get_default_database()
        except Exception:
            db = client["sopforge"]

        req_doc = await db.sop_requests.find_one({"id": request_id})

        if req_doc:
            sop_request = SOPRequest(**req_doc)
            sop_request.decision = Decision(result.get("decision", "pending"))
            sop_request.confidence = result.get("confidence", 0.0)
            sop_request.evaluation_reasoning = result.get("evaluation_reasoning", "")
            sop_request.retrieved_policy_refs = result.get("retrieved_policy_refs", [])
            sop_request.status = RequestStatus(result.get("status", "in_progress"))

            sla = result.get("sla_deadline")
            if sla:
                from datetime import datetime
                sop_request.sla_deadline = datetime.fromisoformat(sla)

            await db.sop_requests.update_one(
                {"id": request_id},
                {"$set": sop_request.model_dump(mode="json")}
            )
            logger.info(f"Request {request_id} updated with AI result: {result.get('decision')}")

    except Exception as e:
        logger.error(f"AI workflow failed for {request_id}: {e}")
        try:
            client = get_mongodb_client()
            try:
                db = client.get_default_database()
            except Exception:
                db = client["sopforge"]

            await db.sop_requests.update_one(
                {"id": request_id},
                {"$set": {
                    "status": RequestStatus.ESCALATED.value,
                    "decision": Decision.ROUTED.value,
                    "evaluation_reasoning": f"Workflow pipeline encountered an unexpected error ({str(e)}). Request automatically routed to manager for human review.",
                }}
            )
            from app.models.audit import AuditEventType
            from app.services.request_service import create_audit_entry
            await create_audit_entry(
                db,
                request_id=request_id,
                event_type=AuditEventType.ESCALATED,
                actor_id="system",
                actor_role="system",
                decision="routed",
                details={"pipeline_error": str(e)},
            )
        except Exception as ex:
            logger.error(f"Failed to record fail-closed recovery state for {request_id}: {ex}")


@router.post("/submit", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def submit_new_request(
    submission: RequestSubmission,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    """
    Submit a new SOP request. Triggers the AI evaluation pipeline in the background.
    """
    sop_request = await submit_request(
        db,
        employee=current_user,
        request_type=submission.request_type.value,
        submitted_data=submission.submitted_data,
    )

    # Run AI evaluation in the background
    background_tasks.add_task(
        _run_ai_workflow,
        request_id=str(sop_request.id),
        employee_id=str(current_user.id),
        employee_code=current_user.employee_id,
        request_type=submission.request_type.value,
        submitted_data=submission.submitted_data,
    )

    return sop_request


@router.get("/my", response_model=list[RequestListItem])
async def get_my_requests(
    limit: int = 50,
    offset: int = 0,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    """Get the current employee's requests."""
    requests = await get_employee_requests(db, str(current_user.id), limit, offset)
    for req in requests:
        req.confidence = None
    return requests


@router.get("/leave-balances")
async def get_my_leave_balances(
    current_user: User = Depends(require_employee),
):
    """Fetch live HRMS leave balances for the current user."""
    from app.integrations.hrms_mock import get_hrms
    hrms = get_hrms()
    data = await hrms.get_leave_balance(current_user.employee_id)
    return data


@router.get("/{request_id}", response_model=RequestResponse)
async def get_request(
    request_id: UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    """Get a specific request by ID."""
    sop_request = await get_request_by_id(db, str(request_id))
    if sop_request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # Employees can only see their own requests (unless manager+)
    if current_user.role.value == "employee":
        if sop_request.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Sanitize internal AI reasoning for employees to prevent leaking flags/policies
        sop_request.evaluation_reasoning = None
        sop_request.confidence = None
        sop_request.retrieved_policy_refs = None

    return sop_request


@router.post("/assistant", response_model=AssistantChatResponse)
async def chat_assistant(
    payload: AssistantChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    """
    Smart AI Brain — Multi-turn conversational orchestrator.
    """
    msg_clean = payload.message.strip()
    msg_lower = msg_clean.lower()

    # 1. GREETINGS — zero overhead fast path
    GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening",
                 "greetings", "hi there", "hello there", "help", "who are you", "yo", "sup"}
    if msg_lower in GREETINGS or (len(msg_lower) <= 4 and msg_lower not in {"sick", "paid", "info", "days", "leave"}):
        greeting_msg = (
            f"Hello {current_user.name.split()[0]}! Welcome to SOP Forge.\n\n"
            f"I'm your Forge AI Copilot. Which department would you like to talk to?\n\n"
            f"• **HR & Leave** — Leave applications, attendance, balances\n"
            f"• **Finance** — Expense claims, reimbursements\n"
            f"• **IT & Security** — System access, permissions\n"
            f"• **General Operations** — Facility, general inquiries\n\n"
            f"Just tell me what you need, or pick a department to get started!"
        )
        return AssistantChatResponse(response_type="chat", message=greeting_msg, request_details=None)

    # 2. SMART BRAIN — LLM-powered multi-turn orchestrator
    import json
    from datetime import datetime, timedelta
    from app.config import get_settings
    settings = get_settings()

    today_str = datetime.now().strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Build full conversation transcript
    history_transcript = ""
    if payload.history:
        for h in payload.history:
            history_transcript += f"{h.role.upper()}: {h.content}\n"
    history_transcript += f"USER: {msg_clean}"

    # ── LANGUAGE DETECTION (lock from first user message) ──
    first_user_msg = ""
    if payload.history:
        for h in payload.history:
            if h.role.lower() == "user":
                first_user_msg = h.content.strip().lower()
                break
    if not first_user_msg:
        first_user_msg = msg_lower

    ROMAN_URDU_MARKERS = {
        "mujhe", "chahiye", "chutti", "tabiyat", "kharab", "theek", "nahi",
        "hai", "hain", "yar", "yaar", "bhai", "bro", "karo", "karna",
        "mera", "meri", "apni", "kya", "kuch", "hogaya", "hogayi",
        "hogya", "hogyi", "abhi", "kal", "aj", "aaj", "parso",
        "dard", "pet", "sar", "bukhar", "bimaar", "bimaari",
        "zaroorat", "zaroori", "kam", "kaam", "office", "ghar",
        "chalo", "haan", "nhi", "kr", "krna", "krdo", "kro", "krdi",
        "hogyi", "lena", "dena", "rehna", "jana", "aana",
        "shukriya", "meherbani", "please", "plz",
    }
    first_words = set(first_user_msg.split())
    is_roman_urdu = len(first_words & ROMAN_URDU_MARKERS) >= 1

    language_rule = ""
    if is_roman_urdu:
        language_rule = (
            "\n### Rule 8: LANGUAGE LOCK — ROMAN URDU\n"
            "The user's first message was in Roman Urdu. You MUST respond in casual, natural Roman Urdu for this ENTIRE conversation. "
            "Do NOT switch to English. Do NOT mix English sentences. Keep it 100% Roman Urdu (written in English script). "
            "Example: 'Aapki chutti approve hogayi hai, aaram karo!' NOT 'Your leave has been approved.'\n"
        )
    else:
        language_rule = (
            "\n### Rule 8: LANGUAGE LOCK — ENGLISH\n"
            "The user's first message was in English. You MUST respond in clear, professional English for this ENTIRE conversation. "
            "Do NOT switch to Roman Urdu or Hindi. Keep it 100% English.\n"
        )

    # Fetch Live Data for proactive contextual awareness
    from app.integrations.hrms_mock import get_hrms
    hrms = get_hrms()
    try:
        live_balances = await hrms.get_leave_balance(current_user.employee_id)
        balance_str = json.dumps(live_balances, indent=2)
    except Exception:
        balance_str = "Unavailable"

    brain_prompt = f"""You are the "Brain" of SOP Forge — a warm, highly efficient, and concise AI Copilot.
You are talking to: {current_user.name} (Role: {current_user.role.value}, Employee Code: {current_user.employee_id}).
Today's date: {today_str}. Tomorrow: {tomorrow_str}.

## CRITICAL BEHAVIOR RULES — FOLLOW STRICTLY

### Rule 1: EXTREME CONCISENESS & NATURAL TONE (MAX 1-2 SHORT SENTENCES)
- Be incredibly concise, direct, and empathetic. Speak like a smart human colleague.
- NEVER write long paragraphs. NEVER dump balance numbers, tables, or unprompted policy lectures.
- DO NOT mention leave balances unless the user explicitly asks "what is my balance?".
- DO NOT mention backdated rules unless the user explicitly specified a date in the past (before {today_str}).

### Rule 2: EXTRACT EVERYTHING FROM CONTEXT
Scan the ENTIRE conversation for these fields:
- **Date**: "now" / "today" / "aj" / "abhi" = {today_str}. "tomorrow" / "kal" = {tomorrow_str}.
- **Leave type**: Infer naturally:
  - Child/family/emergency/hospital/sick relative/personal = CASUAL or SICK
  - Stomach pain/headache/fever/unwell/sick = SICK
  - Vacation/trip/rest/holiday = ANNUAL
- **Reason**: Whatever the user said about WHY they need leave IS the reason.
  DO NOT re-ask for the reason if the user already explained WHY.

### Rule 3: ASK ONE CONCISE QUESTION FOR MISSING FIELDS
If a required field is missing (e.g., start_date), ask ONLY for that ONE missing piece in a brief 1-sentence question.
Example: "I'm sorry to hear about your teacher. When would you like this leave to start?"

### Rule 4: BACKDATED DATE CHECK (ONLY IF PAST DATE IS GIVEN)
IF AND ONLY IF the user explicitly gave a date in the past (before {today_str}), set action to "ASK" and respond briefly:
"Leave cannot start in the past. When would you like your leave to start?"
Do NOT bring up backdate rules if the user has not mentioned a past date.

### Rule 5: SUBMIT IMMEDIATELY WHEN READY
When you have start_date, leave_type, and reason, set action to "SUBMIT". Do NOT ask "shall I proceed?" — just submit.

### Rule 6: ESCALATE SUSPICIOUS REASONS
If the reason is absurd, inappropriate, or clearly not legitimate (e.g. "no reason", "I don't feel like working"), set action to "ESCALATE".

{language_rule}

## MANDATORY CHECKLIST
1. Did the user say WHEN? (today / tomorrow / specific date) → start_date
2. Did the user say WHY? (any reason) → reason
3. Leave type inferred? → leave_type
4. If ALL 3 present → set action to "SUBMIT".
5. IF MISSING FIELD → set action to "ASK" and ask a 1-sentence question for ONLY what is missing.

## REQUIRED FIELDS PER REQUEST TYPE
- **leave**: leave_type, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), reason
- **reimbursement**: category, amount (number), description
- **it_access**: system_name, access_level, justification

## FULL CONVERSATION HISTORY
{history_transcript}

## YOUR RESPONSE
Respond with ONLY valid JSON (no markdown, no backticks):
{{
  "action": "ASK" | "SUBMIT" | "ESCALATE" | "POLICY_QUESTION",
  "message": "Your ultra-short, natural 1-2 sentence response",
  "suggested_options": ["Option 1", "Option 2"] | null,
  "request_type": "leave" | "reimbursement" | "it_access" | null,
  "extracted_data": {{
    // ALL fields gathered from the ENTIRE conversation
  }},
  "missing_fields": ["field1"],
  "escalation_reason": "only if action is ESCALATE"
}}"""

    parsed_brain = None
    try:
        if settings.is_llm_configured:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model="deepseek-chat",
                openai_api_key=settings.deepseek_api_key,
                openai_api_base="https://api.deepseek.com/v1",
                temperature=0.15,
                max_tokens=800,
            )
            res = await llm.ainvoke(brain_prompt)
            content = res.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            parsed_brain = json.loads(content)
    except Exception as e:
        logger.warning(f"Brain LLM failed, falling back to rules: {e}")

    if not parsed_brain:
        parsed_brain = _rule_based_brain(msg_lower, msg_clean, today_str, tomorrow_str)

    # 3. EXECUTE BRAIN ACTION
    action = parsed_brain.get("action", "ASK")

    if action == "ASK":
        return AssistantChatResponse(
            response_type="chat",
            message=parsed_brain.get("message", "Could you tell me more about what you need?"),
            request_details=None,
            suggested_options=parsed_brain.get("suggested_options")
        )

    elif action == "ESCALATE":
        reason = parsed_brain.get("escalation_reason", "Flagged for HR review")
        
        from app.models.incident import HRIncident
        import uuid
        
        incident = HRIncident(
            id=str(uuid.uuid4()),
            employee_id=current_user.id,
            incident_type="inappropriate_chat",
            message=msg_clean,
            ai_reasoning=reason,
            status="open"
        )
        await db.hr_incidents.insert_one(incident.model_dump(mode="json"))

        return AssistantChatResponse(
            response_type="chat",
            message="I'm sorry, but I cannot process this. This conversation has been flagged and securely logged for HR review.",
            request_details=None,
        )

    elif action == "SUBMIT":
        req_type = parsed_brain.get("request_type") or "leave"
        data = parsed_brain.get("extracted_data") or {}
        
        if req_type == "leave":
            missing = []
            if not data.get("reason"): missing.append("reason")
            if not data.get("start_date"): missing.append("start_date")
            if not data.get("leave_type"): missing.append("type of leave")
            
            # Check if duration/days/end_date is specified
            days_val = data.get("days") or data.get("duration_days") or data.get("days_requested")
            has_duration = bool(days_val or (data.get("end_date") and data.get("end_date") != data.get("start_date")))
            
            # Also check transcript if duration was mentioned
            if not has_duration:
                transcript_lower = history_transcript.lower()
                import re
                if re.search(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(day|days|din)\b', transcript_lower) or any(w in transcript_lower for w in ["1 day", "one day", "half day", "today only"]):
                    has_duration = True

            if not has_duration:
                return AssistantChatResponse(
                    response_type="chat",
                    message="How many days of leave do you need?",
                    request_details=None,
                    suggested_options=["1 day", "2 days", "3 days", "5 days"]
                )

            if missing:
                return AssistantChatResponse(
                    response_type="chat",
                    message=f"I need a bit more detail before I can submit this. Could you provide the {' and '.join(missing)}?",
                    request_details=None,
                )

            # Strict Backdate Validation Check: Reject submission if start_date < today
            start_val = data.get("start_date")
            if start_val and start_val < today_str:
                return AssistantChatResponse(
                    response_type="chat",
                    message=f"Leave requests cannot be backdated for past days ({start_val}). Leave must start today ({today_str}) or a future date. When would you like your leave to start?",
                    request_details=None,
                    suggested_options=[f"Start today ({today_str})", f"Start tomorrow ({tomorrow_str})"],
                )

        _set_defaults(data, req_type, today_str, msg_clean)

        sop_req = await submit_request(db, employee=current_user, request_type=req_type, submitted_data=data)

        from orchestration.graph import run_request_workflow
        eval_result = await run_request_workflow(
            request_id=str(sop_req.id),
            employee_id=str(current_user.id),
            employee_code=current_user.employee_id,
            request_type=req_type,
            submitted_data=data,
        )

        sop_req.decision = Decision(eval_result.get("decision", "pending"))
        sop_req.confidence = eval_result.get("confidence", 0.0)
        sop_req.evaluation_reasoning = eval_result.get("evaluation_reasoning", "")
        sop_req.retrieved_policy_refs = eval_result.get("retrieved_policy_refs", [])
        sop_req.status = RequestStatus(eval_result.get("status", "in_progress"))
        sla = eval_result.get("sla_deadline")
        if sla:
            sop_req.sla_deadline = datetime.fromisoformat(sla)
            
        await db.sop_requests.update_one(
            {"id": sop_req.id},
            {"$set": sop_req.model_dump(mode="json")}
        )

        dec_str = sop_req.decision.value if hasattr(sop_req.decision, 'value') else str(sop_req.decision)
        status_str = sop_req.status.value if hasattr(sop_req.status, 'value') else str(sop_req.status)

        # Generate an intelligent, empathetic, contextual response via LLM
        resp_msg = ""
        if settings.is_llm_configured:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage
            llm = ChatOpenAI(
                model="deepseek-chat",
                openai_api_key=settings.deepseek_api_key,
                openai_api_base="https://api.deepseek.com/v1",
                temperature=0.7,
                max_tokens=200,
            )
            response_prompt = f"""You are Forge AI Copilot, a highly intelligent, Stanford-level enterprise AI assistant.
The user ({current_user.name}) submitted a '{req_type}' request: "{msg_clean}".
The system evaluated this request against company policy. The final decision is: {dec_str.upper()} (Status: {status_str.upper()}).
System's internal evaluation reasoning (DO NOT expose raw metrics): {sop_req.evaluation_reasoning}

Write a highly concise, helpful, and empathetic message to the user explaining this outcome. 
CRITICAL RULES:
1. Do NOT sound robotic. Speak naturally like a smart colleague in 1-2 short sentences.
2. Be concise. Give just enough context to be helpful, but NEVER over-explain or write long paragraphs.
3. DO NOT mention backdated rules or leave balance numbers unless the user explicitly asked about them or provided a past date.
4. LANGUAGE MATCHING: If the user's request ('{msg_clean}') contains Roman Urdu/Hindi (e.g., 'mujhe', 'chutti', 'cuz', 'yaar', 'bhai', 'tabiyat'), you MUST reply in the EXACT SAME casual Roman Urdu style. Otherwise, reply in English.
5. {'LANGUAGE LOCK: The user started this conversation in Roman Urdu. ALL your replies MUST be in Roman Urdu. NO English.' if is_roman_urdu else 'LANGUAGE LOCK: The user started in English. Reply in English only.'}
6. Keep it ultra-short (1-2 sentences max).
"""
            try:
                res = await llm.ainvoke([HumanMessage(content=response_prompt)])
                resp_msg = res.content.strip()
            except Exception as e:
                logger.error(f"Response generation failed: {e}")
        
        # Enforce deterministic status header so LLM can never contradict workflow decision
        if dec_str == "approved":
            status_header = "✅ Request Approved."
        elif status_str == "awaiting_evidence" or dec_str == "awaiting_evidence":
            status_header = "📎 Action Required: Medical Certificate / Evidence Required."
        elif status_str == "escalated" or dec_str == "routed":
            status_header = "⏳ Request Sent for Manager Review. (It has not been approved yet.)"
        elif dec_str == "rejected":
            status_header = "❌ Request Declined."
        else:
            status_header = f"📋 Request Status: {status_str.upper()}"

        if not resp_msg:
            resp_msg = status_header
        elif not resp_msg.startswith("✅") and not resp_msg.startswith("⏳") and not resp_msg.startswith("❌"):
            resp_msg = f"{status_header}\n\n{resp_msg}"

        # Sanitize internal AI reasoning for employees to prevent leaking flags/policies
        if current_user.role.value == "employee":
            sop_req.evaluation_reasoning = None
            sop_req.confidence = None
            sop_req.retrieved_policy_refs = None

        return AssistantChatResponse(
            response_type="request_processed",
            message=resp_msg,
            request_details=sop_req,
        )

    else:
        # POLICY_QUESTION — RAG search
        from app.services.sop_service import search_policy
        chunks = await search_policy(db, msg_clean, top_k=3)

        if chunks:
            policy_context = "\n\n".join([f"[{c['document_title']}]: {c['chunk_text']}" for c in chunks])
            synthesis_prompt = f"""You are SOP Forge's friendly HR advisor. Answer concisely based on our SOP policies.

SOP Policy Context:
{policy_context}

User Question: "{msg_clean}"

Give a clear, direct 2-4 sentence answer.
{'CRITICAL: The user speaks Roman Urdu. Your answer MUST be in Roman Urdu (English script). No English.' if is_roman_urdu else 'Reply in clear English.'}"""

            answer_text = None
            try:
                if settings.is_llm_configured:
                    from langchain_openai import ChatOpenAI
                    llm = ChatOpenAI(
                        model="deepseek-chat",
                        openai_api_key=settings.deepseek_api_key,
                        openai_api_base="https://api.deepseek.com/v1",
                        temperature=0.2,
                    )
                    res = await llm.ainvoke(synthesis_prompt)
                    answer_text = res.content.strip()
            except Exception as e:
                logger.warning(f"Policy synthesis failed: {e}")

            if not answer_text:
                answer_text = "\n\n".join([f"**{c['document_title']}**: {c['chunk_text'][:200]}..." for c in chunks])

            return AssistantChatResponse(
                response_type="policy_info",
                message=f"**SOP Policy Guidance:**\n\n{answer_text}",
                request_details=None,
            )
        else:
            return AssistantChatResponse(
                response_type="chat",
                message=parsed_brain.get("message", "I couldn't find a specific policy for that. Could you rephrase, or tell me which department you need?"),
                request_details=None,
            )


def _set_defaults(data: dict, req_type: str, today_str: str, msg_clean: str):
    if req_type == "leave":
        data.setdefault("leave_type", "annual")
        data.setdefault("start_date", today_str)
        data.setdefault("end_date", data.get("start_date", today_str))
        data.setdefault("reason", msg_clean)
        data.setdefault("half_day", False)
    elif req_type == "reimbursement":
        data.setdefault("category", "other")
        data.setdefault("amount", 100.0)
        data.setdefault("description", msg_clean)
    else:
        data.setdefault("system_name", "Internal System")
        data.setdefault("access_level", "write")
        data.setdefault("justification", msg_clean)


def _rule_based_brain(msg_lower: str, msg_clean: str, today_str: str, tomorrow_str: str) -> dict:
    is_leave = any(w in msg_lower for w in ["leave", "vacation", "day off", "time off", "sick", "holiday", "chutti", "chuti"])
    is_reimb = any(w in msg_lower for w in ["reimburse", "expense", "receipt", "claim", "$", "dollar", "refund"])
    is_it = any(w in msg_lower for w in ["access", "permission", "github", "jira", "aws", "system"])
    is_policy = any(w in msg_lower for w in ["policy", "rule", "limit", "carryover", "sop", "guideline", "allowed"])

    if is_policy:
        return {"action": "POLICY_QUESTION", "message": "Let me look that up in our SOP database."}

    if is_leave:
        has_date = any(w in msg_lower for w in ["today", "tomorrow", "monday", "aj", "kal", today_str])
        has_reason = any(w in msg_lower for w in ["sick", "unwell", "fever", "vacation", "personal", "family", "emergency", "tabiyat"])

        if has_date and has_reason:
            import re
            has_dur = bool(re.search(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(day|days|din)\b', msg_lower) or any(w in msg_lower for w in ["half day", "today only", "tomorrow only"]))
            if not has_dur:
                return {
                    "action": "ASK",
                    "message": "How many days of leave do you need?",
                    "suggested_options": ["1 day", "2 days", "3 days", "5 days"],
                    "request_type": "leave",
                    "missing_fields": ["duration_days"]
                }
            leave_cat = "sick" if any(w in msg_lower for w in ["sick", "unwell", "fever", "tabiyat"]) else "casual" if "personal" in msg_lower else "annual"
            start = today_str if any(w in msg_lower for w in ["today", "aj"]) else tomorrow_str
            return {
                "action": "SUBMIT", "request_type": "leave", "message": "Processing your leave request...",
                "extracted_data": {"leave_type": leave_cat, "start_date": start, "end_date": start, "reason": msg_clean},
                "missing_fields": [],
            }
        elif has_date:
            return {"action": "ASK", "message": "Got it! Could you tell me the reason for your leave?", "request_type": "leave", "missing_fields": ["reason"]}
        elif has_reason:
            return {"action": "ASK", "message": "I understand. When do you need the leave? Today, tomorrow, or specific dates?", "request_type": "leave", "missing_fields": ["start_date"]}
        else:
            return {"action": "ASK", "message": "Sure, I can help with leave! When do you need the time off, and what's the reason?", "request_type": "leave", "missing_fields": ["start_date", "reason"]}

    if is_reimb:
        return {"action": "ASK", "message": "I can help with expense claims! What category is this expense? (Travel, Medical, Equipment, or Other) And what's the amount?", "request_type": "reimbursement", "missing_fields": ["category", "amount"]}

    if is_it:
        return {"action": "ASK", "message": "I can help with IT access! Which system do you need access to, and what level? (Read, Write, or Admin)", "request_type": "it_access", "missing_fields": ["system_name", "access_level"]}

    return {"action": "ASK", "message": "I'm here to help! Which department would you like to talk to?\n\n- **HR & Leave** — Leave applications, attendance\n- **Finance** — Expense claims\n- **IT & Security** — System access\n- **General Operations** — Facility, inquiries"}
