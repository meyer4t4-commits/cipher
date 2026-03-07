"""
Deployment Agent - Git, Docker, Railway deployments, and environment management.
ALL REAL OPERATIONS — subprocess calls, real API requests. No mock data.
REQUIRES APPROVAL FOR: pushes to main, deployments, env changes.
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Any, Optional

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


async def _run_command(cmd: list[str], cwd: Optional[str] = None, timeout: int = 120) -> dict:
    """
    Run a shell command and return structured output.
    This is the real deal — actual subprocess execution.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )

        return {
            "returncode": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace").strip(),
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
            "success": process.returncode == 0,
        }
    except asyncio.TimeoutError:
        process.kill()
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "success": False,
        }
    except FileNotFoundError:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command not found: {cmd[0]}",
            "success": False,
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False,
        }


class DeployAgent(BaseAgent):
    """Manage deployments and infrastructure — real operations only."""

    def __init__(self):
        """Initialize the deploy agent."""
        super().__init__(
            name="deploy_agent",
            description="Git operations, Docker, and deployment management",
            version="2.0.0",
            capabilities=[
                AgentCapability(
                    name="git_status",
                    description="Check git repository status",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="git_commit",
                    description="Commit changes to git",
                    category="execution",
                    requires_approval=False,
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="git_push",
                    description="Push to remote repository",
                    category="execution",
                    requires_approval=True,
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="docker_build",
                    description="Build Docker image",
                    category="execution",
                    timeout_seconds=300,
                ),
                AgentCapability(
                    name="docker_run",
                    description="Run Docker container",
                    category="execution",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="railway_deploy",
                    description="Deploy to Railway",
                    category="execution",
                    requires_approval=True,
                    timeout_seconds=300,
                ),
                AgentCapability(
                    name="set_environment",
                    description="Set environment variables",
                    category="execution",
                    requires_approval=True,
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="health_check",
                    description="Check service health",
                    category="data",
                    timeout_seconds=15,
                ),
                AgentCapability(
                    name="get_logs",
                    description="Retrieve service logs",
                    category="data",
                    timeout_seconds=10,
                ),
            ],
        )

    def requires_approval_for(self, instruction: str) -> bool:
        """Check if operation requires approval."""
        dangerous_ops = ["push", "deploy", "environment", "set_env"]
        return any(op in instruction.lower() for op in dangerous_ops)

    async def validate(self, task: AgentTask) -> bool:
        """Validate deploy task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation", "status")

        # Push and deploy operations require approval
        if operation in ("git_push", "railway_deploy", "set_environment"):
            if not task.approved_at:
                logger.warning(f"Task {task.task_id}: Operation '{operation}' requires approval")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute deployment operation."""
        operation = task.params.get("operation", "status")

        try:
            if operation == "git_status":
                return await self._git_status(task)
            elif operation == "git_commit":
                return await self._git_commit(task)
            elif operation == "git_push":
                return await self._git_push(task)
            elif operation == "docker_build":
                return await self._docker_build(task)
            elif operation == "docker_run":
                return await self._docker_run(task)
            elif operation == "railway_deploy":
                return await self._railway_deploy(task)
            elif operation == "set_environment":
                return await self._set_environment(task)
            elif operation == "health_check":
                return await self._health_check(task)
            elif operation == "get_logs":
                return await self._get_logs(task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Deploy operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _git_status(self, task: AgentTask) -> AgentResult:
        """Check git status — real subprocess call."""
        cwd = task.params.get("cwd")

        # Get branch name
        branch_result = await _run_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd
        )
        branch = branch_result["stdout"] if branch_result["success"] else "unknown"

        # Get status (porcelain for machine-readable output)
        status_result = await _run_command(
            ["git", "status", "--porcelain"], cwd=cwd
        )

        modified = []
        untracked = []
        if status_result["success"] and status_result["stdout"]:
            for line in status_result["stdout"].split("\n"):
                if line.startswith("??"):
                    untracked.append(line[3:])
                elif line.strip():
                    modified.append(line.strip())

        # Get ahead/behind counts
        ab_result = await _run_command(
            ["git", "rev-list", "--left-right", "--count", f"HEAD...@{{upstream}}"],
            cwd=cwd,
        )
        ahead, behind = 0, 0
        if ab_result["success"] and ab_result["stdout"]:
            parts = ab_result["stdout"].split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])

        output = {
            "operation": "git_status",
            "status": "clean" if not modified and not untracked else "dirty",
            "branch": branch,
            "ahead": ahead,
            "behind": behind,
            "modified_files": modified,
            "untracked_files": untracked,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _git_commit(self, task: AgentTask) -> AgentResult:
        """Create a git commit — real subprocess call."""
        message = task.params.get("message", "Auto-commit by Cipher")
        files = task.params.get("files", [])
        cwd = task.params.get("cwd")

        # Stage files
        if files:
            add_result = await _run_command(["git", "add"] + files, cwd=cwd)
        else:
            add_result = await _run_command(["git", "add", "-A"], cwd=cwd)

        if not add_result["success"]:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"git add failed: {add_result['stderr']}",
            )

        # Commit
        commit_result = await _run_command(
            ["git", "commit", "-m", message], cwd=cwd
        )

        if not commit_result["success"]:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"git commit failed: {commit_result['stderr']}",
            )

        # Get the commit hash
        hash_result = await _run_command(
            ["git", "rev-parse", "--short", "HEAD"], cwd=cwd
        )

        output = {
            "operation": "git_commit",
            "message": message,
            "files_staged": len(files) if files else "all",
            "commit_hash": hash_result["stdout"] if hash_result["success"] else "unknown",
            "status": "committed",
            "full_output": commit_result["stdout"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _git_push(self, task: AgentTask) -> AgentResult:
        """Push to remote repository — real subprocess call."""
        branch = task.params.get("branch", "main")
        remote = task.params.get("remote", "origin")
        cwd = task.params.get("cwd")

        result = await _run_command(
            ["git", "push", remote, branch], cwd=cwd, timeout=60
        )

        if not result["success"]:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"git push failed: {result['stderr']}",
            )

        output = {
            "operation": "git_push",
            "branch": branch,
            "remote": remote,
            "status": "pushed",
            "full_output": result["stdout"] or result["stderr"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _docker_build(self, task: AgentTask) -> AgentResult:
        """Build Docker image — real subprocess call."""
        dockerfile = task.params.get("dockerfile", "Dockerfile")
        tag = task.params.get("tag", "cipher:latest")
        context = task.params.get("context", ".")
        cwd = task.params.get("cwd")

        start = time.time()
        result = await _run_command(
            ["docker", "build", "-f", dockerfile, "-t", tag, context],
            cwd=cwd,
            timeout=300,
        )
        elapsed = time.time() - start

        if not result["success"]:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"docker build failed: {result['stderr'][-500:]}",
            )

        # Get image ID
        inspect = await _run_command(
            ["docker", "inspect", "--format", "{{.Id}}", tag], cwd=cwd
        )

        output = {
            "operation": "docker_build",
            "dockerfile": dockerfile,
            "tag": tag,
            "status": "built",
            "image_id": inspect["stdout"][:20] if inspect["success"] else "unknown",
            "build_time_seconds": round(elapsed, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _docker_run(self, task: AgentTask) -> AgentResult:
        """Run Docker container — real subprocess call."""
        image = task.params.get("image", "cipher:latest")
        container_name = task.params.get("name", "cipher-app")
        ports = task.params.get("ports", {})
        env = task.params.get("env", {})
        detach = task.params.get("detach", True)
        cwd = task.params.get("cwd")

        cmd = ["docker", "run"]
        if detach:
            cmd.append("-d")
        cmd.extend(["--name", container_name])

        for host_port, container_port in ports.items():
            cmd.extend(["-p", f"{host_port}:{container_port}"])

        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.append(image)

        result = await _run_command(cmd, cwd=cwd, timeout=60)

        if not result["success"]:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"docker run failed: {result['stderr']}",
            )

        container_id = result["stdout"][:12] if result["stdout"] else "unknown"

        output = {
            "operation": "docker_run",
            "image": image,
            "container_name": container_name,
            "container_id": container_id,
            "status": "running",
            "ports": ports,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _railway_deploy(self, task: AgentTask) -> AgentResult:
        """Deploy to Railway — real CLI call."""
        cwd = task.params.get("cwd")
        service_name = task.params.get("service_name", "cipher")

        # Check if Railway CLI is installed
        check = await _run_command(["railway", "version"])
        if not check["success"]:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Railway CLI not installed. Install with: npm i -g @railway/cli",
            )

        # Deploy using Railway CLI
        start = time.time()
        result = await _run_command(
            ["railway", "up", "--detach"],
            cwd=cwd,
            timeout=300,
        )
        elapsed = time.time() - start

        if not result["success"]:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Railway deploy failed: {result['stderr']}",
            )

        output = {
            "operation": "railway_deploy",
            "service_name": service_name,
            "status": "deploying",
            "deploy_time_seconds": round(elapsed, 1),
            "full_output": result["stdout"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _set_environment(self, task: AgentTask) -> AgentResult:
        """Set environment variables — writes to real .env file or Railway."""
        env_vars = task.params.get("env_vars", {})
        scope = task.params.get("scope", "local")  # local or railway
        cwd = task.params.get("cwd")

        if scope == "railway":
            # Set on Railway via CLI
            results = []
            for key, value in env_vars.items():
                r = await _run_command(
                    ["railway", "variables", "set", f"{key}={value}"],
                    cwd=cwd,
                )
                results.append({"key": key, "success": r["success"]})

            output = {
                "operation": "set_environment",
                "scope": "railway",
                "results": results,
                "variables_set": sum(1 for r in results if r["success"]),
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            # Write to local .env file
            env_file = os.path.join(cwd, ".env") if cwd else ".env"
            try:
                # Read existing .env
                existing = {}
                if os.path.exists(env_file):
                    with open(env_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                existing[k.strip()] = v.strip()

                # Update with new vars
                existing.update(env_vars)

                # Write back
                with open(env_file, "w") as f:
                    for k, v in existing.items():
                        f.write(f"{k}={v}\n")

                output = {
                    "operation": "set_environment",
                    "scope": "local",
                    "env_file": env_file,
                    "variables_set": len(env_vars),
                    "variables": list(env_vars.keys()),
                    "status": "set",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Failed to write .env: {e}",
                )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _health_check(self, task: AgentTask) -> AgentResult:
        """Check service health — real HTTP request."""
        service_url = task.params.get("url", "http://localhost:8000")
        timeout_seconds = task.params.get("timeout", 5)

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                start = time.time()
                response = await client.get(f"{service_url}/ping")
                latency = (time.time() - start) * 1000

            output = {
                "operation": "health_check",
                "url": service_url,
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response_time_ms": round(latency, 1),
                "response_body": response.json() if response.status_code == 200 else response.text[:200],
                "timestamp": datetime.utcnow().isoformat(),
            }
        except httpx.ConnectError:
            output = {
                "operation": "health_check",
                "url": service_url,
                "status": "unreachable",
                "error": "Connection refused — service may not be running",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except httpx.TimeoutException:
            output = {
                "operation": "health_check",
                "url": service_url,
                "status": "timeout",
                "error": f"No response within {timeout_seconds}s",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            output = {
                "operation": "health_check",
                "url": service_url,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=output.get("status") == "healthy",
            output=output,
        )

    async def _get_logs(self, task: AgentTask) -> AgentResult:
        """Get service logs — real Docker or Railway logs."""
        service_name = task.params.get("service_name", "cipher-app")
        lines = task.params.get("lines", 100)
        source = task.params.get("source", "docker")  # docker or railway
        cwd = task.params.get("cwd")

        if source == "railway":
            result = await _run_command(
                ["railway", "logs", "--lines", str(lines)],
                cwd=cwd,
                timeout=15,
            )
        else:
            result = await _run_command(
                ["docker", "logs", "--tail", str(lines), service_name],
                timeout=15,
            )

        if not result["success"]:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Failed to get logs: {result['stderr']}",
            )

        log_lines = result["stdout"].split("\n") if result["stdout"] else []

        output = {
            "operation": "get_logs",
            "service_name": service_name,
            "source": source,
            "lines_returned": len(log_lines),
            "logs": log_lines[-lines:],  # Trim to requested count
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def verify(self, result: AgentResult) -> bool:
        """Verify deployment result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        if "operation" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing 'operation'")
            return False

        return True
