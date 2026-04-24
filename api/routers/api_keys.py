"""
api/routers/api_keys.py — Manage per-user encrypted API keys.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.models.db import get_db, UserApiKeys
from api.models.schemas import UpsertOpenAIKeyRequest, ApiKeyStatusOut
from api.dependencies import get_current_user, CurrentUser
from api.services.encryption import encrypt_key, decrypt_key

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


@router.get("", response_model=ApiKeyStatusOut)
async def get_key_status(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Return whether the user has connected their OpenAI key and YouTube."""
    result = await db.execute(
        select(UserApiKeys).where(UserApiKeys.user_id == uuid.UUID(user.id))
    )
    row = result.scalar_one_or_none()
    if not row:
        return ApiKeyStatusOut(has_openai_key=False, has_youtube_token=False)
    return ApiKeyStatusOut(
        has_openai_key=bool(row.openai_api_key_enc),
        has_youtube_token=bool(row.youtube_refresh_token_enc),
        youtube_channel_id=row.youtube_channel_id,
        youtube_channel_name=row.youtube_channel_name,
        youtube_connected_at=row.youtube_connected_at,
        openai_added_at=row.openai_added_at,
    )


@router.post("/openai")
async def upsert_openai_key(
    req: UpsertOpenAIKeyRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Save (or update) the user's OpenAI API key (encrypted)."""
    if not req.openai_api_key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="Invalid OpenAI API key format")

    encrypted = encrypt_key(req.openai_api_key)
    result = await db.execute(
        select(UserApiKeys).where(UserApiKeys.user_id == uuid.UUID(user.id))
    )
    row = result.scalar_one_or_none()

    if row:
        row.openai_api_key_enc = encrypted
        row.openai_added_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(UserApiKeys(
            user_id=uuid.UUID(user.id),
            openai_api_key_enc=encrypted,
            openai_added_at=datetime.now(timezone.utc),
        ))
    await db.commit()
    return {"message": "OpenAI key saved"}


@router.delete("/openai")
async def delete_openai_key(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(UserApiKeys).where(UserApiKeys.user_id == uuid.UUID(user.id))
    )
    row = result.scalar_one_or_none()
    if row:
        row.openai_api_key_enc = None
        row.openai_added_at = None
        await db.commit()
    return {"message": "OpenAI key removed"}
