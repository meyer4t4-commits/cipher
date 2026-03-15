"""
Idle Trainer — Triggers self-improvement when the user isn't actively chatting.

WHY THIS EXISTS:
Cipher has an extensive self-improvement stack (self_improvement_agent, autonomous_loop,
experiment_runner, self_test) but it only runs on fixed cron schedules or when the user
explicitly asks. The best time to self-improve is when the user is IDLE — no resource
contention, no latency impact on active conversations.

HOW IT WORKS:
1. The orchestrator calls `record_activity()` on every incoming message
2. A cron-triggered `maybe_train()` checks if the user has been idle long enough
3. If idle for IDLE_THRESHOLD_MINUTES, it runs a focused self-improvement cycle
4. If the user sends a message during training, the cycle is gracefully cancelled

This module is designed to be lightweight — no background threads, no polling.
The cron registry drives the check cadence.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from app.core.logging import logger

# ─── Configuration ───────────────────────────────────────────────────────────

# Minimum idle time before self-training kicks in (minutes)
IDLE_THRESHOLD_MINUTES = 30

# Maximum training duration per idle session (minutes)
MAX_TRAINING_MINUTES = 60

# Minimum time between training sessions (minutes)
MIN_TRAINING_INTERVAL_MINUTES = 120

# Maximum fixes per idle training cycle
MAX_FIXES_PER_CYCLE = 5

# Maximum experiments per idle training cycle
MAX_EXPERIMENTS_PER_CYCLE = 10


# ─── State ───────────────────────────────────────────────────────────────────

_last_user_activity: float = time.time()
_last_training_end: float = 0.0
_training_in_progress: bool = False
_training_task: Optional[asyncio.Task] = None


def record_activity() -> None:
    """Record that the user just interacted. Call on every incoming message."""
    global _last_user_activity
    _last_user_activity = time.time()

    # If training is in progress, cancel it gracefully
    if _training_in_progress and _training_task and not _training_task.done():
        logger.info("[IDLE TRAINER] User active — cancelling idle training")
        _training_task.cancel()


def get_idle_minutes() -> float:
    """Get how many minutes the user has been idle."""
    return (time.time() - _last_user_activity) / 60


def get_training_status() -> dict:
    """Get current idle training status."""
    return {
        "idle_minutes": round(get_idle_minutes(), 1),
        "idle_threshold_minutes": IDLE_THRESHOLD_MINUTES,
        "training_in_progress": _training_in_progress,
        "last_training_end": (
            datetime.fromtimestamp(_last_training_end, tz=timezone.utc).isoformat()
            if _last_training_end > 0 else None
        ),
        "minutes_since_last_training": round((time.time() - _last_training_end) / 60, 1) if _last_training_end > 0 else None,
        "eligible_for_training": _is_eligible_for_training(),
    }


def _is_eligible_for_training() -> bool:
    """Check if conditions are met for idle training."""
    idle_mins = get_idle_minutes()
    since_last = (time.time() - _last_training_end) / 60 if _last_training_end > 0 else float("inf")

    return (
        idle_mins >= IDLE_THRESHOLD_MINUTES
        and since_last >= MIN_TRAINING_INTERVAL_MINUTES
        and not _training_in_progress
    )


async def maybe_train() -> dict:
    """
    Check if the user is idle and run self-improvement if so.

    This is called by the cron registry on a regular schedule.
    Returns a status dict describing what happened.
    """
    global _training_in_progress, _training_task, _last_training_end

    if not _is_eligible_for_training():
        idle_mins = get_idle_minutes()
        return {
            "action": "skipped",
            "reason": (
                f"idle {idle_mins:.0f}m (need {IDLE_THRESHOLD_MINUTES}m)"
                if idle_mins < IDLE_THRESHOLD_MINUTES
                else "training cooldown or already running"
            ),
        }

    logger.info(f"[IDLE TRAINER] User idle for {get_idle_minutes():.0f}m — starting self-training")
    _training_in_progress = True

    try:
        _training_task = asyncio.current_task()
        result = await _run_idle_training_cycle()
        return result
    except asyncio.CancelledError:
        logger.info("[IDLE TRAINER] Training cancelled (user returned)")
        return {"action": "cancelled", "reason": "user_returned"}
    except Exception as e:
        logger.error(f"[IDLE TRAINER] Training error: {e}")
        return {"action": "error", "error": str(e)}
    finally:
        _training_in_progress = False
        _last_training_end = time.time()
        _training_task = None


async def _run_idle_training_cycle() -> dict:
    """
    Execute a focused self-improvement cycle during idle time.

    Strategy:
    1. Run a quick benchmark to identify broken agents
    2. Fix any broken agents (syntax/import errors)
    3. Run a few experiments from the autonomous loop
    4. Return summary
    """
    results = {
        "action": "trained",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": None,
        "fixes_applied": 0,
        "experiments_run": 0,
        "experiments_kept": 0,
    }

    start = time.time()
    max_runtime = MAX_TRAINING_MINUTES * 60

    # ── Phase 1: Quick benchmark ──
    logger.info("[IDLE TRAINER] Phase 1: Quick benchmark")
    try:
        from app.agents.skills.self_improvement_agent import SelfImprovementAgent
        from app.agents.models import AgentTask

        agent = SelfImprovementAgent()
        benchmark_task = AgentTask(
            agent_name="self_improvement_agent",
            instruction="Benchmark all agents",
            params={"capability": "benchmark"},
        )
        benchmark_result = await agent._benchmark(benchmark_task)
        results["benchmark"] = {
            "total": benchmark_result.get("total_agents", 0),
            "healthy": benchmark_result.get("healthy", 0),
            "broken_syntax": benchmark_result.get("broken_syntax", 0),
            "broken_imports": benchmark_result.get("broken_imports", 0),
        }

        # ── Phase 2: Fix broken agents ──
        broken = benchmark_result.get("broken_agents", [])
        if broken:
            logger.info(f"[IDLE TRAINER] Phase 2: Fixing {len(broken)} broken agents")
            for agent_info in broken[:MAX_FIXES_PER_CYCLE]:
                # Check if user came back
                if get_idle_minutes() < 5:
                    logger.info("[IDLE TRAINER] User active — stopping fixes")
                    break

                agent_name = agent_info.get("agent", "")
                error = agent_info.get("import_error", "") or agent_info.get("syntax_error", "")
                if agent_name and error:
                    fix_task = AgentTask(
                        agent_name="self_improvement_agent",
                        instruction=f"Fix {agent_name}",
                        params={
                            "capability": "improve",
                            "focus": "agents",
                            "max_fixes": 1,
                        },
                    )
                    try:
                        fix_result = await agent._improve_cycle(fix_task)
                        results["fixes_applied"] += len(fix_result.get("fixes_applied", []))
                    except Exception as e:
                        logger.warning(f"[IDLE TRAINER] Fix failed for {agent_name}: {e}")
        else:
            logger.info("[IDLE TRAINER] Phase 2: All agents healthy, skipping fixes")

    except Exception as e:
        logger.warning(f"[IDLE TRAINER] Benchmark/fix phase failed: {e}")

    # ── Phase 3: Run autonomous experiments if time remains ──
    elapsed = time.time() - start
    remaining = max_runtime - elapsed
    if remaining > 120 and get_idle_minutes() >= 10:  # Need at least 2 min and user still idle
        logger.info(f"[IDLE TRAINER] Phase 3: Running experiments ({remaining/60:.0f}m remaining)")
        try:
            from app.services.self_research.autonomous_loop import run_autonomous_loop

            loop_result = await run_autonomous_loop(
                max_experiments=MAX_EXPERIMENTS_PER_CYCLE,
                max_hours=remaining / 3600,
            )
            results["experiments_run"] = loop_result.get("total_experiments", 0)
            results["experiments_kept"] = loop_result.get("kept", 0)
        except asyncio.CancelledError:
            raise  # Let cancellation propagate
        except Exception as e:
            logger.warning(f"[IDLE TRAINER] Experiment phase failed: {e}")
    else:
        logger.info("[IDLE TRAINER] Phase 3: Skipped (no time remaining or user active)")

    results["duration_minutes"] = round((time.time() - start) / 60, 1)
    logger.info(
        f"[IDLE TRAINER] Complete: {results['fixes_applied']} fixes, "
        f"{results['experiments_kept']}/{results['experiments_run']} experiments kept, "
        f"{results['duration_minutes']}m runtime"
    )
    return results
