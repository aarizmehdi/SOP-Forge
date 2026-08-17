"""
SOP Forge â€” Request API router.
Employee request submission and status tracking.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.auth.rbac import require_employee
from app.database import get_db
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
        from app.database import async_session_factory
        from app.models.request import SOPRequest
        from sqlalchemy import select

        result = await run_request_workflow(
            request_id=request_id,
            employee_id=employee_id,
            employee_code=employee_code,
            request_type=request_type,
            submitted_data=submitted_data,
        )

        # Update the request with AI results
        async with async_session_factory() as db:
            req_uuid = UUID(request_id) if isinstance(request_id, str) else request_id
            stmt = select(SOPRequest).where(SOPRequest.id == req_uuid)
            req_result = await db.execute(stmt)
            sop_request = req_result.scalar_one_or_none()

            if sop_request:
                sop_request.decision = result.get("decision", "pending")
                sop_request.confidence = result.get("confidence", 0.0)
                sop_request.evaluation_reasoning = result.get("evaluation_reasoning", "")
                sop_request.retrieved_policy_refs = result.get("retrieved_policy_refs", [])
                sop_request.status = result.get("status", "in_progress")

                sla = result.get("sla_deadline")
                if sla:
                    from datetime import datetime
                    sop_request.sla_deadline = datetime.fromisoformat(sla)

                await db.commit()
                logger.info(f"Request {request_id} updated with AI result: {result.get('decision')}")

    except Exception as e:
        logger.error(f"AI workflow failed for {request_id}: {e}")


@router.post("/submit", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def submit_new_request(
    submission: RequestSubmission,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
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
    await db.commit()

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    """Get the current employee's requests."""
    requests = await get_employee_requests(db, current_user.id, limit, offset)
    for req in requests:
        db.expunge(req)
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    """Get a specific request by ID."""
    sop_request = await get_request_by_id(db, request_id)
    if sop_request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # Employees can only see their own requests (unless manager+)
    from app.models.user import UserRole
    if current_user.role == UserRole.EMPLOYEE:
        if sop_request.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Sanitize internal AI reasoning for employees to prevent leaking flags/policies
        db.expunge(sop_request)
        sop_request.evaluation_reasoning = None
        sop_request.confidence = None
        sop_request.retrieved_policy_refs = None

    return sop_request


@router.post("/assistant", response_model=AssistantChatResponse)
async def chat_assistant(
    payload: AssistantChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    """
    Smart AI Brain â€” Multi-turn conversational orchestrator.
    Tracks state, infers intent, never repeats questions, escalates suspicious reasons.
    """
    msg_clean = payload.message.strip()
    msg_lower = msg_clean.lower()

    # 1. GREETINGS â€” zero overhead fast path
    GREETINGS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening",
                 "greetings", "hi there", "hello there", "help", "who are you", "yo", "sup"}
    if msg_lower in GREETINGS or (len(msg_lower) <= 4 and msg_lower not in {"sick", "paid", "info", "days", "leave"}):
        greeting_msg = (
            f"Hello {current_user.name.split()[0]}! Welcome to SOP Forge.\n\n"
            f"I'm your Forge AI Copilot. Which department would you like to talk to?\n\n"
            f"• **HR & Leave** — Leave applications, attendance, balances\n"
            f"â€¢ **Finance** â€” Expense claims, reimbursements\n"
            f"â€¢ **IT & Security** â€” System access, permissions\n"
            f"â€¢ **General Operations** â€” Facility, general inquiries\n\n"
            f"Just tell me what you need, or pick a department to get started!"
        )
        return AssistantChatResponse(response_type="chat", message=greeting_msg, request_details=None)

    # 2. SMART BRAIN â€” LLM-powered multi-turn orchestrator
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

    brain_prompt = f"""You are the "Brain" of SOP Forge — a warm, professional, and SMART AI Copilot.
You are talking to: {current_user.name} (Role: {current_user.role.value}, Employee Code: {current_user.employee_id}).
Today's date: {today_str}. Tomorrow: {tomorrow_str}.

## LIVE EMPLOYEE DATA
Current Leave Balances: {balance_str}
If the user asks for more days than their balance, PROACTIVELY WARN THEM in your message (but still allow submission if they insist, or ask them what they want to do).

## CRITICAL RULES â€” FOLLOW STRICTLY

### Rule 1: EXTRACT EVERYTHING FROM CONTEXT
Before responding, carefully scan the ENTIRE conversation for these fields:
- **Date**: "now" / "right now" / "immediately" / "abhi" = TODAY ({today_str}). "tomorrow" / "kal" = {tomorrow_str}. "today" / "aj" = {today_str}.
- **Leave type**: Infer from context. NEVER ask "what type of leave?" if you can infer it:
  - Child crying/sick child/family emergency/personal emergency = CASUAL
  - Stomach pain/headache/fever/unwell/sick/tabiyat kharab = SICK
  - Vacation/trip/rest/holiday = ANNUAL
  - Funeral/death/bereavement = CASUAL
- **Reason**: Whatever the user said about WHY they need leave IS the reason. Examples:
  - "my child is crying" â†’ reason = "Child needs immediate attention"
  - "I have a headache" â†’ reason = "Feeling unwell - headache"
  - "family emergency" â†’ reason = "Family emergency"
  DO NOT re-ask for the reason if the user already explained WHY.

### Rule 2: NEVER REPEAT QUESTIONS
If the user already provided a piece of information in ANY previous message, do NOT ask for it again. Read the FULL transcript.

### Rule 3: ASK ONE QUESTION AT A TIME
If something is genuinely missing, ask for ONLY that ONE thing in a warm, conversational tone. Never give a numbered list of questions.

### Rule 4: SUBMIT IMMEDIATELY WHEN READY
When you have ALL required fields (even if inferred), set action to "SUBMIT". Do NOT ask "shall I proceed?" or "can I confirm?" â€” just submit.

### Rule 5: ESCALATE SUSPICIOUS REASONS
If the reason is absurd, inappropriate, or clearly not legitimate (e.g., "my husband misses me", "I feel like it", "no reason", "I just don't want to work"), set action to "ESCALATE".

### Rule 6: POLICY QUESTIONS
If the user is asking ABOUT rules/limits (not submitting a request), set action to "POLICY_QUESTION".

### Rule 7: ROMAN URDU SUPPORT
"chutti chahiye" = want leave, "tabiyat kharab" = sick, "mujhe leave chahiye" = want leave, "aj" = today, "kal" = tomorrow, "abhi" = now (today).
{language_rule}

## BEFORE YOU RESPOND — MANDATORY CHECKLIST
Look at the conversation history and answer internally:
1. Has the user said WHEN? (date or "now/today/tomorrow") → If yes, you have start_date.
2. Has the user said WHY? (any reason/explanation at all) → If yes, you have reason.
3. Can you INFER the leave type from their reason? → If yes, you have leave_type.
4. If you have ALL 3 above → set action to "SUBMIT".
5. IF REASON IS MISSING: You MUST set action to "ASK" and politely ask for the reason. DO NOT MAKE UP A REASON. DO NOT SUBMIT WITHOUT A REASON.

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
  "message": "Your warm, friendly response",
  "suggested_options": ["Option 1", "Option 2"] | null,
  "request_type": "leave" | "reimbursement" | "it_access" | null,
  "extracted_data": {{
    // ALL fields gathered from the ENTIRE conversation (not just this message)
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
        
        incident = HRIncident(
            employee_id=current_user.id,
            incident_type="inappropriate_chat",
            message=msg_clean,
            ai_reasoning=reason,
            status="open"
        )
        db.add(incident)
        await db.commit()

        return AssistantChatResponse(
            response_type="chat",
            message="I'm sorry, but I cannot process this. This conversation has been flagged and securely logged for HR review.",
            request_details=None,
        )

    elif action == "SUBMIT":
        req_type = parsed_brain.get("request_type") or "leave"
        data = parsed_brain.get("extracted_data") or {}
        
        # Hard Python Validation: ZERO hallucination tolerance.
        # If the LLM tries to submit a leave request without a reason or date, intercept it.
        if req_type == "leave":
            missing = []
            if not data.get("reason"): missing.append("reason")
            if not data.get("start_date"): missing.append("start_date")
            if not data.get("leave_type"): missing.append("type of leave")
            
            if missing:
                return AssistantChatResponse(
                    response_type="chat",
                    message=f"I need a bit more detail before I can submit this. Could you provide the {' and '.join(missing)}?",
                    request_details=None,
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

        sop_req.decision = eval_result.get("decision", "pending")
        sop_req.confidence = eval_result.get("confidence", 0.0)
        sop_req.evaluation_reasoning = eval_result.get("evaluation_reasoning", "")
        sop_req.retrieved_policy_refs = eval_result.get("retrieved_policy_refs", [])
        sop_req.status = eval_result.get("status", "in_progress")
        sla = eval_result.get("sla_deadline")
        if sla:
            sop_req.sla_deadline = datetime.fromisoformat(sla)
        await db.commit()

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
1. Do NOT sound robotic. NEVER use generic phrases like "approved automatically" or "SOP policy checks out". Speak naturally.
2. Be incredibly smart and human-like. Give just enough context to be helpful (e.g., if declined, briefly explain why), but don't over-explain.
3. LANGUAGE MATCHING: If the user's request ('{msg_clean}') contains Roman Urdu/Hindi (e.g., 'mujhe', 'chutti', 'cuz', 'yaar', 'bhai', 'tabiyat'), you MUST reply in the EXACT SAME casual Roman Urdu style. Otherwise, reply in English.
4. {'LANGUAGE LOCK: The user started this conversation in Roman Urdu. ALL your replies MUST be in Roman Urdu. NO English.' if is_roman_urdu else 'LANGUAGE LOCK: The user started in English. Reply in English only.'}
5. Keep it very short (1-3 sentences max).
"""
            try:
                res = await llm.ainvoke([HumanMessage(content=response_prompt)])
                resp_msg = res.content.strip()
            except Exception as e:
                logger.error(f"Response generation failed: {e}")
        
        # Fallback if LLM fails or is disabled
        if not resp_msg:
            if dec_str == "approved":
                resp_msg = f"Your request has been approved. The system has recorded it."
            elif status_str == "escalated":
                resp_msg = f"I've forwarded your request to management for a quick review."
            else:
                resp_msg = f"Unfortunately, this request was declined based on current policy."

        # Sanitize internal AI reasoning for employees to prevent leaking flags/policies
        from app.models.user import UserRole
        if current_user.role == UserRole.EMPLOYEE:
            db.expunge(sop_req)
            sop_req.evaluation_reasoning = None
            sop_req.confidence = None
            sop_req.retrieved_policy_refs = None

        return AssistantChatResponse(
            response_type="request_processed",
            message=resp_msg,
            request_details=sop_req,
        )

    else:
        # POLICY_QUESTION â€” RAG search
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
    """Fill in default values for any missing required fields."""
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
    """Fallback brain when LLM is unavailable."""
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

    return {"action": "ASK", "message": "I'm here to help! Which department would you like to talk to?\n\n- **HR & Leave** â€” Leave applications, attendance\n- **Finance** â€” Expense claims\n- **IT & Security** â€” System access\n- **General Operations** â€” Facility, inquiries"}

