"""
Self-Improvement Dashboard API — Visibility into Cipher's autonomous training.

Provides endpoints to check:
- Current idle training status
- Recent experiment results
- Benchmark health
- Fix history
- Training statistics
"""

from fastapi import APIRouter

from app.core.logging import logger

router = APIRouter(prefix="/api/v1/self-improvement", tags=["self-improvement"])


@router.get("/status")
async def get_self_improvement_status():
    """Get a comprehensive status overview of Cipher's self-improvement systems."""
    result = {
        "idle_trainer": None,
        "experiment_stats": None,
        "recent_experiments": [],
        "best_experiments": [],
        "queued_experiments": 0,
    }

    # Idle trainer status
    try:
        from app.services.idle_trainer import get_training_status
        result["idle_trainer"] = get_training_status()
    except Exception as e:
        result["idle_trainer"] = {"error": str(e)}

    # Experiment stats
    try:
        from app.services.self_research.experiment_runner import ExperimentLog
        log = ExperimentLog()
        result["experiment_stats"] = log.get_stats()
        result["recent_experiments"] = log.get_recent(10)
        result["best_experiments"] = log.get_best_experiments(5)
    except Exception as e:
        result["experiment_stats"] = {"error": str(e)}

    # Queued experiments from insight absorber
    try:
        from app.services.self_research.autonomous_loop import _load_queued_experiments
        queued = _load_queued_experiments()
        result["queued_experiments"] = len(queued)
    except Exception:
        pass

    return result


@router.get("/benchmark")
async def run_quick_benchmark():
    """Run a quick benchmark of all agents and return results."""
    try:
        from app.agents.skills.self_improvement_agent import SelfImprovementAgent
        from app.agents.models import AgentTask

        agent = SelfImprovementAgent()
        task = AgentTask(
            agent_name="self_improvement_agent",
            instruction="Benchmark all agents",
            params={"capability": "benchmark"},
        )
        result = await agent._benchmark(task)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/fix-history")
async def get_fix_history():
    """Get recent self-improvement fix history from the database."""
    try:
        from app.db.database import SessionLocal
        from app.db.models import SelfFixLog

        db = SessionLocal()
        fixes = db.query(SelfFixLog).order_by(SelfFixLog.created_at.desc()).limit(50).all()
        result = [
            {
                "id": f.id,
                "file_path": f.file_path,
                "action": f.action,
                "description": f.description,
                "success": f.success,
                "verified": f.verified,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in fixes
        ]
        db.close()
        return {"fixes": result, "total": len(result)}
    except Exception as e:
        return {"fixes": [], "error": str(e)}


@router.post("/train-now")
async def trigger_training():
    """Manually trigger an idle training cycle (ignores idle check)."""
    try:
        from app.services.idle_trainer import _run_idle_training_cycle
        result = await _run_idle_training_cycle()
        return result
    except Exception as e:
        return {"action": "error", "error": str(e)}
