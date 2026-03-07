"""
Shell Execution Agent - Execute terminal commands safely.
Sandboxed with allowlist/denylist for dangerous operations.
"""

import asyncio
import re
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class ShellAgent(BaseAgent):
    """Execute shell commands in a sandboxed environment."""

    # Commands that are always denied for safety
    DENIED_PATTERNS = [
        r"^\s*rm\s+(-rf|-r|-f|--recursive)",  # rm -rf, rm -r, etc
        r"^\s*sudo\s+",  # sudo anything
        r"^\s*:()",  # vim ex mode
        r"^\s*mkfs",  # filesystem formatting
        r"^\s*dd\s+",  # low-level disk operations
        r"^\s*fdisk",  # partition table editing
        r"^\s*parted",  # partition editing
        r"^\s*lvm",  # LVM operations
        r"^\s*cfdisk",  # partition editor
        r"^\s*sfdisk",  # partition editor
        r"chown\s+",  # ownership changes
        r"chmod\s+",  # permission changes
        r"^\s*iptables",  # firewall rules
        r"^\s*systemctl\s+stop",  # stop system services
        r"^\s*systemctl\s+disable",  # disable services
        r"^\s*reboot",  # system reboot
        r"^\s*halt",  # system halt
        r"^\s*shutdown",  # system shutdown
        r"^\s*poweroff",  # power off
    ]

    def __init__(self):
        """Initialize the shell agent."""
        super().__init__(
            name="shell_agent",
            description="Execute shell commands in a sandboxed environment",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="execute_shell",
                    description="Execute shell commands (bash/zsh)",
                    category="execution",
                    requires_approval=False,
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="execute_shell_with_approval",
                    description="Execute potentially dangerous shell commands",
                    category="execution",
                    requires_approval=True,
                    timeout_seconds=30,
                ),
            ],
        )
        self.working_directory = Path.cwd()

    def _is_dangerous(self, command: str) -> bool:
        """
        Check if a command is dangerous.

        Args:
            command: The command to check

        Returns:
            True if dangerous
        """
        for pattern in self.DENIED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE | re.MULTILINE):
                return True
        return False

    def requires_approval_for(self, instruction: str) -> bool:
        """Check if the instruction contains a dangerous command."""
        # Check the raw instruction text against danger patterns
        return self._is_dangerous(instruction)

    async def validate(self, task: AgentTask) -> bool:
        """Validate the shell command task."""
        if not await super().validate(task):
            return False

        # Extract command from params
        if "command" not in task.params:
            logger.warning(f"Task {task.task_id}: Missing 'command' parameter")
            return False

        command = task.params["command"]
        if not isinstance(command, str) or not command.strip():
            logger.warning(f"Task {task.task_id}: Invalid command parameter")
            return False

        # Check if dangerous and requires approval
        if self._is_dangerous(command) and not task.approved_at:
            logger.warning(f"Task {task.task_id}: Dangerous command requires approval")
            return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """
        Execute a shell command.

        Args:
            task: The task containing the command

        Returns:
            AgentResult with command output
        """
        command = task.params["command"]
        cwd = task.params.get("cwd", str(self.working_directory))

        logger.debug(f"[{self.name}] Executing: {command}")

        try:
            # Use asyncio to run the shell command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            stdout, stderr = await process.communicate()

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            # Determine success
            success = process.returncode == 0

            output = {
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": process.returncode,
                "command": command,
            }

            logger.debug(f"[{self.name}] Command completed with exit code {process.returncode}")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=success,
                output=output,
                error=stderr_str if not success else None,
            )

        except Exception as e:
            logger.error(f"[{self.name}] Command execution failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                output={
                    "command": command,
                    "exception": str(e),
                },
            )

    async def verify(self, result: AgentResult) -> bool:
        """
        Verify the command execution result.

        Args:
            result: The result to verify

        Returns:
            True if result is valid
        """
        if not result.success:
            # Even if the command failed, if we got exit code info, it's real
            if isinstance(result.output, dict):
                return "exit_code" in result.output
            return False

        # For successful commands, verify we have output structure
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        # Check that we have the expected fields
        required_fields = ["stdout", "stderr", "exit_code", "command"]
        for field in required_fields:
            if field not in result.output:
                logger.warning(f"Result {result.task_id}: Missing field '{field}' in output")
                return False

        # Verify exit code is 0 for successful execution
        exit_code = result.output.get("exit_code")
        if not isinstance(exit_code, int):
            logger.warning(f"Result {result.task_id}: Invalid exit_code type")
            return False

        if exit_code != 0:
            logger.warning(f"Result {result.task_id}: Exit code {exit_code} != 0 but success=True")
            return False

        return True

    async def set_working_directory(self, path: str) -> bool:
        """
        Set the working directory for subsequent commands.

        Args:
            path: Directory path

        Returns:
            True if successful
        """
        try:
            new_path = Path(path).expanduser().resolve()
            if not new_path.exists():
                logger.warning(f"Directory does not exist: {path}")
                return False

            self.working_directory = new_path
            logger.info(f"Changed working directory to {new_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to set working directory: {e}")
            return False

    def get_working_directory(self) -> str:
        """Get the current working directory."""
        return str(self.working_directory)
