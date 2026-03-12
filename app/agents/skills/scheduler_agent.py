"""
Scheduler Agent - Task scheduling with JSON persistence and cron registry integration.
v2.0.0 — All tasks persisted to disk, integrates with Cipher's CronRegistry.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class SchedulerAgent(BaseAgent):
    """Schedule tasks with persistence — survives restarts, integrates with cron registry."""

    def __init__(self):
        """Initialize the scheduler agent."""
        super().__init__(
            name="scheduler_agent",
            description="Task scheduling and cron job management with persistence",
            version="2.0.0",
            capabilities=[
                AgentCapability(
                    name="schedule_once",
                    description="Schedule task to run once at a specific time",
                    category="scheduling",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="schedule_recurring",
                    description="Schedule recurring task with cron expression",
                    category="scheduling",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="schedule_delay",
                    description="Schedule task to run after a delay",
                    category="scheduling",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="list_scheduled",
                    description="List all scheduled tasks",
                    category="data",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="cancel_scheduled",
                    description="Cancel a scheduled task",
                    category="execution",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="create_chain",
                    description="Create task dependency chain",
                    category="scheduling",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="get_queue_status",
                    description="Get task queue status",
                    category="data",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="recover_missed",
                    description="Recover and execute missed tasks",
                    category="execution",
                    timeout_seconds=30,
                ),
            ],
        )
        self.data_dir = Path("data/scheduler")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._tasks_file = self.data_dir / "scheduled_tasks.json"
        self._history_file = self.data_dir / "task_history.json"

    def _load_tasks(self) -> dict[str, dict]:
        """Load scheduled tasks from disk."""
        if self._tasks_file.exists():
            try:
                return json.loads(self._tasks_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_tasks(self, tasks: dict[str, dict]):
        """Persist scheduled tasks to disk."""
        self._tasks_file.write_text(json.dumps(tasks, indent=2, default=str))

    def _load_history(self) -> list[dict]:
        """Load task execution history."""
        if self._history_file.exists():
            try:
                return json.loads(self._history_file.read_text())
            except Exception:
                return []
        return []

    def _append_history(self, entry: dict):
        """Append to task execution history."""
        history = self._load_history()
        history.append(entry)
        # Keep last 500 entries
        history = history[-500:]
        self._history_file.write_text(json.dumps(history, indent=2, default=str))

    async def validate(self, task: AgentTask) -> bool:
        """Validate scheduler task."""
        if not await super().validate(task):
            return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute scheduler operation."""
        operation = task.params.get("operation", "schedule_once")

        try:
            if operation == "schedule_once":
                return await self._schedule_once(task)
            elif operation == "schedule_recurring":
                return await self._schedule_recurring(task)
            elif operation == "schedule_delay":
                return await self._schedule_delay(task)
            elif operation == "list_scheduled":
                return await self._list_scheduled(task)
            elif operation == "cancel_scheduled":
                return await self._cancel_scheduled(task)
            elif operation == "create_chain":
                return await self._create_chain(task)
            elif operation == "get_queue_status":
                return await self._get_queue_status(task)
            elif operation == "recover_missed":
                return await self._recover_missed(task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Scheduler operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _schedule_once(self, task: AgentTask) -> AgentResult:
        """Schedule task to run once — persisted to disk and registered with cron."""
        task_id = task.params.get("task_id", f"once_{uuid.uuid4().hex[:8]}")
        run_at = task.params.get("run_at")
        task_def = task.params.get("task", {})
        description = task.params.get("description", "One-time scheduled task")

        if not run_at:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Missing 'run_at' parameter (ISO format datetime)")

        tasks = self._load_tasks()
        tasks[task_id] = {
            "type": "once",
            "run_at": run_at,
            "task": task_def,
            "description": description,
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
        }
        self._save_tasks(tasks)

        # Try to register with CronRegistry for actual execution
        registered = await self._register_with_cron(task_id, description, task_def, cron_expr=None, run_at=run_at)

        output = {
            "operation": "schedule_once",
            "scheduled_task_id": task_id,
            "run_at": run_at,
            "description": description,
            "status": "scheduled",
            "persisted": True,
            "cron_registered": registered,
            "created_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _schedule_recurring(self, task: AgentTask) -> AgentResult:
        """Schedule recurring task with cron expression — persisted and registered."""
        task_id = task.params.get("task_id", f"recurring_{uuid.uuid4().hex[:8]}")
        cron = task.params.get("cron")
        interval = task.params.get("interval")
        task_def = task.params.get("task", {})
        description = task.params.get("description", "Recurring scheduled task")

        if not cron and not interval:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Need 'cron' expression (e.g. '0 9 * * *') or 'interval' in seconds")

        # Convert interval to cron if needed
        if not cron and interval:
            if interval <= 60:
                cron = "* * * * *"  # every minute
            elif interval <= 3600:
                mins = max(1, interval // 60)
                cron = f"*/{mins} * * * *"
            else:
                hours = max(1, interval // 3600)
                cron = f"0 */{hours} * * *"

        tasks = self._load_tasks()
        tasks[task_id] = {
            "type": "recurring",
            "cron": cron,
            "interval": interval,
            "task": task_def,
            "description": description,
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
            "run_count": 0,
        }
        self._save_tasks(tasks)

        registered = await self._register_with_cron(task_id, description, task_def, cron_expr=cron)

        output = {
            "operation": "schedule_recurring",
            "scheduled_task_id": task_id,
            "cron": cron,
            "interval": interval,
            "description": description,
            "status": "scheduled",
            "persisted": True,
            "cron_registered": registered,
            "created_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _schedule_delay(self, task: AgentTask) -> AgentResult:
        """Schedule task after delay — persisted."""
        task_id = task.params.get("task_id", f"delay_{uuid.uuid4().hex[:8]}")
        delay_seconds = task.params.get("delay_seconds")
        task_def = task.params.get("task", {})
        description = task.params.get("description", f"Delayed task ({delay_seconds}s)")

        if not delay_seconds:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Missing 'delay_seconds' parameter")

        run_at = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()

        tasks = self._load_tasks()
        tasks[task_id] = {
            "type": "delayed",
            "delay_seconds": delay_seconds,
            "run_at": run_at,
            "task": task_def,
            "description": description,
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
        }
        self._save_tasks(tasks)

        registered = await self._register_with_cron(task_id, description, task_def, run_at=run_at)

        output = {
            "operation": "schedule_delay",
            "scheduled_task_id": task_id,
            "delay_seconds": delay_seconds,
            "run_at": run_at,
            "description": description,
            "status": "scheduled",
            "persisted": True,
            "cron_registered": registered,
            "created_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _list_scheduled(self, task: AgentTask) -> AgentResult:
        """List all scheduled tasks from persistent storage."""
        tasks = self._load_tasks()

        output = {
            "operation": "list_scheduled",
            "total_scheduled": len(tasks),
            "tasks": [
                {
                    "scheduled_task_id": tid,
                    "type": info.get("type"),
                    "status": info.get("status", "unknown"),
                    "description": info.get("description", ""),
                    "cron": info.get("cron"),
                    "run_at": info.get("run_at"),
                    "created_at": info.get("created_at"),
                    "run_count": info.get("run_count", 0),
                }
                for tid, info in list(tasks.items())[:50]
            ],
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _cancel_scheduled(self, task: AgentTask) -> AgentResult:
        """Cancel a scheduled task — removes from storage and cron registry."""
        scheduled_task_id = task.params.get("scheduled_task_id") or task.params.get("task_id")

        if not scheduled_task_id:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Need 'scheduled_task_id' to cancel")

        tasks = self._load_tasks()
        if scheduled_task_id not in tasks:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error=f"Task '{scheduled_task_id}' not found. Use list_scheduled to see available tasks.")

        removed = tasks.pop(scheduled_task_id)
        self._save_tasks(tasks)

        # Try to remove from cron registry
        try:
            from app.services.cron_registry import get_cron_registry
            registry = get_cron_registry()
            if hasattr(registry, "remove_task"):
                registry.remove_task(scheduled_task_id)
        except Exception:
            pass

        self._append_history({
            "task_id": scheduled_task_id,
            "action": "cancelled",
            "timestamp": datetime.utcnow().isoformat(),
        })

        output = {
            "operation": "cancel_scheduled",
            "scheduled_task_id": scheduled_task_id,
            "status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _create_chain(self, task: AgentTask) -> AgentResult:
        """Create task dependency chain — persisted."""
        chain_id = task.params.get("chain_id", f"chain_{uuid.uuid4().hex[:8]}")
        tasks_list = task.params.get("tasks", [])

        if not tasks_list:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Need 'tasks' list with at least one task definition")

        tasks = self._load_tasks()
        tasks[chain_id] = {
            "type": "chain",
            "tasks": tasks_list,
            "description": task.params.get("description", f"Chain of {len(tasks_list)} tasks"),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "current_step": 0,
        }
        self._save_tasks(tasks)

        output = {
            "operation": "create_chain",
            "chain_id": chain_id,
            "total_tasks": len(tasks_list),
            "status": "created",
            "persisted": True,
            "tasks_in_chain": [
                {"order": i + 1, "task_id": t.get("task_id", f"step_{i+1}"), "description": t.get("description", "")}
                for i, t in enumerate(tasks_list)
            ],
            "created_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _get_queue_status(self, task: AgentTask) -> AgentResult:
        """Get task queue status from persistent storage."""
        tasks = self._load_tasks()
        history = self._load_history()

        by_status = {}
        for tid, info in tasks.items():
            s = info.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1

        by_type = {}
        for tid, info in tasks.items():
            t = info.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        output = {
            "operation": "get_queue_status",
            "total_tasks": len(tasks),
            "by_status": by_status,
            "by_type": by_type,
            "recent_history": history[-10:],
            "status_timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _recover_missed(self, task: AgentTask) -> AgentResult:
        """Find and flag tasks that missed their run_at time."""
        lookback_hours = task.params.get("lookback_hours", 24)
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)

        tasks = self._load_tasks()
        missed = []

        for tid, info in tasks.items():
            if info.get("status") != "scheduled":
                continue
            run_at_str = info.get("run_at")
            if not run_at_str:
                continue
            try:
                run_at = datetime.fromisoformat(run_at_str)
                if run_at < datetime.utcnow() and run_at > cutoff:
                    missed.append({
                        "task_id": tid,
                        "run_at": run_at_str,
                        "type": info.get("type"),
                        "description": info.get("description", ""),
                    })
                    # Mark as missed
                    info["status"] = "missed"
            except Exception:
                continue

        if missed:
            self._save_tasks(tasks)

        output = {
            "operation": "recover_missed",
            "lookback_hours": lookback_hours,
            "missed_tasks_found": len(missed),
            "missed_tasks": missed,
            "note": "Missed tasks have been flagged. Re-schedule them or execute manually." if missed else "No missed tasks found.",
            "recovery_timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _register_with_cron(self, task_id: str, description: str, task_def: dict,
                                   cron_expr: str | None = None, run_at: str | None = None) -> bool:
        """Try to register a task with Cipher's CronRegistry for actual execution."""
        try:
            from app.services.cron_registry import get_cron_registry
            registry = get_cron_registry()

            if cron_expr and hasattr(registry, "register_task"):
                agent_name = task_def.get("agent_name", "")
                operation = task_def.get("operation", "")
                params = task_def.get("params", {})

                registry.register_task(
                    task_id=task_id,
                    name=description,
                    cron_expression=cron_expr,
                    agent_name=agent_name,
                    operation=operation,
                    params=params,
                    description=description,
                )
                logger.info(f"Registered task {task_id} with CronRegistry (cron={cron_expr})")
                return True

        except Exception as e:
            logger.warning(f"Could not register with CronRegistry: {e}")

        return False

    async def verify(self, result: AgentResult) -> bool:
        """Verify scheduler result."""
        if not isinstance(result.output, dict):
            return False
        if "operation" not in result.output:
            return False
        return True
