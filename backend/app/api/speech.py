from fastapi import APIRouter, HTTPException
import httpx
from app.config import get_settings

router = APIRouter(prefix="/api/speech", tags=["Speech"])
settings = get_settings()

@router.get("/token")
async def get_speech_token():
    """
    Get a temporary authentication token for AssemblyAI streaming API.
    """
    if not settings.assemblyai_api_key or settings.assemblyai_api_key == "your-assemblyai-api-key-here":
        raise HTTPException(
            status_code=500, 
            detail="AssemblyAI API key is not configured."
        )

    url = "https://api.assemblyai.com/v2/realtime/token"
    headers = {
        "Authorization": settings.assemblyai_api_key
    }
    payload = {
        "expires_in": 3600  # Token valid for 1 hour
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return {"token": data["token"]}
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Failed to generate AssemblyAI token: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Error generating token: {str(e)}"
            )
