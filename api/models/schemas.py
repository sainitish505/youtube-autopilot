"""
api/models/schemas.py — Pydantic request/response schemas for the FastAPI API.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
import uuid


# ── Auth ─────────────────────────────────────────────────────────────────────
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


# ── Jobs ─────────────────────────────────────────────────────────────────────
class CreateJobRequest(BaseModel):
    niche: Optional[str] = ""


class AgentStatusOut(BaseModel):
    agent_name: str
    status: str
    updated_at: Optional[datetime]


class JobOut(BaseModel):
    id: str
    status: str
    niche: Optional[str]
    title: Optional[str]
    scenes_count: Optional[int]
    video_url: Optional[str]
    total_cost_usd: float
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    agents: List[AgentStatusOut] = []
    assets: List[dict] = []


class JobListOut(BaseModel):
    jobs: List[JobOut]
    total: int


# ── API Keys ──────────────────────────────────────────────────────────────────
class UpsertOpenAIKeyRequest(BaseModel):
    openai_api_key: str


class ApiKeyStatusOut(BaseModel):
    has_openai_key: bool
    has_youtube_token: bool
    youtube_channel_id: Optional[str] = None
    youtube_channel_name: Optional[str] = None
    youtube_connected_at: Optional[datetime] = None
    openai_added_at: Optional[datetime] = None


# ── Settings ─────────────────────────────────────────────────────────────────
class UpdateSettingsRequest(BaseModel):
    autonomous_mode: Optional[bool] = None
    max_video_minutes: Optional[int] = None
    default_niche: Optional[str] = None
    tts_voice: Optional[str] = None
    upload_privacy: Optional[str] = None
    video_model: Optional[str] = None
    auto_approve_under_dollars: Optional[float] = None


class SettingsOut(BaseModel):
    autonomous_mode: bool
    max_video_minutes: int
    default_niche: str
    tts_voice: str
    upload_privacy: str
    video_model: str
    auto_approve_under_dollars: float


# ── Analytics ─────────────────────────────────────────────────────────────────
class AnalyticsSummaryOut(BaseModel):
    total_videos: int
    total_cost_usd: float
    success_rate: float
    avg_cost_per_video: float
    videos_this_month: int
    cost_this_month_usd: float
    cost_by_type: dict  # {"sora": 1.20, "tts": 0.05, ...}
    videos_by_niche: dict
