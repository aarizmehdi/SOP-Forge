"""
SOP Forge — Incidents API router.
Dedicated endpoints for HR to review flagged inappropriate chats.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.rbac import require_manager
from app.database import get_db
from app.models.user import User
from app.models.incident import HRIncident
from app.schemas.incident import IncidentResponse

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


@router.get("", response_model=list[IncidentResponse])
async def get_incidents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """
    Fetch all HR incidents. Restricted to Manager and Admin roles.
    """
    stmt = select(HRIncident).order_by(HRIncident.created_at.desc())
    result = await db.execute(stmt)
    incidents = result.scalars().all()
    return list(incidents)


@router.put("/{incident_id}/dismiss", response_model=IncidentResponse)
async def dismiss_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """
    Mark an incident as reviewed/dismissed.
    """
    stmt = select(HRIncident).where(HRIncident.id == incident_id)
    result = await db.execute(stmt)
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    incident.status = "reviewed"
    await db.commit()
    await db.refresh(incident)

    return incident
