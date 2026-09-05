"""
SOP Forge — FastAPI application entry point.
Governed AI engine for internal SOP request processing.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import close_redis, init_redis

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and cleanup resources."""
    # Initialize DB (No schema needed for MongoDB)
    logger.info("Database initialized (MongoDB)")

    # Initialize Redis
    try:
        await init_redis()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed (non-critical): {e}")

    # Log LLM status
    if settings.is_llm_configured:
        logger.info("✅ DeepSeek V4 Pro API configured")
    else:
        logger.info("ℹ️ LLM not configured — using rule-based fallback")

    logger.info("🚀 SOP Forge ready")

    yield

    # Cleanup
    await close_redis()
    logger.info("👋 SOP Forge shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SOP Forge",
        description=(
            "Internal SOP AI Agent — Governed Employee Request Engine. "
            "Digitizes organizational SOP manuals into a governed, queryable rule engine."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Register API Routers ──
    from app.api.admin import router as admin_router
    from app.api.audit import router as audit_router
    from app.api.auth import router as auth_router
    from app.api.evidence import router as evidence_router
    from app.api.incident import router as incident_router
    from app.api.request import router as request_router
    from app.api.review import router as review_router
    from app.api.speech import router as speech_router

    app.include_router(auth_router)
    app.include_router(request_router)
    app.include_router(review_router)
    app.include_router(admin_router)
    app.include_router(audit_router)
    app.include_router(incident_router)
    app.include_router(speech_router)
    app.include_router(evidence_router)

    # ── Health Check (must be before static mount) ──
    @app.get("/health", tags=["System"])
    async def health_check():
        """System health check."""
        from app.database import redis_client

        redis_ok = False
        try:
            if redis_client:
                await redis_client.ping()
                redis_ok = True
        except Exception:
            pass

        return {
            "status": "healthy",
            "service": "SOP Forge",
            "version": "0.1.0",
            "llm_configured": settings.is_llm_configured,
            "redis_connected": redis_ok,
        }

    # ── Serve Frontend Static Files (catch-all, must be last) ──
    import os
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
    if os.path.exists(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

    return app


# Create the app instance
app = create_app()
