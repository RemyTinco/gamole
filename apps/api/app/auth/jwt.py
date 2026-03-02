"""JWT session management - ported from apps/api/src/auth/session.ts."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from ..config import settings


def create_session(user_id: str, workspace_id: str | None = None) -> str:
    """Create a JWT session token."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "userId": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.jwt_expiry_days)).timestamp()),
    }
    if workspace_id:
        payload["workspaceId"] = workspace_id

    return jwt.encode(payload, settings.session_secret, algorithm=settings.jwt_algorithm)


def validate_session(token: str) -> dict:
    """Validate and decode a JWT session token."""
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid or expired session token: {e}")
