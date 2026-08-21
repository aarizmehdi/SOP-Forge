"""
SOP Forge — Database module.
MongoDB Async Client and Redis client.
"""

from collections.abc import AsyncGenerator
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

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


# ── MongoDB Client ──
# Global database client instance
mongodb_client: AsyncIOMotorClient = None

def get_mongodb_client() -> AsyncIOMotorClient:
    global mongodb_client
    if mongodb_client is None:
        # Use tlsAllowInvalidCertificates if running locally or avoiding cert issues
        mongodb_client = motor.motor_asyncio.AsyncIOMotorClient(
            settings.database_url, 
            serverSelectionTimeoutMS=5000,
            tlsAllowInvalidCertificates=True 
        )
    return mongodb_client

# ── Dependency Injection ──
async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """FastAPI dependency that yields the async MongoDB database instance."""
    client = get_mongodb_client()
    try:
        db = client.get_default_database()
    except Exception:
        # If no DB specified in URI, default to sopforge
        db = client["sopforge"]
    yield db


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
