"""Auth middleware - ported from apps/api/src/auth/middleware.ts."""

from fastapi import HTTPException, Request

from .jwt import validate_session


async def auth_dependency(request: Request) -> dict:
    """FastAPI dependency that validates JWT Bearer token."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = auth_header[7:]
    if not token or len(token) < 10:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = validate_session(token)
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
