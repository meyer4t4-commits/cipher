"""
Research API — Endpoints for Cipher's autonomous self-improvement engine.

Provides control over the research loop, experiment viewing, and self-test execution.
"""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.core.logging import logger
from app.services.background_tasks import get_task_manager
from app.services.self_research.autonomous_loop import run_autonomous_loop
from app.services.self_research.self_test import run_self_tests
from app.services.self_research.experiment_runner import ExperimentLog, RESEARCH_DIR

router = APIRouter(prefix="/api/v1/research", tags=["research"])


# --- Request Models ---

class StartResearchRequest(BaseModel):
    max_experiments: int = Field(default=50, ge=1, le=500)
    max_hours: float = Field(default=8.0, ge=0.1, le=24.0)


# --- Endpoints ---

@router.post("/start")
async def start_research_loop(request: StartResearchRequest):
    """
    Start the autonomous research loop as a background task.
    Cipher will iterate on its own code, testing improvements.
    The operator can sleep — Cipher won't ask for permission.
    """
    task_manager = get_task_manager()

    # Check if already running
    running = task_manager.get_running_tasks()
    for t in running:
        if "research" in t.name.lower():
            raise HTTPException(
                status_code=409,
                detail="Research loop is already running. Stop it first.",
            )

    # Start as background task
    async def research_task():
        return await run_autonomous_loop(
            max_experiments=request.max_experiments,
            max_hours=request.max_hours,
        )

    task_id = task_manager.spawn(
        name="CipherResearch Autonomous Loop",
        coroutine=research_task(),
        description=f"Running up to {request.max_experiments} experiments over {request.max_hours}h",
    )

    return {
        "status": "started",
        "task_id": task_id,
        "max_experiments": request.max_experiments,
        "max_hours": request.max_hours,
        "message": "Autonomous research loop started. Cipher will iterate on its own code.",
    }


@router.post("/stop")
async def stop_research_loop():
    """Stop the running research loop."""
    task_manager = get_task_manager()
    running = task_manager.get_running_tasks()

    stopped = 0
    for t in running:
        if "research" in t.name.lower():
            task_manager.cancel_task(t.task_id)
            stopped += 1

    if stopped == 0:
        return {"status": "not_running", "message": "No research loop is running."}

    return {"status": "stopped", "tasks_cancelled": stopped}


@router.get("/status")
async def get_research_status():
    """Get current research loop status and experiment stats."""
    task_manager = get_task_manager()
    experiment_log = ExperimentLog()

    running = False
    running_task = None
    for t in task_manager.get_running_tasks():
        if "research" in t.name.lower():
            running = True
            running_task = {
                "task_id": t.task_id,
                "name": t.name,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "progress": [
                    {"message": p.message, "timestamp": p.timestamp.isoformat()}
                    for p in (t.progress[-5:] if t.progress else [])
                ],
            }
            break

    stats = experiment_log.get_stats()
    recent = experiment_log.get_recent(10)
    best = experiment_log.get_best_experiments(3)

    return {
        "running": running,
        "running_task": running_task,
        "stats": stats,
        "recent_experiments": recent,
        "best_experiments": best,
    }


@router.get("/experiments")
async def get_experiments(limit: int = 20):
    """Get the experiment history."""
    experiment_log = ExperimentLog()
    return {
        "experiments": experiment_log.get_recent(limit),
        "stats": experiment_log.get_stats(),
    }


@router.get("/experiments/best")
async def get_best_experiments(limit: int = 10):
    """Get the best experiments by improvement."""
    experiment_log = ExperimentLog()
    return {
        "best": experiment_log.get_best_experiments(limit),
    }


@router.post("/self-test")
async def run_self_test():
    """
    Run the self-test suite once and return results.
    Useful for checking Cipher's health before/after changes.
    """
    try:
        results = await run_self_tests()
        return results
    except Exception as e:
        logger.error(f"Self-test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/program")
async def get_research_program():
    """Get the current research program directives."""
    program_path = RESEARCH_DIR / "research_program.md"
    if not program_path.exists():
        return {"program": "", "exists": False}

    return {
        "program": program_path.read_text(encoding="utf-8"),
        "exists": True,
    }


class UpdateProgramRequest(BaseModel):
    content: str


@router.put("/program")
async def update_research_program(request: UpdateProgramRequest):
    """Update the research program directives (operator control)."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    program_path = RESEARCH_DIR / "research_program.md"
    program_path.write_text(request.content, encoding="utf-8")

    return {
        "status": "updated",
        "length": len(request.content),
    }


@router.post("/evaluate-models")
async def evaluate_models():
    """
    Run the model evaluation benchmark suite.
    Compares all registered models and proposes routing updates.
    This is what the research loop runs at the start of every session,
    but you can also trigger it manually.
    """
    try:
        from app.services.self_research.model_evaluator import (
            compare_models, propose_routing_updates,
        )
        from app.services.llm_router import MODEL_REGISTRY, save_model_benchmarks

        all_models = [info["model_id"] for info in MODEL_REGISTRY.values()]
        comparison = await compare_models(all_models)
        proposals = await propose_routing_updates(comparison)

        # Save benchmarks if there are improvements
        if proposals.get("model_map_overrides") or proposals.get("agent_model_overrides"):
            save_model_benchmarks({
                "comparison": comparison,
                "proposals": proposals,
                "model_map_overrides": proposals.get("model_map_overrides", {}),
                "agent_model_overrides": proposals.get("agent_model_overrides", {}),
            })

        return {
            "comparison": comparison,
            "proposals": proposals,
            "saved": bool(proposals.get("model_map_overrides") or proposals.get("agent_model_overrides")),
        }
    except Exception as e:
        logger.error(f"Model evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-routing")
async def get_model_routing():
    """Get current model routing configuration (what model each tier/agent uses)."""
    from app.services.llm_router import get_registry_info
    return get_registry_info()


@router.get("/weaknesses")
async def get_weaknesses():
    """
    Analyze Cipher's current weaknesses and suggest overnight training priorities.

    This is the intelligence behind the auto-training loop:
    - Identifies failing tests and low-scoring capabilities
    - Detects recurring error patterns from experiment history
    - Suggests what to build/train overnight based on actual gaps
    - Generates research program updates targeting weaknesses

    Mark can ask Cipher: "What should you train on tonight?" and this powers the answer.
    """
    from app.services.self_research.weakness_analyzer import analyze_weaknesses

    try:
        # Run self-tests to get current state
        test_results = await run_self_tests()

        # Analyze weaknesses
        analysis = analyze_weaknesses(test_results=test_results)

        return analysis
    except Exception as e:
        logger.error(f"Weakness analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train-overnight")
async def train_overnight():
    """
    Start an intelligent overnight training session.

    Unlike the basic research loop, this first analyzes weaknesses,
    updates the research program to target them, then starts the loop.
    Cipher focuses on its ACTUAL gaps, not random experiments.
    """
    from app.services.self_research.weakness_analyzer import analyze_weaknesses

    try:
        # Step 1: Analyze current weaknesses
        test_results = await run_self_tests()
        analysis = analyze_weaknesses(test_results=test_results)

        # Step 2: Update research program with weakness-targeted priorities
        if analysis.get("research_program_update"):
            current_program = ""
            program_path = RESEARCH_DIR / "research_program.md"
            if program_path.exists():
                current_program = program_path.read_text(encoding="utf-8")

            # Append weakness-based priorities to the research program
            updated_program = current_program + "\n\n" + analysis["research_program_update"]
            RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
            program_path.write_text(updated_program, encoding="utf-8")

            logger.info(f"Research program updated with {len(analysis['weaknesses'])} weakness targets")

        # Step 3: Start the research loop targeting weaknesses
        task_manager = get_task_manager()

        # Check if already running
        for t in task_manager.get_running_tasks():
            if "research" in t.name.lower():
                raise HTTPException(
                    status_code=409,
                    detail="Research loop is already running. Stop it first.",
                )

        async def overnight_task():
            return await run_autonomous_loop(
                max_experiments=100,
                max_hours=8.0,
            )

        task_id = task_manager.spawn(
            name="CipherResearch Overnight Training (Weakness-Targeted)",
            coroutine=overnight_task(),
            description=f"Targeting {len(analysis['weaknesses'])} identified weaknesses",
        )

        return {
            "status": "started",
            "task_id": task_id,
            "weaknesses_targeted": len(analysis["weaknesses"]),
            "top_priorities": analysis["overnight_priorities"][:5],
            "message": (
                f"Overnight training started. Targeting {len(analysis['weaknesses'])} weaknesses: "
                + ", ".join(w["label"] for w in analysis["weaknesses"][:3])
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Overnight training setup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
