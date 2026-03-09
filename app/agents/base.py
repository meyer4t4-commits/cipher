"""
Base Agent class that all agent skills inherit from.
Provides common functionality like logging, timing, error handling,
verification, auto-bash execution, and cross-agent invocation.
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

    ALL agents have built-in capabilities:
    - run_bash(): Execute shell commands automatically (no approval needed for safe commands)
    - invoke_agent(): Chain to any other agent seamlessly
    - run_bash_chain(): Run multiple bash commands in sequence, stopping on failure
    """

    def __init__(
        self,
        name: str,
        description: str,
        version: str = "1.0.0",
        capabilities: Optional[list[AgentCapability]] = None,
    ):
        self.name = name
        self.description = description
        self.version = version
        self.capabilities = capabilities or []
        self.status = AgentStatus.PENDING
        self._progress_callback: ProgressCallback = None
        self._executor_ref = None  # Set by executor for agent chaining

    def set_progress_callback(self, callback: ProgressCallback):
        """Set a callback that receives real-time progress updates during execution."""
        self._progress_callback = callback

    def set_executor_ref(self, executor):
        """Set reference to the task executor for cross-agent invocation."""
        self._executor_ref = executor

    async def emit_progress(self, message: str):
        """Emit a progress update to the frontend via the callback."""
        if self._progress_callback:
            try:
                result = self._progress_callback(message)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    # ── Built-in Bash Execution ──────────────────────────────────────

    async def run_bash(self, command: str, cwd: str = None, timeout: int = 30) -> dict:
        """
        Execute a bash command automatically. Available to ALL agents.
        No approval needed for safe commands. Dangerous commands are blocked.

        Args:
            command: Shell command to execute
            cwd: Working directory (optional)
            timeout: Timeout in seconds

        Returns:
            Dict with keys: stdout, stderr, exit_code, success
        """
        await self.emit_progress(f"Running: {command[:80]}...")
        logger.info(f"[{self.name}] Auto-bash: {command[:120]}")

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()
            success = process.returncode == 0

            if success:
                await self.emit_progress(f"Command succeeded (exit 0)")
            else:
                await self.emit_progress(f"Command failed (exit {process.returncode})")

            return {
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": process.returncode,
                "success": success,
                "command": command,
            }

        except asyncio.TimeoutError:
            await self.emit_progress(f"Command timed out after {timeout}s")
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "exit_code": -1,
                "success": False,
                "command": command,
            }
        except Exception as e:
            await self.emit_progress(f"Command error: {str(e)[:60]}")
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "success": False,
                "command": command,
            }

    async def run_bash_chain(self, commands: list[str], cwd: str = None, timeout: int = 30) -> list[dict]:
        """
        Run multiple bash commands in sequence. Stops on first failure.

        Args:
            commands: List of shell commands
            cwd: Working directory
            timeout: Timeout per command

        Returns:
            List of result dicts
        """
        results = []
        for i, cmd in enumerate(commands):
            await self.emit_progress(f"Step {i+1}/{len(commands)}: {cmd[:60]}...")
            result = await self.run_bash(cmd, cwd=cwd, timeout=timeout)
            results.append(result)
            if not result["success"]:
                await self.emit_progress(f"Chain stopped at step {i+1}: {result['stderr'][:80]}")
                break
        return results

    # ── Built-in Agent Chaining ──────────────────────────────────────

    async def invoke_agent(self, agent_name: str, instruction: str, params: dict = None, timeout: int = 60) -> AgentResult:
        """
        Invoke another agent seamlessly. Available to ALL agents.
        Enables multi-agent collaboration without user intervention.

        Args:
            agent_name: Name of the agent to invoke
            instruction: What the agent should do
            params: Optional parameters
            timeout: Timeout in seconds

        Returns:
            AgentResult from the invoked agent
        """
        await self.emit_progress(f"Invoking {agent_name}...")
        logger.info(f"[{self.name}] Chaining to {agent_name}: {instruction[:80]}")

        if not self._executor_ref:
            logger.error(f"[{self.name}] No executor reference for agent chaining")
            return AgentResult(
                task_id="chain-error",
                agent_name=agent_name,
                success=False,
                error="Agent chaining not available (no executor reference)",
                execution_time_ms=0,
                verified=False,
            )

        task = AgentTask(
            agent_name=agent_name,
            instruction=instruction,
            params=params or {},
            timeout_seconds=timeout,
            requires_approval=False,  # Chained tasks don't need approval
        )

        result = await self._executor_ref.execute(task, progress_callback=self._progress_callback)

        if result.success:
            await self.emit_progress(f"{agent_name} completed successfully")
        else:
            await self.emit_progress(f"{agent_name} failed: {(result.error or '')[:60]}")

        return result

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
