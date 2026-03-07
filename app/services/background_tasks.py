"""
Background Task Manager — Spawn and manage async jobs that run while the operator chats.

Cipher can kick off long-running tasks (building files, research, deployments, multi-step operations)
in the background. The operator keeps chatting. Cipher reports progress when asked or when tasks complete.

Architecture:
- Tasks are asyncio.Tasks running in the event loop
- Each task has an ID, status, progress updates, and output
- The orchestrator can spawn tasks and check status inline
- Tasks can chain agents (research → code → file → deploy)
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from pydantic import BaseModel, Field

from app.core.logging import logger


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskProgress(BaseModel):
    """A single progress update from a running task."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str = ""
    percent: Optional[float] = None  # 0.0 - 1.0
    step: Optional[str] = None  # Current step name
    details: Optional[dict] = None


class BackgroundTask(BaseModel):
    """Represents a background task with full lifecycle tracking."""
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.QUEUED
    progress: list[TaskProgress] = Field(default_factory=list)
    output: Any = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def latest_progress(self) -> Optional[TaskProgress]:
        return self.progress[-1] if self.progress else None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at:
            end = self.completed_at or datetime.utcnow()
            return (end - self.started_at).total_seconds()
        return None

    def summary(self) -> str:
        """Human-readable status summary."""
        latest = self.latest_progress
        duration = self.duration_seconds

        if self.status == TaskStatus.RUNNING:
            progress_msg = f" — {latest.message}" if latest else ""
            percent = f" ({int(latest.percent * 100)}%)" if latest and latest.percent else ""
            return f"[RUNNING] {self.name}{progress_msg}{percent}"
        elif self.status == TaskStatus.COMPLETED:
            time_str = f" in {duration:.1f}s" if duration else ""
            return f"[DONE] {self.name}{time_str}"
        elif self.status == TaskStatus.FAILED:
            return f"[FAILED] {self.name} — {self.error or 'Unknown error'}"
        elif self.status == TaskStatus.CANCELLED:
            return f"[CANCELLED] {self.name}"
        else:
            return f"[QUEUED] {self.name}"


class BackgroundTaskManager:
    """
    Manages background async tasks that run while the operator chats.

    Usage:
        manager = get_task_manager()

        # Spawn a task
        task_id = await manager.spawn(
            name="Build Next.js web app",
            description="Creating 15 files for the web frontend",
            coroutine=build_web_app_coroutine(params),
        )

        # Check status
        task = manager.get_task(task_id)
        print(task.summary())

        # List all running
        running = manager.get_running_tasks()

        # Update progress from within a task
        await manager.update_progress(task_id, "Creating package.json", percent=0.1)
    """

    def __init__(self, max_concurrent: int = 0):
        self._tasks: dict[str, BackgroundTask] = {}
        self._async_handles: dict[str, asyncio.Task] = {}
        self._max_concurrent = max_concurrent  # 0 = unlimited
        self._lock = asyncio.Lock()

    async def spawn(
        self,
        name: str,
        coroutine: Coroutine,
        description: str = "",
    ) -> str:
        """
        Spawn a new background task.

        Args:
            name: Human-readable task name
            coroutine: The async coroutine to run
            description: Longer description of what this task does

        Returns:
            task_id for tracking
        """
        if self._max_concurrent > 0:
            async with self._lock:
                running_count = sum(
                    1 for t in self._tasks.values()
                    if t.status == TaskStatus.RUNNING
                )
                if running_count >= self._max_concurrent:
                    logger.warning(f"Max concurrent tasks reached ({self._max_concurrent})")
                    raise RuntimeError(
                        f"Maximum concurrent tasks ({self._max_concurrent}) reached. "
                        f"Wait for running tasks to complete."
                    )

        task = BackgroundTask(name=name, description=description)
        self._tasks[task.task_id] = task

        logger.info(f"[TaskManager] Spawning background task: {task.task_id} — {name}")

        # Wrap the coroutine to handle lifecycle
        async def _run_task():
            try:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.utcnow()
                task.progress.append(TaskProgress(message="Started", percent=0.0))

                logger.info(f"[TaskManager] Task {task.task_id} started: {name}")

                result = await coroutine

                task.output = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                task.progress.append(TaskProgress(
                    message="Completed",
                    percent=1.0,
                ))

                logger.info(
                    f"[TaskManager] Task {task.task_id} completed in "
                    f"{task.duration_seconds:.1f}s: {name}"
                )

            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.utcnow()
                logger.info(f"[TaskManager] Task {task.task_id} cancelled: {name}")

            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.utcnow()
                logger.error(f"[TaskManager] Task {task.task_id} failed: {name} — {e}")

        async_task = asyncio.create_task(_run_task())
        self._async_handles[task.task_id] = async_task

        return task.task_id

    async def update_progress(
        self,
        task_id: str,
        message: str,
        percent: Optional[float] = None,
        step: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        """Update progress on a running task. Call this from within the task coroutine."""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.RUNNING:
            task.progress.append(TaskProgress(
                message=message,
                percent=percent,
                step=step,
                details=details,
            ))
            logger.debug(f"[TaskManager] Task {task_id} progress: {message}")

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[BackgroundTask]:
        """Get all tasks, newest first."""
        return sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )

    def get_running_tasks(self) -> list[BackgroundTask]:
        """Get all currently running tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def get_completed_tasks(self) -> list[BackgroundTask]:
        """Get all completed tasks (success or failure)."""
        return [
            t for t in self._tasks.values()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        ]

    def get_status_summary(self) -> str:
        """Get a human-readable summary of all tasks."""
        running = self.get_running_tasks()
        completed = self.get_completed_tasks()
        queued = [t for t in self._tasks.values() if t.status == TaskStatus.QUEUED]

        lines = []
        if running:
            lines.append(f"**Running ({len(running)}):**")
            for t in running:
                lines.append(f"  • {t.summary()}")
        if queued:
            lines.append(f"**Queued ({len(queued)}):**")
            for t in queued:
                lines.append(f"  • {t.summary()}")
        if completed:
            # Show last 5 completed
            lines.append(f"**Recent ({len(completed)} total):**")
            for t in completed[:5]:
                lines.append(f"  • {t.summary()}")

        if not lines:
            return "No background tasks running."

        return "\n".join(lines)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        handle = self._async_handles.get(task_id)
        if handle and not handle.done():
            handle.cancel()
            logger.info(f"[TaskManager] Cancelling task {task_id}")
            return True
        return False

    async def cancel_all(self):
        """Cancel all running tasks."""
        for task_id, handle in self._async_handles.items():
            if not handle.done():
                handle.cancel()
                logger.info(f"[TaskManager] Cancelling task {task_id}")

    def clear_completed(self) -> int:
        """Remove completed/failed/cancelled tasks from history."""
        to_remove = [
            tid for tid, t in self._tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        ]
        for tid in to_remove:
            del self._tasks[tid]
            self._async_handles.pop(tid, None)
        return len(to_remove)


# Singleton
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """Get the global BackgroundTaskManager singleton."""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager(max_concurrent=0)  # Unlimited
    return _task_manager
