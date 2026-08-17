"""
SOP Forge — Seed Users script.
Creates sample users across all roles with proper department hierarchy.
Run: python -m scripts.seed_users
"""

import asyncio
import sys
import os
import uuid

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.auth.jwt import hash_password
from app.database import async_session_factory, engine, Base
from app.models.user import Department, User, UserRole


# Default password for all seed users
DEFAULT_PASSWORD = "password123"


async def seed():
    """Seed the database with sample users and departments."""
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # ── Create Departments ──
        eng_dept_id = uuid.uuid4()
        mkt_dept_id = uuid.uuid4()
        hr_dept_id = uuid.uuid4()
        exec_dept_id = uuid.uuid4()

        departments = [
            Department(id=eng_dept_id, name="Engineering", description="Software development team"),
            Department(id=mkt_dept_id, name="Marketing", description="Marketing and communications"),
            Department(id=hr_dept_id, name="HR", description="Human resources and compliance"),
            Department(id=exec_dept_id, name="Executive", description="C-suite and VP leadership"),
        ]

        for dept in departments:
            db.add(dept)
        await db.flush()

        # ── Create Users ──
        hashed_pw = hash_password(DEFAULT_PASSWORD)

        # Executive
        exec_id = uuid.uuid4()
        executive = User(
            id=exec_id,
            employee_id="EMP008",
            name="Tariq Rashid",
            email="tariq.rashid@company.com",
            hashed_password=hashed_pw,
            role=UserRole.EXECUTIVE,
            department_id=exec_dept_id,
        )
        db.add(executive)

        # Engineering Manager
        eng_mgr_id = uuid.uuid4()
        eng_manager = User(
            id=eng_mgr_id,
            employee_id="EMP006",
            name="Bilal Hussain",
            email="bilal.hussain@company.com",
            hashed_password=hashed_pw,
            role=UserRole.MANAGER,
            department_id=eng_dept_id,
            manager_id=exec_id,
        )
        db.add(eng_manager)

        # Marketing Manager
        mkt_mgr_id = uuid.uuid4()
        mkt_manager = User(
            id=mkt_mgr_id,
            employee_id="EMP007",
            name="Zainab Malik",
            email="zainab.malik@company.com",
            hashed_password=hashed_pw,
            role=UserRole.MANAGER,
            department_id=mkt_dept_id,
            manager_id=exec_id,
        )
        db.add(mkt_manager)

        # Admin (HR)
        admin_id = uuid.uuid4()
        admin_user = User(
            id=admin_id,
            employee_id="EMP009",
            name="Nadia Bukhari",
            email="nadia.bukhari@company.com",
            hashed_password=hashed_pw,
            role=UserRole.ADMIN,
            department_id=hr_dept_id,
            manager_id=exec_id,
        )
        db.add(admin_user)

        # Employees
        employees = [
            User(
                id=uuid.uuid4(),
                employee_id="EMP001",
                name="Aisha Khan",
                email="aisha.khan@company.com",
                hashed_password=hashed_pw,
                role=UserRole.EMPLOYEE,
                department_id=eng_dept_id,
                manager_id=eng_mgr_id,
            ),
            User(
                id=uuid.uuid4(),
                employee_id="EMP002",
                name="Omar Farooq",
                email="omar.farooq@company.com",
                hashed_password=hashed_pw,
                role=UserRole.EMPLOYEE,
                department_id=eng_dept_id,
                manager_id=eng_mgr_id,
            ),
            User(
                id=uuid.uuid4(),
                employee_id="EMP003",
                name="Sara Ahmed",
                email="sara.ahmed@company.com",
                hashed_password=hashed_pw,
                role=UserRole.EMPLOYEE,
                department_id=mkt_dept_id,
                manager_id=mkt_mgr_id,
            ),
            User(
                id=uuid.uuid4(),
                employee_id="EMP004",
                name="Hassan Ali",
                email="hassan.ali@company.com",
                hashed_password=hashed_pw,
                role=UserRole.EMPLOYEE,
                department_id=eng_dept_id,
                manager_id=eng_mgr_id,
            ),
            User(
                id=uuid.uuid4(),
                employee_id="EMP005",
                name="Fatima Zahra",
                email="fatima.zahra@company.com",
                hashed_password=hashed_pw,
                role=UserRole.EMPLOYEE,
                department_id=mkt_dept_id,
                manager_id=mkt_mgr_id,
            ),
        ]

        for emp in employees:
            db.add(emp)

        # Set department heads
        for dept in departments:
            if dept.name == "Engineering":
                dept.head_user_id = eng_mgr_id
            elif dept.name == "Marketing":
                dept.head_user_id = mkt_mgr_id
            elif dept.name == "HR":
                dept.head_user_id = admin_id
            elif dept.name == "Executive":
                dept.head_user_id = exec_id

        await db.commit()

        print("[OK] Database seeded successfully!")
        print()
        print("Users created (all passwords: 'password123'):")
        print("-" * 60)
        print(f"  {'Role':<12} {'Employee ID':<12} {'Name':<20} {'Email'}")
        print("-" * 60)
        print(f"  {'ADMIN':<12} {'EMP009':<12} {'Nadia Bukhari':<20} nadia.bukhari@company.com")
        print(f"  {'EXECUTIVE':<12} {'EMP008':<12} {'Tariq Rashid':<20} tariq.rashid@company.com")
        print(f"  {'MANAGER':<12} {'EMP006':<12} {'Bilal Hussain':<20} bilal.hussain@company.com")
        print(f"  {'MANAGER':<12} {'EMP007':<12} {'Zainab Malik':<20} zainab.malik@company.com")
        print(f"  {'EMPLOYEE':<12} {'EMP001':<12} {'Aisha Khan':<20} aisha.khan@company.com")
        print(f"  {'EMPLOYEE':<12} {'EMP002':<12} {'Omar Farooq':<20} omar.farooq@company.com")
        print(f"  {'EMPLOYEE':<12} {'EMP003':<12} {'Sara Ahmed':<20} sara.ahmed@company.com")
        print(f"  {'EMPLOYEE':<12} {'EMP004':<12} {'Hassan Ali':<20} hassan.ali@company.com")
        print(f"  {'EMPLOYEE':<12} {'EMP005':<12} {'Fatima Zahra':<20} fatima.zahra@company.com")


if __name__ == "__main__":
    asyncio.run(seed())
