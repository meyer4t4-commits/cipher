"""
Tests for the Agent Registry.
"""

import pytest
from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.agents.registry import AgentRegistry


class MockAgent(BaseAgent):
    """A simple mock agent for testing."""

    async def execute(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output="mock output",
            execution_time_ms=1.0,
        )

    async def verify(self, result: AgentResult) -> bool:
        return result.success


def make_agent(name="test_agent", caps=None):
    return MockAgent(
        name=name,
        description=f"{name} description",
        capabilities=caps or [
            AgentCapability(name="cap1", description="Cap 1", category="test"),
        ],
    )


class TestAgentRegistry:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_register_agent(self):
        agent = make_agent("shell")
        self.registry.register(agent)
        assert self.registry.is_registered("shell")
        assert self.registry.count() == 1

    def test_duplicate_registration_raises(self):
        agent = make_agent("shell")
        self.registry.register(agent)
        with pytest.raises(ValueError):
            self.registry.register(make_agent("shell"))

    def test_unregister_agent(self):
        agent = make_agent("shell")
        self.registry.register(agent)
        self.registry.unregister("shell")
        assert not self.registry.is_registered("shell")
        assert self.registry.count() == 0

    def test_unregister_nonexistent_is_noop(self):
        self.registry.unregister("nonexistent")  # Should not raise

    def test_get_agent(self):
        agent = make_agent("shell")
        self.registry.register(agent)
        retrieved = self.registry.get_agent("shell")
        assert retrieved is agent

    def test_get_nonexistent_returns_none(self):
        assert self.registry.get_agent("nonexistent") is None

    def test_list_agents(self):
        self.registry.register(make_agent("shell"))
        self.registry.register(make_agent("web"))
        self.registry.register(make_agent("code"))
        names = self.registry.list_agents()
        assert set(names) == {"shell", "web", "code"}

    def test_list_agents_detailed(self):
        caps = [
            AgentCapability(name="run", description="Run cmd", category="exec"),
            AgentCapability(name="kill", description="Kill proc", category="exec", requires_approval=True),
        ]
        self.registry.register(make_agent("shell", caps=caps))
        detailed = self.registry.list_agents_detailed()
        assert len(detailed) == 1
        assert detailed[0]["name"] == "shell"
        assert detailed[0]["capabilities_count"] == 2

    def test_get_capabilities_across_agents(self):
        self.registry.register(make_agent("shell", caps=[
            AgentCapability(name="execute", description="d1", category="exec"),
        ]))
        self.registry.register(make_agent("web", caps=[
            AgentCapability(name="fetch", description="d2", category="net"),
        ]))
        capabilities = self.registry.get_capabilities()
        assert "shell.execute" in capabilities
        assert "web.fetch" in capabilities

    def test_list_capabilities_by_category(self):
        self.registry.register(make_agent("shell", caps=[
            AgentCapability(name="execute", description="d1", category="exec"),
        ]))
        self.registry.register(make_agent("web", caps=[
            AgentCapability(name="fetch", description="d2", category="net"),
        ]))
        exec_caps = self.registry.list_capabilities_by_category("exec")
        assert len(exec_caps) == 1
        assert exec_caps[0]["agent"] == "shell"

    def test_clear(self):
        self.registry.register(make_agent("a"))
        self.registry.register(make_agent("b"))
        self.registry.clear()
        assert self.registry.count() == 0

    def test_str_repr(self):
        self.registry.register(make_agent("shell"))
        assert "1 agents" in str(self.registry)
        assert "shell" in repr(self.registry)
