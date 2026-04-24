"""
agents/ceo_agent.py — CEO / Orchestrator Agent definition

The CEO Agent is a world-class YouTube strategist powered by GPT-4o.
It autonomously:
  1. Researches trending niches
  2. Designs video format, length, and target audience
  3. Creates a full scene-by-scene production plan
  4. Estimates cost and requests human approval
  5. Delegates production to CrewFactory sub-crews

Tools:
  - TrendResearchTool  (web-search simulation via GPT-4o internal knowledge)
  - CostEstimatorTool
  - ScriptApproverTool
"""

import logging
import os

from crewai import Agent, LLM

from tools.cost_estimator import CostEstimatorTool
from tools.script_approver import ScriptApproverTool
from tools.trend_research import TrendResearchTool

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_ceo_agent(openai_api_key: str) -> Agent:
    """
    Construct and return the CEO orchestrator Agent.

    Parameters
    ----------
    openai_api_key : str
        OpenAI API key for GPT-4o.

    Returns
    -------
    Agent
        Configured CrewAI Agent with CEO role.
    """
    llm = LLM(
        model="gpt-4o",
        api_key=openai_api_key,
        temperature=0.8,
        max_tokens=4096,
    )

    ceo = Agent(
        role="YouTube Channel CEO & Creative Director",
        goal=(
            "Autonomously run a profitable YouTube channel by researching trending niches, "
            "designing high-engagement video concepts, writing full scene-by-scene scripts, "
            "estimating production costs, obtaining approval, and orchestrating the full "
            "AI-driven production pipeline to publish videos that rank and go viral."
        ),
        backstory=(
            "You are Alex Mercer — a world-class YouTube strategist with 15 years of experience "
            "growing channels from zero to millions of subscribers. You have deep expertise in "
            "SEO, audience psychology, viral hooks, storytelling structure, and AI-assisted "
            "video production. You think in systems: every video you greenlight has a clear "
            "niche, a defined target audience, a compelling hook in the first 3 seconds, "
            "and an optimised title/thumbnail strategy. You obsess over data: CTR, AVD, "
            "impressions, and subscriber conversion. You obsess over DIVERSITY: you know the "
            "hottest trends span all categories — finance, lifestyle, science, sports, food, "
            "history, comedy, travel, health, gaming, DIY, and more. You actively seek "
            "opportunities across diverse niches and never default to AI-focused content "
            "unless it is genuinely the #1 trending topic right now. You know exactly which "
            "topics are trending and why they will perform. You delegate production to "
            "specialised sub-agents only after you have a tight, approved plan."
        ),
        llm=llm,
        tools=[
            TrendResearchTool(),
            CostEstimatorTool(),
            ScriptApproverTool(),
        ],
        verbose=True,
        allow_delegation=True,
        max_iter=10,
    )

    logger.info("CEO Agent created: GPT-4o, 3 tools, allow_delegation=True")
    return ceo
