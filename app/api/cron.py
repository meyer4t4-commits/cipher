"""
Cron API endpoints — View and manage Cipher's internal scheduled tasks.

These endpoints power the web app's Scheduled Tasks view and iOS app.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.cron_registry import get_cron_registry, CronTask
from app.core.logging import logger

router = APIRouter(prefix="/api/v1/cron", tags=["cron"])


class CronTaskCreate(BaseModel):
    task_id: str
    name: str
    cron_expression: str
    agent_name: str
    operation: str
    params: dict = {}
    enabled: bool = True
    description: str = ""


class CronTaskUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    agent_name: Optional[str] = None
    operation: Optional[str] = None
    params: Optional[dict] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


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


@router.post("/tasks")
async def create_cron_task(body: CronTaskCreate):
    """Create a new cron task."""
    registry = get_cron_registry()
    if registry.get_task(body.task_id):
        raise HTTPException(status_code=409, detail=f"Task '{body.task_id}' already exists")
    task = CronTask(
        task_id=body.task_id,
        name=body.name,
        cron_expression=body.cron_expression,
        agent_name=body.agent_name,
        operation=body.operation,
        params=body.params,
        enabled=body.enabled,
        description=body.description,
    )
    registry.register(task)
    registry._save_state()
    logger.info(f"Created cron task: {body.task_id}")
    return registry.get_task(body.task_id)


@router.put("/tasks/{task_id}")
async def update_cron_task(task_id: str, body: CronTaskUpdate):
    """Update an existing cron task."""
    registry = get_cron_registry()
    task = registry._tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    if body.name is not None:
        task.name = body.name
    if body.cron_expression is not None:
        task.cron_expression = body.cron_expression
        from app.services.cron_registry import next_cron_time
        try:
            task.next_run = next_cron_time(body.cron_expression)
        except Exception:
            pass
    if body.agent_name is not None:
        task.agent_name = body.agent_name
    if body.operation is not None:
        task.operation = body.operation
    if body.params is not None:
        task.params = body.params
    if body.enabled is not None:
        task.enabled = body.enabled
    if body.description is not None:
        task.description = body.description
    registry._save_state()
    logger.info(f"Updated cron task: {task_id}")
    return task.to_dict()


@router.delete("/tasks/{task_id}")
async def delete_cron_task(task_id: str):
    """Delete a cron task."""
    registry = get_cron_registry()
    if registry.unregister(task_id):
        logger.info(f"Deleted cron task: {task_id}")
        return {"task_id": task_id, "deleted": True}
    raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
