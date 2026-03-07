"""
Tests for agent framework Pydantic models.
"""

import pytest
from datetime import datetime
from app.agents.models import (
    AgentCapability,
    AgentResult,
    AgentStatus,
    AgentTask,
    AgentTaskRequest,
    ApprovalRequest,
    ExecutionHistoryEntry,
)


class TestAgentStatus:
    def test_status_values(self):
        assert AgentStatus.PENDING == "pending"
        assert AgentStatus.AWAITING_APPROVAL == "awaiting_approval"
        assert AgentStatus.RUNNING == "running"
        assert AgentStatus.VERIFYING == "verifying"
        assert AgentStatus.COMPLETED == "completed"
        assert AgentStatus.FAILED == "failed"

    def test_status_is_string(self):
        assert isinstance(AgentStatus.PENDING, str)


class TestAgentCapability:
    def test_basic_capability(self):
        cap = AgentCapability(
            name="execute_shell",
            description="Run shell commands",
            category="execution",
        )
        assert cap.name == "execute_shell"
        assert cap.requires_approval is False
        assert cap.timeout_seconds == 30

    def test_approval_required(self):
        cap = AgentCapability(
            name="place_trade",
            description="Place a stock trade",
            category="trading",
            requires_approval=True,
            timeout_seconds=60,
        )
        assert cap.requires_approval is True
        assert cap.timeout_seconds == 60


class TestAgentTask:
    def test_default_task(self):
        task = AgentTask(
            agent_name="shell",
            instruction="List files",
        )
        assert task.agent_name == "shell"
        assert task.instruction == "List files"
        assert task.timeout_seconds == 30
        assert task.requires_approval is False
        assert task.priority == 0
        assert task.task_id  # auto-generated
        assert isinstance(task.requested_at, datetime)

    def test_task_with_params(self):
        task = AgentTask(
            agent_name="trading",
            instruction="Buy 10 shares of AAPL",
            params={"symbol": "AAPL", "quantity": 10, "action": "buy"},
            requires_approval=True,
            timeout_seconds=60,
        )
        assert task.params["symbol"] == "AAPL"
        assert task.requires_approval is True

    def test_task_ids_are_unique(self):
        t1 = AgentTask(agent_name="test", instruction="a")
        t2 = AgentTask(agent_name="test", instruction="b")
        assert t1.task_id != t2.task_id


class TestAgentResult:
    def test_success_result(self):
        result = AgentResult(
            task_id="abc123",
            agent_name="shell",
            success=True,
            output="file1.txt\nfile2.txt\n",
            execution_time_ms=125.5,
            verified=True,
        )
        assert result.success is True
        assert result.error is None
        assert result.verified is True

    def test_failure_result(self):
        result = AgentResult(
            task_id="abc123",
            agent_name="shell",
            success=False,
            error="Command not found",
            execution_time_ms=10.0,
            verified=False,
        )
        assert result.success is False
        assert result.error == "Command not found"


class TestAgentTaskRequest:
    def test_minimal_request(self):
        req = AgentTaskRequest(
            agent_name="web",
            instruction="Fetch Google homepage",
        )
        assert req.timeout_seconds == 30
        assert req.params == {}

    def test_request_timeout_bounds(self):
        with pytest.raises(Exception):
            AgentTaskRequest(
                agent_name="web",
                instruction="test",
                timeout_seconds=0,  # Below minimum
            )

        with pytest.raises(Exception):
            AgentTaskRequest(
                agent_name="web",
                instruction="test",
                timeout_seconds=7200,  # Above maximum
            )


class TestApprovalRequest:
    def test_basic_approval(self):
        req = ApprovalRequest(approved_by="mark")
        assert req.approved_by == "mark"
        assert req.notes is None

    def test_approval_with_notes(self):
        req = ApprovalRequest(approved_by="mark", notes="Go ahead")
        assert req.notes == "Go ahead"


class TestExecutionHistoryEntry:
    def test_entry_creation(self):
        entry = ExecutionHistoryEntry(
            task_id="abc123",
            agent_name="shell",
            instruction="ls -la",
            status=AgentStatus.COMPLETED,
            success=True,
            execution_time_ms=50.0,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            error=None,
        )
        assert entry.status == AgentStatus.COMPLETED
        assert entry.success is True
