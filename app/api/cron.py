"""
Cron API endpoints — View and manage Cipher's internal scheduled tasks.

These endpoints power the iOS app's Scheduled Tasks view.
"""

from fastapi import APIRouter

from app.services.cron_registry import get_cron_registry
from app.core.logging import logger

router = APIRouter(prefix="/api/v1/cron", tags=["cron"])


@router.get("/tasks")
async def list_cron_tasks():
    """List all registered cron tasks with their status."""
    registry = get_cron_registry()
    tasks = registry.list_tasks()
    return {
        "total": len(tasks),
        "enabled": len([t for t in tasks if t["enabled"]]),
        "tasks": tasks,
    }


@router.get("/tasks/{task_id}")
async def get_cron_task(task_id: str):
    """Get details for a specific cron task."""
    registry = get_cron_registry()
    task = registry.get_task(task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}
    return task


@router.post("/tasks/{task_id}/enable")
async def enable_cron_task(task_id: str):
    """Enable a cron task."""
    registry = get_cron_registry()
    if registry.enable(task_id):
        return {"task_id": task_id, "enabled": True}
    return {"error": f"Task {task_id} not found"}


@router.post("/tasks/{task_id}/disable")
async def disable_cron_task(task_id: str):
    """Disable a cron task."""
    registry = get_cron_registry()
    if registry.disable(task_id):
        return {"task_id": task_id, "enabled": False}
    return {"error": f"Task {task_id} not found"}


@router.post("/tasks/{task_id}/run")
async def run_cron_task_now(task_id: str):
    """Manually trigger a cron task to run immediately."""
    registry = get_cron_registry()
    task_data = registry.get_task(task_id)
    if not task_data:
        return {"error": f"Task {task_id} not found"}

    task = registry._tasks.get(task_id)
    if task:
        await registry._execute_task(task)
        registry._save_state()
        return {
            "task_id": task_id,
            "triggered": True,
            "last_run": task.last_run.isoformat() if task.last_run else None,
            "last_error": task.last_error,
        }
    return {"error": "Execution failed"}
