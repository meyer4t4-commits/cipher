"""
Task Executor - manages the task execution lifecycle.
Handles routing, approval gates, concurrent execution, and history logging.
"""

import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.models import AgentResult, AgentStatus, AgentTask
from app.agents.registry import get_registry
from app.core.logging import logger
from app.db.database import SessionLocal


class ExecutionHistoryDB:
    """Stores execution history in the database."""

    @staticmethod
    def log_task(
        db: Session,
        task: AgentTask,
        result: AgentResult,
        status: AgentStatus,
    ) -> None:
        """
        Log a task execution to the database.

        Args:
            db: Database session
            task: The task that was executed
            result: The execution result
            status: Final status of the task
        """
        from app.db.models import TaskRecord

        try:
            import json

            record = TaskRecord(
                id=task.task_id,
                task_type=f"agent:{task.agent_name}",
                status=status.value,
                input_data=json.dumps({
                    "agent": task.agent_name,
                    "instruction": task.instruction,
                    "params": task.params,
                    "timeout": task.timeout_seconds,
                }),
                output_data=json.dumps({
                    "success": result.success,
                    "output": result.output,
                    "execution_time_ms": result.execution_time_ms,
                    "verified": result.verified,
                }),
                error=result.error,
                completed_at=result.completed_at if status == AgentStatus.COMPLETED else None,
            )
            db.add(record)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log task {task.task_id} to database: {e}")
            db.rollback()


class TaskExecutor:
    """
    Executes tasks by routing them to appropriate agents.
    Manages approval gates, timeouts, and concurrent execution.
    """

    def __init__(self, max_concurrent_tasks: int = 10):
        """
        Initialize the executor.

        Args:
            max_concurrent_tasks: Maximum concurrent tasks to run
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.registry = get_registry()
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._pending_approvals: dict[str, AgentTask] = {}
        self._execution_history: dict[str, AgentResult] = {}

    async def execute(self, task: AgentTask, db: Optional[Session] = None, progress_callback=None) -> AgentResult:
        """
        Execute a task with validation and routing.

        Args:
            task: The task to execute
            db: Optional database session for logging
            progress_callback: Optional async callback for real-time progress updates

        Returns:
            Execution result
        """
        async with self._semaphore:
            return await self._execute_internal(task, db, progress_callback)

    async def _execute_internal(self, task: AgentTask, db: Optional[Session] = None, progress_callback=None) -> AgentResult:
        """Internal execution method."""
        logger.info(f"Executing task {task.task_id} on agent {task.agent_name}")

        # Get the agent
        agent = self.registry.get_agent(task.agent_name)
        if not agent:
            logger.error(f"Agent '{task.agent_name}' not found in registry")
            result = AgentResult(
                task_id=task.task_id,
                agent_name=task.agent_name,
                success=False,
                error=f"Agent '{task.agent_name}' not found",
                execution_time_ms=0,
                verified=False,
            )
            if db:
                ExecutionHistoryDB.log_task(db, task, result, AgentStatus.FAILED)
            return result

        # Check approval requirement
        if task.requires_approval and not task.approved_at:
            logger.info(f"Task {task.task_id} requires approval")
            self._pending_approvals[task.task_id] = task
            if db:
                ExecutionHistoryDB.log_task(db, task, AgentResult(
                    task_id=task.task_id,
                    agent_name=task.agent_name,
                    success=False,
                    error="Awaiting approval",
                    execution_time_ms=0,
                    verified=False,
                ), AgentStatus.AWAITING_APPROVAL)
            return AgentResult(
                task_id=task.task_id,
                agent_name=task.agent_name,
                success=False,
                error="Task requires operator approval",
                execution_time_ms=0,
                verified=False,
            )

        # Set progress callback if provided
        if progress_callback:
            agent.set_progress_callback(progress_callback)

        # Execute the task
        result = await agent.run(task)

        # Clear callback after execution
        agent.set_progress_callback(None)

        # Store in history
        self._execution_history[task.task_id] = result

        # Log to database
        if db:
            status = AgentStatus.COMPLETED if result.success else AgentStatus.FAILED
            ExecutionHistoryDB.log_task(db, task, result, status)

        return result

    def approve_task(
        self,
        task_id: str,
        approved_by: str,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Approve a pending task.

        Args:
            task_id: Task ID to approve
            approved_by: Username/ID of approver
            notes: Optional approval notes

        Returns:
            True if approved, False if not found
        """
        if task_id not in self._pending_approvals:
            logger.warning(f"Approval requested for unknown task {task_id}")
            return False

        task = self._pending_approvals[task_id]
        task.approved_at = datetime.utcnow()
        task.approved_by = approved_by

        logger.info(f"Task {task_id} approved by {approved_by}")

        if notes:
            logger.info(f"Approval notes: {notes}")

        # Remove from pending
        del self._pending_approvals[task_id]

        return True

    def reject_task(
        self,
        task_id: str,
        rejected_by: str,
        reason: str,
    ) -> bool:
        """
        Reject a pending task.

        Args:
            task_id: Task ID to reject
            rejected_by: Username/ID of rejector
            reason: Reason for rejection

        Returns:
            True if rejected, False if not found
        """
        if task_id not in self._pending_approvals:
            logger.warning(f"Rejection requested for unknown task {task_id}")
            return False

        task = self._pending_approvals[task_id]
        logger.info(f"Task {task_id} rejected by {rejected_by}: {reason}")

        # Store rejection result
        self._execution_history[task_id] = AgentResult(
            task_id=task_id,
            agent_name=task.agent_name,
            success=False,
            error=f"Task rejected: {reason}",
            execution_time_ms=0,
            verified=False,
        )

        # Remove from pending
        del self._pending_approvals[task_id]

        return True

    def get_pending_approvals(self) -> list[dict]:
        """
        Get all tasks awaiting approval.

        Returns:
            List of pending tasks
        """
        return [
            {
                "task_id": task.task_id,
                "agent_name": task.agent_name,
                "instruction": task.instruction,
                "requested_at": task.requested_at.isoformat(),
                "priority": task.priority,
            }
            for task in self._pending_approvals.values()
        ]

    def get_task_status(self, task_id: str) -> Optional[AgentResult]:
        """
        Get the result of a task.

        Args:
            task_id: Task ID

        Returns:
            AgentResult or None if not found
        """
        return self._execution_history.get(task_id)

    def get_execution_history(self, limit: int = 100) -> list[AgentResult]:
        """
        Get recent execution history.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of recent execution results
        """
        # Return most recent tasks
        tasks = sorted(
            self._execution_history.values(),
            key=lambda r: r.completed_at,
            reverse=True,
        )
        return tasks[:limit]

    async def execute_many(
        self,
        tasks: list[AgentTask],
        db: Optional[Session] = None,
    ) -> list[AgentResult]:
        """
        Execute multiple tasks concurrently.

        Args:
            tasks: List of tasks to execute
            db: Optional database session

        Returns:
            List of results in same order as input tasks
        """
        results = await asyncio.gather(
            *[self.execute(task, db) for task in tasks],
            return_exceptions=True,
        )

        # Convert any exceptions to AgentResult
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(AgentResult(
                    task_id=tasks[i].task_id,
                    agent_name=tasks[i].agent_name,
                    success=False,
                    error=str(result),
                    execution_time_ms=0,
                    verified=False,
                ))
            else:
                final_results.append(result)

        return final_results

    def clear_history(self) -> int:
        """
        Clear execution history. Use with caution!

        Returns:
            Number of entries cleared
        """
        count = len(self._execution_history)
        self._execution_history.clear()
        logger.warning(f"Cleared {count} execution history entries")
        return count

    def __str__(self) -> str:
        return (
            f"TaskExecutor(max_concurrent={self.max_concurrent_tasks}, "
            f"pending_approvals={len(self._pending_approvals)}, "
            f"history={len(self._execution_history)})"
        )


# Global executor instance
_executor = TaskExecutor()


def get_executor() -> TaskExecutor:
    """Get the global task executor."""
    return _executor
