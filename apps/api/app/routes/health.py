"""Health endpoint - ported from apps/api/src/routes/health.ts."""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "gamole-api",
    }
