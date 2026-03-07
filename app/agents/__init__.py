"""
Agent Framework - Agentic execution system for Cipher.
Manages agent registration, task execution, and result verification.
"""

from app.agents.base import BaseAgent
from app.agents.executor import TaskExecutor, get_executor
from app.agents.models import (
    AgentCapability,
    AgentResult,
    AgentStatus,
    AgentTask,
    AgentTaskRequest,
    ApprovalRequest,
)
from app.agents.registry import AgentRegistry, get_registry

__all__ = [
    # Classes
    "BaseAgent",
    "TaskExecutor",
    "AgentRegistry",
    # Models
    "AgentTask",
    "AgentResult",
    "AgentCapability",
    "AgentStatus",
    "AgentTaskRequest",
    "ApprovalRequest",
    # Functions
    "get_executor",
    "get_registry",
]
