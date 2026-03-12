"""
System API endpoints - health checks, prompts, and admin.
"""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import __version__
from app.db.database import get_db
from app.db.models import SystemPrompt
from app.models.schemas import HealthCheck
from app.services.memory import get_memory_stats

router = APIRouter(prefix="/system", tags=["system"])

# Track server start time
_start_time = time.time()


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """Full system health check."""
    # Check memory
    try:
        mem_stats = get_memory_stats()
        chroma_ok = True
    except Exception:
        chroma_ok = False

    return HealthCheck(
        status="healthy",
        version=__version__,
        uptime_seconds=round(time.time() - _start_time, 1),
        database_connected=True,
        chroma_connected=chroma_ok,
    )


@router.get("/diagnose")
async def run_diagnostic():
    """
    Comprehensive self-diagnostic — checks all subsystems.
    Returns pass/fail/warning for API keys, database, memory,
    LLM routing, agent registry, cron, tools, and external services.
    """
    from app.services.self_diagnostic import run_full_diagnostic
    try:
        report = await run_full_diagnostic()
        return report
    except Exception as e:
        return {
            "overall_status": "error",
            "detail": f"Diagnostic failed: {str(e)[:500]}",
            "checks": [],
        }


@router.post("/fix")
async def attempt_fix(issue: str = "all"):
    """
    Attempt automatic fix for a known issue.
    Pass issue='all' to try fixing everything, or a specific subsystem name.
    """
    from app.services.self_diagnostic import attempt_self_fix, run_full_diagnostic

    if issue == "all":
        # Run diagnostic first, then fix all errors
        report = await run_full_diagnostic()
        fixes = []
        for error in report.get("errors", []):
            fix = await attempt_self_fix(error)
            fixes.append(fix)
        return {"fixes": fixes, "recheck": await run_full_diagnostic()}

    fix = await attempt_self_fix(issue)
    return fix


@router.get("/errors")
async def get_error_history():
    """Get error tracking history — all errors, patterns, and fix rates."""
    try:
        from app.services.self_healing import get_error_tracker
        tracker = get_error_tracker()
        return tracker.get_error_summary()
    except Exception as e:
        return {"error": str(e), "total_unique_errors": 0}


@router.get("/self-healing")
async def get_self_healing_status():
    """Get self-healing loop status and health report."""
    try:
        from app.services.self_healing import get_healing_loop
        heal = get_healing_loop()
        return heal.get_health_report()
    except Exception as e:
        return {"error": str(e), "self_healing": {"status": "error"}}


@router.get("/prompts")
async def list_prompts(db: Session = Depends(get_db)):
    """List all stored system prompts."""
    prompts = db.query(SystemPrompt).all()
    return {
        "prompts": [
            {
                "id": p.id,
                "name": p.name,
                "is_default": p.is_default,
                "content_preview": p.content[:200] + "..." if len(p.content) > 200 else p.content,
                "created_at": p.created_at,
            }
            for p in prompts
        ]
    }


@router.post("/prompts")
async def create_prompt(name: str, content: str, is_default: bool = False, db: Session = Depends(get_db)):
    """Create or update a system prompt."""
    existing = db.query(SystemPrompt).filter_by(name=name).first()
    if existing:
        existing.content = content
        existing.is_default = is_default
    else:
        prompt = SystemPrompt(name=name, content=content, is_default=is_default)
        db.add(prompt)

    if is_default:
        # Unset other defaults
        db.query(SystemPrompt).filter(SystemPrompt.name != name).update({"is_default": False})

    db.commit()
    return {"status": "saved", "name": name}


@router.delete("/prompts/{name}")
async def delete_prompt(name: str, db: Session = Depends(get_db)):
    """Delete a system prompt."""
    prompt = db.query(SystemPrompt).filter_by(name=name).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(prompt)
    db.commit()
    return {"status": "deleted", "name": name}
