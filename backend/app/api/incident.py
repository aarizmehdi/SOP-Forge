"""
SOP Forge — Incidents API router (MongoDB).
Dedicated endpoints for HR to review flagged inappropriate chats.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.rbac import require_manager
from app.database import get_db
from app.models.user import User
from app.models.incident import HRIncident
from app.schemas.incident import IncidentResponse

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


@router.get("", response_model=list[IncidentResponse])
async def get_incidents(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """
    Fetch all HR incidents. Restricted to Manager and Admin roles.
    """
    cursor = db.hr_incidents.find({}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    return [HRIncident(**doc) for doc in docs]


@router.put("/{incident_id}/dismiss", response_model=IncidentResponse)
async def dismiss_incident(
    incident_id: UUID,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """
    Mark an incident as reviewed/dismissed.
    """
    incident_id_str = str(incident_id)
    doc = await db.hr_incidents.find_one({"id": incident_id_str})

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    incident = HRIncident(**doc)
    incident.status = "reviewed"
    
    await db.hr_incidents.update_one(
        {"id": incident_id_str},
        {"$set": incident.model_dump(mode="json")}
    )

    return incident
