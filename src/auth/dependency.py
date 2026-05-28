"""
auth/dependency.py — FastAPI security dependency.

Usage in a route:
    from src.auth.dependency import require_api_key

    @router.get("/protected")
    async def protected(key=Depends(require_api_key)):
        ...

Routes that do NOT require auth (public):
    /health, /metrics, /dashboard, /docs, /redoc, /openapi.json
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from src.auth.keys import validate_key


async def require_api_key(request: Request) -> dict:
    """
    Dependency that validates the X-API-Key header.
    Reads directly from request headers — works correctly at router level.
    Raises 401 if missing, 403 if invalid or revoked.
    Returns the key record on success.

    OPTIONS requests (CORS preflight) are passed through without auth
    so the CORS middleware can respond correctly to the browser.
    """
    # CORS preflight — let the CORS middleware handle it, no auth needed
    if request.method == "OPTIONS":
        return {}

    raw_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_record = await validate_key(raw_key)

    if key_record is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or revoked API key.",
        )

    return key_record
