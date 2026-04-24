"""
tools/video_editor.py — VideoEditorTool

Uses MoviePy to assemble a final video from scene clips:
  - Loads each scene's video clip and optional audio (voiceover)
  - Overlays voiceover on each scene clip
  - Adds 0.5s crossfade transitions between scenes
  - Adds background music at 20% volume (optional)
  - Exports final MP4 to output/videos/final_{timestamp}.mp4

Input JSON schema:
{
  "scenes": [
    {
      "video_path": "/abs/path/to/clip.mp4",
      "audio_path": "/abs/path/to/voiceover.mp3",   // optional
      "duration": 8.0                                 // seconds
    }
  ],
  "background_music_path": "/abs/path/to/music.mp3", // optional
  "output_filename": "my_video"                       // optional, no extension
}
"""

import json
import logging
import os
import time
from typing import List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)


class VideoEditorInput(BaseModel):
    edit_spec_json: str = Field(
        description=(
            "JSON string specifying the editing job. Keys: "
            "'scenes' (list of {video_path, audio_path?, duration}), "
            "'background_music_path' (optional), "
            "'output_filename' (optional stem, no extension)."
        )
    )


class VideoEditorTool(BaseTool):
    name: str = "Video Editor"
    description: str = (
        "Assembles scene video clips with voiceover audio and optional background music "
        "into a final polished MP4 using MoviePy. "
        "Applies crossfade transitions between scenes. "
        "Input: JSON string with scenes list and optional music/output fields. "
        "Returns absolute path to the final MP4."
    )
    args_schema: Type[BaseModel] = VideoEditorInput

    def _run(self, edit_spec_json: str) -> str:
        try:
            spec = json.loads(edit_spec_json)
        except json.JSONDecodeError as e:
            return f"ERROR: Invalid JSON input to VideoEditorTool: {e}"

        try:
            return self._edit(spec)
        except Exception as e:
            logger.exception(f"VideoEditorTool failed: {e}")
            return f"ERROR: Video editing failed: {e}"

    def _edit(self, spec: dict) -> str:
        # Lazy import so missing MoviePy doesn't crash tool loading
        try:
            from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
            from moviepy import concatenate_videoclips
            from moviepy.audio.AudioClip import AudioArrayClip
        except ImportError as e:
            return f"ERROR: MoviePy not installed — run 'pip install moviepy>=2.0.0'. Details: {e}"

        scenes: List[dict] = spec.get("scenes", [])
        bg_music_path: Optional[str] = spec.get("background_music_path")
        output_filename: Optional[str] = spec.get("output_filename")

        if not scenes:
            return "ERROR: No scenes provided to VideoEditorTool."

        try:
            from config import get_config
            cfg = get_config()
            crossfade = cfg.crossfade_duration
            bg_vol = cfg.background_music_volume
            out_dir = cfg.output_videos_dir
        except Exception:
            crossfade = 0.5
            bg_vol = 0.20
            out_dir = os.path.join(BASE_DIR, "output", "videos")

        os.makedirs(out_dir, exist_ok=True)

        # ── Process each scene ─────────────────────────────────────────────────
        processed_clips = []
        for i, scene in enumerate(scenes):
            video_path = scene.get("video_path", "")
            audio_path = scene.get("audio_path", "")
            duration = float(scene.get("duration", 8.0))

            if not video_path or not os.path.exists(video_path):
                logger.warning(f"Scene {i+1}: video not found at '{video_path}' — skipping.")
                continue

            try:
                clip = VideoFileClip(video_path)
                # Trim or pad to specified duration
                if clip.duration > duration:
                    clip = clip.subclipped(0, duration)
            except Exception as e:
                logger.warning(f"Scene {i+1}: could not load video '{video_path}': {e} — skipping.")
                continue

            # Attach voiceover if available
            if audio_path and os.path.exists(audio_path):
                try:
                    voiceover = AudioFileClip(audio_path)
                    # Trim voiceover to clip duration to avoid extension
                    if voiceover.duration > clip.duration:
                        voiceover = voiceover.subclipped(0, clip.duration)
                    clip = clip.with_audio(voiceover)
                    logger.debug(f"Scene {i+1}: voiceover attached ({audio_path})")
                except Exception as e:
                    logger.warning(f"Scene {i+1}: could not attach audio '{audio_path}': {e}")
            else:
                logger.debug(f"Scene {i+1}: no voiceover audio — using video audio track (if any).")

            processed_clips.append(clip)

        if not processed_clips:
            return "ERROR: All scenes failed to load. No video produced."

        # ── Concatenate with crossfade ─────────────────────────────────────────
        logger.info(f"Concatenating {len(processed_clips)} clips with {crossfade}s crossfade")
        try:
            if len(processed_clips) == 1:
                final_clip = processed_clips[0]
            else:
                final_clip = concatenate_videoclips(
                    processed_clips,
                    method="compose",
                    padding=-crossfade,
                )
        except Exception as e:
            logger.warning(f"Crossfade concatenation failed ({e}), falling back to simple join.")
            try:
                final_clip = concatenate_videoclips(processed_clips, method="chain")
            except Exception as e2:
                return f"ERROR: Could not concatenate video clips: {e2}"

        # ── Background music (optional) ────────────────────────────────────────
        if bg_music_path and os.path.exists(bg_music_path):
            try:
                bg_audio = AudioFileClip(bg_music_path).with_volume_scaled(bg_vol)
                # Loop music to fill the full video
                if bg_audio.duration < final_clip.duration:
                    repeats = int(final_clip.duration / bg_audio.duration) + 1
                    from moviepy import concatenate_audioclips
                    bg_audio = concatenate_audioclips([bg_audio] * repeats)
                bg_audio = bg_audio.subclipped(0, final_clip.duration)

                # Composite with existing audio
                existing_audio = final_clip.audio
                if existing_audio is not None:
                    mixed = CompositeAudioClip([existing_audio, bg_audio])
                else:
                    mixed = bg_audio
                final_clip = final_clip.with_audio(mixed)
                logger.info("Background music mixed in at volume %.0f%%", bg_vol * 100)
            except Exception as e:
                logger.warning(f"Could not add background music: {e}")

        # ── Export ────────────────────────────────────────────────────────────
        if output_filename:
            stem = output_filename.replace(" ", "_").replace("/", "_")
            if not stem.endswith(".mp4"):
                stem += ".mp4"
        else:
            stem = f"final_{int(time.time())}.mp4"

        out_path = os.path.join(out_dir, stem)

        logger.info(f"Exporting final video to {out_path} ...")
        try:
            final_clip.write_videofile(
                out_path,
                codec="libx264",
                audio_codec="aac",
                fps=24,
                logger=None,  # suppress MoviePy's verbose bar
            )
        except Exception as e:
            return f"ERROR: Failed to write final video: {e}"
        finally:
            # Close all clips to free resources
            for c in processed_clips:
                try:
                    c.close()
                except Exception:
                    pass
            try:
                final_clip.close()
            except Exception:
                pass

        logger.info(f"Final video exported: {out_path}")
        return out_path
