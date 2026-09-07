"""Clear transactional/demo data while preserving organization configuration.

Dry run: python scripts/maintenance/clear_test_transactional_data.py
Execute: python scripts/maintenance/clear_test_transactional_data.py --confirm CLEAR-TEST-TRANSACTIONAL-DATA
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

CONFIRMATION = "CLEAR-TEST-TRANSACTIONAL-DATA"
TRANSACTIONAL_COLLECTIONS = ("sop_requests", "request_drafts", "request_history", "evidence", "hr_incidents")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", help="Override MONGO_URI for this run.")
    parser.add_argument("--confirm", help=f"Required destructive confirmation: {CONFIRMATION}")
    return parser.parse_args()

async def run() -> None:
    args = parse_args()
    repository_root = Path(__file__).resolve().parents[2]
    load_dotenv(repository_root / ".env")
    load_dotenv(repository_root / "backend" / ".env")
    uri = args.mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/sopforge")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000, tlsAllowInvalidCertificates=True)
    try:
        database = client.get_default_database(default="sopforge")
        evidence_docs = await database.evidence.find({}, {"storage_path": 1, "_id": 0}).to_list(length=None)
        counts = {name: await database[name].count_documents({}) for name in TRANSACTIONAL_COLLECTIONS}
        audit_filter = {"event_type": {"$ne": "sop_updated"}}
        counts["request_related_audit_logs"] = await database.audit_logs.count_documents(audit_filter)
        print("Planned transactional cleanup:")
        for name, count in counts.items(): print(f"  {name}: {count}")
        print(f"  evidence files referenced: {len(evidence_docs)}")
        print("Preserved: users, departments, sop_documents, sop_chunks, SOP maintenance audit entries, configuration")
        if args.confirm != CONFIRMATION:
            print(f"Dry run only. Re-run with --confirm {CONFIRMATION} to execute.")
            return
        for name in TRANSACTIONAL_COLLECTIONS: await database[name].delete_many({})
        await database.audit_logs.delete_many(audit_filter)
        upload_roots = {
            (repository_root / "uploads" / "evidence").resolve(),
            (repository_root / "backend" / "uploads" / "evidence").resolve(),
        }
        deleted_files = 0
        for item in evidence_docs:
            raw_path = item.get("storage_path")
            if not raw_path: continue
            path = Path(raw_path).resolve()
            if any(path.is_relative_to(root) for root in upload_roots) and path.is_file():
                path.unlink()
                deleted_files += 1
        print(f"Cleanup complete. Deleted {deleted_files} referenced evidence files.")
    finally:
        client.close()

if __name__ == "__main__": asyncio.run(run())
