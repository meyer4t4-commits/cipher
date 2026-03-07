"""
Pydantic models for the agent execution framework.
Defines task, result, capability, and status structures.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Execution status of an agent task."""
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentCapability(BaseModel):
    """Describes a capability that an agent can perform."""
    name: str = Field(..., description="Capability name (e.g., 'execute_shell')")
    description: str = Field(..., description="Human-readable description")
    category: str = Field(..., description="Category (e.g., 'execution', 'data', 'communication')")
    requires_approval: bool = Field(default=False, description="Whether this capability requires operator approval")
    timeout_seconds: int = Field(default=30, description="Default timeout for this capability")


class AgentTask(BaseModel):
    """A task to be executed by an agent."""
    task_id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex, description="Unique task ID")
    agent_name: str = Field(..., description="Name of the agent to execute (e.g., 'shell_agent')")
    instruction: str = Field(..., description="What the agent should do")
    params: dict[str, Any] = Field(default_factory=dict, description="Parameters for the task")
    timeout_seconds: int = Field(default=30, description="Task timeout in seconds")
    requires_approval: bool = Field(default=False, description="Whether this task needs operator approval")
    priority: int = Field(default=0, description="Task priority (higher = more important)")
    requested_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    approved_at: Optional[datetime] = Field(default=None, description="When task was approved")
    approved_by: Optional[str] = Field(default=None, description="Who approved the task")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc123",
                "agent_name": "shell_agent",
                "instruction": "List files in the project directory",
                "params": {"command": "ls -la ~/project"},
                "timeout_seconds": 30,
                "requires_approval": False,
                "priority": 0,
            }
        }


class AgentResult(BaseModel):
    """Result of an agent task execution."""
    task_id: str = Field(..., description="ID of the task that was executed")
    agent_name: str = Field(..., description="Name of the agent that executed it")
    success: bool = Field(..., description="Whether the task succeeded")
    output: Any = Field(default=None, description="Task output/result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: float = Field(default=0.0, description="How long the task took to execute")
    verified: bool = Field(default=False, description="Whether the output was verified by the agent")
    verification_notes: Optional[str] = Field(default=None, description="Notes from verification step")
    started_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    completed_at: datetime = Field(default_factory=lambda: datetime.utcnow())

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc123",
                "agent_name": "shell_agent",
                "success": True,
                "output": "file1.txt\nfile2.txt\n",
                "error": None,
                "execution_time_ms": 125.5,
                "verified": True,
                "verification_notes": "Output matches expected command format",
            }
        }


class AgentTaskRequest(BaseModel):
    """API request to execute a task."""
    agent_name: str = Field(..., description="Name of the agent to use")
    instruction: str = Field(..., description="What to do")
    params: dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    timeout_seconds: int = Field(default=30, ge=1, le=3600, description="Timeout in seconds")
    priority: int = Field(default=0, description="Task priority")


class ApprovalRequest(BaseModel):
    """Request to approve a pending task."""
    approved_by: str = Field(..., description="Username/ID of approver")
    notes: Optional[str] = Field(default=None, description="Optional approval notes")


class ExecutionHistoryEntry(BaseModel):
    """A single entry in the execution history."""
    task_id: str
    agent_name: str
    instruction: str
    status: AgentStatus
    success: Optional[bool]
    execution_time_ms: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
