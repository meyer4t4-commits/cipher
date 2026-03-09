"""
Agent Recommendation API — Analyzes user messages and recommends agents.
Powers the "Let Crawler scrape that for you?" cards in ChatView.
"""

import json
import re
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.logging import logger

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


# ---------------------------------------------------------------------------
# Agent catalog for keyword matching (fast path, no LLM needed)
# ---------------------------------------------------------------------------

AGENT_TRIGGERS = {
    "web": {
        "display_name": "Crawler",
        "keywords": ["scrape", "crawl", "fetch url", "web page", "download site",
                      "extract from website", "browse", "pull data from"],
        "description": "Web scraping and data extraction from websites",
    },
    "shell": {
        "display_name": "Bolt",
        "keywords": ["run command", "terminal", "shell", "bash", "execute script",
                      "server command", "ssh", "deploy script"],
        "description": "Execute shell commands and system operations",
    },
    "code": {
        "display_name": "Forge",
        "keywords": ["write code", "build a script", "create a program", "refactor",
                      "code review", "implement function", "write a bot"],
        "description": "Code generation, review, and refactoring",
    },
    "data": {
        "display_name": "Prism",
        "keywords": ["analyze data", "csv", "spreadsheet", "statistics", "parse data",
                      "data cleaning", "transform data", "visualize data"],
        "description": "Data analysis, transformation, and visualization",
    },
    "brave_search": {
        "display_name": "Radar",
        "keywords": ["search for", "find information", "look up", "research",
                      "what's the latest", "news about", "find articles"],
        "description": "Web search and research via Brave Search",
    },
    "image": {
        "display_name": "Canvas",
        "keywords": ["generate image", "create a logo", "design", "make a picture",
                      "draw", "illustration", "graphic", "visual"],
        "description": "AI image generation and design",
    },
    "video": {
        "display_name": "Director",
        "keywords": ["create video", "edit video", "make a clip", "video content",
                      "animation", "render video"],
        "description": "Video creation and editing",
    },
    "deploy": {
        "display_name": "Launchpad",
        "keywords": ["deploy", "push to production", "railway", "hosting",
                      "launch app", "docker", "kubernetes"],
        "description": "Application deployment and infrastructure",
    },
    "monitor": {
        "display_name": "Watchtower",
        "keywords": ["monitor", "uptime", "health check", "metrics", "alert",
                      "track performance", "system status"],
        "description": "System monitoring and alerting",
    },
    "communication": {
        "display_name": "Mercury",
        "keywords": ["send email", "send sms", "send message", "notify",
                      "slack message", "telegram", "draft email"],
        "description": "Multi-channel communication (email, SMS, Slack, Telegram)",
    },
    "trading": {
        "display_name": "Maverick",
        "keywords": ["trade", "stock", "crypto", "portfolio", "market order",
                      "buy shares", "sell position", "price", "quote", "ticker",
                      "what is tesla", "what is apple", "how much is",
                      "tsla", "aapl", "goog", "amzn", "msft", "nvda", "btc", "eth",
                      "market cap", "pe ratio", "stock price", "share price",
                      "trading at", "what's the price", "check the market"],
        "description": "Real-time stock/crypto prices, trading, and portfolio management",
    },
    "legal": {
        "display_name": "Arbiter",
        "keywords": ["contract", "legal review", "terms", "compliance",
                      "legal analysis", "nda", "agreement"],
        "description": "Legal document analysis and compliance review",
    },
    "apex_architect": {
        "display_name": "Apex",
        "keywords": ["property analysis", "real estate deal", "investment property",
                      "house analysis", "rental yield", "cap rate"],
        "description": "Real estate investment analysis and property evaluation",
    },
    "provisioning": {
        "display_name": "Terraform",
        "keywords": ["provision server", "infrastructure", "cloud setup",
                      "spin up", "create instance", "cloud resources"],
        "description": "Cloud infrastructure provisioning",
    },
    "scheduler": {
        "display_name": "Clockwork",
        "keywords": ["schedule", "cron", "automate recurring", "set timer",
                      "run every", "daily task", "weekly job"],
        "description": "Task scheduling and automation",
    },
    "research": {
        "display_name": "Oracle",
        "keywords": ["deep research", "comprehensive analysis", "investigation",
                      "due diligence", "market research", "competitive analysis"],
        "description": "Deep research and comprehensive analysis",
    },
    "file": {
        "display_name": "Vault",
        "keywords": ["organize files", "rename files", "move files", "convert format",
                      "file management", "sort documents", "backup files", "clean up folder"],
        "description": "File organization, conversion, and management",
    },
    "market_pulse": {
        "display_name": "Pulse",
        "keywords": ["market trends", "real estate market", "housing prices", "inventory levels",
                      "pricing trends", "market conditions", "home values", "median price"],
        "description": "Real estate market tracking and trend analysis",
    },
    "profitability_analyst": {
        "display_name": "Ledger",
        "keywords": ["profitability", "cash flow", "roi analysis", "net operating income",
                      "expense ratio", "rental income", "property financials", "cap rate analysis"],
        "description": "Property profitability and financial analysis",
    },
    "neighborhood_growth": {
        "display_name": "Atlas",
        "keywords": ["neighborhood score", "growth potential", "area analysis", "demographics",
                      "school ratings", "crime data", "walkability", "neighborhood trends"],
        "description": "Neighborhood scoring, growth analysis, and demographic insights",
    },
    "deal_flow": {
        "display_name": "Prospector",
        "keywords": ["find deals", "source properties", "property deals", "off market",
                      "deal flow", "investment opportunities", "distressed properties", "wholesale"],
        "description": "Property deal sourcing and opportunity pipeline",
    },
    "scout": {
        "display_name": "Pathfinder",
        "keywords": ["new markets", "expansion", "explore city", "emerging market",
                      "scout location", "market entry", "growth city", "relocation analysis"],
        "description": "Market exploration and expansion scouting",
    },
    "analyst": {
        "display_name": "Cipher Analytics",
        "keywords": ["financial model", "projections", "forecast", "data analysis",
                      "business analysis", "metrics", "kpi", "performance analysis"],
        "description": "Financial modeling, forecasting, and business analytics",
    },
    "outreach": {
        "display_name": "Piper",
        "keywords": ["outreach campaign", "cold email", "lead generation", "follow up",
                      "sales email", "prospect", "outreach sequence", "nurture campaign"],
        "description": "Outreach campaigns, lead generation, and follow-up sequences",
    },
    "chronos": {
        "display_name": "Chronos",
        "keywords": ["plan my day", "time management", "daily schedule", "prioritize tasks",
                      "morning routine", "time block", "agenda", "what should i do today"],
        "description": "Schedule optimization, time management, and daily planning",
    },
    "archivist": {
        "display_name": "Librarian",
        "keywords": ["archive", "organize knowledge", "document library", "catalog",
                      "find document", "knowledge base", "index files", "retrieve notes"],
        "description": "Document archiving, knowledge base management, and retrieval",
    },
    "sentinel": {
        "display_name": "Sentinel",
        "keywords": ["security scan", "vulnerability", "threat detection", "audit security",
                      "check for breaches", "scan email", "security alert", "intrusion"],
        "description": "Security monitoring, vulnerability scanning, and threat detection",
    },
    "synthesis": {
        "display_name": "Nexus",
        "keywords": ["combine reports", "cross reference", "synthesize", "merge insights",
                      "big picture", "connect the dots", "unified report", "multi-source analysis"],
        "description": "Cross-agent synthesis, unified reporting, and insight merging",
    },
    "skill_creator": {
        "display_name": "Architect",
        "keywords": ["create skill", "build capability", "new tool", "custom agent",
                      "extend cipher", "add feature", "build workflow", "create automation"],
        "description": "Custom skill and capability development for Cipher",
    },
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SuggestAgentRequest(BaseModel):
    user_message: str
    conversation_context: list[dict] = Field(default_factory=list)


class RecommendedAgent(BaseModel):
    agent_name: str
    display_name: str
    reason: str
    confidence: float
    suggested_instruction: str
    action: str = "spawn"


class AgentRecommendationResponse(BaseModel):
    should_recommend: bool
    recommended_agents: list[RecommendedAgent]
    chat_response: str = ""


# ---------------------------------------------------------------------------
# Recommendation Logic — keyword-first, fast and reliable
# ---------------------------------------------------------------------------

def _score_agent_match(message: str, agent_name: str, trigger_info: dict) -> float:
    """Score how well a message matches an agent's triggers. Returns 0.0-1.0."""
    msg_lower = message.lower()
    keywords = trigger_info["keywords"]

    # Count keyword matches
    matches = sum(1 for kw in keywords if kw in msg_lower)
    if matches == 0:
        return 0.0

    # Normalize: more matches = higher confidence
    base_score = min(matches / 3.0, 1.0)

    # Boost for action-oriented messages (verbs)
    action_words = ["can you", "please", "help me", "i need", "i want",
                    "go ahead", "do this", "run", "execute", "start",
                    "create", "build", "make", "send", "find"]
    has_action = any(aw in msg_lower for aw in action_words)
    if has_action:
        base_score = min(base_score + 0.15, 1.0)

    # Penalize short messages (likely not substantive enough)
    if len(message.split()) < 5:
        base_score *= 0.6

    return round(base_score, 2)


@router.post("/suggest-agent", response_model=AgentRecommendationResponse)
async def suggest_agent(request: SuggestAgentRequest):
    """
    Analyze user message and recommend an agent if appropriate.
    Uses keyword matching for speed and reliability.
    """
    message = request.user_message.strip()
    if not message:
        return AgentRecommendationResponse(
            should_recommend=False,
            recommended_agents=[],
        )

    # Score all agents
    scored = []
    for agent_name, info in AGENT_TRIGGERS.items():
        score = _score_agent_match(message, agent_name, info)
        if score > 0.0:
            scored.append((agent_name, info, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[2], reverse=True)

    # Only recommend if top score > 0.5
    if not scored or scored[0][2] < 0.5:
        return AgentRecommendationResponse(
            should_recommend=False,
            recommended_agents=[],
            chat_response="",
        )

    # Take top recommendation
    top_name, top_info, top_score = scored[0]

    recommended = RecommendedAgent(
        agent_name=top_name,
        display_name=top_info["display_name"],
        reason=top_info["description"],
        confidence=top_score,
        suggested_instruction=message,
        action="spawn",
    )

    logger.info(
        f"Agent recommendation: {top_info['display_name']} "
        f"(confidence={top_score:.2f}) for: '{message[:60]}...'"
    )

    return AgentRecommendationResponse(
        should_recommend=True,
        recommended_agents=[recommended],
        chat_response=f"I can have {top_info['display_name']} handle this for you.",
    )
