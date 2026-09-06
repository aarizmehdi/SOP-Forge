"""Read-only environment availability probe. Never prints credentials or connection URLs."""
import asyncio
import importlib.metadata
from app.config import get_settings
from app.database import get_mongodb_client


async def main():
    settings = get_settings()
    print({"deepseek_configured": settings.is_llm_configured, "embeddings_configured": bool(settings.openai_api_key)})
    for name in ("pydantic", "fastapi", "langgraph", "langchain-openai", "motor"):
        print(name, importlib.metadata.version(name))
    try:
        await get_mongodb_client().admin.command("ping")
        print("mongodb_ping=ok")
    except Exception as exc:
        print("mongodb_ping=unavailable", type(exc).__name__)


if __name__ == '__main__':
    asyncio.run(main())
