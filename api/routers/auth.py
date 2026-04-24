"""
api/routers/auth.py — Auth endpoints (sign up, sign in, me, sign out).

Authentication modes:
  • SUPABASE_URL set → delegates to Supabase Auth; creates local user_profiles row
  • SUPABASE_URL not set → local password hashing + JWT minting (development mode)
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.models.schemas import SignUpRequest, SignInRequest, TokenResponse
from api.models.db import get_db, UserProfile, UserSettings
from api.dependencies import get_current_user, CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_supabase_anon():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _mint_local_jwt(user_id: str, email: str) -> str:
    """Mint a HS256 JWT for local dev mode."""
    from jose import jwt
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def _ensure_local_profile(db: AsyncSession, user_uuid: uuid.UUID, display_name: str):
    """Create user_profiles + user_settings rows if they don't exist."""
    existing = await db.execute(select(UserProfile).where(UserProfile.id == user_uuid))
    if not existing.scalar_one_or_none():
        db.add(UserProfile(id=user_uuid, display_name=display_name))
        db.add(UserSettings(user_id=user_uuid))
        await db.commit()


# ── Supabase mode endpoints ───────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse)
async def sign_up(req: SignUpRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""

    if SUPABASE_URL and SUPABASE_ANON_KEY:
        # ── Supabase mode ──────────────────────────────────────────────────────
        sb = _get_supabase_anon()
        try:
            res = sb.auth.sign_up({"email": req.email, "password": req.password})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        user = res.user
        if not user:
            raise HTTPException(status_code=400, detail="Signup failed — check email/password requirements")

        user_uuid = uuid.UUID(str(user.id))
        await _ensure_local_profile(db, user_uuid, req.display_name or req.email)

        session = res.session
        return TokenResponse(
            access_token=session.access_token if session else "",
            token_type="bearer",
            user_id=str(user.id),
            email=user.email or req.email,
        )

    else:
        # ── Local dev mode ─────────────────────────────────────────────────────
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

        # Check if user already exists (store email as UUID namespace)
        email_uuid = uuid.uuid5(uuid.NAMESPACE_URL, req.email)
        existing = await db.execute(
            select(UserProfile).where(UserProfile.id == email_uuid)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="User already exists")

        # Store password hash in display_name field as a stopgap for local dev
        # (production always uses Supabase — this is development-only)
        pw_hash = pwd_ctx.hash(req.password)
        profile = UserProfile(
            id=email_uuid,
            display_name=req.display_name or req.email,
            plan="free",
        )
        # Store pw_hash in a way we can retrieve — attach as metadata
        # For local dev we encode: "PWHASH:{hash}" in display_name
        profile.display_name = f"{req.display_name or req.email}||PWHASH:{pw_hash}"
        db.add(profile)
        db.add(UserSettings(user_id=email_uuid))
        await db.commit()

        token = _mint_local_jwt(str(email_uuid), req.email)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=str(email_uuid),
            email=req.email,
        )


@router.post("/signin", response_model=TokenResponse)
async def sign_in(req: SignInRequest, db: AsyncSession = Depends(get_db)):
    """Sign in with email + password."""

    if SUPABASE_URL and SUPABASE_ANON_KEY:
        # ── Supabase mode ──────────────────────────────────────────────────────
        sb = _get_supabase_anon()
        try:
            res = sb.auth.sign_in_with_password({"email": req.email, "password": req.password})
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        session = res.session
        user = res.user
        if not session or not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Ensure profile row exists (Supabase trigger may not have run in all setups)
        user_uuid = uuid.UUID(str(user.id))
        await _ensure_local_profile(db, user_uuid, user.email or req.email)

        return TokenResponse(
            access_token=session.access_token,
            token_type="bearer",
            user_id=str(user.id),
            email=user.email or req.email,
        )

    else:
        # ── Local dev mode ─────────────────────────────────────────────────────
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

        email_uuid = uuid.uuid5(uuid.NAMESPACE_URL, req.email)
        result = await db.execute(
            select(UserProfile).where(UserProfile.id == email_uuid)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Extract pw_hash
        dn = profile.display_name or ""
        if "||PWHASH:" in dn:
            pw_hash = dn.split("||PWHASH:", 1)[1]
        else:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not pwd_ctx.verify(req.password, pw_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = _mint_local_jwt(str(email_uuid), req.email)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_id=str(email_uuid),
            email=req.email,
        )


@router.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """Return current user info from token."""
    return {"user_id": user.id, "email": user.email}


@router.post("/signout")
async def sign_out(user: CurrentUser = Depends(get_current_user)):
    """Invalidate session (client should discard the token)."""
    return {"message": "Signed out"}
