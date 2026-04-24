"""
tools/media_generator.py — MediaGeneratorTool

Unified media generation tool supporting:
  action="video"     → OpenAI Sora (sora-2) MP4
  action="image"     → DALL-E 3 PNG
  action="tts"       → OpenAI TTS MP3
  action="thumbnail" → DALL-E 3 PNG (thumbnail-optimised prompt)

All outputs are saved to output/{videos|images|audio|thumbnails}/ with
absolute paths.  Returns the absolute path on success, or an error string.
"""

import logging
import os
import time
from typing import Optional, Type

from crewai.tools import BaseTool
from openai import OpenAI
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)


# ── Input schema ──────────────────────────────────────────────────────────────
class MediaGeneratorInput(BaseModel):
    action: str = Field(
        description=(
            "What to generate. Must be one of: "
            "'video' (Sora MP4), 'image' (DALL-E PNG), "
            "'tts' (OpenAI TTS MP3), 'thumbnail' (DALL-E PNG)."
        )
    )
    prompt: str = Field(
        description="Descriptive text prompt for the media generation."
    )
    duration_seconds: Optional[int] = Field(
        default=8,
        description="Duration in seconds (only used for action='video'). Default 8."
    )
    output_filename: Optional[str] = Field(
        default=None,
        description=(
            "Optional filename (without extension) for the saved file. "
            "If omitted, a timestamped name is generated automatically."
        )
    )


# ── Tool ─────────────────────────────────────────────────────────────────────
class MediaGeneratorTool(BaseTool):
    name: str = "Media Generator"
    description: str = (
        "Generates video (Sora MP4), images (DALL-E PNG), "
        "voiceover audio (OpenAI TTS MP3), or thumbnails (DALL-E PNG). "
        "Input: action (video|image|tts|thumbnail), prompt, "
        "optional duration_seconds, optional output_filename. "
        "Returns the absolute path to the saved file."
    )
    args_schema: Type[BaseModel] = MediaGeneratorInput

    def _run(
        self,
        action: str,
        prompt: str,
        duration_seconds: int = 8,
        output_filename: Optional[str] = None,
    ) -> str:
        action = action.strip().lower()
        dispatch = {
            "video": self._generate_video,
            "image": self._generate_image,
            "tts": self._generate_tts,
            "thumbnail": self._generate_thumbnail,
        }
        if action not in dispatch:
            return f"ERROR: Unknown action '{action}'. Must be one of: {list(dispatch.keys())}"

        try:
            return dispatch[action](prompt, duration_seconds, output_filename)
        except Exception as e:
            logger.exception(f"MediaGeneratorTool[{action}] failed: {e}")
            return f"ERROR: Media generation ({action}) failed: {e}"

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _get_client(self) -> OpenAI:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            try:
                from config import get_config
                api_key = get_config().openai_api_key
            except Exception:
                pass
        return OpenAI(api_key=api_key)

    def _output_path(self, subdir: str, filename: str) -> str:
        """Return absolute output path, ensuring the directory exists."""
        try:
            from config import get_config
            cfg = get_config()
            base = cfg.output_dir
        except Exception:
            base = os.path.join(BASE_DIR, "output")
        out_dir = os.path.join(base, subdir)
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, filename)

    def _make_filename(self, prefix: str, ext: str, custom: Optional[str]) -> str:
        if custom:
            stem = custom.replace(" ", "_").replace("/", "_")
            if not stem.endswith(f".{ext}"):
                stem = f"{stem}.{ext}"
            return stem
        return f"{prefix}_{int(time.time())}.{ext}"

    # ── Video (Sora) ──────────────────────────────────────────────────────────
    def _generate_video(
        self, prompt: str, duration_seconds: int, output_filename: Optional[str]
    ) -> str:
        try:
            from config import get_config
            cfg = get_config()
            model = cfg.video_model
        except Exception:
            model = "sora-2"

        # Sora-2 only supports 720x1280 (vertical) and 1280x720 (landscape)
        # Use landscape for long-form YouTube videos
        resolution = "1280x720"

        # Sora-2 only accepts "4", "8", or "12" — snap to nearest valid value
        valid_secs = [4, 8, 12]
        sora_secs = min(valid_secs, key=lambda v: abs(v - duration_seconds))

        # Augment prompt with cinematic/realism keywords to avoid AI-generated look
        # Following the same pattern as _generate_thumbnail() for consistency
        video_prompt = (
            f"Cinematic, photorealistic, documentary-style, 4K professional quality, "
            f"natural lighting, shallow depth of field, realistic colors, "
            f"shot on professional cinema camera, no cartoon/illustration/3D-render/anime style, "
            f"genuine documentary footage. Subject: {prompt}"
        )

        client = self._get_client()
        logger.info(f"Sora: generating {sora_secs}s clip — model={model}, size={resolution}")

        video = client.videos.create_and_poll(
            model=model,
            prompt=video_prompt,
            size=resolution,
            seconds=str(sora_secs),
        )

        if video.status != "completed":
            return (
                f"ERROR: Sora video generation failed — "
                f"status={video.status}, error={getattr(video, 'error', 'unknown')}"
            )

        content = client.videos.download_content(video.id)
        filename = self._make_filename("scene", "mp4", output_filename)
        path = self._output_path("videos", filename)
        with open(path, "wb") as f:
            f.write(content.read())

        logger.info(f"Sora clip saved: {path}")
        return path

    # ── Image (DALL-E 3) ──────────────────────────────────────────────────────
    def _generate_image(
        self, prompt: str, duration_seconds: int, output_filename: Optional[str]
    ) -> str:
        import requests

        client = self._get_client()
        logger.info(f"DALL-E 3: generating image")

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url
        filename = self._make_filename("image", "png", output_filename)
        path = self._output_path("images", filename)

        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(img_resp.content)

        logger.info(f"DALL-E image saved: {path}")
        return path

    # ── TTS (OpenAI TTS) ──────────────────────────────────────────────────────
    def _generate_tts(
        self, prompt: str, duration_seconds: int, output_filename: Optional[str]
    ) -> str:
        try:
            from config import get_config
            voice = get_config().tts_voice
        except Exception:
            voice = "alloy"

        client = self._get_client()
        logger.info(f"TTS: generating voiceover — voice={voice}, chars={len(prompt)}")

        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=prompt,
        )

        filename = self._make_filename("voiceover", "mp3", output_filename)
        path = self._output_path("audio", filename)
        response.stream_to_file(path)

        logger.info(f"TTS audio saved: {path}")
        return path

    # ── Thumbnail (DALL-E 3, 16:9 style) ─────────────────────────────────────
    def _generate_thumbnail(
        self, prompt: str, duration_seconds: int, output_filename: Optional[str]
    ) -> str:
        import requests

        client = self._get_client()

        # Enhance prompt for YouTube thumbnail
        thumb_prompt = (
            f"YouTube video thumbnail, eye-catching, bold text overlay, "
            f"vibrant colors, high contrast, 16:9 ratio. "
            f"Subject: {prompt}. "
            f"Style: professional YouTube thumbnail, photorealistic, no watermarks."
        )
        logger.info("DALL-E 3: generating thumbnail")

        response = client.images.generate(
            model="dall-e-3",
            prompt=thumb_prompt,
            size="1792x1024",  # closest to 16:9 available in DALL-E 3
            quality="hd",
            n=1,
        )

        image_url = response.data[0].url
        filename = self._make_filename("thumbnail", "png", output_filename)
        path = self._output_path("thumbnails", filename)

        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(img_resp.content)

        logger.info(f"Thumbnail saved: {path}")
        return path
