"""
Base Agent class that all agent skills inherit from.
Provides common functionality like logging, timing, error handling, and verification.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Optional

from app.agents.models import AgentCapability, AgentResult, AgentStatus, AgentTask
from app.core.logging import logger

# Type for progress callbacks: async fn(message: str) -> None
ProgressCallback = Optional[Callable[[str], Any]]


class BaseAgent(ABC):
    """
    Abstract base class for all agent skills.
    Every agent must implement execute() and verify() methods.
    """

    def __init__(
        self,
        name: str,
        description: str,
        version: str = "1.0.0",
        capabilities: Optional[list[AgentCapability]] = None,
    ):
        """
        Initialize the agent.

        Args:
            name: Unique agent identifier
            description: Human-readable description
            version: Version string
            capabilities: List of capabilities this agent provides
        """
        self.name = name
        self.description = description
        self.version = version
        self.capabilities = capabilities or []
        self.status = AgentStatus.PENDING
        self._progress_callback: ProgressCallback = None

    def set_progress_callback(self, callback: ProgressCallback):
        """Set a callback that receives real-time progress updates during execution."""
        self._progress_callback = callback

    async def emit_progress(self, message: str):
        """Emit a progress update to the frontend via the callback."""
        if self._progress_callback:
            try:
                result = self._progress_callback(message)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    async def validate(self, task: AgentTask) -> bool:
        """
        Validate a task before execution.
        Override in subclasses for specific validation logic.

        Args:
            task: The task to validate

        Returns:
            True if valid, False otherwise
        """
        if not task.agent_name:
            logger.warning(f"Task {task.task_id}: Missing agent_name")
            return False

        if not task.instruction or not task.instruction.strip():
            logger.warning(f"Task {task.task_id}: Empty instruction")
            return False

        if task.timeout_seconds < 1:
            logger.warning(f"Task {task.task_id}: Invalid timeout {task.timeout_seconds}")
            return False

        return True

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        """
        Execute the agent task. Must be implemented by subclasses.

        Args:
            task: The task to execute

        Returns:
            AgentResult with execution details
        """
        pass

    @abstractmethod
    async def verify(self, result: AgentResult) -> bool:
        """
        Verify that the execution result is valid and real.
        CRITICAL: Every agent must verify its own output.

        This is NOT optional - it catches:
        - Command failures that didn't set success=False
        - Partial/corrupted output
        - Timeouts that still returned data
        - API errors disguised as success

        Args:
            result: The result to verify

        Returns:
            True if result is verified as legitimate, False otherwise
        """
        pass

    async def run(self, task: AgentTask) -> AgentResult:
        """
        Main execution method with validation and verification.
        This is the entry point for task execution.

        Args:
            task: The task to execute

        Returns:
            AgentResult with execution details
        """
        start_time = time.time()
        self.status = AgentStatus.RUNNING

        logger.info(f"[{self.name}] Starting task {task.task_id}: {task.instruction[:60]}...")

        try:
            # Validation step
            await self.emit_progress("Validating request...")
            if not await self.validate(task):
                self.status = AgentStatus.FAILED
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error="Task validation failed",
                    execution_time_ms=0,
                    verified=False,
                )

            # Execution step
            await self.emit_progress("Executing...")
            result = await asyncio.wait_for(
                self.execute(task),
                timeout=task.timeout_seconds,
            )

            # Verification step
            self.status = AgentStatus.VERIFYING
            await self.emit_progress("Verifying results...")
            verified = await self.verify(result)

            execution_time_ms = (time.time() - start_time) * 1000

            result.execution_time_ms = execution_time_ms
            result.verified = verified
            result.completed_at = datetime.utcnow()

            if verified:
                self.status = AgentStatus.COMPLETED
                logger.info(
                    f"[{self.name}] Task {task.task_id} completed successfully in {execution_time_ms:.1f}ms"
                )
            else:
                logger.warning(
                    f"[{self.name}] Task {task.task_id} completed but verification failed"
                )

            return result

        except asyncio.TimeoutError:
            execution_time_ms = (time.time() - start_time) * 1000
            self.status = AgentStatus.FAILED
            logger.error(
                f"[{self.name}] Task {task.task_id} timed out after {task.timeout_seconds}s"
            )
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Task execution timed out after {task.timeout_seconds} seconds",
                execution_time_ms=execution_time_ms,
                verified=False,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.status = AgentStatus.FAILED
            logger.exception(f"[{self.name}] Task {task.task_id} failed with exception")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
                verified=False,
            )

    def get_capability(self, name: str) -> Optional[AgentCapability]:
        """Get a specific capability by name."""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None

    def requires_approval_for(self, instruction: str) -> bool:
        """
        Check if an instruction requires approval.
        Override in subclasses for custom logic.

        Args:
            instruction: The instruction to check

        Returns:
            True if approval is required
        """
        return False

    def __str__(self) -> str:
        return f"{self.name} v{self.version} - {self.description}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, capabilities={len(self.capabilities)})>"
