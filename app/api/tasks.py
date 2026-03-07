"""
Background Tasks API — Spawn, monitor, and manage background jobs.

Cipher can kick off long-running work in the background while the operator
continues chatting. These endpoints let Cipher (and the operator) check on
progress, cancel tasks, and get results.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.services.background_tasks import get_task_manager

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskStatusResponse(BaseModel):
    task_id: str
    name: str
    description: str
    status: str
    latest_progress: Optional[str] = None
    percent_complete: Optional[float] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    output: Optional[str] = None


@router.get("/")
async def list_tasks(status_filter: Optional[str] = None):
    """
    List all background tasks, optionally filtered by status.

    Query params:
        status_filter: "running", "completed", "failed", "queued", "all" (default: "all")
    """
    manager = get_task_manager()

    if status_filter == "running":
        tasks = manager.get_running_tasks()
    elif status_filter in ("completed", "done"):
        tasks = manager.get_completed_tasks()
    else:
        tasks = manager.get_all_tasks()

    return {
        "total": len(tasks),
        "tasks": [
            {
                "task_id": t.task_id,
                "name": t.name,
                "description": t.description,
                "status": t.status.value,
                "latest_progress": t.latest_progress.message if t.latest_progress else None,
                "percent_complete": t.latest_progress.percent if t.latest_progress else None,
                "duration_seconds": t.duration_seconds,
                "error": t.error,
                "created_at": t.created_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
    }


@router.get("/status")
async def get_task_summary():
    """
    Get a human-readable summary of all background tasks.
    This is what Cipher uses to report task status to the operator.
    """
    manager = get_task_manager()
    return {
        "summary": manager.get_status_summary(),
        "running": len(manager.get_running_tasks()),
        "completed": len(manager.get_completed_tasks()),
        "total": len(manager.get_all_tasks()),
    }


@router.get("/{task_id}")
async def get_task_detail(task_id: str):
    """Get detailed status of a specific background task."""
    manager = get_task_manager()
    task = manager.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return {
        "task_id": task.task_id,
        "name": task.name,
        "description": task.description,
        "status": task.status.value,
        "progress": [
            {
                "timestamp": p.timestamp.isoformat(),
                "message": p.message,
                "percent": p.percent,
                "step": p.step,
            }
            for p in task.progress
        ],
        "output": str(task.output)[:2000] if task.output else None,
        "error": task.error,
        "duration_seconds": task.duration_seconds,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running background task."""
    manager = get_task_manager()
    task = manager.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    success = await manager.cancel_task(task_id)

    if success:
        logger.info(f"Task {task_id} cancelled by operator")
        return {"task_id": task_id, "cancelled": True}
    else:
        return {"task_id": task_id, "cancelled": False, "reason": "Task not running"}


@router.post("/cancel-all")
async def cancel_all_tasks():
    """Cancel all running background tasks."""
    manager = get_task_manager()
    await manager.cancel_all()
    return {"cancelled": True, "message": "All running tasks cancelled"}


@router.delete("/history")
async def clear_task_history():
    """Clear completed/failed/cancelled tasks from history."""
    manager = get_task_manager()
    cleared = manager.clear_completed()
    return {"cleared": cleared, "message": f"Removed {cleared} completed tasks from history"}
