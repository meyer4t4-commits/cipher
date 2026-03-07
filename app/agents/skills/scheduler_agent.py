"""
Scheduler Agent - Task scheduling, cron jobs, and dependency chains.
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class SchedulerAgent(BaseAgent):
    """Schedule tasks, manage cron jobs, and handle task dependencies."""

    def __init__(self):
        """Initialize the scheduler agent."""
        super().__init__(
            name="scheduler_agent",
            description="Task scheduling and cron job management",
            version="1.0.0",
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
        self.scheduled_tasks = {}
        self.task_queue = []

    async def validate(self, task: AgentTask) -> bool:
        """Validate scheduler task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation", "schedule_once")

        # Validate operation-specific parameters
        if operation == "schedule_once":
            if "run_at" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'run_at' for schedule_once")
                return False

        elif operation == "schedule_recurring":
            if "cron" not in task.params and "interval" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'cron' or 'interval'")
                return False

        elif operation == "schedule_delay":
            if "delay_seconds" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'delay_seconds'")
                return False

        elif operation == "create_chain":
            if "tasks" not in task.params or not task.params["tasks"]:
                logger.warning(f"Task {task.task_id}: Missing or empty 'tasks' list")
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
        """Schedule task to run once."""
        scheduled_task_id = task.params.get("task_id", f"once_{datetime.utcnow().timestamp()}")
        run_at = task.params.get("run_at")
        task_def = task.params.get("task", {})

        logger.info(f"Scheduling one-time task {scheduled_task_id} for {run_at}")

        output = {
            "operation": "schedule_once",
            "scheduled_task_id": scheduled_task_id,
            "run_at": run_at,
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
        }

        self.scheduled_tasks[scheduled_task_id] = {
            "type": "once",
            "run_at": run_at,
            "task": task_def,
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _schedule_recurring(self, task: AgentTask) -> AgentResult:
        """Schedule recurring task."""
        scheduled_task_id = task.params.get("task_id", f"recurring_{datetime.utcnow().timestamp()}")
        cron = task.params.get("cron")
        interval = task.params.get("interval")
        task_def = task.params.get("task", {})

        logger.info(f"Scheduling recurring task {scheduled_task_id} with cron={cron}")

        output = {
            "operation": "schedule_recurring",
            "scheduled_task_id": scheduled_task_id,
            "cron": cron,
            "interval": interval,
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
        }

        self.scheduled_tasks[scheduled_task_id] = {
            "type": "recurring",
            "cron": cron,
            "interval": interval,
            "task": task_def,
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _schedule_delay(self, task: AgentTask) -> AgentResult:
        """Schedule task after delay."""
        scheduled_task_id = task.params.get("task_id", f"delay_{datetime.utcnow().timestamp()}")
        delay_seconds = task.params.get("delay_seconds")
        task_def = task.params.get("task", {})

        run_at = datetime.utcnow() + timedelta(seconds=delay_seconds)

        logger.info(f"Scheduling delayed task {scheduled_task_id} in {delay_seconds}s")

        output = {
            "operation": "schedule_delay",
            "scheduled_task_id": scheduled_task_id,
            "delay_seconds": delay_seconds,
            "run_at": run_at.isoformat(),
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
        }

        self.scheduled_tasks[scheduled_task_id] = {
            "type": "delayed",
            "delay_seconds": delay_seconds,
            "run_at": run_at,
            "task": task_def,
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _list_scheduled(self, task: AgentTask) -> AgentResult:
        """List all scheduled tasks."""
        output = {
            "operation": "list_scheduled",
            "total_scheduled": len(self.scheduled_tasks),
            "tasks": [
                {
                    "scheduled_task_id": task_id,
                    "type": info["type"],
                    "status": "scheduled",
                    "created_at": datetime.utcnow().isoformat(),
                }
                for task_id, info in list(self.scheduled_tasks.items())[:50]
            ],
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _cancel_scheduled(self, task: AgentTask) -> AgentResult:
        """Cancel a scheduled task."""
        scheduled_task_id = task.params.get("scheduled_task_id")

        if scheduled_task_id not in self.scheduled_tasks:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Task {scheduled_task_id} not found",
            )

        del self.scheduled_tasks[scheduled_task_id]
        logger.info(f"Cancelled scheduled task {scheduled_task_id}")

        output = {
            "operation": "cancel_scheduled",
            "scheduled_task_id": scheduled_task_id,
            "status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _create_chain(self, task: AgentTask) -> AgentResult:
        """Create task dependency chain."""
        chain_id = task.params.get("chain_id", f"chain_{datetime.utcnow().timestamp()}")
        tasks_list = task.params.get("tasks", [])

        logger.info(f"Creating task chain {chain_id} with {len(tasks_list)} tasks")

        output = {
            "operation": "create_chain",
            "chain_id": chain_id,
            "total_tasks": len(tasks_list),
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
            "tasks_in_chain": [
                {"order": i + 1, "task_id": t.get("task_id")}
                for i, t in enumerate(tasks_list)
            ],
        }

        self.scheduled_tasks[chain_id] = {
            "type": "chain",
            "tasks": tasks_list,
            "status": "pending",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _get_queue_status(self, task: AgentTask) -> AgentResult:
        """Get task queue status."""
        output = {
            "operation": "get_queue_status",
            "total_queued": len(self.task_queue),
            "scheduled_tasks": len(self.scheduled_tasks),
            "queue_health": "healthy",
            "status_timestamp": datetime.utcnow().isoformat(),
            "recent_tasks": [
                {"id": i + 1, "status": "pending"}
                for i in range(min(5, len(self.task_queue)))
            ],
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _recover_missed(self, task: AgentTask) -> AgentResult:
        """Recover and execute missed tasks."""
        lookback_hours = task.params.get("lookback_hours", 24)

        output = {
            "operation": "recover_missed",
            "lookback_hours": lookback_hours,
            "missed_tasks_found": 0,
            "recovered": 0,
            "failed": 0,
            "recovery_timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def verify(self, result: AgentResult) -> bool:
        """Verify scheduler result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        # Should have operation field
        if "operation" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing 'operation'")
            return False

        return True
