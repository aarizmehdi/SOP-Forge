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
    ConversationStartRequest,
    RequestListItem,
    RequestResponse,
    RequestStatusResponse,
    RequestSubmission,
)
from app.services.request_service import (
    can_access_request,
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
            from datetime import datetime, timezone
            sop_request.updated_at = datetime.now(timezone.utc)

            sla = result.get("sla_deadline")
            if sla:
                from datetime import datetime
                sop_request.sla_deadline = datetime.fromisoformat(sla)

            await db.sop_requests.update_one(
                {"id": request_id, "status": "in_progress"},
                {"$set": sop_request.model_dump(mode="json")}
            )
            logger.info(f"Request {request_id} updated with AI result: {result.get('decision')}")
            if result.get("error"):
                from app.models.audit import AuditEventType
                from app.services.audit_service import create_audit_entry
                await create_audit_entry(db, request_id=request_id, event_type=AuditEventType.WORKFLOW_FAILED,
                                         actor_id="system", actor_role="system", decision="routed",
                                         details={"reason": "workflow_failure"})

    except Exception as e:
        logger.error(f"AI workflow failed for {request_id}: {e}")
        try:
            client = get_mongodb_client()
            try:
                db = client.get_default_database()
            except Exception:
                db = client["sopforge"]

            await db.sop_requests.update_one(
                {"id": request_id, "status": "in_progress"},
                {"$set": {
                    "status": RequestStatus.ESCALATED.value,
                    "decision": Decision.ROUTED.value,
                    "evaluation_reasoning": "Workflow failed. Request routed to manager for human review.",
                }}
            )
            from app.models.audit import AuditEventType
            from app.services.request_service import create_audit_entry
            await create_audit_entry(
                db,
                request_id=request_id,
                event_type=AuditEventType.WORKFLOW_FAILED,
                actor_id="system",
                actor_role="system",
                decision="routed",
                details={"reason": "workflow_failure"},
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

    if not await can_access_request(db, sop_request, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    # Employees receive the public lifecycle result without internal evaluation data.
    if current_user.role.value == "employee":
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
    from app.services.conversation_service import handle_message
    return await handle_message(db, current_user, payload)


@router.post("/assistant/start", response_model=AssistantChatResponse, status_code=status.HTTP_201_CREATED)
async def start_assistant_conversation(
    payload: ConversationStartRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    from app.services.conversation_service import start_conversation
    return await start_conversation(db, current_user, payload.domain)
