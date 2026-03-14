"""
Self-Diagnostic Service — Cipher's ability to check and fix itself.

This is the core of Cipher's self-healing:
1. Check all API keys and external service connectivity
2. Verify agent registry and execution
3. Test LLM routing and failover
4. Check database, memory, cron health
5. Generate actionable fix instructions

When Cipher encounters an error, it can call diagnose_self to understand
what's broken and attempt to fix it automatically.
"""

import asyncio
import json
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Optional

from app.core.logging import logger


async def run_full_diagnostic() -> dict:
    """
    Run comprehensive self-diagnostic across all subsystems.
    Returns a structured report with pass/fail/warning for each check.
    """
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "healthy",
        "checks": [],
        "errors": [],
        "warnings": [],
        "fixes_available": [],
    }

    checks = [
        _check_api_keys,
        _check_database,
        _check_memory,
        _check_llm_routing,
        _check_agent_registry,
        _check_cron_registry,
        _check_tool_calling,
        _check_external_services,
    ]

    for check_fn in checks:
        try:
            result = await check_fn()
            report["checks"].append(result)
            if result["status"] == "error":
                report["errors"].append(result["name"] + ": " + result.get("detail", ""))
                report["overall_status"] = "degraded"
            elif result["status"] == "warning":
                report["warnings"].append(result["name"] + ": " + result.get("detail", ""))
                if report["overall_status"] == "healthy":
                    report["overall_status"] = "warning"
            if result.get("fix"):
                report["fixes_available"].append(result["fix"])
        except Exception as e:
            report["checks"].append({
                "name": check_fn.__name__,
                "status": "error",
                "detail": f"Check itself failed: {str(e)[:200]}",
            })
            report["errors"].append(f"{check_fn.__name__}: {str(e)[:200]}")
            report["overall_status"] = "degraded"

    return report


async def _check_api_keys() -> dict:
    """Check all required API keys are present and non-empty."""
    keys = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "BRAVE_SEARCH_API_KEY": os.getenv("BRAVE_SEARCH_API_KEY", ""),
        "XAI_API_KEY": os.getenv("XAI_API_KEY", ""),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
    }

    optional_keys = {
        "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY", ""),
        "STABILITY_API_KEY": os.getenv("STABILITY_API_KEY", ""),
        "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID", ""),
        "STRIPE_SECRET_KEY": os.getenv("STRIPE_SECRET_KEY", ""),
        "ATTOM_API_KEY": os.getenv("ATTOM_API_KEY", ""),
        "PINECONE_API_KEY": os.getenv("PINECONE_API_KEY", ""),
    }

    missing = [k for k, v in keys.items() if not v]
    optional_missing = [k for k, v in optional_keys.items() if not v]

    if missing:
        return {
            "name": "API Keys",
            "status": "error",
            "detail": f"Missing required keys: {', '.join(missing)}",
            "present": [k for k, v in keys.items() if v],
            "missing": missing,
            "optional_missing": optional_missing,
            "fix": f"Set environment variables: {', '.join(missing)}",
        }

    return {
        "name": "API Keys",
        "status": "pass" if not optional_missing else "warning",
        "detail": f"All {len(keys)} required keys present" + (f", {len(optional_missing)} optional missing" if optional_missing else ""),
        "present": list(keys.keys()),
        "optional_missing": optional_missing,
    }


async def _check_database() -> dict:
    """Check database connectivity and basic operations."""
    try:
        from app.db.database import get_db

        db = next(get_db())
        # Test a simple query
        from app.db.models import ConversationRecord
        count = db.query(ConversationRecord).count()
        db.close()

        return {
            "name": "Database",
            "status": "pass",
            "detail": f"Connected, {count} conversations stored",
        }
    except Exception as e:
        return {
            "name": "Database",
            "status": "error",
            "detail": f"Database error: {str(e)[:200]}",
            "fix": "Check DATABASE_URL environment variable and database connectivity",
        }


async def _check_memory() -> dict:
    """Check PostgreSQL-backed memory system."""
    try:
        from app.services.memory import get_memory_stats, recall_memories

        stats = get_memory_stats()
        total = stats.get("total_memories", stats.get("total_documents", 0))
        storage = stats.get("storage", "unknown")
        # Quick test recall
        test = recall_memories("test query", n_results=1)

        return {
            "name": "Memory (PostgreSQL)",
            "status": "pass",
            "detail": f"Connected via {storage}, {total} memories stored",
        }
    except Exception as e:
        return {
            "name": "Memory (PostgreSQL)",
            "status": "warning",
            "detail": f"Memory unavailable: {str(e)[:200]}. Chat still works without memory.",
        }


async def _check_llm_routing() -> dict:
    """Test LLM routing with a simple completion."""
    try:
        from app.services.llm_router import chat_completion, get_model_for_tier, FAILOVER_CHAINS
        from app.models.schemas import ModelTier

        # Check what model we'd use
        model = get_model_for_tier(ModelTier.FAST)
        failover_count = len(FAILOVER_CHAINS.get(ModelTier.DEFAULT, []))

        # Quick test with the FAST tier (cheapest)
        start = time.time()
        result = await chat_completion(
            messages=[{"role": "user", "content": "Reply with just the word 'ok'"}],
            model_tier=ModelTier.FAST,
            max_tokens=10,
            temperature=0,
        )
        latency = (time.time() - start) * 1000

        return {
            "name": "LLM Routing",
            "status": "pass",
            "detail": f"Model {result.get('model_used', 'unknown')} responded in {latency:.0f}ms",
            "model_used": result.get("model_used"),
            "failover_depth": failover_count,
            "latency_ms": round(latency),
        }
    except Exception as e:
        return {
            "name": "LLM Routing",
            "status": "error",
            "detail": f"LLM call failed: {str(e)[:300]}",
            "fix": "Check API keys (ANTHROPIC_API_KEY, XAI_API_KEY, etc.) and network connectivity",
        }


async def _check_agent_registry() -> dict:
    """Verify agent registry, force-load if needed, and run per-agent health checks."""
    try:
        from app.agents.registry import get_registry

        registry = get_registry()
        agents = registry.list_agents() if hasattr(registry, 'list_agents') else []
        count = len(agents) if agents else 0

        # If no agents registered, force the lazy-load so we get real data
        if count == 0:
            try:
                from app.api.agents import _init_agents
                _init_agents()
                agents = registry.list_agents()
                count = len(agents)
            except Exception as init_err:
                return {
                    "name": "Agent Registry",
                    "status": "error",
                    "detail": f"Agent initialization failed: {str(init_err)[:200]}",
                }

        # Run per-agent health checks
        health_results = await check_agent_health(registry)

        healthy = sum(1 for r in health_results if r["status"] == "healthy")
        degraded = sum(1 for r in health_results if r["status"] == "degraded")
        broken = sum(1 for r in health_results if r["status"] == "broken")

        status = "pass"
        if broken > 0:
            status = "error"
        elif degraded > 0:
            status = "warning"

        return {
            "name": "Agent Registry",
            "status": status,
            "detail": f"{count} agents registered — {healthy} healthy, {degraded} degraded, {broken} broken",
            "agents_total": count,
            "agents_healthy": healthy,
            "agents_degraded": degraded,
            "agents_broken": broken,
            "agent_health": health_results,
        }
    except Exception as e:
        return {
            "name": "Agent Registry",
            "status": "warning",
            "detail": f"Registry check failed: {str(e)[:200]}",
        }


async def check_agent_health(registry=None) -> list[dict]:
    """
    Run per-agent health checks: verify each agent initializes, has capabilities,
    and has required API keys available.

    Returns a list of {name, status, capabilities, missing_keys, detail} dicts.
    """
    if registry is None:
        from app.agents.registry import get_registry
        registry = get_registry()

    # Map of agent names to the env vars they need
    AGENT_API_REQUIREMENTS = {
        "brave_search": ["BRAVE_SEARCH_API_KEY"],
        "image": ["STABILITY_API_KEY"],
        "video": ["STABILITY_API_KEY"],
        "trading": ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
        "communication": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
        "deploy": ["RAILWAY_API_TOKEN"],
        "scout": ["ATTOM_API_KEY"],
        "analyst": ["ATTOM_API_KEY"],
        "neighborhood_growth": ["ATTOM_API_KEY"],
        "deal_flow": ["ATTOM_API_KEY"],
        "market_pulse": ["ATTOM_API_KEY"],
        "profitability_analyst": ["ATTOM_API_KEY"],
        "outreach": ["TWILIO_ACCOUNT_SID"],
        "provisioning": ["SHOPIFY_ACCESS_TOKEN"],
    }

    results = []
    agents = registry.list_agents() if hasattr(registry, 'list_agents') else []

    for agent_name in agents:
        agent = registry.get_agent(agent_name)
        if agent is None:
            results.append({
                "name": agent_name,
                "status": "broken",
                "capabilities": 0,
                "missing_keys": [],
                "detail": "Agent registered but instance is None",
            })
            continue

        # Check capabilities
        cap_count = len(agent.capabilities) if hasattr(agent, 'capabilities') else 0

        # Check required API keys
        required_keys = AGENT_API_REQUIREMENTS.get(agent_name, [])
        missing_keys = [k for k in required_keys if not os.getenv(k, "")]

        # Determine status
        if cap_count == 0:
            status = "broken"
            detail = "No capabilities defined"
        elif missing_keys:
            status = "degraded"
            detail = f"Missing API keys: {', '.join(missing_keys)}"
        else:
            status = "healthy"
            detail = f"{cap_count} capabilities, all dependencies met"

        results.append({
            "name": agent_name,
            "status": status,
            "capabilities": cap_count,
            "missing_keys": missing_keys,
            "detail": detail,
        })

    return results


async def _check_cron_registry() -> dict:
    """Check cron task registry."""
    try:
        from app.services.cron_registry import get_cron_registry

        registry = get_cron_registry()
        tasks = registry.list_tasks() if hasattr(registry, 'list_tasks') else []

        return {
            "name": "Cron Registry",
            "status": "pass",
            "detail": f"{len(tasks)} cron tasks registered",
        }
    except Exception as e:
        return {
            "name": "Cron Registry",
            "status": "warning",
            "detail": f"Cron check failed: {str(e)[:200]}. Non-critical.",
        }


async def _check_tool_calling() -> dict:
    """Verify tool calling works with a simple test."""
    try:
        from app.services.tool_calling import execute_tool

        # Test the simplest tool — list_directory
        result = await execute_tool("list_directory", {"path": "."})
        parsed = json.loads(result)

        if parsed.get("error"):
            return {
                "name": "Tool Calling",
                "status": "error",
                "detail": f"Tool test failed: {parsed['error'][:200]}",
                "fix": "Check file system permissions and project root detection",
            }

        return {
            "name": "Tool Calling",
            "status": "pass",
            "detail": f"Tools operational, project has {parsed.get('count', 0)} root entries",
        }
    except Exception as e:
        return {
            "name": "Tool Calling",
            "status": "error",
            "detail": f"Tool system broken: {str(e)[:200]}",
            "fix": "Check tool_calling.py for import errors",
        }


async def _check_external_services() -> dict:
    """Check connectivity to external APIs."""
    results = []

    # Test Brave Search
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    if brave_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": "test", "count": 1},
                    headers={"X-Subscription-Token": brave_key, "Accept": "application/json"},
                )
                results.append(f"Brave Search: {'OK' if resp.status_code == 200 else f'HTTP {resp.status_code}'}")
        except Exception as e:
            results.append(f"Brave Search: FAILED ({str(e)[:50]})")
    else:
        results.append("Brave Search: NO API KEY")

    return {
        "name": "External Services",
        "status": "pass" if all("OK" in r or "NO API KEY" in r for r in results) else "warning",
        "detail": "; ".join(results),
    }


async def attempt_self_fix(issue: str) -> dict:
    """
    Attempt to automatically fix a known issue.
    Returns what was attempted and whether it succeeded.
    """
    fixes_attempted = []

    if "memory" in issue.lower() or "chroma" in issue.lower():
        try:
            from app.services.memory import initialize_memory
            initialize_memory()
            fixes_attempted.append({"issue": "Memory/ChromaDB", "action": "Re-initialized memory store", "success": True})
        except Exception as e:
            fixes_attempted.append({"issue": "Memory/ChromaDB", "action": "Re-initialize failed", "success": False, "error": str(e)[:200]})

    if "database" in issue.lower() or "db" in issue.lower():
        try:
            from app.db.database import init_db
            init_db()
            fixes_attempted.append({"issue": "Database", "action": "Re-initialized database", "success": True})
        except Exception as e:
            fixes_attempted.append({"issue": "Database", "action": "Re-initialize failed", "success": False, "error": str(e)[:200]})

    if "agent" in issue.lower() or "registry" in issue.lower():
        try:
            from app.agents.registry import get_registry
            registry = get_registry()
            if hasattr(registry, 'reload'):
                registry.reload()
            fixes_attempted.append({"issue": "Agent Registry", "action": "Reloaded agent registry", "success": True})
        except Exception as e:
            fixes_attempted.append({"issue": "Agent Registry", "action": "Reload failed", "success": False, "error": str(e)[:200]})

    if not fixes_attempted:
        fixes_attempted.append({"issue": issue, "action": "No automatic fix available", "success": False})

    return {
        "issue": issue,
        "fixes_attempted": fixes_attempted,
        "recommendation": "Run full diagnostic after fix attempts to verify",
    }
