"""
api/routers/settings.py — User settings CRUD.
"""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.models.db import get_db, UserSettings
from api.models.schemas import UpdateSettingsRequest, SettingsOut
from api.dependencies import get_current_user, CurrentUser

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user.id)))
    s = result.scalar_one_or_none()
    if not s:
        return SettingsOut(
            autonomous_mode=True, max_video_minutes=10, default_niche="",
            tts_voice="alloy", upload_privacy="public", video_model="sora-2",
            auto_approve_under_dollars=2.0
        )
    return SettingsOut(
        autonomous_mode=s.autonomous_mode,
        max_video_minutes=s.max_video_minutes,
        default_niche=s.default_niche or "",
        tts_voice=s.tts_voice,
        upload_privacy=s.upload_privacy,
        video_model=s.video_model,
        auto_approve_under_dollars=s.auto_approve_under_dollars,
    )


@router.put("")
async def update_settings(
    req: UpdateSettingsRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == uuid.UUID(user.id)))
    s = result.scalar_one_or_none()
    if not s:
        s = UserSettings(user_id=uuid.UUID(user.id))
        db.add(s)

    for field, val in req.model_dump(exclude_none=True).items():
        setattr(s, field, val)

    await db.commit()
    return {"message": "Settings updated"}
