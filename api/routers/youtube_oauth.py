"""
api/routers/youtube_oauth.py — YouTube OAuth 2.0 per-user flow.
"""
import os
import uuid
import secrets
from urllib.parse import urlencode
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from api.models.db import get_db, UserApiKeys
from api.dependencies import get_current_user, CurrentUser
from api.services.encryption import encrypt_key

router = APIRouter(prefix="/api/youtube", tags=["youtube-oauth"])

YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REDIRECT_URI = os.environ.get("YOUTUBE_REDIRECT_URI", "http://localhost:8000/api/youtube/callback")

# In-memory state store (use Redis in production)
_oauth_states: dict = {}

YOUTUBE_SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


@router.get("/connect")
async def youtube_connect(user: CurrentUser = Depends(get_current_user)):
    """Generate YouTube OAuth URL. User is redirected to Google."""
    if not YOUTUBE_CLIENT_ID:
        return {"auth_url": ""}   # not configured — UI will show instructions instead

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = user.id

    params = {
        "client_id": YOUTUBE_CLIENT_ID,
        "redirect_uri": YOUTUBE_REDIRECT_URI,
        "scope": YOUTUBE_SCOPES,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"auth_url": auth_url}


@router.get("/callback")
async def youtube_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback. Exchange code for refresh token."""
    user_id = _oauth_states.pop(state, None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": YOUTUBE_CLIENT_ID,
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "redirect_uri": YOUTUBE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_res.json()

    if "refresh_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"No refresh token: {token_data}")

    # Fetch channel info
    channel_id, channel_name = await _get_channel_info(token_data["access_token"])

    # Store encrypted
    enc_token = encrypt_key(token_data["refresh_token"])
    result = await db.execute(
        select(UserApiKeys).where(UserApiKeys.user_id == uuid.UUID(user_id))
    )
    row = result.scalar_one_or_none()
    if row:
        row.youtube_refresh_token_enc = enc_token
        row.youtube_channel_id = channel_id
        row.youtube_channel_name = channel_name
        row.youtube_connected_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(UserApiKeys(
            user_id=uuid.UUID(user_id),
            youtube_refresh_token_enc=enc_token,
            youtube_channel_id=channel_id,
            youtube_channel_name=channel_name,
            youtube_connected_at=datetime.now(timezone.utc),
        ))
    await db.commit()

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(f"{frontend_url}/settings?youtube_connected=1")


@router.delete("/disconnect")
async def youtube_disconnect(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(UserApiKeys).where(UserApiKeys.user_id == uuid.UUID(user.id))
    )
    row = result.scalar_one_or_none()
    if row:
        row.youtube_refresh_token_enc = None
        row.youtube_channel_id = None
        row.youtube_channel_name = None
        row.youtube_connected_at = None
        await db.commit()
    return {"message": "YouTube disconnected"}


async def _get_channel_info(access_token: str):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            data = res.json()
            items = data.get("items", [])
            if items:
                return items[0]["id"], items[0]["snippet"]["title"]
    except Exception:
        pass
    return None, None
