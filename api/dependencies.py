"""
api/dependencies.py — FastAPI dependency injection: auth middleware, DB session.

Authentication strategy:
  • If SUPABASE_URL is set → validate JWT via Supabase Admin API
    (production mode — verifies token with Supabase's own server)
  • Otherwise → validate JWT locally using JWT_SECRET
    (local dev mode — works without a live Supabase project)

The CurrentUser object exposes .id (user UUID str) and .email.
"""
import os
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.db import get_db

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")

security = HTTPBearer()

# Lazy-initialised Supabase admin client
_supabase_admin = None


def _get_supabase_admin():
    global _supabase_admin
    if _supabase_admin is None:
        from supabase import create_client
        _supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_admin


class CurrentUser:
    def __init__(self, user_id: str, email: str):
        self.id = user_id
        self.email = email


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """
    Validate the Bearer JWT token and return a CurrentUser.

    Falls back to local JWT validation when SUPABASE_URL is not configured.
    """
    token = credentials.credentials

    # ── Mode A: Supabase JWT validation (production) ──────────────────────────
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            supabase = _get_supabase_admin()
            response = supabase.auth.get_user(token)
            user = response.user
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                )
            return CurrentUser(user_id=str(user.id), email=user.email or "")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Supabase token validation failed: {e}. Trying local JWT.")
            # Fall through to local JWT if Supabase is temporarily unavailable

    # ── Mode B: Local JWT validation (development / no-Supabase mode) ─────────
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authentication not configured. "
                "Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY, or JWT_SECRET."
            ),
        )

    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        sub = payload.get("sub") or payload.get("user_id") or payload.get("id")
        email = payload.get("email", "")
        if not sub:
            raise ValueError("No subject in token payload")
        return CurrentUser(user_id=str(sub), email=str(email))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}",
        )
