"""
SOP Forge — Database module.
Async SQLAlchemy engine, session factory, and Redis client.
"""

from collections.abc import AsyncGenerator

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ── InMemory Redis Fallback ──
class InMemoryRedis:
    def __init__(self):
        self._data = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, *args, **kwargs):
        self._data[key] = value
        return True

    async def setex(self, key: str, time: int, value: str):
        self._data[key] = value
        return True

    async def delete(self, key: str):
        self._data.pop(key, None)
        return True

    async def ping(self):
        return True

    async def close(self):
        pass


# ── Database URL Determination ──
import os
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SQLITE_PATH = os.path.join(ROOT_DIR, "sopforge.db").replace("\\", "/")

db_url = settings.database_url

# Determine database engine options
if "sqlite" in db_url or "sopforge_dev" in db_url:
    # Default to SQLite for local standalone development
    db_url = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH}"
    engine = create_async_engine(db_url, echo=False, connect_args={"timeout": 30.0})
else:
    try:
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
    except Exception:
        db_url = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH}"
        engine = create_async_engine(db_url, echo=False, connect_args={"timeout": 30.0})

# Enable WAL mode for SQLite
from sqlalchemy import event
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in str(db_url):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.close()

# ── Session Factory ──
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Redis Client ──
redis_client = None


async def init_redis():
    """Initialize the Redis connection pool with fallback to in-memory store."""
    global redis_client
    try:
        client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=1.0,
        )
        await client.ping()
        redis_client = client
    except Exception:
        redis_client = InMemoryRedis()
    return redis_client


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global redis_client
    if redis_client and hasattr(redis_client, "close"):
        await redis_client.close()
        redis_client = None


def get_redis():
    """Get the active Redis client."""
    global redis_client
    if redis_client is None:
        redis_client = InMemoryRedis()
    return redis_client


# ── Base Model ──
class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""
    pass


# ── Dependency Injection ──
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
