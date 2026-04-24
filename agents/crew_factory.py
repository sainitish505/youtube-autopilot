"""
agents/crew_factory.py — CrewFactory

Dynamically builds and runs a full production crew from a CEO-approved plan.

The plan dict format (from the CEO Task output):
{
  "niche": str,
  "title": str,
  "script": str,
  "scenes": [
    {
      "scene_num": int,
      "description": str,
      "duration_seconds": int,
      "voiceover_text": str
    }
  ],
  "video_length_minutes": float,
  "target_audience": str,
  "tags": [str],
  "thumbnail_description": str,
  "seo_description": str       // optional
}

Agents created:
  1. ScriptPolisherAgent   — refines voiceover text per scene
  2. VisualGeneratorAgent  — generates Sora video clips for each scene
  3. AudioEngineerAgent    — generates TTS voiceover MP3 per scene
  4. VideoEditorAgent      — assembles final MP4
  5. SEOOptimizerAgent     — refines title/description/tags
  6. UploaderAgent         — uploads to YouTube

Returns: YouTube URL string
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from crewai import Agent, Crew, LLM, Process, Task

from tools.dashboard_tool import DashboardTool, update_status, add_asset, set_youtube_url
from tools.media_generator import MediaGeneratorTool
from tools.video_editor import VideoEditorTool
from tools.youtube_uploader import YouTubeUploaderTool

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CrewFactory:
    """Builds and executes the full production pipeline from a CEO-approved plan."""

    def __init__(self, openai_api_key: str, youtube_refresh_token: str = ""):
        self.api_key = openai_api_key
        self.youtube_refresh_token = youtube_refresh_token
        self.mini_llm = LLM(
            model="gpt-4o-mini",
            api_key=openai_api_key,
            temperature=0.7,
            max_tokens=2048,
        )
        self.media_tool = MediaGeneratorTool()
        self.editor_tool = VideoEditorTool()
        self.uploader_tool = YouTubeUploaderTool()
        self.dashboard_tool = DashboardTool()

    def build_and_run(self, plan: Dict[str, Any]) -> str:
        """
        Execute the full production pipeline and return the YouTube URL.

        Parameters
        ----------
        plan : dict
            CEO-approved production plan.

        Returns
        -------
        str
            YouTube video URL.
        """
        logger.info(f"CrewFactory: starting production for '{plan.get('title', 'untitled')}'")
        logger.info(f"Scenes: {len(plan.get('scenes', []))}")

        scenes = plan.get("scenes", [])
        if not scenes:
            raise ValueError("Plan contains no scenes — cannot produce video.")

        # ── Step 1: Script polishing ───────────────────────────────────────────
        update_status("ScriptPolisher", "running", 0.0)
        polished_scenes = self._polish_scripts(plan)
        update_status("ScriptPolisher", "done", 0.0)

        # ── Step 2: Visual generation (Sora clips) ─────────────────────────────
        update_status("VisualGenerator", "running", 0.0)
        video_paths = self._generate_visuals(polished_scenes)
        update_status("VisualGenerator", "done", 0.0)

        # ── Step 3: Audio generation (TTS voiceover) ──────────────────────────
        update_status("AudioEngineer", "running", 0.0)
        audio_paths = self._generate_audio(polished_scenes)
        update_status("AudioEngineer", "done", 0.0)

        # ── Step 4: Thumbnail generation ──────────────────────────────────────
        thumbnail_path = self._generate_thumbnail(plan)

        # ── Step 5: Video editing ──────────────────────────────────────────────
        update_status("VideoEditor", "running", 0.0)
        final_video_path = self._edit_video(polished_scenes, video_paths, audio_paths)
        update_status("VideoEditor", "done", 0.0)
        add_asset("video", final_video_path)

        # ── Step 6: SEO optimisation ───────────────────────────────────────────
        update_status("SEOOptimizer", "running", 0.0)
        seo_meta = self._optimize_seo(plan)
        update_status("SEOOptimizer", "done", 0.0)

        # ── Step 7: Upload ────────────────────────────────────────────────────
        update_status("Uploader", "running", 0.0)
        youtube_url = self._upload_video(final_video_path, seo_meta, plan)
        update_status("Uploader", "done", 0.0)
        set_youtube_url(youtube_url)

        logger.info(f"CrewFactory: pipeline complete. URL: {youtube_url}")
        return youtube_url

    # ── Internal pipeline steps ────────────────────────────────────────────────

    def _polish_scripts(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use GPT-4o-mini to polish each scene's voiceover text."""
        scenes = plan.get("scenes", [])
        target_audience = plan.get("target_audience", "general audience")
        title = plan.get("title", "")

        script_agent = Agent(
            role="Script Polisher",
            goal="Refine voiceover scripts for maximum engagement and clarity",
            backstory=(
                "You are an expert YouTube scriptwriter who specialises in punchy, "
                "conversational voiceovers that hold viewer attention. "
                "You adapt tone to the target audience and ensure every word counts."
            ),
            llm=self.mini_llm,
            verbose=False,
        )

        polished = []
        for scene in scenes:
            vo_text = scene.get("voiceover_text", "")
            if not vo_text.strip():
                polished.append(scene.copy())
                continue

            task = Task(
                description=(
                    f"Polish this voiceover script for scene {scene.get('scene_num', '?')} "
                    f"of a YouTube video titled '{title}'. "
                    f"Target audience: {target_audience}. "
                    f"Scene description: {scene.get('description', '')}. "
                    f"Original voiceover: {vo_text}. "
                    f"Keep it under {scene.get('duration_seconds', 8) * 3} words. "
                    f"Make it punchy, clear, and engaging. Return ONLY the polished text."
                ),
                expected_output="Polished voiceover text only — no labels, no formatting.",
                agent=script_agent,
            )

            crew = Crew(agents=[script_agent], tasks=[task], process=Process.sequential, verbose=False)
            result = crew.kickoff()
            polished_text = str(result).strip()

            updated = scene.copy()
            updated["voiceover_text"] = polished_text if polished_text else vo_text
            polished.append(updated)
            logger.debug(f"Scene {scene.get('scene_num')}: voiceover polished.")

        return polished

    def _generate_visuals(self, scenes: List[Dict[str, Any]]) -> Dict[int, str]:
        """Generate a Sora video clip for each scene directly. Returns {scene_num: path}.

        Calls MediaGeneratorTool directly (no agent wrapper) to avoid CrewAI's
        max-iteration timeout cutting off long-running Sora generation jobs.
        """
        paths = {}
        total = len(scenes)
        for i, scene in enumerate(scenes, 1):
            num = scene.get("scene_num", 0)
            description = scene.get("description", "")
            duration = int(scene.get("duration_seconds", 8))
            # Snap to nearest Sora-supported value: 4, 8, or 12
            valid_secs = [4, 8, 12]
            sora_secs = min(valid_secs, key=lambda v: abs(v - duration))

            logger.info(f"Generating video Scene {num}/{total} ({sora_secs}s) ...")
            try:
                path = self.media_tool._run(
                    action="video",
                    prompt=description,
                    duration_seconds=sora_secs,
                    output_filename=f"scene_{num:03d}",
                )
                if path and not path.startswith("ERROR") and os.path.exists(path):
                    paths[num] = path
                    add_asset("video_clip", path)
                    logger.info(f"Scene {num} video saved: {path}")
                else:
                    logger.warning(f"Scene {num} video generation failed: {path}")
            except Exception as e:
                logger.warning(f"Scene {num} video generation exception: {e}")

        return paths

    def _generate_audio(self, scenes: List[Dict[str, Any]]) -> Dict[int, str]:
        """Generate TTS voiceover for each scene directly. Returns {scene_num: path}.

        Calls MediaGeneratorTool directly (no agent wrapper) for speed and reliability.
        """
        paths = {}
        for scene in scenes:
            num = scene.get("scene_num", 0)
            vo_text = scene.get("voiceover_text", "").strip()
            if not vo_text:
                logger.debug(f"Scene {num}: no voiceover text — skipping TTS.")
                continue

            logger.info(f"Generating TTS for Scene {num} ({len(vo_text)} chars) ...")
            try:
                path = self.media_tool._run(
                    action="tts",
                    prompt=vo_text,
                    output_filename=f"voiceover_{num:03d}",
                )
                if path and not path.startswith("ERROR") and os.path.exists(path):
                    paths[num] = path
                    add_asset("audio", path)
                    logger.info(f"Scene {num} audio saved: {path}")
                else:
                    logger.warning(f"Scene {num} TTS failed: {path}")
            except Exception as e:
                logger.warning(f"Scene {num} TTS exception: {e}")

        return paths

    def _generate_thumbnail(self, plan: Dict[str, Any]) -> str:
        """Generate a YouTube thumbnail via DALL-E 3."""
        thumb_desc = plan.get("thumbnail_description", plan.get("title", "YouTube video"))
        try:
            path = self.media_tool._run(
                action="thumbnail",
                prompt=thumb_desc,
                output_filename=f"thumbnail_{plan.get('title', 'video')[:30]}",
            )
            if path and not path.startswith("ERROR") and os.path.exists(path):
                add_asset("thumbnail", path)
                logger.info(f"Thumbnail: {path}")
                return path
        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {e}")
        return ""

    def _edit_video(
        self,
        scenes: List[Dict[str, Any]],
        video_paths: Dict[int, str],
        audio_paths: Dict[int, str],
    ) -> str:
        """Assemble all scene clips into the final video."""
        # Build scene list for the editor tool
        edit_scenes = []
        for scene in scenes:
            num = scene.get("scene_num", 0)
            duration = float(scene.get("duration_seconds", 8))
            video_path = video_paths.get(num, "")
            audio_path = audio_paths.get(num, "")

            if not video_path:
                logger.warning(f"Scene {num}: no video path — skipping in edit.")
                continue

            edit_scenes.append({
                "video_path": video_path,
                "audio_path": audio_path,
                "duration": duration,
            })

        if not edit_scenes:
            raise RuntimeError("No valid scenes to edit — all video generation failed.")

        import time as _time
        spec = {
            "scenes": edit_scenes,
            "output_filename": f"final_{int(_time.time())}",
        }
        spec_json = json.dumps(spec)

        logger.info(f"Assembling final video from {len(edit_scenes)} scenes ...")
        try:
            path = self.editor_tool._run(spec_json)
        except Exception as e:
            raise RuntimeError(f"Video editing failed: {e}")

        if not path or path.startswith("ERROR"):
            raise RuntimeError(f"Video editing failed: {path}")
        if not os.path.exists(path):
            raise RuntimeError(f"Editor returned path but file not found: {path}")

        logger.info(f"Final video assembled: {path}")
        return path

    def _optimize_seo(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Use GPT-4o-mini to refine title, description, and tags."""
        seo_agent = Agent(
            role="SEO Optimizer",
            goal="Maximise YouTube video discoverability with optimised metadata",
            backstory=(
                "You are a YouTube SEO expert who knows exactly how to craft titles, "
                "descriptions, and tags that rank and get clicked. "
                "You balance keyword richness with natural language and emotional hooks."
            ),
            llm=self.mini_llm,
            verbose=False,
        )

        original_title = plan.get("title", "")
        original_tags = plan.get("tags", [])
        niche = plan.get("niche", "")
        target_audience = plan.get("target_audience", "")
        script_summary = plan.get("script", "")[:500]

        task = Task(
            description=(
                f"Optimise the YouTube metadata for this video:\n"
                f"Original title: {original_title}\n"
                f"Niche: {niche}\n"
                f"Target audience: {target_audience}\n"
                f"Script summary: {script_summary}\n"
                f"Original tags: {', '.join(original_tags)}\n\n"
                f"Return a JSON object (no markdown fences) with keys:\n"
                f"  title: string (under 60 chars, clickbait + SEO)\n"
                f"  description: string (150-300 words, keyword-rich, CTA at end)\n"
                f"  tags: array of 15-20 strings (mix of broad + specific)\n"
                f"  category_id: string (YouTube category ID as string)\n"
            ),
            expected_output=(
                "JSON object with title, description, tags (array), category_id. "
                "No markdown fences. Valid JSON only."
            ),
            agent=seo_agent,
        )

        crew = Crew(agents=[seo_agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()
        raw = str(result).strip()

        try:
            # Strip potential markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            meta = json.loads(raw)
            logger.info(f"SEO meta optimised: title='{meta.get('title', '')}'")
            return meta
        except Exception as e:
            logger.warning(f"SEO optimisation JSON parse failed ({e}). Using original metadata.")
            return {
                "title": original_title,
                "description": plan.get("seo_description", plan.get("script", "")[:200]),
                "tags": original_tags,
                "category_id": "28",
            }

    def _upload_video(
        self, video_path: str, seo_meta: Dict[str, Any], plan: Dict[str, Any]
    ) -> str:
        """Upload the final video to YouTube and return the URL."""
        title = seo_meta.get("title", plan.get("title", "AI Generated Video"))
        description = seo_meta.get(
            "description",
            plan.get("seo_description", "AI-generated video. Subscribe for more!"),
        )
        tags = seo_meta.get("tags", plan.get("tags", []))

        # Ensure tags is a list of strings
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        try:
            url = self.uploader_tool._run(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category_id=seo_meta.get("category_id", "28"),
            )
            if url and url.startswith("https://"):
                logger.info(f"Upload successful: {url}")
                return url
            else:
                logger.error(f"Upload returned unexpected result: {url}")
                return url
        except Exception as e:
            logger.exception(f"YouTube upload failed: {e}")
            raise RuntimeError(f"YouTube upload failed: {e}")
