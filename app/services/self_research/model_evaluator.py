"""
Model Evaluator — Autonomous model benchmarking for the research loop.

The research loop can call this to:
1. Test new models as they become available
2. Re-benchmark existing models on Cipher-specific tasks
3. Update the MODEL_MAP and AGENT_MODEL_MAP when a better model is found
4. Track model performance over time

This is how Cipher stays current without manual intervention.
When xAI releases Grok 5 or Anthropic releases Claude 4, the research loop
can discover it, benchmark it, and promote it — all while Mark sleeps.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.logging import logger

# Lazy imports to avoid circular dependency
_litellm = None
_settings = None


def _get_litellm():
    global _litellm
    if _litellm is None:
        import litellm
        _litellm = litellm
    return _litellm


def _get_settings():
    global _settings
    if _settings is None:
        from app.core.config import settings
        _settings = settings
    return _settings


# ═══════════════════════════════════════════════════════════════════════════════
# CIPHER-SPECIFIC BENCHMARK SUITE
# ═══════════════════════════════════════════════════════════════════════════════
# These tests evaluate what matters for Cipher's actual use cases,
# not generic benchmarks. Each test has a category, prompt, and scoring criteria.

CIPHER_BENCHMARKS = [
    {
        "id": "coding_python",
        "category": "coding",
        "prompt": "Write a Python function that takes a list of stock tickers and returns the top 3 by market cap. Use yfinance. Include error handling for invalid tickers.",
        "score_criteria": ["has_function_def", "has_error_handling", "has_yfinance_import", "has_return"],
        "weight": 3.0,
    },
    {
        "id": "coding_swift",
        "category": "coding",
        "prompt": "Write a SwiftUI view that shows a list of items with pull-to-refresh, empty state, and loading indicator. Use modern Swift 5.9 features.",
        "score_criteria": ["has_struct_view", "has_refreshable", "has_loading_state", "has_empty_state"],
        "weight": 2.0,
    },
    {
        "id": "tool_calling",
        "category": "tool_use",
        "prompt": "I need you to search the web for the current Bitcoin price and then send the result to Mark via SMS.",
        "score_criteria": ["mentions_search_tool", "mentions_sms_tool", "structured_plan"],
        "weight": 3.0,
    },
    {
        "id": "reasoning_realestate",
        "category": "reasoning",
        "prompt": "A property at 123 Main St is listed at $450K. It needs $80K in repairs. Comparable rentals are $2,200/mo. Should I buy it? Walk me through the analysis including cap rate, cash-on-cash return, and risk factors.",
        "score_criteria": ["has_cap_rate", "has_cash_on_cash", "has_risk_factors", "has_numbers"],
        "weight": 2.5,
    },
    {
        "id": "creative_email",
        "category": "creative",
        "prompt": "Write a professional but warm follow-up email to a roofing contractor who quoted a job. I want to negotiate 10% off while maintaining the relationship.",
        "score_criteria": ["professional_tone", "has_negotiation", "maintains_relationship", "has_call_to_action"],
        "weight": 1.5,
    },
    {
        "id": "fast_simple",
        "category": "fast",
        "prompt": "What's 15% of $340,000?",
        "score_criteria": ["correct_answer_51000", "concise_response"],
        "weight": 1.0,
    },
    {
        "id": "analysis_complex",
        "category": "reasoning",
        "prompt": "Compare and contrast running Cipher on AWS vs self-hosted bare metal. Consider cost at scale, latency, data sovereignty, maintenance burden, and alignment with the Elysian Protocol's mission of sovereign AI.",
        "score_criteria": ["covers_cost", "covers_latency", "covers_sovereignty", "covers_maintenance", "has_recommendation"],
        "weight": 2.0,
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING
# ═══════════════════════════════════════════════════════════════════════════════

def _score_response(response: str, criteria: list[str]) -> float:
    """
    Score a model response against criteria.
    Returns 0.0 to 1.0.
    """
    if not response or len(response.strip()) < 10:
        return 0.0

    content_lower = response.lower()
    criteria_met = 0

    for criterion in criteria:
        if criterion == "has_function_def":
            criteria_met += 1 if ("def " in response or "function " in response) else 0
        elif criterion == "has_error_handling":
            criteria_met += 1 if ("try" in content_lower and ("except" in content_lower or "catch" in content_lower)) else 0
        elif criterion == "has_yfinance_import":
            criteria_met += 1 if "yfinance" in content_lower else 0
        elif criterion == "has_return":
            criteria_met += 1 if "return " in response else 0
        elif criterion == "has_struct_view":
            criteria_met += 1 if ("struct " in response and "View" in response) else 0
        elif criterion == "has_refreshable":
            criteria_met += 1 if "refreshable" in content_lower else 0
        elif criterion == "has_loading_state":
            criteria_met += 1 if ("loading" in content_lower or "isloading" in content_lower or "progressview" in content_lower) else 0
        elif criterion == "has_empty_state":
            criteria_met += 1 if "empty" in content_lower else 0
        elif criterion == "mentions_search_tool":
            criteria_met += 1 if any(w in content_lower for w in ["search", "brave", "web", "look up"]) else 0
        elif criterion == "mentions_sms_tool":
            criteria_met += 1 if any(w in content_lower for w in ["sms", "twilio", "text", "message"]) else 0
        elif criterion == "structured_plan":
            criteria_met += 1 if ("1." in response or "step" in content_lower or "first" in content_lower) else 0
        elif criterion == "has_cap_rate":
            criteria_met += 1 if "cap rate" in content_lower else 0
        elif criterion == "has_cash_on_cash":
            criteria_met += 1 if "cash" in content_lower else 0
        elif criterion == "has_risk_factors":
            criteria_met += 1 if "risk" in content_lower else 0
        elif criterion == "has_numbers":
            criteria_met += 1 if any(c.isdigit() for c in response) else 0
        elif criterion == "professional_tone":
            # No slang, no emojis, proper greeting
            criteria_met += 1 if (len(response) > 100 and not any(e in response for e in ["😀", "lol", "bruh"])) else 0
        elif criterion == "has_negotiation":
            criteria_met += 1 if any(w in content_lower for w in ["negotiate", "discount", "price", "10%", "percent"]) else 0
        elif criterion == "maintains_relationship":
            criteria_met += 1 if any(w in content_lower for w in ["appreciate", "value", "relationship", "quality", "thank"]) else 0
        elif criterion == "has_call_to_action":
            criteria_met += 1 if any(w in content_lower for w in ["let me know", "looking forward", "discuss", "call", "schedule"]) else 0
        elif criterion == "correct_answer_51000":
            criteria_met += 1 if "51,000" in response or "51000" in response or "$51,000" in response else 0
        elif criterion == "concise_response":
            criteria_met += 1 if len(response) < 200 else 0
        elif criterion == "covers_cost":
            criteria_met += 1 if "cost" in content_lower else 0
        elif criterion == "covers_latency":
            criteria_met += 1 if "latency" in content_lower else 0
        elif criterion == "covers_sovereignty":
            criteria_met += 1 if "sovereign" in content_lower else 0
        elif criterion == "covers_maintenance":
            criteria_met += 1 if "maintenance" in content_lower or "maintain" in content_lower else 0
        elif criterion == "has_recommendation":
            criteria_met += 1 if any(w in content_lower for w in ["recommend", "suggest", "would choose", "best option"]) else 0

    return criteria_met / len(criteria) if criteria else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL EVALUATION
# ═══════════════════════════════════════════════════════════════════════════════

async def evaluate_model(model_id: str, benchmarks: list[dict] = None, timeout_per_test: float = 60.0) -> dict:
    """
    Run the Cipher benchmark suite against a model.

    Returns:
        {
            "model_id": str,
            "overall_score": float (0-1),
            "category_scores": {"coding": float, "reasoning": float, ...},
            "individual_results": [...],
            "total_latency_ms": float,
            "total_cost_usd": float,
            "evaluated_at": str,
        }
    """
    litellm = _get_litellm()
    if benchmarks is None:
        benchmarks = CIPHER_BENCHMARKS

    results = []
    category_totals = {}
    category_weights = {}
    total_latency = 0.0
    total_cost = 0.0

    for bench in benchmarks:
        try:
            start = time.time()
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=model_id,
                    messages=[{"role": "user", "content": bench["prompt"]}],
                    max_tokens=2048,
                    temperature=0.3,
                ),
                timeout=timeout_per_test,
            )
            latency_ms = (time.time() - start) * 1000
            content = response.choices[0].message.content or ""

            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception:
                cost = 0.0

            score = _score_response(content, bench["score_criteria"])
            weighted_score = score * bench["weight"]

            cat = bench["category"]
            category_totals[cat] = category_totals.get(cat, 0.0) + weighted_score
            category_weights[cat] = category_weights.get(cat, 0.0) + bench["weight"]

            total_latency += latency_ms
            total_cost += cost

            results.append({
                "id": bench["id"],
                "category": cat,
                "score": round(score, 3),
                "weighted_score": round(weighted_score, 3),
                "latency_ms": round(latency_ms, 1),
                "cost_usd": cost,
                "response_length": len(content),
            })

        except asyncio.TimeoutError:
            logger.warning(f"Benchmark {bench['id']} timed out for {model_id}")
            results.append({
                "id": bench["id"],
                "category": bench["category"],
                "score": 0.0,
                "error": "timeout",
            })
        except Exception as e:
            logger.warning(f"Benchmark {bench['id']} failed for {model_id}: {e}")
            results.append({
                "id": bench["id"],
                "category": bench["category"],
                "score": 0.0,
                "error": str(e),
            })

    # Calculate category scores
    category_scores = {}
    for cat, total in category_totals.items():
        weight = category_weights.get(cat, 1.0)
        category_scores[cat] = round(total / weight, 3) if weight > 0 else 0.0

    # Overall score is weighted average across all benchmarks
    total_weight = sum(b["weight"] for b in benchmarks)
    total_weighted = sum(r.get("weighted_score", 0.0) for r in results)
    overall = total_weighted / total_weight if total_weight > 0 else 0.0

    return {
        "model_id": model_id,
        "overall_score": round(overall, 3),
        "category_scores": category_scores,
        "individual_results": results,
        "total_latency_ms": round(total_latency, 1),
        "total_cost_usd": round(total_cost, 6),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


async def compare_models(model_ids: list[str], benchmarks: list[dict] = None) -> dict:
    """
    Compare multiple models head-to-head on the benchmark suite.
    Returns results sorted by overall score (best first).
    """
    tasks = [evaluate_model(m, benchmarks) for m in model_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    evaluations = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Model evaluation failed: {r}")
        else:
            evaluations.append(r)

    # Sort by overall score, best first
    evaluations.sort(key=lambda x: x["overall_score"], reverse=True)

    return {
        "evaluations": evaluations,
        "best_overall": evaluations[0]["model_id"] if evaluations else None,
        "best_by_category": _find_best_per_category(evaluations),
        "compared_at": datetime.now(timezone.utc).isoformat(),
    }


def _find_best_per_category(evaluations: list[dict]) -> dict:
    """Find the best model for each benchmark category."""
    best = {}
    for eval_result in evaluations:
        for cat, score in eval_result.get("category_scores", {}).items():
            if cat not in best or score > best[cat]["score"]:
                best[cat] = {
                    "model_id": eval_result["model_id"],
                    "score": score,
                }
    return best


async def propose_routing_updates(comparison: dict) -> dict:
    """
    Given a model comparison, propose updates to MODEL_MAP and AGENT_MODEL_MAP.
    Only proposes changes if the new model scores significantly better (>5%).

    Returns dict that can be saved via save_model_benchmarks() in llm_router.
    """
    from app.services.llm_router import MODEL_MAP, AGENT_MODEL_MAP, MODEL_REGISTRY

    proposals = {
        "model_map_overrides": {},
        "agent_model_overrides": {},
        "reasoning": [],
    }

    best_by_cat = comparison.get("best_by_category", {})

    # Map benchmark categories → ModelTier
    category_to_tier = {
        "coding": "code",
        "reasoning": "reasoning",
        "fast": "fast",
        "tool_use": "default",  # Tool use is the primary chat brain
        "creative": "default",
    }

    # Map benchmark categories → agent groups
    category_to_agents = {
        "coding": ["code_agent", "shell_agent", "deploy_agent", "skill_creator_agent"],
        "reasoning": ["research_agent", "analyst_agent", "legal_agent", "deal_flow_agent",
                       "profitability_analyst_agent", "synthesis_agent", "apex_architect_agent"],
        "fast": ["brave_search_agent", "sentinel_agent", "scheduler_agent", "chronos_agent",
                 "archivist_agent", "file_agent", "monitor_agent"],
        "tool_use": [],  # Tool use affects the main brain, not specific agents
        "creative": ["communication_agent", "outreach_agent", "image_agent", "video_agent"],
    }

    for cat, best_info in best_by_cat.items():
        best_model = best_info["model_id"]
        best_score = best_info["score"]

        # Check tier mapping
        tier_str = category_to_tier.get(cat)
        if tier_str:
            from app.models.schemas import ModelTier
            try:
                tier = ModelTier(tier_str)
                current_model = MODEL_MAP.get(tier)
                # Find current model's score in this category
                current_score = 0.0
                for eval_r in comparison.get("evaluations", []):
                    if eval_r["model_id"] == current_model:
                        current_score = eval_r.get("category_scores", {}).get(cat, 0.0)
                        break

                improvement = best_score - current_score
                if improvement > 0.05 and best_model != current_model:
                    proposals["model_map_overrides"][tier_str] = best_model
                    proposals["reasoning"].append(
                        f"Tier '{tier_str}': {current_model} ({current_score:.2f}) → "
                        f"{best_model} ({best_score:.2f}) [+{improvement:.2f}]"
                    )
            except (ValueError, KeyError):
                pass

        # Check agent mappings
        agents = category_to_agents.get(cat, [])
        for agent_name in agents:
            current_model = AGENT_MODEL_MAP.get(agent_name)
            if current_model and current_model != best_model:
                # Only propose if improvement is meaningful
                current_score_for_agent = 0.0
                for eval_r in comparison.get("evaluations", []):
                    if eval_r["model_id"] == current_model:
                        current_score_for_agent = eval_r.get("category_scores", {}).get(cat, 0.0)
                        break

                improvement = best_score - current_score_for_agent
                if improvement > 0.05:
                    proposals["agent_model_overrides"][agent_name] = best_model
                    proposals["reasoning"].append(
                        f"Agent '{agent_name}': {current_model} → {best_model} "
                        f"[{cat} +{improvement:.2f}]"
                    )

    return proposals
