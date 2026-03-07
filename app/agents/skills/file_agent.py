"""
File System Agent - Read, write, search, and manage files safely.
Sandboxed to allowed directories only.
"""

import glob
from pathlib import Path
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class FileAgent(BaseAgent):
    """Manage files with sandboxed directory access."""

    def __init__(self, allowed_dirs: Optional[list[str]] = None):
        """
        Initialize the file agent.

        Args:
            allowed_dirs: List of allowed directories. Defaults to current project dir.
        """
        super().__init__(
            name="file_agent",
            description="File system operations within sandboxed directories",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="read_file",
                    description="Read file contents",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="write_file",
                    description="Write content to a file",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="create_file",
                    description="Create a new file",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="delete_file",
                    description="Delete a file",
                    category="data",
                    requires_approval=True,
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="list_directory",
                    description="List files in a directory",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="search_files",
                    description="Search for files by pattern or content",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="get_file_info",
                    description="Get file metadata (size, modified, type)",
                    category="data",
                    timeout_seconds=10,
                ),
            ],
        )

        # Default to project root and subdirs
        if allowed_dirs is None:
            allowed_dirs = [
                str(Path.cwd()),
                str(Path.cwd() / "app"),
                str(Path.cwd() / "data"),
            ]

        self.allowed_dirs = [Path(d).resolve() for d in allowed_dirs]
        logger.info(f"FileAgent initialized with allowed dirs: {self.allowed_dirs}")

    def _is_path_allowed(self, path: str) -> bool:
        """
        Check if a path is within allowed directories.

        Args:
            path: Path to check

        Returns:
            True if allowed
        """
        try:
            resolved = Path(path).resolve()
            for allowed_dir in self.allowed_dirs:
                if resolved.is_relative_to(allowed_dir):
                    return True
            logger.warning(f"Path not allowed: {path}")
            return False
        except Exception as e:
            logger.error(f"Error checking path permissions: {e}")
            return False

    async def validate(self, task: AgentTask) -> bool:
        """Validate the file operation task."""
        if not await super().validate(task):
            return False

        # Check for path parameter
        if "path" not in task.params:
            logger.warning(f"Task {task.task_id}: Missing 'path' parameter")
            return False

        path = task.params["path"]
        if not isinstance(path, str):
            logger.warning(f"Task {task.task_id}: Invalid path parameter")
            return False

        # Check path is allowed
        if not self._is_path_allowed(path):
            logger.warning(f"Task {task.task_id}: Path not in allowed directories")
            return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a file operation."""
        # Support both "operation" and "action" param keys
        operation = task.params.get("operation") or task.params.get("action", "read")

        # Auto-detect: if path is a directory and operation is "read", switch to "list"
        path = Path(task.params.get("path", "."))
        if operation == "read" and path.is_dir():
            operation = "list"

        if operation == "read":
            return await self._read_file(task)
        elif operation == "write":
            return await self._write_file(task)
        elif operation == "create":
            return await self._create_file(task)
        elif operation == "delete":
            return await self._delete_file(task)
        elif operation == "list":
            return await self._list_directory(task)
        elif operation == "search":
            return await self._search_files(task)
        elif operation == "info":
            return await self._get_file_info(task)
        else:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Unknown operation: {operation}",
            )

    async def _read_file(self, task: AgentTask) -> AgentResult:
        """Read a file."""
        try:
            path = Path(task.params["path"])
            max_size = task.params.get("max_size", 100000)

            if not path.exists():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"File not found: {path}",
                )

            if path.is_dir():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Path is a directory: {path}",
                )

            file_size = path.stat().st_size
            if file_size > max_size:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"File too large: {file_size} > {max_size} bytes",
                )

            content = path.read_text(encoding="utf-8", errors="replace")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "path": str(path),
                    "size": file_size,
                    "content": content,
                },
            )

        except Exception as e:
            logger.error(f"Read file failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _write_file(self, task: AgentTask) -> AgentResult:
        """Write to a file."""
        try:
            path = Path(task.params["path"])
            content = task.params.get("content", "")
            append = task.params.get("append", False)

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            if append and path.exists():
                existing = path.read_text(encoding="utf-8", errors="replace")
                content = existing + content

            path.write_text(content, encoding="utf-8")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "path": str(path),
                    "bytes_written": len(content.encode("utf-8")),
                    "operation": "append" if append else "write",
                },
            )

        except Exception as e:
            logger.error(f"Write file failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _create_file(self, task: AgentTask) -> AgentResult:
        """Create a new file."""
        try:
            path = Path(task.params["path"])

            if path.exists():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"File already exists: {path}",
                )

            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={"path": str(path), "created": True},
            )

        except Exception as e:
            logger.error(f"Create file failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _delete_file(self, task: AgentTask) -> AgentResult:
        """Delete a file."""
        try:
            path = Path(task.params["path"])

            if not path.exists():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"File not found: {path}",
                )

            if path.is_dir():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Path is a directory: {path}",
                )

            path.unlink()

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={"path": str(path), "deleted": True},
            )

        except Exception as e:
            logger.error(f"Delete file failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _list_directory(self, task: AgentTask) -> AgentResult:
        """List directory contents."""
        try:
            path = Path(task.params["path"])

            if not path.exists():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Directory not found: {path}",
                )

            if not path.is_dir():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Path is not a directory: {path}",
                )

            items = []
            for item in sorted(path.iterdir()):
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "path": str(path),
                    "count": len(items),
                    "items": items,
                },
            )

        except Exception as e:
            logger.error(f"List directory failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _search_files(self, task: AgentTask) -> AgentResult:
        """Search for files by pattern or content."""
        try:
            path = Path(task.params.get("path", "."))
            pattern = task.params.get("pattern", "*")
            search_content = task.params.get("search_content")

            if not path.exists():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Path not found: {path}",
                )

            results = []

            # Glob pattern search
            if pattern != "*":
                files = glob.glob(str(path / pattern), recursive=True)
                results.extend(files)

            # Content search
            if search_content:
                for file_path in path.rglob("*"):
                    if not file_path.is_file():
                        continue

                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        if search_content in content:
                            results.append(str(file_path))
                    except Exception:
                        pass

            # Deduplicate and limit
            results = list(set(results))[:100]

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "path": str(path),
                    "pattern": pattern,
                    "count": len(results),
                    "files": results,
                },
            )

        except Exception as e:
            logger.error(f"Search files failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _get_file_info(self, task: AgentTask) -> AgentResult:
        """Get file metadata."""
        try:
            path = Path(task.params["path"])

            if not path.exists():
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"File not found: {path}",
                )

            stat = path.stat()

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "path": str(path),
                    "type": "directory" if path.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "created": stat.st_ctime,
                    "is_symlink": path.is_symlink(),
                },
            )

        except Exception as e:
            logger.error(f"Get file info failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def verify(self, result: AgentResult) -> bool:
        """Verify file operation result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        # All file operations should have a path in output
        if "path" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing 'path' in output")
            return False

        # For read operations, should have content
        if "content" in result.output:
            if not isinstance(result.output["content"], str):
                logger.warning(f"Result {result.task_id}: Content is not a string")
                return False

        return True
