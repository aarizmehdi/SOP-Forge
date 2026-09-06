"""Owned draft attachments and authorized human evidence review."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.auth.jwt import get_current_user
from app.auth.rbac import require_employee
from app.database import get_db
from app.models.audit import AuditEventType
from app.models.draft import DraftState
from app.models.evidence import Evidence
from app.models.user import User
from app.services.audit_service import create_audit_entry

router = APIRouter(prefix="/api/evidence", tags=["Evidence"])
UPLOAD_DIR = Path("uploads/evidence")
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/jpg", "image/png"}
ALLOWED_EXTENSIONS = {".pdf", ".jpeg", ".jpg", ".png"}
MAX_FILE_SIZE = 5 * 1024 * 1024


async def authorize_evidence(db, owner_id, user):
    if str(owner_id) == str(user.id):
        return
    role = user.role.value
    if role in {"admin", "executive"}:
        return
    if role == "manager" and user.department_id:
        employee = await db.users.find_one({"id": str(owner_id)})
        if employee and employee.get("department_id") == user.department_id:
            return
    raise HTTPException(403, "You cannot access evidence for this employee.")


async def store_file(db, file, user, *, request_id=None, draft_id=None):
    filename = Path((file.filename or "file.bin").replace("\\", "/")).name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, "Allowed formats are PDF, JPEG and PNG (up to 5MB).")
    content = await file.read(MAX_FILE_SIZE + 1)
    if not content or len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "The file must be nonempty and no larger than 5MB.")
    valid_signature = ((ext == ".pdf" and content.startswith(b"%PDF-")) or
                       (ext in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff")) or
                       (ext == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n")))
    if not valid_signature:
        raise HTTPException(400, "The file content does not match the selected format.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = uuid.uuid4().hex + ext
    path = UPLOAD_DIR / stored
    path.write_bytes(content)
    entry = Evidence(request_id=request_id, draft_id=draft_id, original_filename=filename,
                     stored_filename=stored, storage_path=str(path.resolve()), content_type=file.content_type,
                     size_bytes=len(content), uploaded_by=user.id)
    try:
        await db.evidence.insert_one(entry.model_dump(mode="json"))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    await create_audit_entry(db, request_id=request_id, event_type=AuditEventType.EVIDENCE_ATTACHED,
                             actor_id=user.id, actor_role=user.role.value,
                             details={"evidence_id": entry.id, "draft_id": draft_id, "verified": False})
    return entry


def public_metadata(entry):
    data = entry.model_dump(mode="json") if isinstance(entry, Evidence) else dict(entry)
    for key in ("_id", "storage_path", "stored_filename"):
        data.pop(key, None)
    return data


@router.post("/draft/{conversation_id}")
async def upload_draft_evidence(conversation_id: str, file: UploadFile = File(...),
                                db=Depends(get_db), current_user: User = Depends(require_employee)):
    from app.services.conversation_service import load_draft, save_draft, finalize_draft
    draft = await load_draft(db, conversation_id, current_user.id)
    if draft.state != DraftState.AWAITING_EVIDENCE:
        raise HTTPException(409, "This conversation is not waiting for an attachment.")
    draft.state, draft.evidence_choice = DraftState.ATTACHING_EVIDENCE, "upload"
    await save_draft(db, draft)
    try:
        await store_file(db, file, current_user, draft_id=draft.id)
    except Exception:
        draft.state = DraftState.AWAITING_EVIDENCE
        draft.evidence_choice = "undecided"
        await save_draft(db, draft)
        raise
    if not await db.evidence.find_one({"draft_id": draft.id}):
        draft.state = DraftState.AWAITING_EVIDENCE
        draft.evidence_choice = "undecided"
        await save_draft(db, draft)
        raise HTTPException(409, "The uploaded evidence could not be confirmed. Please retry.")
    draft.evidence_present = True
    return await finalize_draft(db, current_user, draft)


@router.post("/draft/{conversation_id}/skip")
async def skip_draft_evidence(conversation_id: str, db=Depends(get_db),
                              current_user: User = Depends(require_employee)):
    from app.services.conversation_service import skip_evidence
    return await skip_evidence(db, current_user, conversation_id)


@router.post("/upload/{request_id}")
async def upload_evidence(request_id: str, file: UploadFile = File(...),
                          db=Depends(get_db), current_user: User = Depends(get_current_user)):
    request = await db.sop_requests.find_one({"id": request_id})
    if not request:
        raise HTTPException(404, "Request not found")
    await authorize_evidence(db, request["employee_id"], current_user)
    if request["status"] not in {"in_progress", "escalated"}:
        raise HTTPException(409, "Evidence cannot change a finalized request.")
    entry = await store_file(db, file, current_user, request_id=request_id)
    await db.sop_requests.update_one({"id": request_id, "status": {"$in": ["in_progress", "escalated"]}},
        {"$set": {"has_evidence": True, "decision": "routed", "status": "escalated",
                  "evaluation_reasoning": "Supporting evidence attached; human evidence review required."},
         "$push": {"evidence_list": public_metadata(entry)}})
    current = await db.sop_requests.find_one({"id": request_id})
    return {"status": "success", "message": "Evidence attached for human review.",
            "evidence": public_metadata(entry), "new_request_status": current["status"],
            "new_decision": current["decision"]}


@router.get("/file/{evidence_id}")
async def get_evidence_file(evidence_id: str, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = await db.evidence.find_one({"id": evidence_id})
    if not doc:
        raise HTTPException(404, "Evidence not found")
    owner = await db.sop_requests.find_one({"id": doc["request_id"]}) if doc.get("request_id") else await db.request_drafts.find_one({"id": doc.get("draft_id")})
    if not owner:
        raise HTTPException(404, "Associated request not found")
    await authorize_evidence(db, owner["employee_id"], current_user)
    path = Path(doc["storage_path"]).resolve()
    if not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
        raise HTTPException(404, "File content not found")
    return FileResponse(path, media_type=doc["content_type"], filename=doc["original_filename"],
                        headers={"X-Content-Type-Options": "nosniff"})


@router.get("/request/{request_id}")
async def list_request_evidence(request_id: str, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    request = await db.sop_requests.find_one({"id": request_id})
    if not request:
        raise HTTPException(404, "Request not found")
    await authorize_evidence(db, request["employee_id"], current_user)
    docs = await db.evidence.find({"request_id": request_id}).to_list(length=100)
    return [public_metadata(doc) for doc in docs]
