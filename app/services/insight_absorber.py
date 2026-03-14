"""
Insight Absorber — Converts extracted content into actionable self-improvement.

When Cipher extracts a tweet, YouTube video, or article, this module analyzes it
for actionable intelligence and does ONE of three things:

1. STORE as a capability insight in memory (for future reference)
2. PROPOSE a concrete self-improvement experiment (fed to self-research loop)
3. BUILD a new capability or agent workflow based on what was learned

This is what makes Cipher genuinely learn from content — not just summarize it.

The key principle: "What did I learn, and what do I DO with it?"
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.logging import logger
from app.services.memory import store_memory, recall_memories


# ---------------------------------------------------------------------------
# Insight categories — what kind of actionable intelligence did we extract?
# ---------------------------------------------------------------------------
INSIGHT_TYPES = {
    "capability_gap": "Something Cipher can't do yet but should be able to",
    "workflow_pattern": "A multi-step automation pattern worth replicating",
    "tool_integration": "A new tool/API/service Cipher should integrate",
    "optimization": "A way to make an existing capability faster/better",
    "architecture": "A design pattern or architecture improvement",
    "market_intel": "Business/market intelligence relevant to Mark's projects",
    "competitive_intel": "What competitors or peers are building",
}


async def analyze_and_absorb(
    extracted_content: dict | str,
    source_url: str = "",
    source_type: str = "unknown",
    user_instruction: str = "",
) -> dict:
    """
    Analyze extracted content for actionable insights and absorb them.

    This is the main entry point. Called after content extraction completes.

    Returns:
        {
            "insights_found": int,
            "insights": [...],
            "actions_taken": [...],
            "stored_memory_ids": [...],
        }
    """
    # Convert to string if dict
    content_str = (
        json.dumps(extracted_content, indent=2, default=str)[:8000]
        if isinstance(extracted_content, dict)
        else str(extracted_content)[:8000]
    )

    # Step 1: Ask LLM to extract actionable insights
    insights = await _extract_insights(content_str, source_url, source_type, user_instruction)

    if not insights:
        logger.info("[INSIGHT ABSORBER] No actionable insights found in extracted content")
        return {"insights_found": 0, "insights": [], "actions_taken": [], "stored_memory_ids": []}

    # Step 2: For each insight, decide what to do and do it
    actions_taken = []
    stored_ids = []

    for insight in insights:
        insight_type = insight.get("type", "market_intel")
        action = insight.get("action", "store")

        # Always store in memory with rich metadata
        mem_id = store_memory(
            content=json.dumps(insight, default=str),
            metadata={
                "source": "insight_absorber",
                "source_url": source_url,
                "source_type": source_type,
                "insight_type": insight_type,
                "action": action,
                "priority": insight.get("priority", "medium"),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "tags": insight.get("tags", []),
            },
            collection_name="cipher_insights",
        )
        stored_ids.append(mem_id)

        # Take action based on insight type
        if action == "propose_experiment" and insight_type in ("capability_gap", "workflow_pattern", "tool_integration"):
            experiment = await _propose_experiment_from_insight(insight)
            if experiment:
                actions_taken.append({
                    "action": "experiment_proposed",
                    "insight": insight.get("summary", ""),
                    "experiment": experiment,
                })
                # Save experiment proposal to research queue
                _queue_experiment(experiment)

        elif action == "update_research_program" and insight_type in ("architecture", "optimization"):
            updated = _append_to_research_program(insight)
            if updated:
                actions_taken.append({
                    "action": "research_program_updated",
                    "insight": insight.get("summary", ""),
                    "added_priority": insight.get("research_priority", ""),
                })

        elif action == "store":
            actions_taken.append({
                "action": "stored_as_reference",
                "insight": insight.get("summary", ""),
                "memory_id": mem_id,
            })

    logger.info(
        f"[INSIGHT ABSORBER] Processed {len(insights)} insights, "
        f"{len(actions_taken)} actions taken, {len(stored_ids)} memories stored"
    )

    return {
        "insights_found": len(insights),
        "insights": insights,
        "actions_taken": actions_taken,
        "stored_memory_ids": stored_ids,
    }


async def _extract_insights(
    content: str,
    source_url: str,
    source_type: str,
    user_instruction: str,
) -> list[dict]:
    """
    Use LLM to extract actionable insights from content.

    Returns list of insight dicts:
    [
        {
            "type": "capability_gap|workflow_pattern|tool_integration|...",
            "summary": "One-line description",
            "detail": "What specifically can be learned",
            "action": "propose_experiment|update_research_program|store",
            "priority": "high|medium|low",
            "tags": ["tag1", "tag2"],
            "implementation_hint": "How Cipher could implement this",
            "research_priority": "Priority text for research program (if applicable)",
        }
    ]
    """
    try:
        from app.services.llm_router import chat_completion

        # Check what Cipher already knows/has
        existing_capabilities = _get_current_capabilities_summary()

        messages = [
            {"role": "system", "content": (
                "You are Cipher's Insight Absorber. Your job is to analyze content that was "
                "extracted from the web (tweets, YouTube videos, articles) and identify ACTIONABLE "
                "intelligence that Cipher can use to improve itself or help its operator Mark.\n\n"
                "Cipher is an AI daemon with real tools, agents, and APIs. It has:\n"
                f"{existing_capabilities}\n\n"
                "For each insight, determine:\n"
                "1. What TYPE of insight is it? (capability_gap, workflow_pattern, tool_integration, "
                "optimization, architecture, market_intel, competitive_intel)\n"
                "2. What specific ACTION should Cipher take? (propose_experiment, update_research_program, store)\n"
                "3. HOW would Cipher implement this? (concrete implementation hints)\n\n"
                "RULES:\n"
                "- Only extract insights that are ACTIONABLE — skip fluff and opinions\n"
                "- If someone built something cool, figure out how Cipher could replicate it\n"
                "- If there's a new tool/API, figure out how Cipher could integrate it\n"
                "- If there's a workflow pattern, figure out how Cipher could automate it\n"
                "- Be SPECIFIC in implementation hints — name files, functions, agents\n"
                "- Prioritize insights that directly benefit Mark's projects\n\n"
                "Output ONLY a JSON array of insight objects. If no actionable insights, return []."
            )},
            {"role": "user", "content": (
                f"Source: {source_url or 'unknown'}\n"
                f"Type: {source_type}\n"
                f"User said: {user_instruction}\n\n"
                f"Extracted content:\n{content}\n\n"
                "Extract all actionable insights as JSON array."
            )},
        ]

        result = await chat_completion(
            messages=messages,
            model_tier="balanced",
            max_tokens=2048,
            temperature=0.3,
        )

        if not result or not isinstance(result, dict):
            return []

        response_text = result.get("content", "").strip()

        # Parse JSON from response
        import re
        # Try to find JSON array in the response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            insights = json.loads(json_match.group())
            if isinstance(insights, list):
                return insights

        return []

    except Exception as e:
        logger.error(f"[INSIGHT ABSORBER] Failed to extract insights: {e}")
        return []


def _get_current_capabilities_summary() -> str:
    """Quick summary of what Cipher can currently do, for LLM context."""
    return (
        "- 30+ specialized agents (research, code, deploy, Shopify, real estate, trading, etc.)\n"
        "- Content extraction from YouTube, Twitter/X, web articles (ContentExtractorAgent)\n"
        "- Image generation (DALL-E 3, Stability AI)\n"
        "- Video generation (Replicate, fal.ai)\n"
        "- Web search (Brave Search API)\n"
        "- Browser automation (scraping, form filling, screenshots)\n"
        "- Self-healing and self-research loop (Karpathy-inspired autoresearch)\n"
        "- Memory system (persistent context across conversations)\n"
        "- Multi-model routing (Claude, GPT-4, Groq, DeepSeek)\n"
        "- Shopify Admin API (read/write products, pages, SEO)\n"
        "- Communication (email, SMS via Twilio)\n"
        "- Real estate analysis (ATTOM API, property valuation)\n"
        "- Voice synthesis (ElevenLabs)\n"
        "- iOS app frontend (SwiftUI)\n"
        "- Self-modification (can patch its own code)\n"
    )


async def _propose_experiment_from_insight(insight: dict) -> Optional[dict]:
    """
    Convert an actionable insight into a concrete experiment proposal
    for the self-research loop.
    """
    try:
        from app.services.llm_router import chat_completion

        messages = [
            {"role": "system", "content": (
                "You are Cipher's research engine. Convert this insight into a concrete "
                "experiment proposal that the self-research loop can execute.\n\n"
                "The experiment should modify ONE file in the Cipher codebase to add or "
                "improve a capability. Be specific about what code to write.\n\n"
                "Output ONLY a JSON object with: hypothesis, target_file, modification_type, "
                "reasoning, implementation_steps (list of strings)."
            )},
            {"role": "user", "content": json.dumps(insight, default=str)},
        ]

        result = await chat_completion(
            messages=messages,
            model_tier="balanced",
            max_tokens=1024,
            temperature=0.3,
        )

        if not result or not isinstance(result, dict):
            return None

        import re
        response_text = result.get("content", "").strip()
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            return json.loads(json_match.group())

        return None

    except Exception as e:
        logger.error(f"[INSIGHT ABSORBER] Failed to propose experiment: {e}")
        return None


def _queue_experiment(experiment: dict) -> None:
    """Save an experiment proposal to the research queue for the next training run."""
    try:
        queue_dir = Path(os.getenv("CIPHER_RESEARCH_DIR", "/tmp/cipher_research")) / "queued_experiments"
        queue_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"insight_experiment_{ts}.json"
        (queue_dir / filename).write_text(json.dumps(experiment, indent=2, default=str))

        logger.info(f"[INSIGHT ABSORBER] Queued experiment: {filename}")
    except Exception as e:
        logger.warning(f"[INSIGHT ABSORBER] Failed to queue experiment (non-fatal): {e}")


def _append_to_research_program(insight: dict) -> bool:
    """Append a new priority to the research program from an insight."""
    try:
        from app.services.self_research.autonomous_loop import RESEARCH_PROGRAM_PATH

        priority_text = insight.get("research_priority", "")
        if not priority_text:
            priority_text = f"- {insight.get('summary', 'Improvement from extracted content')}"

        program_path = RESEARCH_PROGRAM_PATH
        if program_path.exists():
            current = program_path.read_text()
        else:
            current = ""

        # Add under a new section for insight-driven priorities
        if "## Insight-Driven Priorities" not in current:
            current += "\n\n## Insight-Driven Priorities\n"
            current += "# Auto-added from content Cipher extracted and analyzed:\n"

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        current += f"\n### [{ts}] {insight.get('summary', 'New priority')}\n"
        current += f"{priority_text}\n"
        current += f"Source: {insight.get('source_url', 'conversation')}\n"

        program_path.parent.mkdir(parents=True, exist_ok=True)
        program_path.write_text(current)

        logger.info(f"[INSIGHT ABSORBER] Updated research program with new priority")
        return True

    except Exception as e:
        logger.warning(f"[INSIGHT ABSORBER] Failed to update research program: {e}")
        return False


# ---------------------------------------------------------------------------
# Convenience: absorb content that was just extracted
# ---------------------------------------------------------------------------

async def absorb_extracted_content(
    extraction_result: dict,
    source_url: str,
    user_message: str,
) -> dict:
    """
    Called directly after content extraction completes.
    Wraps analyze_and_absorb with content-extraction-specific logic.
    """
    # Determine source type from URL
    source_type = "article"
    url_lower = source_url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        source_type = "youtube"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        source_type = "twitter"
    elif "github.com" in url_lower:
        source_type = "github"

    return await analyze_and_absorb(
        extracted_content=extraction_result,
        source_url=source_url,
        source_type=source_type,
        user_instruction=user_message,
    )
