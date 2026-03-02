"""Admin endpoints."""

from fastapi import APIRouter, Depends

from ..auth.middleware import auth_dependency

router = APIRouter()


@router.get("/admin/metrics", dependencies=[Depends(auth_dependency)])
async def get_metrics():
    """30-day metrics (stub)."""
    return {
        "totalWorkflows": 0,
        "completedWorkflows": 0,
        "averageQualityScore": 0,
        "totalAgentRuns": 0,
        "period": "30d",
    }
