"""
core/user_context.py — Per-user tenant context replacing global Config singleton.

Each pipeline run gets a UserContext containing:
  - Decrypted API keys for that user
  - Isolated output directory: /tmp/jobs/{user_id}/{job_id}/
  - User-specific settings (voice, max_minutes, etc.)
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserContext:
    user_id: str
    job_id: str
    openai_api_key: str
    youtube_refresh_token: Optional[str] = None
    youtube_channel_id: Optional[str] = None

    # Settings (mirrors config.yaml but per-user)
    autonomous_mode: bool = True
    max_video_minutes: int = 10
    default_niche: str = ""
    tts_voice: str = "alloy"
    upload_privacy: str = "public"
    video_model: str = "sora-2"
    auto_approve_under_dollars: float = 2.0
    crossfade_duration: float = 0.5
    background_music_volume: float = 0.20
    log_level: str = "INFO"

    @property
    def output_dir(self) -> str:
        """Isolated output directory for this job."""
        base = os.environ.get("JOBS_TMP_DIR", "/tmp/jobs")
        return os.path.join(base, self.user_id, self.job_id)

    @property
    def videos_dir(self) -> str:
        return os.path.join(self.output_dir, "videos")

    @property
    def audio_dir(self) -> str:
        return os.path.join(self.output_dir, "audio")

    @property
    def images_dir(self) -> str:
        return os.path.join(self.output_dir, "images")

    @property
    def thumbnails_dir(self) -> str:
        return os.path.join(self.output_dir, "thumbnails")

    @property
    def approvals_path(self) -> str:
        return os.path.join(self.output_dir, "approvals.json")

    @property
    def dashboard_state_path(self) -> str:
        return os.path.join(self.output_dir, "dashboard_state.json")

    def ensure_dirs(self):
        """Create all output directories for this job."""
        for d in [self.output_dir, self.videos_dir, self.audio_dir,
                  self.images_dir, self.thumbnails_dir]:
            os.makedirs(d, exist_ok=True)
