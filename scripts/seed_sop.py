"""
SOP Forge — Master SOP Manual Seeder.
Clears old SOP books & requests, then ingests 4 comprehensive, department-level SOP manuals:
1. HR & Leave Policy Manual (category: leave)
2. Finance & Expense Reimbursements Manual (category: reimbursement)
3. IT Infrastructure & Security SOP (category: it_access)
4. General Operations & Administration SOP (category: general)

Run: python -m scripts.seed_sop
"""

import asyncio
import os
import sys
import uuid

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import delete, func, select
from app.database import Base, async_session_factory, engine
from app.models.audit import AuditLog
from app.models.request import RequestHistory, SOPRequest
from app.models.sop import SOPChunk, SOPDocument
from app.services.sop_service import ingest_sop_document

# ════════════════════════════════════════════════════════════════════
# 1. HR & LEAVE POLICY MANUAL
# ════════════════════════════════════════════════════════════════════
HR_LEAVE_SOP_TEXT = """# Master HR & Leave Policy Manual — Standard Operating Procedure

## 1. Overview & Purpose
This Standard Operating Procedure (SOP) governs all employee leave requests, attendance monitoring, and remote work policies within the organization. It applies to all full-time and part-time staff across all departments. The objective is to maintain operational continuity while supporting employee well-being.

## 2. Leave Categories & Entitlements

### 2.1 Annual Leave (Paid Time Off)
Annual leave is accrued on a monthly basis (1/12 of total entitlement per month). Entitlements are determined by tenure and organizational grade:
- **0 to 2 years of service**: 10 working days per calendar year.
- **2 to 5 years of service**: 15 working days per calendar year.
- **5+ years of service**: 20 working days per calendar year.
- **Management level (Manager and above)**: 18 to 25 working days based on grade.
- **Carryover Limit**: A maximum of 5 unused annual leave days may be carried forward into the next calendar year. Any excess beyond 5 days is automatically forfeited on January 1st.
- **Encashment**: Annual leave encashment is strictly not permitted during active employment.

### 2.2 Sick Leave
Sick leave is provided for medical recovery, illness, or medical appointments:
- **Entitlement**: 8 working days per year for general staff; 10 working days for management level.
- **Medical Documentation**: A formal medical certificate from a licensed physician is mandatory for sick leave exceeding 2 consecutive working days. The certificate must be submitted within 3 working days of returning to duty.
- **Notification**: Employees must notify their direct manager via SOP Forge within 1 hour of their scheduled shift start time.
- **Carryover**: Sick leave does not carry over to subsequent calendar years.

### 2.3 Casual Leave
Casual leave is intended for urgent, unforeseen personal matters that cannot be scheduled in advance:
- **Entitlement**: 5 working days per year for staff; 7 working days for management level.
- **Duration Limit**: Maximum of 3 consecutive working days per instance.
- **Notice**: Advance notice must be provided as early as possible on the day of absence.
- **Carryover**: Unused casual leave lapses at year-end.

### 2.4 Unpaid Leave
Unpaid leave may be requested when all paid leave balances have been exhausted:
- **Availability**: Requires prior approval from the Department Head and HR Manager.
- **Maximum Duration**: 30 calendar days per year maximum, unless special executive waiver is granted.
- **Impact**: Unpaid leave results in proportional deduction from monthly salary.

## 3. Leave Application Rules & Notice Periods

### 3.1 Advance Notice Requirements
Leave applications must adhere to the following advance notice guidelines:
- **1 to 3 days annual leave**: Minimum 3 working days advance notice.
- **4 to 7 days annual leave**: Minimum 7 working days advance notice.
- **8+ days annual leave**: Minimum 14 working days advance notice.
- **Casual leave**: Minimum notification prior to shift start time.
- **Sick leave**: Notification within 1 hour of shift start time.

### 3.2 Attendance & Blackout Constraints
- **Attendance Rate**: Employees with a 30-day attendance rate below 80% will have non-urgent leave requests escalated to their manager for review.
- **Blackout Periods**: Annual and casual leave are restricted during year-end financial close (December 28 to December 31) and quarter-end close (last 2 days of March, June, and September). Sick leave with medical proof is exempt.
- **Team Absence Cap**: No more than 30% of a team may be on leave simultaneously. If team size is 3 or fewer, at least 1 member must remain on duty.

## 4. Remote Work & Hybrid Policy
- **WFH Allowance**: Eligible employees may work remotely up to 2 days per week.
- **Approval**: Remote work days must be requested 24 hours in advance and approved by the direct manager.
"""

# ════════════════════════════════════════════════════════════════════
# 2. FINANCE & EXPENSE REIMBURSEMENT MANUAL
# ════════════════════════════════════════════════════════════════════
FINANCE_SOP_TEXT = """# Master Finance & Expense Reimbursement Manual — Standard Operating Procedure

## 1. Purpose & Scope
This SOP outlines the rules, limits, and submission procedures for business-related expense reimbursements, travel allowances, and equipment purchases. All expenses must be legitimate business expenditures supported by valid documentation.

## 2. Expense Categories & Policy Limits

### 2.1 Business Travel & Daily Allowances
- **Per Diem Allowance**: Daily travel allowance is capped at $150 per day for domestic travel to cover meals and local transport.
- **Lodging & Flights**: Hotel accommodation and flight bookings must be pre-arranged through the Finance Operations desk.
- **Receipt Threshold**: Itemized receipts are mandatory for any individual expense item exceeding $25.

### 2.2 Medical & Outpatient Reimbursements
- **Annual Cap**: Employees are entitled to up to $500 per calendar year for outpatient medical consultation and prescribed medicines.
- **Documentation**: Submissions must include original clinic receipts and doctor's prescriptions.

### 2.3 Workstation Equipment & Accessories
- **Self-Purchase Allowance**: Employees may claim up to $200 per year for work-related hardware accessories (monitors, keyboards, headsets).
- **Major Hardware**: Equipment purchases exceeding $200 require prior written approval from the IT Manager and Finance Director.

## 3. Claim Submission & Approval Thresholds

### 3.1 Automated & Manual Routing Thresholds
- **Under $100**: Auto-approved if category limit is not exceeded and valid receipt is attached.
- **$100 to $500**: Evaluated against policy rules; requires Direct Manager sign-off.
- **$500 to $2,000**: Requires Department Head and Finance Manager approval.
- **Over $2,000**: Escalated to Executive VP and CFO for mandatory sign-off.

### 3.2 Monthly Cutoff & Payout Timeline
- **Cutoff Date**: Expense claims submitted by the 20th of the month are processed in the current month's payroll cycle.
- **Late Submissions**: Claims submitted after the 20th will be processed in the subsequent month's payroll cycle.
"""

# ════════════════════════════════════════════════════════════════════
# 3. IT INFRASTRUCTURE & SECURITY SOP
# ════════════════════════════════════════════════════════════════════
IT_SECURITY_SOP_TEXT = """# Master IT Infrastructure & Security SOP — Standard Operating Procedure

## 1. Overview
This Standard Operating Procedure governs access control, software permissions, hardware lifecycle, and cybersecurity protocols across the organization.

## 2. System Access & Permission Levels

### 2.1 Standard Software Access (Developer / Staff Tier)
- **Covered Systems**: GitHub Repositories, Jira Workspaces, Figma, Slack Admin.
- **Auto-Approval**: Write/Developer access to team GitHub repos and Jira projects is auto-approved for verified Engineering and Product department staff.

### 2.2 Privileged & Production Access (Admin Tier)
- **Covered Systems**: AWS Production Account, Production Database, Core Router VPN.
- **Security Escalation**: All admin and production access requests are automatically escalated to the Head of IT Security with a strict 2-hour SLA.
- **Justification**: Requests must include business justification and duration (temporary access default: 30 days).

## 3. Hardware Lifecycle & Security Controls

### 3.1 Device Refresh & Replacement
- **Laptops**: Laptops are eligible for replacement every 3 years or upon verified physical failure confirmed by IT Support.
- **Asset Return**: All company hardware must be surrendered to IT upon employee departure.

### 3.2 Cybersecurity Compliance
- **Two-Factor Authentication (2FA)**: 2FA is mandatory across all enterprise systems.
- **Offboarding Revocation**: User accounts and credentials must be fully revoked within 2 hours of HR offboarding notification.
"""

# ════════════════════════════════════════════════════════════════════
# 4. GENERAL OPERATIONS & FACILITY MANAGEMENT SOP
# ════════════════════════════════════════════════════════════════════
OPERATIONS_SOP_TEXT = """# Master General Operations & Facility Management SOP — Standard Operating Procedure

## 1. Purpose
This procedure defines guidelines for facility usage, meeting room reservations, after-hours office access, and visitor management.

## 2. Facility Usage & Access Control

### 2.1 Meeting Room Reservations
- **Main Boardroom**: Main Executive Boardroom bookings require 24-hour advance reservation via the SOP Forge portal.
- **Standard Huddle Rooms**: Available on a first-come, first-served basis for meetings under 1 hour.

### 2.2 Weekend & After-Hours Office Access
- **Requirement**: Working in the office outside standard hours (Weekends or 8:00 PM – 7:00 AM) requires a Security Access Request.
- **Submission**: Requests must be submitted by Friday 4:00 PM for weekend access.

### 2.3 Guest & Visitor Policy
- **Registration**: All external visitors must be registered at reception with host employee notification.
- **Escort**: Visitors must be escorted by host staff at all times within secure work areas.
"""


async def seed():
    """Clear old database state and seed 4 Master SOP manuals."""
    print("1. Initializing Database Schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        print("\n2. Clearing old requests, audit logs, and old SOP books...")
        await db.execute(delete(RequestHistory))
        await db.execute(delete(AuditLog))
        await db.execute(delete(SOPRequest))
        await db.execute(delete(SOPChunk))
        await db.execute(delete(SOPDocument))
        await db.commit()
        print("   [OK] Old database state cleared cleanly!")

        print("\n3. Ingesting & Embedding Master SOP Books...")

        books = [
            ("Master HR & Leave Policy Manual", "leave", HR_LEAVE_SOP_TEXT),
            ("Master Finance & Expense Reimbursement Manual", "reimbursement", FINANCE_SOP_TEXT),
            ("Master IT Infrastructure & Security SOP", "it_access", IT_SECURITY_SOP_TEXT),
            ("Master General Operations & Facility SOP", "general", OPERATIONS_SOP_TEXT),
        ]

        for title, category, text_content in books:
            doc = await ingest_sop_document(
                db,
                title=title,
                category=category,
                content_text=text_content,
            )
            await db.commit()

            # Count chunks
            chunk_count = await db.scalar(
                select(func.count(SOPChunk.id)).where(SOPChunk.document_id == doc.id)
            )
            print(f"   [OK] Ingested '{title}' (Category: {category}) -> {chunk_count} clean paragraph chunks")

        print("\n[SUCCESS] Master SOP Books ingested cleanly into SOP Forge Vector Database!")


if __name__ == "__main__":
    asyncio.run(seed())
