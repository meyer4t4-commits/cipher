"""
Cipher LLM Router — Quality-First Model Selection

PHILOSOPHY: Use the BEST model for each task type. Perfect output matters more
than saving money. Cascade is FAILOVER ONLY (primary model down → try backup),
NOT cost optimization. Cipher should never give a mediocre response when a
better model exists.

MODEL SELECTION IS SELF-UPDATING:
- The MODEL_REGISTRY defines all known models with capabilities and benchmarks
- The research loop can propose model upgrades when new models are released
- Agent-specific overrides ensure each agent gets the optimal brain for its task

Last updated: 2026-03-08 (March 2026 model landscape)
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

import litellm
from litellm import acompletion, completion_cost

from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import ModelTier

litellm.drop_params = True
litellm.set_verbose = False


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL REGISTRY — Single source of truth for all available models
# ═══════════════════════════════════════════════════════════════════════════════
# Each model entry includes:
#   - provider: LiteLLM provider prefix
#   - model_id: Full LiteLLM model string
#   - capabilities: What this model excels at
#   - context_window: Max context in tokens
#   - cost_per_m_input: Cost per million input tokens (USD)
#   - cost_per_m_output: Cost per million output tokens (USD)
#   - benchmark_scores: Key benchmark results (0-100 scale)
#   - released: Release date for freshness tracking
#   - notes: Why this model is in the registry

MODEL_REGISTRY = {
    # ── Anthropic (Claude) ──────────────────────────────────────────────────
    "claude-opus-4-6": {
        "model_id": "anthropic/claude-opus-4-6",
        "provider": "anthropic",
        "capabilities": ["reasoning", "coding", "creative", "vision", "tool_calling", "analysis", "agentic"],
        "context_window": 200_000,
        "cost_per_m_input": 15.0,
        "cost_per_m_output": 75.0,
        "benchmark_scores": {
            "humaneval": 95,
            "mmlu": 90,
            "reasoning": 97,
            "tool_use": 98,
            "coding": 95,
            "creative": 96,
        },
        "released": "2026-02-24",
        "notes": "Latest Opus. Best reasoning + agentic model. Upgrade from Opus 4.",
    },
    "claude-opus-4": {
        "model_id": "anthropic/claude-opus-4-20250514",
        "provider": "anthropic",
        "capabilities": ["reasoning", "coding", "creative", "vision", "tool_calling", "analysis"],
        "context_window": 200_000,
        "cost_per_m_input": 15.0,
        "cost_per_m_output": 75.0,
        "benchmark_scores": {
            "humaneval": 93,
            "mmlu": 88,
            "reasoning": 95,
            "tool_use": 96,
            "coding": 93,
            "creative": 95,
        },
        "released": "2025-05-14",
        "notes": "Previous Opus. Still excellent. Kept as fallback.",
    },
    "claude-sonnet-4": {
        "model_id": "anthropic/claude-sonnet-4-20250514",
        "provider": "anthropic",
        "capabilities": ["coding", "tool_calling", "vision", "reasoning", "creative", "analysis"],
        "context_window": 200_000,
        "cost_per_m_input": 3.0,
        "cost_per_m_output": 15.0,
        "benchmark_scores": {
            "humaneval": 92,
            "mmlu": 85,
            "reasoning": 88,
            "tool_use": 95,
            "coding": 92,
            "creative": 88,
        },
        "released": "2025-05-14",
        "notes": "Best coding model. Excellent tool use. Primary brain for Cipher.",
    },

    # ── xAI (Grok) ─────────────────────────────────────────────────────────
    "grok-4": {
        "model_id": "xai/grok-4-latest",
        "provider": "xai",
        "capabilities": ["reasoning", "analysis", "creative", "vision", "tool_calling", "coding"],
        "context_window": 131_072,
        "cost_per_m_input": 3.0,
        "cost_per_m_output": 15.0,
        "benchmark_scores": {
            "humaneval": 92,
            "mmlu": 90,
            "reasoning": 94,
            "tool_use": 90,
            "coding": 92,
            "creative": 90,
        },
        "released": "2026-02-01",
        "notes": "Latest Grok. Strong reasoning + real-time X/Twitter knowledge. Excellent all-rounder.",
    },
    "grok-3": {
        "model_id": "xai/grok-3-latest",
        "provider": "xai",
        "capabilities": ["reasoning", "analysis", "creative", "vision", "tool_calling"],
        "context_window": 131_072,
        "cost_per_m_input": 3.0,
        "cost_per_m_output": 15.0,
        "benchmark_scores": {
            "humaneval": 88,
            "mmlu": 86,
            "reasoning": 90,
            "tool_use": 85,
            "coding": 88,
            "creative": 87,
        },
        "released": "2025-04-01",
        "notes": "Strong reasoning, real-time X/Twitter knowledge, great for analysis.",
    },
    "grok-3-mini": {
        "model_id": "xai/grok-3-mini-latest",
        "provider": "xai",
        "capabilities": ["fast", "reasoning", "analysis"],
        "context_window": 131_072,
        "cost_per_m_input": 0.30,
        "cost_per_m_output": 0.50,
        "benchmark_scores": {
            "humaneval": 80,
            "mmlu": 78,
            "reasoning": 82,
            "tool_use": 75,
            "coding": 80,
            "creative": 72,
        },
        "released": "2025-04-01",
        "notes": "Fast and cheap. Good for fact-checking, quick queries, classification.",
    },

    # ── OpenAI ──────────────────────────────────────────────────────────────
    "gpt-5.4": {
        "model_id": "openai/gpt-5.4",
        "provider": "openai",
        "capabilities": ["reasoning", "vision", "coding", "creative", "tool_calling", "analysis", "computer_use"],
        "context_window": 1_050_000,
        "cost_per_m_input": 2.50,
        "cost_per_m_output": 15.0,
        "benchmark_scores": {
            "humaneval": 96,
            "mmlu": 94,
            "reasoning": 96,
            "tool_use": 96,
            "coding": 96,
            "creative": 94,
        },
        "released": "2026-03-05",
        "notes": "LATEST. 1M context, native computer use, financial plugins. OpenAI's frontier model. 3 days old.",
    },
    "gpt-5.3": {
        "model_id": "openai/gpt-5.3",
        "provider": "openai",
        "capabilities": ["reasoning", "vision", "coding", "creative", "tool_calling", "analysis"],
        "context_window": 128_000,
        "cost_per_m_input": 1.75,
        "cost_per_m_output": 14.0,
        "benchmark_scores": {
            "humaneval": 95,
            "mmlu": 93,
            "reasoning": 94,
            "tool_use": 94,
            "coding": 95,
            "creative": 93,
        },
        "released": "2026-02-01",
        "notes": "High intelligence, medium speed. Strong all-rounder. GPT-5.3-Codex variant for coding.",
    },
    "gpt-5": {
        "model_id": "openai/gpt-5",
        "provider": "openai",
        "capabilities": ["reasoning", "vision", "coding", "creative", "tool_calling", "analysis"],
        "context_window": 400_000,
        "cost_per_m_input": 1.25,
        "cost_per_m_output": 10.0,
        "benchmark_scores": {
            "humaneval": 94,
            "mmlu": 92,
            "reasoning": 93,
            "tool_use": 93,
            "coding": 94,
            "creative": 92,
        },
        "released": "2025-12-01",
        "notes": "GPT-5 — new default. 400K context, strong everything. Replaced GPT-4o as the default.",
    },
    "gpt-5-mini": {
        "model_id": "openai/gpt-5-mini",
        "provider": "openai",
        "capabilities": ["fast", "coding", "tool_calling", "vision"],
        "context_window": 400_000,
        "cost_per_m_input": 0.25,
        "cost_per_m_output": 2.0,
        "benchmark_scores": {
            "humaneval": 86,
            "mmlu": 85,
            "reasoning": 82,
            "tool_use": 86,
            "coding": 86,
            "creative": 80,
        },
        "released": "2025-12-01",
        "notes": "GPT-5 Mini — cheap + fast. 400K context. Replaces gpt-4o-mini.",
    },
    "gpt-4.1": {
        "model_id": "openai/gpt-4.1",
        "provider": "openai",
        "capabilities": ["coding", "tool_calling", "vision", "analysis"],
        "context_window": 1_050_000,
        "cost_per_m_input": 2.0,
        "cost_per_m_output": 8.0,
        "benchmark_scores": {
            "humaneval": 92,
            "mmlu": 88,
            "reasoning": 87,
            "tool_use": 92,
            "coding": 93,
            "creative": 85,
        },
        "released": "2025-04-14",
        "notes": "1M context. Smartest non-reasoning OpenAI model. Excellent coding + instruction following.",
    },
    "o3": {
        "model_id": "openai/o3",
        "provider": "openai",
        "capabilities": ["reasoning", "coding", "analysis"],
        "context_window": 200_000,
        "cost_per_m_input": 10.0,
        "cost_per_m_output": 40.0,
        "benchmark_scores": {
            "humaneval": 92,
            "mmlu": 90,
            "reasoning": 96,
            "tool_use": 88,
            "coding": 92,
            "creative": 80,
        },
        "released": "2025-04-01",
        "notes": "Deep reasoning model. Use for complex analytical tasks.",
    },
    "o3-pro": {
        "model_id": "openai/o3-pro",
        "provider": "openai",
        "capabilities": ["reasoning", "analysis", "coding"],
        "context_window": 200_000,
        "cost_per_m_input": 20.0,
        "cost_per_m_output": 80.0,
        "benchmark_scores": {
            "humaneval": 93,
            "mmlu": 92,
            "reasoning": 98,
            "tool_use": 88,
            "coding": 93,
            "creative": 82,
        },
        "released": "2025-06-01",
        "notes": "Most reliable reasoning. Thinks longer for hardest problems. Expensive but elite.",
    },
    "o4-mini": {
        "model_id": "openai/o4-mini",
        "provider": "openai",
        "capabilities": ["reasoning", "fast", "coding", "tool_calling"],
        "context_window": 200_000,
        "cost_per_m_input": 1.10,
        "cost_per_m_output": 4.40,
        "benchmark_scores": {
            "humaneval": 90,
            "mmlu": 88,
            "reasoning": 92,
            "tool_use": 88,
            "coding": 90,
            "creative": 78,
        },
        "released": "2025-04-01",
        "notes": "Fast reasoning model. Great cost-to-reasoning ratio. Replaces o3-mini.",
    },

    # ── DeepSeek ────────────────────────────────────────────────────────────
    "deepseek-reasoner": {
        "model_id": "deepseek/deepseek-reasoner",
        "provider": "deepseek",
        "capabilities": ["reasoning", "coding", "analysis"],
        "context_window": 64_000,
        "cost_per_m_input": 0.55,
        "cost_per_m_output": 2.19,
        "benchmark_scores": {
            "humaneval": 89,
            "mmlu": 85,
            "reasoning": 92,
            "tool_use": 70,
            "coding": 89,
            "creative": 72,
        },
        "released": "2025-01-20",
        "notes": "Excellent reasoning at low cost. Weak on tool use.",
    },
    "deepseek-chat": {
        "model_id": "deepseek/deepseek-chat",
        "provider": "deepseek",
        "capabilities": ["coding", "analysis", "fast"],
        "context_window": 64_000,
        "cost_per_m_input": 0.27,
        "cost_per_m_output": 1.10,
        "benchmark_scores": {
            "humaneval": 88,
            "mmlu": 83,
            "reasoning": 80,
            "tool_use": 68,
            "coding": 88,
            "creative": 70,
        },
        "released": "2025-01-20",
        "notes": "Strong coder at budget price. Poor tool use.",
    },

    # ── Google (Gemini) ────────────────────────────────────────────────────
    "gemini-2.5-pro": {
        "model_id": "google/gemini-2.5-pro",
        "provider": "google",
        "capabilities": ["reasoning", "vision", "coding", "creative", "tool_calling", "analysis"],
        "context_window": 1_000_000,
        "cost_per_m_input": 1.25,
        "cost_per_m_output": 10.0,
        "benchmark_scores": {
            "humaneval": 93,
            "mmlu": 92,
            "reasoning": 93,
            "tool_use": 90,
            "coding": 93,
            "creative": 90,
        },
        "released": "2025-12-01",
        "notes": "1M context, multimodal (text/image/video/audio). Competitive with Claude and GPT-5.",
    },
    "gemini-2.5-flash": {
        "model_id": "google/gemini-2.5-flash",
        "provider": "google",
        "capabilities": ["fast", "vision", "coding", "tool_calling"],
        "context_window": 1_000_000,
        "cost_per_m_input": 0.15,
        "cost_per_m_output": 0.60,
        "benchmark_scores": {
            "humaneval": 85,
            "mmlu": 84,
            "reasoning": 82,
            "tool_use": 84,
            "coding": 85,
            "creative": 78,
        },
        "released": "2025-12-01",
        "notes": "1M context, blazing fast, dirt cheap. Great for high-volume tasks.",
    },

    # ── Perplexity (Research-grade) ──────────────────────────────────────
    "sonar-pro": {
        "model_id": "perplexity/sonar-pro",
        "provider": "perplexity",
        "capabilities": ["reasoning", "analysis", "search"],
        "context_window": 200_000,
        "cost_per_m_input": 3.0,
        "cost_per_m_output": 15.0,
        "benchmark_scores": {
            "humaneval": 78,
            "mmlu": 85,
            "reasoning": 88,
            "tool_use": 70,
            "coding": 78,
            "creative": 75,
        },
        "released": "2025-09-01",
        "notes": "Built-in search grounding. Best for research queries with citations.",
    },

    # ── Groq (Llama) ───────────────────────────────────────────────────────
    "llama-3.3-70b": {
        "model_id": "groq/llama-3.3-70b-versatile",
        "provider": "groq",
        "capabilities": ["fast"],
        "context_window": 128_000,
        "cost_per_m_input": 0.59,
        "cost_per_m_output": 0.79,
        "benchmark_scores": {
            "humaneval": 75,
            "mmlu": 79,
            "reasoning": 72,
            "tool_use": 55,
            "coding": 75,
            "creative": 68,
        },
        "released": "2024-12-01",
        "notes": "Fastest inference via Groq. Use ONLY for speed-critical simple queries.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# QUALITY-FIRST MODEL MAP — Best model for each tier
# ═══════════════════════════════════════════════════════════════════════════════
# This is the PRIMARY routing table. Each tier gets the BEST model, period.
# No more starting with Llama and hoping it's "good enough."

MODEL_MAP = {
    ModelTier.DEFAULT: "anthropic/claude-sonnet-4-20250514",   # Primary brain — best all-rounder
    ModelTier.REASONING: "anthropic/claude-opus-4-6",           # Deep analysis needs the best (Opus 4.6)
    ModelTier.FAST: "xai/grok-3-mini-latest",                 # Fast + smart (not just fast)
    ModelTier.LOCAL: "groq/llama-3.3-70b-versatile",          # Speed-optimized local inference
    ModelTier.CODE: "anthropic/claude-sonnet-4-20250514",     # Claude dominates coding benchmarks
    ModelTier.AUTO: "anthropic/claude-sonnet-4-20250514",     # Fallback = best general model
}


# ═══════════════════════════════════════════════════════════════════════════════
# FAILOVER CHAINS — Only used when the primary model is DOWN or errors out
# NOT for cost optimization. Just reliability.
# ═══════════════════════════════════════════════════════════════════════════════

FAILOVER_CHAINS = {
    ModelTier.DEFAULT: [
        "anthropic/claude-sonnet-4-20250514",  # Primary
        "openai/gpt-5.4",                      # Backup 1 — GPT-5.4 (1M context, LATEST)
        "xai/grok-4-latest",                   # Backup 2 — Grok 4
        "deepseek/deepseek-chat",              # Emergency fallback
    ],
    ModelTier.FAST: [
        "xai/grok-3-mini-latest",              # Primary — fast + smart
        "openai/gpt-5-mini",                   # Backup — GPT-5 Mini (cheap, 400K)
        "openai/o4-mini",                      # Backup 2 — fast reasoning
        "groq/llama-3.3-70b-versatile",        # Emergency — fastest inference
    ],
    ModelTier.CODE: [
        "anthropic/claude-sonnet-4-20250514",  # Primary — best coder
        "openai/gpt-5.4",                      # Backup — 1M context, frontier coding
        "openai/gpt-5.3",                      # Backup 2 — GPT-5.3-Codex class
        "deepseek/deepseek-chat",              # Budget backup (still good at code)
    ],
    ModelTier.REASONING: [
        "anthropic/claude-opus-4-6",           # Primary — Opus 4.6, best reasoner
        "anthropic/claude-opus-4-20250514",    # Backup — previous Opus still excellent
        "openai/o3-pro",                       # Backup 2 — most reliable reasoning
        "openai/gpt-5.4",                      # Backup 3 — GPT-5.4 frontier reasoning
    ],
    ModelTier.AUTO: [
        "anthropic/claude-sonnet-4-20250514",  # Primary
        "openai/gpt-5.4",                      # Backup — OpenAI's best
        "xai/grok-4-latest",                   # Backup 2
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT-SPECIFIC MODEL OVERRIDES
# ═══════════════════════════════════════════════════════════════════════════════
# Each agent gets the best model for its specific task domain.
# The orchestrator can pass agent_name to get_model_for_agent() for optimal routing.

AGENT_MODEL_MAP = {
    # ── Coding & Infrastructure ──
    "code_agent":           "anthropic/claude-sonnet-4-20250514",  # Best coder (92% HumanEval)
    "shell_agent":          "anthropic/claude-sonnet-4-20250514",  # Needs precise command generation
    "deploy_agent":         "anthropic/claude-sonnet-4-20250514",  # Infrastructure = code
    "apex_architect_agent": "anthropic/claude-opus-4-6",            # Architecture needs deep reasoning
    "skill_creator_agent":  "anthropic/claude-sonnet-4-20250514",  # Creates agent code

    # ── Research & Analysis ──
    "research_agent":       "anthropic/claude-opus-4-6",            # Deep research = deep reasoning
    "analyst_agent":        "anthropic/claude-opus-4-6",            # Financial analysis
    "data_agent":           "anthropic/claude-sonnet-4-20250514",  # Data processing
    "legal_agent":          "anthropic/claude-opus-4-6",            # Legal = zero tolerance for errors
    "synthesis_agent":      "anthropic/claude-opus-4-6",            # Cross-domain synthesis

    # ── Real Estate ──
    "scout_agent":          "anthropic/claude-sonnet-4-20250514",  # Property scouting
    "market_pulse_agent":   "anthropic/claude-sonnet-4-20250514",  # Market analysis
    "profitability_analyst_agent": "anthropic/claude-opus-4-6",          # Financial modeling
    "neighborhood_growth_agent":   "anthropic/claude-sonnet-4-20250514",
    "deal_flow_agent":      "anthropic/claude-opus-4-6",            # Deal evaluation = high stakes

    # ── Media Generation ──
    "image_agent":          "anthropic/claude-sonnet-4-20250514",  # Prompt engineering for DALL-E/Stability
    "video_agent":          "anthropic/claude-sonnet-4-20250514",  # Prompt engineering for Replicate/fal

    # ── Communication ──
    "communication_agent":  "anthropic/claude-sonnet-4-20250514",  # Email/SMS composition
    "outreach_agent":       "anthropic/claude-sonnet-4-20250514",  # Outreach messaging

    # ── Search & Intelligence ──
    "brave_search_agent":   "xai/grok-3-mini-latest",             # Fast search result processing
    "web_agent":            "anthropic/claude-sonnet-4-20250514",  # Web interaction
    "sentinel_agent":       "xai/grok-3-mini-latest",             # Monitoring = fast checks

    # ── Organization & Scheduling ──
    "scheduler_agent":      "xai/grok-3-mini-latest",             # Simple scheduling logic
    "chronos_agent":        "xai/grok-3-mini-latest",             # Time-based tasks
    "archivist_agent":      "xai/grok-3-mini-latest",             # File organization
    "file_agent":           "xai/grok-3-mini-latest",             # File operations

    # ── Monitoring ──
    "monitor_agent":        "xai/grok-3-mini-latest",             # System monitoring
    "provisioning_agent":   "anthropic/claude-sonnet-4-20250514",  # Server provisioning = infrastructure

    # ── Trading ──
    "trading_agent":        "anthropic/claude-opus-4-6",            # Financial trading = zero error tolerance
}


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-UPDATING BENCHMARKS FILE
# ═══════════════════════════════════════════════════════════════════════════════
# The research loop writes updated model benchmarks here.
# On next restart, the router loads them and adjusts routing.

BENCHMARKS_FILE = Path("./data/model_benchmarks.json")


def _load_custom_benchmarks() -> dict:
    """Load self-updated model benchmarks from the research loop."""
    if BENCHMARKS_FILE.exists():
        try:
            data = json.loads(BENCHMARKS_FILE.read_text(encoding="utf-8"))
            logger.info(f"Loaded custom model benchmarks (updated: {data.get('updated_at', 'unknown')})")
            return data
        except Exception as e:
            logger.warning(f"Failed to load custom benchmarks: {e}")
    return {}


def save_model_benchmarks(benchmarks: dict):
    """Save updated benchmarks from research loop. Called by autonomous_loop."""
    BENCHMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    benchmarks["updated_at"] = datetime.now(timezone.utc).isoformat()
    BENCHMARKS_FILE.write_text(json.dumps(benchmarks, indent=2), encoding="utf-8")
    logger.info("Saved updated model benchmarks")


def _apply_custom_overrides():
    """Apply research-loop-discovered model overrides to routing tables."""
    custom = _load_custom_benchmarks()
    overrides = custom.get("model_map_overrides", {})
    agent_overrides = custom.get("agent_model_overrides", {})

    for tier_str, model_id in overrides.items():
        try:
            tier = ModelTier(tier_str)
            if model_id != MODEL_MAP.get(tier):
                logger.info(f"Research override: {tier.value} → {model_id}")
                MODEL_MAP[tier] = model_id
        except (ValueError, KeyError):
            pass

    for agent_name, model_id in agent_overrides.items():
        if model_id != AGENT_MODEL_MAP.get(agent_name):
            logger.info(f"Research override: {agent_name} → {model_id}")
            AGENT_MODEL_MAP[agent_name] = model_id


# Apply overrides at import time
_apply_custom_overrides()


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def get_model_for_tier(tier: ModelTier) -> str:
    """Get the best model for a given tier."""
    return MODEL_MAP.get(tier, "anthropic/claude-sonnet-4-20250514")


def get_model_for_agent(agent_name: str) -> str:
    """Get the optimal model for a specific agent."""
    return AGENT_MODEL_MAP.get(agent_name, get_model_for_tier(ModelTier.DEFAULT))


def get_provider(model_id: str) -> str:
    """Extract provider name from LiteLLM model ID."""
    if "/" in model_id:
        return model_id.split("/")[0]
    return "unknown"


def get_registry_info() -> dict:
    """Get the full model registry for display/debugging."""
    return {
        "registry": MODEL_REGISTRY,
        "model_map": {t.value: m for t, m in MODEL_MAP.items()},
        "agent_map": AGENT_MODEL_MAP,
        "failover_chains": {t.value: chain for t, chain in FAILOVER_CHAINS.items()},
        "custom_benchmarks_loaded": BENCHMARKS_FILE.exists(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT COMPLETION WITH TOOLS (Agentic Loop)
# ═══════════════════════════════════════════════════════════════════════════════

async def chat_completion_with_tools(
    messages,
    model_tier=ModelTier.DEFAULT,
    max_tokens=4096,
    temperature=0.7,
    system_prompt=None,
    tools=None,
    agent_name: Optional[str] = None,
    tool_choice=None,
):
    """
    Chat completion with tool/function calling support.
    Uses the BEST model for the tier (or agent-specific override).
    Failover chain only triggers on errors.

    Args:
        agent_name: If provided, uses agent-specific model override
    """
    # Agent-specific model takes priority over tier
    if agent_name and agent_name in AGENT_MODEL_MAP:
        model_id = AGENT_MODEL_MAP[agent_name]
    else:
        model_id = get_model_for_tier(model_tier)

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    start_time = time.time()

    kwargs = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice or "auto"

    # Try primary model, failover on error
    failover = FAILOVER_CHAINS.get(model_tier, [model_id])
    last_error = None

    for attempt, try_model in enumerate(failover):
        if attempt == 0:
            try_model = model_id  # Always try the selected model first
        try:
            kwargs["model"] = try_model
            response = await acompletion(**kwargs)
            latency_ms = (time.time() - start_time) * 1000

            if attempt > 0:
                logger.warning(f"Failover success: {model_id} → {try_model} (attempt {attempt + 1})")

            message = response.choices[0].message
            content = message.content or ""
            usage = response.usage

            try:
                cost = completion_cost(completion_response=response)
            except Exception:
                cost = 0.0

            # Extract tool calls if present
            tool_calls = []
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    })

            return {
                "content": content,
                "model_used": try_model,
                "model_requested": model_id,
                "provider": get_provider(try_model),
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost_usd": cost,
                "latency_ms": latency_ms,
                "tool_calls": tool_calls,
                "finish_reason": response.choices[0].finish_reason,
                "failover_attempt": attempt,
            }

        except Exception as e:
            last_error = e
            logger.warning(f"Model {try_model} failed (attempt {attempt + 1}): {e}")
            start_time = time.time()  # Reset timer for next attempt
            continue

    # All models failed
    raise last_error or Exception("All failover models failed")


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT COMPLETION (Non-tool-calling, used by some services)
# ═══════════════════════════════════════════════════════════════════════════════

async def chat_completion(
    messages,
    model_tier=ModelTier.DEFAULT,
    max_tokens=4096,
    temperature=0.7,
    system_prompt=None,
    cascade_enabled=None,  # DEPRECATED — kept for backward compat, always ignored
    agent_name: Optional[str] = None,
):
    """
    Chat completion — quality-first routing.
    cascade_enabled is DEPRECATED and ignored. Failover only on errors.
    """
    # Agent-specific model takes priority
    if agent_name and agent_name in AGENT_MODEL_MAP:
        model_id = AGENT_MODEL_MAP[agent_name]
    else:
        model_id = get_model_for_tier(model_tier)

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    # Try primary model with failover
    failover = FAILOVER_CHAINS.get(model_tier, [model_id])
    last_error = None

    for attempt, try_model in enumerate(failover):
        if attempt == 0:
            try_model = model_id  # Primary model first
        try:
            start_time = time.time()
            response = await acompletion(
                model=try_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            latency_ms = (time.time() - start_time) * 1000
            content = response.choices[0].message.content
            usage = response.usage

            try:
                cost = completion_cost(completion_response=response)
            except Exception:
                cost = 0.0

            if attempt > 0:
                logger.warning(f"Failover success: {model_id} → {try_model} (attempt {attempt + 1})")

            return {
                "content": content,
                "model_used": try_model,
                "model_requested": model_id,
                "provider": get_provider(try_model),
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost_usd": cost,
                "latency_ms": latency_ms,
                "response_quality_score": 0.95,
                "cascade_attempts": attempt,
                "cascade_enabled": False,
                "failover_attempt": attempt,
            }

        except Exception as e:
            last_error = e
            logger.warning(f"Model {try_model} failed (attempt {attempt + 1}): {e}")
            continue

    raise last_error or Exception("All failover models failed")


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMING COMPLETION
# ═══════════════════════════════════════════════════════════════════════════════

async def stream_completion(
    messages,
    model_tier=ModelTier.DEFAULT,
    max_tokens=4096,
    temperature=0.7,
    system_prompt=None,
    agent_name: Optional[str] = None,
):
    """Stream completion with quality-first model selection."""
    if agent_name and agent_name in AGENT_MODEL_MAP:
        model_id = AGENT_MODEL_MAP[agent_name]
    else:
        model_id = get_model_for_tier(model_tier)

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        response = await acompletion(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        logger.error(f"Stream completion failed with {model_id}: {e}")
        yield str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL AVAILABILITY CHECK
# ═══════════════════════════════════════════════════════════════════════════════

async def check_model_availability() -> list[dict]:
    """Check availability of all configured models."""
    results = []

    for tier, model_id in MODEL_MAP.items():
        provider = get_provider(model_id)
        # Check if the provider's API key is configured
        has_key = True
        if provider == "anthropic":
            has_key = bool(settings.anthropic_api_key)
        elif provider == "openai":
            has_key = bool(settings.openai_api_key)
        elif provider == "xai":
            has_key = bool(getattr(settings, "xai_api_key", ""))
        elif provider == "deepseek":
            has_key = bool(settings.deepseek_api_key)
        elif provider == "google":
            has_key = bool(getattr(settings, "google_api_key", ""))
        elif provider == "perplexity":
            has_key = bool(getattr(settings, "perplexity_api_key", ""))
        elif provider == "groq":
            has_key = bool(settings.groq_api_key)

        results.append({
            "tier": tier.value,
            "model_id": model_id,
            "provider": provider,
            "api_key_configured": has_key,
            "available": has_key,
        })

    # Also include agent-specific models
    unique_agent_models = set(AGENT_MODEL_MAP.values())
    for model_id in unique_agent_models:
        if model_id not in [r["model_id"] for r in results]:
            provider = get_provider(model_id)
            results.append({
                "tier": "agent_specific",
                "model_id": model_id,
                "provider": provider,
                "available": True,
            })

    return results
