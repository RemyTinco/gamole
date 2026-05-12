"""Auth middleware - trusts tinyauth's Remote-User header from Caddy forward_auth."""

from fastapi import HTTPException, Request


async def auth_dependency(request: Request) -> dict:
    """Require a Remote-User header populated by tinyauth via Caddy forward_auth."""
    user = request.headers.get("Remote-User")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "userId": user,
        "email": request.headers.get("Remote-Email"),
        "name": request.headers.get("Remote-Name"),
        "groups": request.headers.get("Remote-Groups"),
    }
