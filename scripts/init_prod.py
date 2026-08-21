import asyncio
import sys
import os
import uuid

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.auth.jwt import hash_password
from app.database import get_mongodb_client
from app.models.user import Department, User, UserRole
from app.services.sop_service import ingest_sop_document

# Default password
DEFAULT_PASSWORD = "password123"

async def init_prod_db():
    print("Checking database status...")
    client = get_mongodb_client()
    try:
        db = client.get_default_database()
    except Exception:
        db = client["sopforge"]

    # Check if users already exist
    existing_user = await db.users.find_one({})

    if existing_user:
        print("[OK] Database already initialized. Skipping seed.")
        return

    print("Database is empty. Running initial production seed...")
    
    # ── 1. Create Departments ──
    eng_dept_id = str(uuid.uuid4())
    mkt_dept_id = str(uuid.uuid4())
    hr_dept_id = str(uuid.uuid4())
    exec_dept_id = str(uuid.uuid4())

    departments = [
        Department(id=eng_dept_id, name="Engineering", description="Software development team"),
        Department(id=mkt_dept_id, name="Marketing", description="Marketing and communications"),
        Department(id=hr_dept_id, name="HR", description="Human resources and compliance"),
        Department(id=exec_dept_id, name="Executive", description="C-suite and VP leadership"),
    ]
    await db.departments.insert_many([d.model_dump(mode="json") for d in departments])

    # ── 2. Create Users ──
    hashed_pw = hash_password(DEFAULT_PASSWORD)
    
    exec_id = str(uuid.uuid4())
    executive = User(
        id=exec_id, employee_id="EMP008", name="Tariq Rashid", email="tariq.rashid@company.com",
        hashed_password=hashed_pw, role=UserRole.EXECUTIVE, department_id=exec_dept_id,
    )
    
    eng_mgr_id = str(uuid.uuid4())
    eng_manager = User(
        id=eng_mgr_id, employee_id="EMP006", name="Bilal Hussain", email="bilal.hussain@company.com",
        hashed_password=hashed_pw, role=UserRole.MANAGER, department_id=eng_dept_id, manager_id=exec_id,
    )
    
    admin_id = str(uuid.uuid4())
    admin_user = User(
        id=admin_id, employee_id="EMP009", name="Nadia Bukhari", email="nadia.bukhari@company.com",
        hashed_password=hashed_pw, role=UserRole.ADMIN, department_id=hr_dept_id, manager_id=exec_id,
    )

    employee = User(
        id=str(uuid.uuid4()), employee_id="EMP001", name="Aisha Khan", email="aisha.khan@company.com",
        hashed_password=hashed_pw, role=UserRole.EMPLOYEE, department_id=eng_dept_id, manager_id=eng_mgr_id,
    )

    await db.users.insert_many([
        executive.model_dump(mode="json"),
        eng_manager.model_dump(mode="json"),
        admin_user.model_dump(mode="json"),
        employee.model_dump(mode="json"),
    ])

    # Set heads
    await db.departments.update_one({"name": "Engineering"}, {"$set": {"head_user_id": eng_mgr_id}})
    await db.departments.update_one({"name": "HR"}, {"$set": {"head_user_id": admin_id}})
    await db.departments.update_one({"name": "Executive"}, {"$set": {"head_user_id": exec_id}})

    # ── 3. Create Basic SOPs ──
    print("Ingesting SOPs and generating embeddings...")
    sops = [
        {
            "title": "Hardware Request Policy",
            "category": "IT",
            "content_text": "Employees can request standard hardware (laptops, monitors). Requires manager approval. If cost > $1000, requires executive approval."
        },
        {
            "title": "Leave Application Policy",
            "category": "HR",
            "content_text": "Annual leaves must be requested 2 weeks in advance. Sick leaves can be applied on the same day. All leaves require manager approval."
        }
    ]
    for sop in sops:
        await ingest_sop_document(
            db, 
            title=sop["title"], 
            category=sop["category"], 
            content_text=sop["content_text"], 
            created_by=admin_id
        )

    print("[OK] Production database successfully initialized and seeded!")

if __name__ == "__main__":
    asyncio.run(init_prod_db())
