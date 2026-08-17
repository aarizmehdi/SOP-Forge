"""
SOP Forge — Review API router.
Manager escalation review and executive override endpoints.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_executive, require_manager
from app.database import get_db
from app.models.user import User
from app.schemas.review import EscalatedRequestItem, ExecutiveOverride, ReviewDecision
from app.services.request_service import (
    get_escalated_requests,
    get_request_by_id,
    process_override,
    process_review_decision,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/review", tags=["Review"])


@router.get("/pending", response_model=list[EscalatedRequestItem])
async def get_pending_reviews(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Get escalated requests pending review for the current manager."""
    requests = await get_escalated_requests(db, current_user)

    items = []
    for req in requests:
        sla_remaining = None
        if req.sla_deadline:
            sla_dl = req.sla_deadline
            if sla_dl.tzinfo is None:
                sla_dl = sla_dl.replace(tzinfo=timezone.utc)
            delta = sla_dl - datetime.now(timezone.utc)
            sla_remaining = max(0, int(delta.total_seconds() / 60))

        items.append(EscalatedRequestItem(
            id=req.id,
            employee_name=req.employee.name if req.employee else "Unknown",
            employee_id_code=req.employee.employee_id if req.employee else "N/A",
            department=req.employee.department.name if req.employee and req.employee.department else None,
            request_type=req.request_type,
            submitted_data=req.submitted_data,
            ai_decision=req.decision,
            ai_confidence=req.confidence,
            evaluation_reasoning=req.evaluation_reasoning,
            policy_refs=req.retrieved_policy_refs,
            status=req.status,
            sla_deadline=req.sla_deadline,
            sla_remaining_minutes=sla_remaining,
            created_at=req.created_at,
        ))

    return items


@router.post("/{request_id}/decide")
async def review_decision(
    request_id: UUID,
    decision: ReviewDecision,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Manager approves, rejects, or requests more info on an escalated request."""
    try:
        sop_request = await process_review_decision(
            db,
            request_id=request_id,
            reviewer=current_user,
            decision=decision.decision.value,
            comment=decision.comment,
        )
        return {
            "status": "success",
            "request_id": str(sop_request.id),
            "decision": sop_request.decision if isinstance(sop_request.decision, str) else sop_request.decision.value,
            "message": f"Request {decision.decision.value} by {current_user.name}",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{request_id}/override")
async def executive_override(
    request_id: UUID,
    override: ExecutiveOverride,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_executive),
):
    """
    Executive override — can happen at any stage.
    Always logged with mandatory justification (PRD requirement).
    """
    try:
        sop_request = await process_override(
            db,
            request_id=request_id,
            executive=current_user,
            new_decision=override.new_decision.value,
            justification=override.justification,
        )
        return {
            "status": "success",
            "request_id": str(sop_request.id),
            "decision": sop_request.decision if isinstance(sop_request.decision, str) else sop_request.decision.value,
            "message": f"Override applied by {current_user.name}",
            "override_logged": True,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
