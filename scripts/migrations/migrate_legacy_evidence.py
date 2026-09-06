"""Explicit, idempotent repair of old invalid request lifecycle values.

Read-only by default. Run from the repository root:
python scripts/migrations/migrate_legacy_evidence.py
Apply only to the intended database:
python scripts/migrations/migrate_legacy_evidence.py --apply
Never auto-approves. Legacy pending-evidence requests become human review requests.
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.database import get_mongodb_client
from app.models.audit import AuditEventType
from app.services.audit_service import create_audit_entry


async def migrate(db, apply=False):
    docs = await db.sop_requests.find({"status": "awaiting_evidence"}).to_list(length=10000)
    other = await db.sop_requests.find({"decision": "awaiting_evidence"}).to_list(length=10000)
    records = {doc["id"]: doc for doc in docs + other}
    changed = 0
    for doc in records.values():
        if not apply:
            continue
        result = await db.sop_requests.update_one({"id": doc["id"], "status": doc["status"], "decision": doc["decision"]},
            {"$set": {"status": "escalated", "decision": "routed", "updated_at": datetime.now(timezone.utc).isoformat(),
                      "evaluation_reasoning": "Legacy evidence collection request migrated to manager review. Evidence remains unverified."}})
        if result.matched_count:
            changed += 1
            await create_audit_entry(db, request_id=doc["id"], event_type=AuditEventType.ESCALATED,
                                     actor_id="system", actor_role="system", decision="routed",
                                     details={"reason": "legacy_evidence_lifecycle_migration"})
    return {"candidates": len(records), "changed": changed, "dry_run": not apply}


async def main(apply):
    client = get_mongodb_client()
    try:
        db = client.get_default_database()
    except Exception:
        db = client["sopforge"]
    print(await migrate(db, apply))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
