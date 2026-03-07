"""
Code Execution Agent - Execute Python and JavaScript code safely.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class CodeAgent(BaseAgent):
    """Execute Python and JavaScript code in sandboxed subprocesses."""

    def __init__(self, sandbox_dir: str = "./data/sandbox"):
        """Initialize the code agent."""
        super().__init__(
            name="code_agent",
            description="Execute Python and JavaScript code safely",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="execute_python",
                    description="Execute Python code",
                    category="execution",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="execute_javascript",
                    description="Execute JavaScript code",
                    category="execution",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="install_package",
                    description="Install Python packages via pip",
                    category="execution",
                    timeout_seconds=120,
                ),
            ],
        )
        self.sandbox_dir = Path(sandbox_dir)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    async def validate(self, task: AgentTask) -> bool:
        """Validate the code execution task."""
        if not await super().validate(task):
            return False

        # Check for code parameter
        if "code" not in task.params and "package" not in task.params:
            logger.warning(f"Task {task.task_id}: Missing 'code' or 'package' parameter")
            return False

        # Check language for code execution
        if "code" in task.params:
            language = task.params.get("language", "python").lower()
            if language not in ("python", "javascript", "js"):
                logger.warning(f"Task {task.task_id}: Unsupported language {language}")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute code in a sandbox."""
        if "package" in task.params:
            return await self._execute_pip_install(task)
        else:
            return await self._execute_code(task)

    async def _execute_code(self, task: AgentTask) -> AgentResult:
        """Execute Python or JavaScript code."""
        code = task.params["code"]
        language = task.params.get("language", "python").lower()

        if language in ("javascript", "js"):
            return await self._execute_javascript(task, code)
        else:
            return await self._execute_python(task, code)

    async def _execute_python(self, task: AgentTask, code: str) -> AgentResult:
        """Execute Python code."""
        logger.debug(f"[{self.name}] Executing Python code")

        # Create temp file with code
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            dir=self.sandbox_dir,
            delete=False,
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            process = await asyncio.create_subprocess_exec(
                "python3",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=task.timeout_seconds,
            )

            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            success = process.returncode == 0

            output = {
                "language": "python",
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": process.returncode,
            }

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=success,
                output=output,
                error=stderr_str if not success else None,
            )

        except asyncio.TimeoutError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Python execution timed out after {task.timeout_seconds}s",
            )
        except Exception as e:
            logger.error(f"[{self.name}] Python execution failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )
        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    async def _execute_javascript(self, task: AgentTask, code: str) -> AgentResult:
        """Execute JavaScript code via Node.js."""
        logger.debug(f"[{self.name}] Executing JavaScript code")

        # Check if node is available
        try:
            await asyncio.create_subprocess_exec("which", "node")
        except FileNotFoundError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Node.js is not installed",
            )

        # Create temp file with code
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".js",
            dir=self.sandbox_dir,
            delete=False,
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            process = await asyncio.create_subprocess_exec(
                "node",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=task.timeout_seconds,
            )

            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            success = process.returncode == 0

            output = {
                "language": "javascript",
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": process.returncode,
            }

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=success,
                output=output,
                error=stderr_str if not success else None,
            )

        except asyncio.TimeoutError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"JavaScript execution timed out after {task.timeout_seconds}s",
            )
        except Exception as e:
            logger.error(f"[{self.name}] JavaScript execution failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )
        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    async def _execute_pip_install(self, task: AgentTask) -> AgentResult:
        """Install Python package via pip."""
        package = task.params["package"]

        logger.debug(f"[{self.name}] Installing package: {package}")

        try:
            process = await asyncio.create_subprocess_exec(
                "pip",
                "install",
                package,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            success = process.returncode == 0

            output = {
                "package": package,
                "stdout": stdout_str[-500:],  # Last 500 chars
                "stderr": stderr_str[-500:],
                "exit_code": process.returncode,
            }

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=success,
                output=output,
                error=f"pip install failed: {stderr_str[-200:]}" if not success else None,
            )

        except Exception as e:
            logger.error(f"[{self.name}] Package install failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def verify(self, result: AgentResult) -> bool:
        """Verify code execution result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        # Check required fields
        required_fields = ["exit_code"]
        for field in required_fields:
            if field not in result.output:
                logger.warning(f"Result {result.task_id}: Missing field '{field}'")
                return False

        # Verify exit code matches success flag
        exit_code = result.output.get("exit_code")
        if not isinstance(exit_code, int):
            logger.warning(f"Result {result.task_id}: Invalid exit_code type")
            return False

        expected_success = exit_code == 0
        if result.success != expected_success:
            logger.warning(
                f"Result {result.task_id}: exit_code {exit_code} but success={result.success}"
            )
            return False

        # Should have either stdout or stderr or both
        has_output = "stdout" in result.output or "stderr" in result.output
        if not has_output:
            logger.warning(f"Result {result.task_id}: No stdout/stderr captured")
            return False

        return True
