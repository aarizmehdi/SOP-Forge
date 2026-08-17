"""
SOP Forge — Aziz Jan Group Mock SOP Generator
Generates realistic enterprise policies (EOBI, Leave, Biometric, Overtime) for factory logic.
Run: python -m scripts.generate_mock_sop
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import async_session_factory, engine, Base
from app.services.sop_service import ingest_sop_document


AZIZ_JAN_GROUP_SOP = """
# Aziz Jan Group — Factory Standard Operating Procedure (SOP) 2026

## 1. Purpose & Scope
This Standard Operating Procedure governs factory operations, HR administration, and payroll for Aziz Jan Group, encompassing A.J Textile Mills and Mohsin Match Factory across all locations (Peshawar, Lahore, Gadoon Swabi). It ensures strict compliance with enterprise standards and labor laws.

## 2. EOBI (Employees' Old-Age Benefits Institution) Policy
- **Mandatory Enrollment**: All factory workers must be enrolled in the EOBI pension scheme upon joining.
- **Contributions**:
  - The Employer (Aziz Jan Group) contributes an amount equal to 5% of the applicable minimum wage.
  - The Employee contributes 1% of the applicable minimum wage.
- **Deduction Rule**: The 1% employee contribution is automatically deducted from the monthly gross salary. Any discrepancies in EOBI deductions must be flagged to the HR department immediately.
- **System Verification**: EOBI status must be verified via the internal portal before processing any end-of-service benefits.

## 3. Leave Categories & Limits (Factory Workers)
- **Annual Leave**: Factory workers are entitled to 14 days of paid annual leave per calendar year. Requires 7 days advance notice unless escalated.
- **Casual Leave**: Entitled to 10 days of casual leave per calendar year. Maximum 2 consecutive days permitted.
- **Medical Leave**: Entitled to 8 days of medical leave per calendar year. Medical certificate mandatory for absences exceeding 2 consecutive days.
- **Auto-Approval Criteria**: Leaves may be auto-approved if the required balance is present, notice period is met, and team overlap is below 25%.
- **Override**: Department Heads have full authority to override leave rejections with a logged justification.

## 4. Biometric Attendance (ZKTeco) Policy
- **Integration**: All factory premises use ZKTeco biometric devices. Punches sync every 15 minutes.
- **Missed Punch Rule**: 
  - An employee who fails to record both punch-in and punch-out is marked Absent.
  - 3 consecutive missed punches (e.g., punching in but forgetting to punch out 3 days in a row) will result in an automatic half-day salary deduction.
- **Exemptions**: System or hardware failures must be logged by IT; affected employees are exempt from deductions during the downtime.
- **Override**: Department Heads can reverse biometric-based deductions by submitting an executive override in the SOP Forge portal.

## 5. Overtime & Compensation (Textile Spinning Staff)
- **Standard Working Hours**: 8 hours per day, 48 hours per week.
- **Overtime Rate**: Overtime is strictly compensated at 1.5x (one and a half times) the standard hourly rate.
- **Eligibility**: Only applicable to non-management factory floor staff, specifically Textile Spinning machine operators and floor supervisors.
- **Approval Limit**: Maximum 2 hours of overtime per day unless pre-approved by the Factory Manager. Overtime claims exceeding this limit without prior approval will be automatically rejected by the system.

## 6. Audit & Compliance
- **Immutability**: All decisions regarding payroll deductions, overtime approvals, and leave grants are recorded in an immutable audit ledger.
- **No Manual Deletion**: Once an action is recorded, it cannot be deleted. Adjustments require a new corrective entry with managerial justification.
"""


async def generate():
    """Seed the SOP vector store with the Aziz Jan Group policy."""
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        doc = await ingest_sop_document(
            db,
            title="Aziz Jan Group Factory SOP 2026",
            category="factory_hr",
            content_text=AZIZ_JAN_GROUP_SOP,
        )
        await db.commit()

        print(f"[OK] Aziz Jan Group SOP ingested successfully!")
        print(f"   Document ID: {doc.id}")
        print(f"   Title: {doc.title}")
        print(f"   Category: {doc.category}")
        
        # Count chunks
        from sqlalchemy import select, func
        from app.models.sop import SOPChunk
        chunk_count = await db.scalar(
            select(func.count(SOPChunk.id)).where(SOPChunk.document_id == doc.id)
        )
        print(f"   Chunks created: {chunk_count}")


if __name__ == "__main__":
    asyncio.run(generate())
