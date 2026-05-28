"""
Auth routes — create, list, and revoke API keys.

All endpoints here require a valid API key themselves (except they are
bootstrapped by the auto-generated first key printed to logs on startup).

POST   /auth/keys          — create a new key
GET    /auth/keys          — list all keys (hashes never returned)
DELETE /auth/keys/{id}     — revoke a key
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.auth.dependency import require_api_key
from src.auth import keys as key_svc

router = APIRouter(prefix="/auth", tags=["auth"])


class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100,
                      description="Human-readable label for this key e.g. 'prod-server' or 'dev-laptop'")


# ── Create ─────────────────────────────────────────────────────────────────────

@router.post(
    "/keys",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
    description=(
        "Generates a new `fca_` prefixed API key. "
        "The raw key is returned **once only** — save it immediately."
    ),
)
async def create_api_key(
    payload: CreateKeyRequest,
    _key=Depends(require_api_key),
) -> dict:
    return await key_svc.create_key(name=payload.name)


# ── List ───────────────────────────────────────────────────────────────────────

@router.get(
    "/keys",
    summary="List all API keys",
    description="Returns all keys with metadata. Raw key values and hashes are never returned.",
)
async def list_api_keys(_key=Depends(require_api_key)) -> list[dict]:
    return await key_svc.list_keys()


# ── Revoke ─────────────────────────────────────────────────────────────────────

@router.delete(
    "/keys/{key_id}",
    status_code=status.HTTP_200_OK,
    summary="Revoke an API key",
    description="Soft-deletes the key (sets is_active=FALSE). Cannot be undone.",
)
async def revoke_api_key(
    key_id: UUID,
    _key=Depends(require_api_key),
) -> dict:
    revoked = await key_svc.revoke_key(key_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key {key_id} not found or already revoked.",
        )
    return {"message": f"Key {key_id} revoked successfully."}
