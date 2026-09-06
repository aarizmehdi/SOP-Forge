"""Typed policy retrieval boundary for the current MongoDB/Python implementation."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services import sop_service

logger = logging.getLogger(__name__)


class PolicyRetrievalStatus(str, Enum):
    """Outcome of a policy lookup, independent of request decision rules."""

    MATCH = "match"
    NO_MATCH = "no_match"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass(frozen=True)
class PolicyRetrievalResult:
    status: PolicyRetrievalStatus
    chunks: list[dict] = field(default_factory=list)


class PolicyRetrievalAdapter(Protocol):
    async def retrieve(
        self,
        db: AsyncIOMotorDatabase,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
    ) -> PolicyRetrievalResult: ...


class MongoPythonPolicyRetrievalAdapter:
    """Adapter around MongoDB chunk storage and Python similarity scoring."""

    async def retrieve(
        self,
        db: AsyncIOMotorDatabase,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
    ) -> PolicyRetrievalResult:
        try:
            chunks = await sop_service.search_policy(
                db,
                query=query,
                top_k=top_k,
                category=category,
            )
        except Exception:
            logger.exception("Policy retrieval failed")
            return PolicyRetrievalResult(PolicyRetrievalStatus.ERROR)

        if not chunks:
            return PolicyRetrievalResult(PolicyRetrievalStatus.NO_MATCH)
        if any(chunk.get("retrieval_mode") != "semantic" for chunk in chunks):
            return PolicyRetrievalResult(PolicyRetrievalStatus.DEGRADED, chunks)
        return PolicyRetrievalResult(PolicyRetrievalStatus.MATCH, chunks)


_adapter: PolicyRetrievalAdapter = MongoPythonPolicyRetrievalAdapter()


def get_policy_retrieval_adapter() -> PolicyRetrievalAdapter:
    """Return the configured retrieval boundary."""
    return _adapter
