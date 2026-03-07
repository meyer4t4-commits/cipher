"""
Tests for the BaseAgent class — validation, execution lifecycle, timeout handling.
"""

import asyncio
import pytest
from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentStatus, AgentTask


class SuccessAgent(BaseAgent):
    """Agent that always succeeds."""

    async def execute(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output="done",
            execution_time_ms=0,
        )

    async def verify(self, result: AgentResult) -> bool:
        return True


class FailAgent(BaseAgent):
    """Agent that always fails."""

    async def execute(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=False,
            error="Intentional failure",
            execution_time_ms=0,
        )

    async def verify(self, result: AgentResult) -> bool:
        return False


class ExceptionAgent(BaseAgent):
    """Agent that throws an exception."""

    async def execute(self, task: AgentTask) -> AgentResult:
        raise RuntimeError("Something broke")

    async def verify(self, result: AgentResult) -> bool:
        return True


class SlowAgent(BaseAgent):
    """Agent that takes too long."""

    async def execute(self, task: AgentTask) -> AgentResult:
        await asyncio.sleep(10)
        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output="slow done",
            execution_time_ms=0,
        )

    async def verify(self, result: AgentResult) -> bool:
        return True


class VerificationFailAgent(BaseAgent):
    """Agent that executes successfully but fails verification."""

    async def execute(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output="suspicious output",
            execution_time_ms=0,
        )

    async def verify(self, result: AgentResult) -> bool:
        return False


def make_task(**kwargs):
    defaults = {"agent_name": "test", "instruction": "do something"}
    defaults.update(kwargs)
    return AgentTask(**defaults)


class TestBaseAgentInit:
    def test_initialization(self):
        agent = SuccessAgent(name="test", description="A test agent")
        assert agent.name == "test"
        assert agent.description == "A test agent"
        assert agent.version == "1.0.0"
        assert agent.capabilities == []
        assert agent.status == AgentStatus.PENDING

    def test_with_capabilities(self):
        caps = [
            AgentCapability(name="run", description="Run things", category="exec"),
        ]
        agent = SuccessAgent(name="test", description="d", capabilities=caps)
        assert len(agent.capabilities) == 1
        assert agent.get_capability("run") is not None
        assert agent.get_capability("nonexistent") is None

    def test_str_repr(self):
        agent = SuccessAgent(name="myagent", description="desc", version="2.0")
        assert "myagent" in str(agent)
        assert "2.0" in str(agent)
        assert "SuccessAgent" in repr(agent)


class TestBaseAgentValidation:
    @pytest.mark.asyncio
    async def test_valid_task(self):
        agent = SuccessAgent(name="test", description="d")
        task = make_task()
        assert await agent.validate(task) is True

    @pytest.mark.asyncio
    async def test_empty_instruction(self):
        agent = SuccessAgent(name="test", description="d")
        task = make_task(instruction="   ")
        assert await agent.validate(task) is False

    @pytest.mark.asyncio
    async def test_empty_agent_name(self):
        agent = SuccessAgent(name="test", description="d")
        task = make_task(agent_name="")
        assert await agent.validate(task) is False

    @pytest.mark.asyncio
    async def test_invalid_timeout(self):
        agent = SuccessAgent(name="test", description="d")
        task = make_task(timeout_seconds=0)
        assert await agent.validate(task) is False


class TestBaseAgentRun:
    @pytest.mark.asyncio
    async def test_successful_run(self):
        agent = SuccessAgent(name="test", description="d")
        result = await agent.run(make_task())
        assert result.success is True
        assert result.verified is True
        assert result.execution_time_ms > 0
        assert agent.status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failed_run(self):
        agent = FailAgent(name="test", description="d")
        result = await agent.run(make_task())
        assert result.success is False
        assert result.verified is False

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        agent = ExceptionAgent(name="test", description="d")
        result = await agent.run(make_task())
        assert result.success is False
        assert "Something broke" in result.error
        assert agent.status == AgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        agent = SlowAgent(name="test", description="d")
        result = await agent.run(make_task(timeout_seconds=1))
        assert result.success is False
        assert "timed out" in result.error.lower()
        assert agent.status == AgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_validation_failure(self):
        agent = SuccessAgent(name="test", description="d")
        result = await agent.run(make_task(instruction=""))
        assert result.success is False
        assert "validation failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_verification_failure(self):
        agent = VerificationFailAgent(name="test", description="d")
        result = await agent.run(make_task())
        assert result.success is True  # Execute succeeded
        assert result.verified is False  # But verification failed

    @pytest.mark.asyncio
    async def test_requires_approval_check(self):
        agent = SuccessAgent(name="test", description="d")
        assert agent.requires_approval_for("anything") is False
