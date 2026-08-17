"""
SOP Forge — Clean Database Script.
Drops all tables, recreates them, and seeds users and SOPs.
Run: python -m scripts.clean_db
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import engine, Base
# Import all models so metadata knows about them
import app.models
from scripts.seed_users import seed as seed_users
from scripts.seed_sop import seed as seed_sops

async def clean_and_seed():
    print("Dropping all database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("Recreating all database tables...")
        await conn.run_sync(Base.metadata.create_all)
    
    print("\n--- Seeding Users ---")
    # seed_users drops and creates again, but that's fine.
    await seed_users()
    
    print("\n--- Seeding SOPs ---")
    await seed_sops()
    
    print("\n[SUCCESS] Database is completely clean and ready for production!")

if __name__ == "__main__":
    asyncio.run(clean_and_seed())
