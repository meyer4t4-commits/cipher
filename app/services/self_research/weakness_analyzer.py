"""
Weakness Analyzer — Identifies Cipher's gaps and suggests overnight training priorities.

Analyzes self-test results, experiment history, and error patterns to determine:
1. What capabilities are weakest (failing tests, low scores)
2. What agents need improvement (error patterns in tool execution logs)
3. What new skills to build overnight (gap analysis)
4. Concrete suggestions for the research program

This is what makes the auto-training loop intelligent — instead of random
experiments, it focuses on actual weaknesses.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.logging import logger
from app.services.self_research.experiment_runner import ExperimentLog, RESEARCH_DIR


# Categories of weakness with severity weights
WEAKNESS_CATEGORIES = {
    "api_health": {
        "label": "API Connectivity",
        "description": "External service connections (Brave Search, OpenAI, ElevenLabs, etc.)",
        "severity": 0.9,  # High — broken APIs mean broken agents
    },
    "agent_execution": {
        "label": "Agent Execution",
        "description": "Agents failing to complete tasks or returning errors",
        "severity": 0.85,
    },
    "tool_reliability": {
        "label": "Tool Reliability",
        "description": "Direct tools (run_shell, read_file, search_web) failing",
        "severity": 0.8,
    },
    "response_quality": {
        "label": "Response Quality",
        "description": "LLM producing empty, off-topic, or low-quality responses",
        "severity": 0.75,
    },
    "prompt_coherence": {
        "label": "Prompt Coherence",
        "description": "Cipher breaking character or ignoring system prompt directives",
        "severity": 0.7,
    },
    "memory_system": {
        "label": "Memory System",
        "description": "PostgreSQL memory recall, relevance scoring, or storage issues",
        "severity": 0.65,
    },
    "streaming": {
        "label": "Streaming Pipeline",
        "description": "SSE streaming, heartbeat, or iOS rendering issues",
        "severity": 0.6,
    },
    "vision": {
        "label": "Vision & Image Processing",
        "description": "Image analysis, generation, or multimodal handling",
        "severity": 0.6,
    },
    "performance": {
        "label": "Performance & Latency",
        "description": "Slow responses, timeout issues, or inefficient routing",
        "severity": 0.5,
    },
}


def analyze_weaknesses(
    test_results: Optional[dict] = None,
    experiment_history: Optional[list] = None,
) -> dict:
    """
    Analyze Cipher's current weaknesses based on test results and experiment history.

    Returns:
        {
            "weaknesses": [
                {
                    "category": str,
                    "label": str,
                    "severity": float (0-1),
                    "score": float (0-1, lower = weaker),
                    "evidence": [str],
                    "suggestion": str,
                }
            ],
            "strengths": [str],
            "overnight_priorities": [str],  # Ordered list of what to train
            "research_program_update": str,  # Suggested additions to research_program.md
        }
    """
    weaknesses = []
    strengths = []
    evidence_by_category = {k: [] for k in WEAKNESS_CATEGORIES}
    scores_by_category = {k: [] for k in WEAKNESS_CATEGORIES}

    # --- Analyze self-test results ---
    if test_results:
        for test in test_results.get("results", []):
            category = _categorize_test(test)
            if not test.get("passed", False):
                evidence_by_category[category].append(
                    f"Test '{test['name']}' failed: {test.get('error', 'unknown error')}"
                )
                scores_by_category[category].append(test.get("score", 0.0))
            else:
                scores_by_category[category].append(test.get("score", 1.0))

    # --- Analyze experiment history for patterns ---
    if experiment_history is None:
        try:
            exp_log = ExperimentLog()
            experiment_history = exp_log.get_recent(50)
        except Exception:
            experiment_history = []

    # Count discarded experiments by category
    discard_counts = {}
    error_patterns = {}
    for exp in experiment_history:
        if not exp.get("kept", False):
            mod_type = exp.get("modification_type", "unknown")
            discard_counts[mod_type] = discard_counts.get(mod_type, 0) + 1

        if exp.get("error"):
            error_str = str(exp["error"])[:100]
            error_patterns[error_str] = error_patterns.get(error_str, 0) + 1

    # Map mod_types to weakness categories
    if discard_counts.get("agent_improve", 0) > 3:
        evidence_by_category["agent_execution"].append(
            f"Multiple agent improvement experiments discarded ({discard_counts['agent_improve']}x)"
        )
    if discard_counts.get("prompt_tune", 0) > 3:
        evidence_by_category["prompt_coherence"].append(
            f"Multiple prompt tuning experiments discarded ({discard_counts['prompt_tune']}x)"
        )

    # Recurring errors indicate systemic issues
    for error_msg, count in sorted(error_patterns.items(), key=lambda x: -x[1]):
        if count >= 2:
            category = _categorize_error(error_msg)
            evidence_by_category[category].append(
                f"Recurring error ({count}x): {error_msg}"
            )

    # --- Build weakness list ---
    for cat_key, cat_info in WEAKNESS_CATEGORIES.items():
        evidence = evidence_by_category.get(cat_key, [])
        scores = scores_by_category.get(cat_key, [])

        if not evidence and not scores:
            continue

        avg_score = sum(scores) / len(scores) if scores else 1.0

        if evidence or avg_score < 0.8:
            weaknesses.append({
                "category": cat_key,
                "label": cat_info["label"],
                "severity": cat_info["severity"],
                "score": round(avg_score, 3),
                "evidence": evidence[:5],  # Top 5 pieces of evidence
                "suggestion": _get_suggestion(cat_key, evidence, avg_score),
            })
        elif avg_score >= 0.9:
            strengths.append(f"{cat_info['label']}: score {avg_score:.2f}")

    # Sort weaknesses by combined severity and score (worst first)
    weaknesses.sort(key=lambda w: w["severity"] * (1 - w["score"]), reverse=True)

    # --- Generate overnight priorities ---
    overnight_priorities = []
    for w in weaknesses[:5]:  # Top 5 weaknesses
        overnight_priorities.append(
            f"[{w['label']}] {w['suggestion']}"
        )

    # Always add capability expansion suggestions
    overnight_priorities.extend(_get_capability_suggestions(experiment_history))

    # --- Generate research program update ---
    research_update = _generate_research_update(weaknesses, overnight_priorities)

    return {
        "weaknesses": weaknesses,
        "strengths": strengths,
        "overnight_priorities": overnight_priorities[:10],
        "research_program_update": research_update,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "test_score": test_results.get("aggregate_score") if test_results else None,
    }


def _categorize_test(test: dict) -> str:
    """Categorize a test result into a weakness category."""
    name = test.get("name", "").lower()
    category = test.get("category", "").lower()

    if "api" in name or "health" in name or "connection" in name:
        return "api_health"
    elif "agent" in name or "delegate" in name:
        return "agent_execution"
    elif "tool" in name or "shell" in name or "file" in name:
        return "tool_reliability"
    elif "prompt" in name or "character" in name or "coherence" in name:
        return "prompt_coherence"
    elif "memory" in name or "recall" in name or "chroma" in name:
        return "memory_system"
    elif "stream" in name or "sse" in name:
        return "streaming"
    elif "vision" in name or "image" in name:
        return "vision"
    elif "latency" in name or "speed" in name or "timeout" in name:
        return "performance"
    elif "quality" in category or "response" in name:
        return "response_quality"
    else:
        return "tool_reliability"  # Default


def _categorize_error(error_msg: str) -> str:
    """Categorize an error message into a weakness category."""
    error_lower = error_msg.lower()

    if "api" in error_lower or "connection" in error_lower or "timeout" in error_lower:
        return "api_health"
    elif "agent" in error_lower or "registry" in error_lower:
        return "agent_execution"
    elif "memory" in error_lower or "chroma" in error_lower:
        return "memory_system"
    elif "stream" in error_lower or "sse" in error_lower:
        return "streaming"
    elif "image" in error_lower or "vision" in error_lower:
        return "vision"
    else:
        return "tool_reliability"


def _get_suggestion(category: str, evidence: list, score: float) -> str:
    """Generate a specific improvement suggestion for a weakness."""
    suggestions = {
        "api_health": "Add retry logic and failover for external API calls. Verify API keys are valid and not expired.",
        "agent_execution": "Improve agent error handling. Ensure agents validate inputs and return structured errors.",
        "tool_reliability": "Add input validation and better error messages to direct tools. Test edge cases.",
        "response_quality": "Tune system prompt for more actionable responses. Add quality gate checks.",
        "prompt_coherence": "Strengthen personality directives. Add examples of correct vs incorrect behavior.",
        "memory_system": "Optimize PostgreSQL memory relevance scoring. Ensure memories are being stored and retrieved correctly.",
        "streaming": "Test SSE heartbeat pattern. Verify iOS client handles keepalive tokens correctly.",
        "vision": "Test image generation end-to-end. Verify DALL-E 3 and Stability AI fallback work.",
        "performance": "Profile the orchestrator pipeline. Optimize the slowest stages (memory recall, fact-checking).",
    }

    base = suggestions.get(category, "Investigate and fix failing tests in this category.")

    if score < 0.3:
        return f"CRITICAL: {base} Score is dangerously low ({score:.2f})."
    elif score < 0.6:
        return f"HIGH PRIORITY: {base}"
    else:
        return base


def _get_capability_suggestions(experiment_history: list) -> list:
    """Suggest new capabilities to build based on what's missing."""
    suggestions = []

    # Check if certain capabilities have never been tested
    tested_areas = set()
    for exp in experiment_history:
        tested_areas.add(exp.get("modification_type", ""))
        target = exp.get("target_file", "")
        if "vision" in target:
            tested_areas.add("vision")
        if "voice" in target:
            tested_areas.add("voice")
        if "streaming" in target:
            tested_areas.add("streaming")

    # Suggest areas that haven't been touched
    if "voice" not in tested_areas:
        suggestions.append("[Capability] Test and improve ElevenLabs voice synthesis and TTS pipeline")
    if "vision" not in tested_areas:
        suggestions.append("[Capability] Test end-to-end image generation and vision analysis")
    if "streaming" not in tested_areas:
        suggestions.append("[Capability] Stress-test SSE streaming under load")

    return suggestions[:3]


def _generate_research_update(weaknesses: list, priorities: list) -> str:
    """Generate a suggested update to research_program.md based on weakness analysis."""
    if not weaknesses:
        return "No changes needed — all systems operating within normal parameters."

    lines = ["## Auto-Generated Priority Updates", ""]
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    for i, w in enumerate(weaknesses[:5], 1):
        lines.append(f"### Auto-Priority {i}: {w['label']} (score: {w['score']:.2f})")
        lines.append(f"- {w['suggestion']}")
        if w['evidence']:
            lines.append(f"- Evidence: {w['evidence'][0]}")
        lines.append("")

    return "\n".join(lines)
