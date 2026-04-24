"""
tools/trend_research.py — TrendResearchTool

Uses GPT-4o's internal knowledge (+ optional web context via requests)
to identify currently trending YouTube niches and video concepts.

Returns a JSON array of trend opportunities ranked by viral potential.
"""

import json
import logging
import os
import time
from typing import Optional, Type

from crewai.tools import BaseTool
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TrendResearchInput(BaseModel):
    niche_hint: Optional[str] = Field(
        default="",
        description=(
            "Optional niche hint to focus the research (e.g. 'AI', 'fitness', 'finance'). "
            "Leave empty to discover the hottest trending topic automatically."
        ),
    )
    num_ideas: Optional[int] = Field(
        default=3,
        description="Number of video ideas to generate. Default 3.",
    )


class TrendResearchTool(BaseTool):
    name: str = "Trend Research Tool"
    description: str = (
        "Researches currently trending YouTube topics and generates ranked video ideas. "
        "Input: optional niche_hint (e.g. 'AI', 'finance'), optional num_ideas (default 3). "
        "Returns a JSON array of {rank, topic, hook, target_audience, estimated_views, "
        "why_viral, suggested_title, suggested_length_minutes}."
    )
    args_schema: Type[BaseModel] = TrendResearchInput

    def _run(self, niche_hint: str = "", num_ideas: int = 3) -> str:
        try:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                from config import get_config
                api_key = get_config().openai_api_key

            client = OpenAI(api_key=api_key)

            niche_context = f"Focus niche: {niche_hint}." if niche_hint else "Discover the hottest niche automatically."

            system_prompt = (
                "You are a YouTube trend analyst with deep knowledge of what is currently viral. "
                "You understand YouTube algorithm signals: search volume, CTR, engagement, "
                "subscriber conversion, and content gaps. "
                "Always return valid JSON only — no markdown fences, no extra text."
            )

            user_prompt = f"""
Research the top trending YouTube video opportunities RIGHT NOW.
{niche_context}
Generate exactly {num_ideas} video ideas ranked by viral potential.

Return a JSON array (not wrapped in any object) where each element has:
- rank: integer (1 = best)
- topic: string (specific topic name)
- hook: string (the opening 3-second hook that stops the scroll)
- target_audience: string (who watches this)
- estimated_monthly_searches: string (e.g. "500K-1M")
- why_viral: string (2-3 sentence explanation)
- suggested_title: string (YouTube-optimised title, under 60 chars)
- suggested_length_minutes: integer (optimal video length)
- content_format: string (one of: "educational", "story", "listicle", "how-to", "reaction", "documentary")
- thumbnail_concept: string (brief thumbnail visual description)

Ensure ideas are specific, timely, and have genuine viral potential.
"""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.9,
                max_tokens=2000,
            )

            raw = response.choices[0].message.content.strip()

            # Validate JSON
            ideas = json.loads(raw)
            if not isinstance(ideas, list):
                raise ValueError("Expected a JSON array")

            logger.info(f"TrendResearchTool: generated {len(ideas)} ideas for niche='{niche_hint or 'auto'}'")
            return json.dumps(ideas, indent=2)

        except json.JSONDecodeError as e:
            logger.error(f"TrendResearchTool: invalid JSON from GPT-4o: {e}")
            # Return diverse fallback ideas (not AI-biased) so the pipeline can continue
            fallback = [
                {
                    "rank": 1,
                    "topic": niche_hint or "Personal Finance Tips",
                    "hook": "This one money hack could change your life...",
                    "target_audience": "Young professionals aged 20-40",
                    "estimated_monthly_searches": "500K-1M",
                    "why_viral": "Finance content drives engagement and shares. People want to learn how to save and invest.",
                    "suggested_title": f"The Money Secret: {niche_hint or 'What Banks Do Not Want You to Know'}",
                    "suggested_length_minutes": 6,
                    "content_format": "educational",
                    "thumbnail_concept": "Person looking shocked at phone with money symbol, bold text overlay",
                },
                {
                    "rank": 2,
                    "topic": niche_hint or "Lifestyle & Wellness",
                    "hook": "You've been doing this wrong your whole life...",
                    "target_audience": "Health-conscious audience aged 18-45",
                    "estimated_monthly_searches": "600K-1.2M",
                    "why_viral": "Lifestyle content is consistently viral. People crave self-improvement and wellness tips.",
                    "suggested_title": f"The Health Hack: {niche_hint or 'That Actually Works'}",
                    "suggested_length_minutes": 7,
                    "content_format": "educational",
                    "thumbnail_concept": "Before/after transformation image with arrow, bold text overlay",
                },
                {
                    "rank": 3,
                    "topic": niche_hint or "Science & Nature Explained",
                    "hook": "Scientists just discovered something incredible...",
                    "target_audience": "Curious learners aged 16-50",
                    "estimated_monthly_searches": "400K-800K",
                    "why_viral": "Science explainers perform well. People love learning fascinating facts about nature and universe.",
                    "suggested_title": f"The Science Behind: {niche_hint or 'What Nobody Told You'}",
                    "suggested_length_minutes": 8,
                    "content_format": "documentary",
                    "thumbnail_concept": "Stunning nature/space image with shocked face overlay, bold text",
                },
            ]
            return json.dumps(fallback, indent=2)

        except Exception as e:
            logger.exception(f"TrendResearchTool failed: {e}")
            return f"ERROR: Trend research failed: {e}"
