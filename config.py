"""
config.py — Unified configuration loader for YouTube Autopilot Agent.
Loads settings from both .env (via python-dotenv) and config.yaml (via PyYAML).
Returns a single Config dataclass with all settings.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class Config:
    # API Keys (from .env)
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # Operational flags (from config.yaml)
    autonomous_mode: bool = False
    max_video_minutes: int = 10
    default_niche: str = ""
    human_approval_timeout: int = 300
    auto_approve_under_dollars: float = 2.0

    # Media settings
    video_model: str = "sora-2"
    tts_voice: str = "alloy"
    upload_privacy: str = "public"
    video_resolution: str = "1920x1080"
    short_resolution: str = "720x1280"

    # Editor settings
    crossfade_duration: float = 0.5
    background_music_volume: float = 0.20

    # Logging & paths
    log_level: str = "INFO"
    output_dir: str = ""
    logs_dir: str = ""

    # Multi-tenant: per-user YouTube OAuth refresh token (optional)
    youtube_refresh_token: str = ""

    # Derived paths (set post-init)
    output_videos_dir: str = field(default="", init=False)
    output_images_dir: str = field(default="", init=False)
    output_audio_dir: str = field(default="", init=False)
    output_thumbnails_dir: str = field(default="", init=False)
    dashboard_state_path: str = field(default="", init=False)
    approvals_path: str = field(default="", init=False)

    def __post_init__(self):
        # Resolve absolute paths
        if not os.path.isabs(self.output_dir):
            self.output_dir = os.path.join(BASE_DIR, self.output_dir)
        if not os.path.isabs(self.logs_dir):
            self.logs_dir = os.path.join(BASE_DIR, self.logs_dir)

        self.output_videos_dir = os.path.join(self.output_dir, "videos")
        self.output_images_dir = os.path.join(self.output_dir, "images")
        self.output_audio_dir = os.path.join(self.output_dir, "audio")
        self.output_thumbnails_dir = os.path.join(self.output_dir, "thumbnails")
        self.dashboard_state_path = os.path.join(self.output_dir, "dashboard_state.json")
        self.approvals_path = os.path.join(self.output_dir, "approvals.json")

        # Create directories
        for d in [
            self.output_dir,
            self.output_videos_dir,
            self.output_images_dir,
            self.output_audio_dir,
            self.output_thumbnails_dir,
            self.logs_dir,
        ]:
            os.makedirs(d, exist_ok=True)


def load_config(niche_override: Optional[str] = None) -> Config:
    """
    Load configuration from .env and config.yaml.
    Optional niche_override replaces default_niche.
    """
    # Load environment variables from .env
    env_path = os.path.join(BASE_DIR, ".env")
    load_dotenv(dotenv_path=env_path, override=False)

    # Load YAML config
    yaml_path = os.path.join(BASE_DIR, "config.yaml")
    yaml_cfg = {}
    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, "r") as f:
                yaml_cfg = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load config.yaml: {e}. Using defaults.")
    else:
        logger.warning("config.yaml not found. Using defaults.")

    # Build output and logs absolute paths
    raw_output = yaml_cfg.get("output_dir", "output")
    raw_logs = yaml_cfg.get("logs_dir", "logs")
    output_dir = raw_output if os.path.isabs(raw_output) else os.path.join(BASE_DIR, raw_output)
    logs_dir = raw_logs if os.path.isabs(raw_logs) else os.path.join(BASE_DIR, raw_logs)

    cfg = Config(
        # API keys from environment
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),

        # YAML settings
        autonomous_mode=yaml_cfg.get("autonomous_mode", True),
        max_video_minutes=int(yaml_cfg.get("max_video_minutes", 10)),
        default_niche=yaml_cfg.get("default_niche", ""),
        human_approval_timeout=int(yaml_cfg.get("human_approval_timeout", 300)),
        auto_approve_under_dollars=float(yaml_cfg.get("auto_approve_under_dollars", 2.0)),
        video_model=yaml_cfg.get("video_model", "sora-2"),
        tts_voice=yaml_cfg.get("tts_voice", "alloy"),
        upload_privacy=yaml_cfg.get("upload_privacy", "public"),
        video_resolution=yaml_cfg.get("video_resolution", "1920x1080"),
        short_resolution=yaml_cfg.get("short_resolution", "720x1280"),
        crossfade_duration=float(yaml_cfg.get("crossfade_duration", 0.5)),
        background_music_volume=float(yaml_cfg.get("background_music_volume", 0.20)),
        log_level=yaml_cfg.get("log_level", "INFO"),
        output_dir=output_dir,
        logs_dir=logs_dir,
    )

    # Apply override
    if niche_override:
        cfg.default_niche = niche_override

    # Validate critical keys
    if not cfg.openai_api_key:
        logger.error("OPENAI_API_KEY is not set in .env — API calls will fail.")

    return cfg


# Module-level singleton (lazy loaded)
_config_instance: Optional[Config] = None


def get_config(niche_override: Optional[str] = None) -> Config:
    """Return the global Config singleton (loads once, cached)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = load_config(niche_override)
    elif niche_override and niche_override != _config_instance.default_niche:
        # Re-load if niche override differs
        _config_instance = load_config(niche_override)
    return _config_instance
