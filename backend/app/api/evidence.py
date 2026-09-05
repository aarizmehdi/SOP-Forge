"""
SOP Forge — Evidence API router.
Handles file uploads and secure viewing of evidence documents.
"""

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.jwt import get_current_user
from app.database import get_db
from app.models.evidence import Evidence
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/evidence", tags=["Evidence"])

UPLOAD_DIR = Path("uploads/evidence")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
ALLOWED_EXTENSIONS = {".pdf", ".jpeg", ".jpg", ".png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB max limit


@router.post("/upload/{request_id}")
async def upload_evidence(
    request_id: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload evidence file for a specific request.
    Validates MIME type, extension, and 5MB size limit.
    Automatically re-evaluates DMN workflow once evidence is attached.
    """
    # Verify request exists
    sop_req = await db.sop_requests.find_one({"id": request_id})
    if not sop_req:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")

    # Validate ownership or manager permission
    if current_user.role.value == "employee" and sop_req.get("employee_id") != current_user.id:
        raise HTTPException(status_code=403, detail="You can only attach evidence to your own request")

    # Validate file extension
    filename = file.filename or "file.bin"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file.content_type}'. Allowed formats: PDF, JPEG, PNG (max 5MB).",
        )

    # Read and check size
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")

    # Save to disk securely
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = UPLOAD_DIR / unique_filename
    with open(file_path, "wb") as f:
        f.write(content)

    # Create Evidence model
    evidence_entry = Evidence(
        id=str(uuid.uuid4()),
        request_id=request_id,
        original_filename=filename,
        stored_filename=unique_filename,
        storage_path=str(file_path),
        content_type=file.content_type,
        size_bytes=len(content),
        uploaded_by=current_user.id,
    )
    evidence_dict = evidence_entry.model_dump(mode="json")
    await db.evidence.insert_one(evidence_dict)

    # Update request document with evidence metadata
    existing_list = sop_req.get("evidence_list", [])
    existing_list.append({
        "id": evidence_entry.id,
        "filename": filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "uploaded_at": evidence_entry.uploaded_at.isoformat(),
    })

    # Re-evaluate DMN workflow now that evidence is attached
    from orchestration.graph import run_request_workflow
    eval_result = await run_request_workflow(
        request_id=request_id,
        employee_id=sop_req.get("employee_id"),
        employee_code=current_user.employee_id,
        request_type=sop_req.get("request_type", "leave"),
        submitted_data=sop_req.get("submitted_data", {}),
    )

    new_decision = eval_result.get("decision", "routed")
    new_status = eval_result.get("status", "escalated")
    new_reasoning = eval_result.get("evaluation_reasoning", "")

    await db.sop_requests.update_one(
        {"id": request_id},
        {"$set": {
            "has_evidence": True,
            "evidence_list": existing_list,
            "decision": new_decision,
            "status": new_status,
            "evaluation_reasoning": new_reasoning,
        }}
    )

    logger.info(f"Evidence {filename} uploaded for request {request_id} by {current_user.name}. Status updated to {new_status}.")
    return {
        "status": "success",
        "message": f"Evidence '{filename}' attached successfully. Request workflow updated.",
        "evidence": evidence_dict,
        "new_request_status": new_status,
        "new_decision": new_decision,
    }


@router.get("/file/{evidence_id}")
async def get_evidence_file(
    evidence_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Securely stream/view an uploaded evidence file with department-level access control."""
    doc = await db.evidence.find_one({"id": evidence_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    # Fetch associated request to verify department authorization
    sop_req = await db.sop_requests.find_one({"id": doc.get("request_id")})
    if not sop_req:
        raise HTTPException(status_code=404, detail="Associated request not found")

    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    # Authorization rules:
    # 1. Employee: Can only view evidence for their own request
    if user_role == "employee":
        if sop_req.get("employee_id") != current_user.id and doc.get("uploaded_by") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied: You can only view evidence for your own requests")

    # 2. Manager: Can view evidence for requests within their own department or their own requests
    elif user_role == "manager":
        is_owner = sop_req.get("employee_id") == current_user.id or doc.get("uploaded_by") == current_user.id
        req_dept = sop_req.get("department")
        same_dept = req_dept and current_user.department and req_dept == current_user.department
        if not (is_owner or same_dept):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: Managers cannot access evidence from department '{req_dept}'",
            )

    # 3. Executive and Admin: Authorized for organization-wide review

    file_path = Path(doc.get("storage_path", ""))
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File content not found on server")

    return FileResponse(
        path=file_path,
        media_type=doc.get("content_type", "application/octet-stream"),
        filename=doc.get("original_filename", "evidence"),
    )


@router.get("/request/{request_id}")
async def list_request_evidence(
    request_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all evidence attached to a request with department access control."""
    sop_req = await db.sop_requests.find_one({"id": request_id})
    if not sop_req:
        raise HTTPException(status_code=404, detail="Request not found")

    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    if user_role == "employee":
        if sop_req.get("employee_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied: You can only view evidence for your own requests")
    elif user_role == "manager":
        is_owner = sop_req.get("employee_id") == current_user.id
        req_dept = sop_req.get("department")
        same_dept = req_dept and current_user.department and req_dept == current_user.department
        if not (is_owner or same_dept):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: Managers cannot list evidence from department '{req_dept}'",
            )

    cursor = db.evidence.find({"request_id": request_id})
    docs = await cursor.to_list(length=100)
    return docs
