"""
SOP Forge — Request service.
Business logic for request submission and lifecycle management.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import get_redis
from app.models.audit import AuditEventType
from app.models.request import Decision, RequestHistory, RequestStatus, SOPRequest
from app.models.user import User
from app.services.audit_service import create_audit_entry

logger = logging.getLogger(__name__)
settings = get_settings()


async def submit_request(
    db: AsyncSession,
    *,
    employee: User,
    request_type: str,
    submitted_data: dict,
) -> SOPRequest:
    """
    Submit a new SOP request and trigger the AI evaluation pipeline.
    """
    request_id = uuid.uuid4()

    # Create the request
    sop_request = SOPRequest(
        id=request_id,
        employee_id=employee.id,
        request_type=request_type,
        submitted_data=submitted_data,
        decision=Decision.PENDING,
        status=RequestStatus.IN_PROGRESS,
    )
    db.add(sop_request)

    # Record submission in history
    history = RequestHistory(
        id=uuid.uuid4(),
        request_id=request_id,
        action="submitted",
        actor_id=employee.id,
        details={"request_type": request_type, "submitted_data": submitted_data},
    )
    db.add(history)

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

    await db.flush()
    logger.info(f"Request {request_id} submitted by {employee.employee_id}")

    return sop_request


async def get_request_by_id(
    db: AsyncSession,
    request_id: uuid.UUID | str,
) -> SOPRequest | None:
    """Get a request by ID with relationships loaded."""
    try:
        req_uuid = request_id if isinstance(request_id, uuid.UUID) else uuid.UUID(str(request_id))
    except (ValueError, TypeError):
        return None

    result = await db.execute(
        select(SOPRequest)
        .options(joinedload(SOPRequest.employee), joinedload(SOPRequest.history))
        .where(SOPRequest.id == req_uuid)
    )
    return result.unique().scalar_one_or_none()


async def get_employee_requests(
    db: AsyncSession,
    employee_id: uuid.UUID | str,
    limit: int = 50,
    offset: int = 0,
) -> list[SOPRequest]:
    """Get all requests submitted by an employee."""
    if isinstance(employee_id, str):
        try:
            employee_id = uuid.UUID(employee_id)
        except ValueError:
            return []

    result = await db.execute(
        select(SOPRequest)
        .where(SOPRequest.employee_id == employee_id)
        .order_by(SOPRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_escalated_requests(
    db: AsyncSession,
    manager: User,
    limit: int = 50,
) -> list[SOPRequest]:
    """Get escalated requests for a manager's department."""
    stmt = (
        select(SOPRequest)
        .options(
            joinedload(SOPRequest.employee).joinedload(User.department)
        )
        .where(SOPRequest.status == RequestStatus.ESCALATED)
        .order_by(SOPRequest.sla_deadline.asc().nullslast())
        .limit(limit)
    )

    # If manager (not executive/admin), filter by department
    from app.models.user import UserRole
    if manager.role == UserRole.MANAGER and manager.department_id:
        stmt = stmt.join(User, SOPRequest.employee_id == User.id).where(
            User.department_id == manager.department_id
        )

    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def process_review_decision(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    reviewer: User,
    decision: str,
    comment: str,
) -> SOPRequest:
    """Process a manager's review decision on an escalated request."""
    sop_request = await get_request_by_id(db, request_id)
    if sop_request is None:
        raise ValueError(f"Request {request_id} not found")

    if sop_request.status != RequestStatus.ESCALATED:
        raise ValueError(f"Request {request_id} is not in escalated status")

    # Update request
    sop_request.decision = decision
    sop_request.status = RequestStatus.RESOLVED

    # Record in history
    history = RequestHistory(
        id=uuid.uuid4(),
        request_id=request_id,
        action=f"manager_{decision}",
        actor_id=reviewer.id,
        details={"decision": decision, "comment": comment},
    )
    db.add(history)

    # Audit log
    event_type = (
        AuditEventType.MANAGER_APPROVED if decision == "approved"
        else AuditEventType.MANAGER_REJECTED if decision == "rejected"
        else AuditEventType.MORE_INFO_REQUESTED
    )
    await create_audit_entry(
        db,
        request_id=request_id,
        event_type=event_type,
        actor_id=reviewer.id,
        actor_role=reviewer.role.value,
        decision=decision,
        details={"comment": comment},
    )

    # Update Redis state
    redis = get_redis()
    await redis.setex(
        f"request:{request_id}:state",
        3600 * 24,
        json.dumps({
            "request_id": str(request_id),
            "status": "resolved",
            "decision": decision,
        }),
    )

    await db.flush()
    logger.info(f"Request {request_id} {decision} by {reviewer.employee_id}")
    return sop_request


async def process_override(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    executive: User,
    new_decision: str,
    justification: str,
) -> SOPRequest:
    """
    Process an executive override. Always logged with mandatory justification.
    Per PRD: Executive override can happen at any stage.
    """
    sop_request = await get_request_by_id(db, request_id)
    if sop_request is None:
        raise ValueError(f"Request {request_id} not found")

    previous_decision = sop_request.decision.value if sop_request.decision else None

    # Update request
    sop_request.decision = new_decision
    sop_request.status = RequestStatus.OVERRIDDEN

    # Append to override log
    override_entry = {
        "by": str(executive.id),
        "by_name": executive.name,
        "justification": justification,
        "previous_decision": previous_decision,
        "new_decision": new_decision,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    current_log = sop_request.override_log or []
    current_log.append(override_entry)
    sop_request.override_log = current_log

    # Record in history
    history = RequestHistory(
        id=uuid.uuid4(),
        request_id=request_id,
        action="executive_override",
        actor_id=executive.id,
        details=override_entry,
    )
    db.add(history)

    # Audit log — override entries always include previous decision
    await create_audit_entry(
        db,
        request_id=request_id,
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
        f"request:{request_id}:state",
        3600 * 24,
        json.dumps({
            "request_id": str(request_id),
            "status": "overridden",
            "decision": new_decision,
        }),
    )

    await db.flush()
    logger.info(
        f"Request {request_id} overridden by {executive.employee_id}: "
        f"{previous_decision} → {new_decision}"
    )
    return sop_request
