"""
SOP Forge — Request service (MongoDB).
Business logic for request submission and lifecycle management.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.database import get_redis
from app.models.audit import AuditEventType
from app.models.request import Decision, RequestHistory, RequestStatus, SOPRequest
from app.models.user import User
from app.services.audit_service import create_audit_entry

logger = logging.getLogger(__name__)
settings = get_settings()


async def submit_request(
    db: AsyncIOMotorDatabase,
    *,
    employee: User,
    request_type: str,
    submitted_data: dict,
) -> SOPRequest:
    """
    Submit a new SOP request and trigger the AI evaluation pipeline.
    """
    request_id = str(uuid.uuid4())

    # Create the request
    sop_request = SOPRequest(
        id=request_id,
        employee_id=employee.id,
        request_type=request_type,
        submitted_data=submitted_data,
        decision=Decision.PENDING,
        status=RequestStatus.IN_PROGRESS,
    )
    await db.sop_requests.insert_one(sop_request.model_dump(mode="json"))

    # Record submission in history
    history = RequestHistory(
        id=str(uuid.uuid4()),
        request_id=request_id,
        action="submitted",
        actor_id=employee.id,
        details={"request_type": request_type, "submitted_data": submitted_data},
    )
    await db.request_history.insert_one(history.model_dump(mode="json"))

    # Create audit entry
    await create_audit_entry(
        db,
        request_id=request_id,
        event_type=AuditEventType.REQUEST_SUBMITTED,
        actor_id=employee.id,
        actor_role=employee.role.value,
        details={
            "request_type": request_type,
            "employee_id": employee.employee_id,
        },
    )

    # Cache request state in Redis for live tracking
    redis = get_redis()
    await redis.setex(
        f"request:{request_id}:state",
        3600 * 24,  # 24 hour TTL
        json.dumps({
            "request_id": str(request_id),
            "status": "in_progress",
            "decision": "pending",
        }),
    )

    logger.info(f"Request {request_id} submitted by {employee.employee_id}")
    return sop_request


async def get_request_by_id(
    db: AsyncIOMotorDatabase,
    request_id: uuid.UUID | str,
) -> SOPRequest | None:
    """Get a request by ID."""
    doc = await db.sop_requests.find_one({"id": str(request_id)})
    if not doc:
        return None
    return SOPRequest(**doc)


async def get_employee_requests(
    db: AsyncIOMotorDatabase,
    employee_id: uuid.UUID | str,
    limit: int = 50,
    offset: int = 0,
) -> list[SOPRequest]:
    """Get all requests submitted by an employee."""
    cursor = db.sop_requests.find({"employee_id": str(employee_id)}).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [SOPRequest(**doc) for doc in docs]


async def get_escalated_requests(
    db: AsyncIOMotorDatabase,
    manager: User,
    limit: int = 50,
    status_filter: str = "escalated",
) -> list[SOPRequest]:
    """Get requests for review, filtered by status and manager department."""
    if status_filter == "past" or status_filter == "resolved":
        query = {"status": {"$in": [RequestStatus.RESOLVED.value, RequestStatus.OVERRIDDEN.value]}}
    elif status_filter == "all":
        query = {}
    else:
        query = {"status": RequestStatus.ESCALATED.value}
    
    # If manager (not executive/admin), filter by department
    if manager.role.value == "manager" and manager.department_id:
        dept_users_cursor = db.users.find({"department_id": manager.department_id}, {"id": 1})
        dept_users = await dept_users_cursor.to_list(length=1000)
        user_ids = [u["id"] for u in dept_users]
        query["employee_id"] = {"$in": user_ids}

    cursor = db.sop_requests.find(query).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [SOPRequest(**doc) for doc in docs]


async def process_review_decision(
    db: AsyncIOMotorDatabase,
    *,
    request_id: uuid.UUID | str,
    reviewer: User,
    decision: str,
    comment: str,
) -> SOPRequest:
    """Process a manager's review decision on an escalated request."""
    request_id_str = str(request_id)
    sop_request = await get_request_by_id(db, request_id_str)
    if sop_request is None:
        raise ValueError(f"Request {request_id_str} not found")

    if sop_request.status != RequestStatus.ESCALATED:
        raise ValueError(f"Request {request_id_str} is not in escalated status")

    # Enforce department check for department managers
    if reviewer.role.value == "manager" and reviewer.department_id:
        emp_user = await db.users.find_one({"id": sop_request.employee_id})
        if emp_user and emp_user.get("department_id") and emp_user["department_id"] != reviewer.department_id:
            raise ValueError("You can only decide on requests belonging to your department.")

    # Update request
    sop_request.decision = Decision(decision)
    sop_request.status = RequestStatus.RESOLVED
    sop_request.updated_at = datetime.now(timezone.utc)
    
    await db.sop_requests.update_one(
        {"id": request_id_str},
        {"$set": sop_request.model_dump(mode="json")}
    )

    # Record in history
    history = RequestHistory(
        id=str(uuid.uuid4()),
        request_id=request_id_str,
        action=f"manager_{decision}",
        actor_id=reviewer.id,
        details={"decision": decision, "comment": comment},
    )
    await db.request_history.insert_one(history.model_dump(mode="json"))

    # Audit log
    event_type = (
        AuditEventType.MANAGER_APPROVED if decision == "approved"
        else AuditEventType.MANAGER_REJECTED if decision == "rejected"
        else AuditEventType.MORE_INFO_REQUESTED
    )
    await create_audit_entry(
        db,
        request_id=request_id_str,
        event_type=event_type,
        actor_id=reviewer.id,
        actor_role=reviewer.role.value,
        decision=decision,
        details={"comment": comment},
    )

    # Update Redis state
    redis = get_redis()
    await redis.setex(
        f"request:{request_id_str}:state",
        3600 * 24,
        json.dumps({
            "request_id": request_id_str,
            "status": "resolved",
            "decision": decision,
        }),
    )

    logger.info(f"Request {request_id_str} {decision} by {reviewer.employee_id}")
    return sop_request


async def process_override(
    db: AsyncIOMotorDatabase,
    *,
    request_id: uuid.UUID | str,
    executive: User,
    new_decision: str,
    justification: str,
) -> SOPRequest:
    """
    Process an executive override. Always logged with mandatory justification.
    """
    request_id_str = str(request_id)
    sop_request = await get_request_by_id(db, request_id_str)
    if sop_request is None:
        raise ValueError(f"Request {request_id_str} not found")

    previous_decision = sop_request.decision.value if sop_request.decision else None

    # Update request
    sop_request.decision = Decision(new_decision)
    sop_request.status = RequestStatus.OVERRIDDEN
    sop_request.updated_at = datetime.now(timezone.utc)

    # Append to override log
    override_entry = {
        "by": executive.id,
        "by_name": executive.name,
        "justification": justification,
        "previous_decision": previous_decision,
        "new_decision": new_decision,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    current_log = sop_request.override_log or []
    current_log.append(override_entry)
    sop_request.override_log = current_log

    await db.sop_requests.update_one(
        {"id": request_id_str},
        {"$set": sop_request.model_dump(mode="json")}
    )

    # Record in history
    history = RequestHistory(
        id=str(uuid.uuid4()),
        request_id=request_id_str,
        action="executive_override",
        actor_id=executive.id,
        details=override_entry,
    )
    await db.request_history.insert_one(history.model_dump(mode="json"))

    # Audit log
    await create_audit_entry(
        db,
        request_id=request_id_str,
        event_type=AuditEventType.EXECUTIVE_OVERRIDE,
        actor_id=executive.id,
        actor_role=executive.role.value,
        decision=new_decision,
        override_justification=justification,
        previous_decision=previous_decision,
        details={"override_entry": override_entry},
    )

    # Update Redis state
    redis = get_redis()
    await redis.setex(
        f"request:{request_id_str}:state",
        3600 * 24,
        json.dumps({
            "request_id": request_id_str,
            "status": "overridden",
            "decision": new_decision,
        }),
    )

    logger.info(
        f"Request {request_id_str} overridden by {executive.employee_id}: "
        f"{previous_decision} → {new_decision}"
    )
    return sop_request
