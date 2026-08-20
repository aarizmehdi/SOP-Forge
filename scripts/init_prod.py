import asyncio
import sys
import os
import uuid
from sqlalchemy import select

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.auth.jwt import hash_password
from app.database import async_session_factory, engine, Base
from app.models.user import Department, User, UserRole
from app.models.sop import SOP

# Default password
DEFAULT_PASSWORD = "password123"

async def init_prod_db():
    print("Checking database status...")
    # Safely create tables if they don't exist (Never drops tables!)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # Check if users already exist
        result = await db.execute(select(User).limit(1))
        existing_user = result.scalars().first()

        if existing_user:
            print("[OK] Database already initialized. Skipping seed.")
            return

        print("Database is empty. Running initial production seed...")
        
        # ── 1. Create Departments ──
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

        # ── 2. Create Users ──
        hashed_pw = hash_password(DEFAULT_PASSWORD)
        
        exec_id = uuid.uuid4()
        executive = User(
            id=exec_id, employee_id="EMP008", name="Tariq Rashid", email="tariq.rashid@company.com",
            hashed_password=hashed_pw, role=UserRole.EXECUTIVE, department_id=exec_dept_id,
        )
        db.add(executive)

        eng_mgr_id = uuid.uuid4()
        eng_manager = User(
            id=eng_mgr_id, employee_id="EMP006", name="Bilal Hussain", email="bilal.hussain@company.com",
            hashed_password=hashed_pw, role=UserRole.MANAGER, department_id=eng_dept_id, manager_id=exec_id,
        )
        db.add(eng_manager)
        
        admin_id = uuid.uuid4()
        admin_user = User(
            id=admin_id, employee_id="EMP009", name="Nadia Bukhari", email="nadia.bukhari@company.com",
            hashed_password=hashed_pw, role=UserRole.ADMIN, department_id=hr_dept_id, manager_id=exec_id,
        )
        db.add(admin_user)

        employee = User(
            id=uuid.uuid4(), employee_id="EMP001", name="Aisha Khan", email="aisha.khan@company.com",
            hashed_password=hashed_pw, role=UserRole.EMPLOYEE, department_id=eng_dept_id, manager_id=eng_mgr_id,
        )
        db.add(employee)

        # Set heads
        for dept in departments:
            if dept.name == "Engineering": dept.head_user_id = eng_mgr_id
            elif dept.name == "HR": dept.head_user_id = admin_id
            elif dept.name == "Executive": dept.head_user_id = exec_id

        await db.flush()
        
        # ── 3. Create Basic SOPs ──
        sops = [
            SOP(
                id=uuid.uuid4(), title="Hardware Request Policy",
                content="""Employees can request standard hardware (laptops, monitors). 
                Requires manager approval. If cost > $1000, requires executive approval.""",
                version="1.0", author_id=admin_id,
            ),
            SOP(
                id=uuid.uuid4(), title="Leave Application Policy",
                content="""Annual leaves must be requested 2 weeks in advance. 
                Sick leaves can be applied on the same day. All leaves require manager approval.""",
                version="1.0", author_id=admin_id,
            )
        ]
        for sop in sops:
            db.add(sop)

        await db.commit()
        print("[OK] Production database successfully initialized and seeded!")

if __name__ == "__main__":
    asyncio.run(init_prod_db())
