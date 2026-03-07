"""
Agent Registry - manages registration, discovery, and routing of agents.
"""

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability
from app.core.logging import logger


class AgentRegistry:
    """
    Registry for agent discovery and routing.
    Maintains a map of agent names to agent instances.
    """

    def __init__(self):
        """Initialize the registry."""
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """
        Register an agent.

        Args:
            agent: The agent instance to register

        Raises:
            ValueError: If agent with same name already registered
        """
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")

        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} ({len(agent.capabilities)} capabilities)")

    def unregister(self, name: str) -> None:
        """
        Unregister an agent.

        Args:
            name: Agent name to unregister
        """
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Unregistered agent: {name}")

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """
        Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        """
        Get list of all registered agent names.

        Returns:
            List of agent names
        """
        return list(self._agents.keys())

    def list_agents_detailed(self) -> list[dict]:
        """
        Get detailed information about all agents.

        Returns:
            List of agent info dicts
        """
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "version": agent.version,
                "capabilities_count": len(agent.capabilities),
                "capabilities": [
                    {
                        "name": cap.name,
                        "description": cap.description,
                        "category": cap.category,
                        "requires_approval": cap.requires_approval,
                    }
                    for cap in agent.capabilities
                ],
            }
            for agent in self._agents.values()
        ]

    def get_capabilities(self) -> dict[str, AgentCapability]:
        """
        Get all capabilities across all agents.

        Returns:
            Dict mapping capability names to capability objects
        """
        capabilities = {}
        for agent in self._agents.values():
            for cap in agent.capabilities:
                key = f"{agent.name}.{cap.name}"
                capabilities[key] = cap
        return capabilities

    def list_capabilities(self) -> list[dict]:
        """
        Get list of all capabilities in human-readable format.

        Returns:
            List of capability dicts
        """
        result = []
        for agent in self._agents.values():
            for cap in agent.capabilities:
                result.append({
                    "agent": agent.name,
                    "capability": cap.name,
                    "description": cap.description,
                    "category": cap.category,
                    "requires_approval": cap.requires_approval,
                    "timeout_seconds": cap.timeout_seconds,
                })
        return result

    def list_capabilities_by_category(self, category: str) -> list[dict]:
        """
        Get capabilities by category.

        Args:
            category: Capability category to filter

        Returns:
            List of matching capabilities
        """
        result = []
        for agent in self._agents.values():
            for cap in agent.capabilities:
                if cap.category == category:
                    result.append({
                        "agent": agent.name,
                        "capability": cap.name,
                        "description": cap.description,
                        "timeout_seconds": cap.timeout_seconds,
                        "requires_approval": cap.requires_approval,
                    })
        return result

    def is_registered(self, name: str) -> bool:
        """
        Check if an agent is registered.

        Args:
            name: Agent name

        Returns:
            True if registered
        """
        return name in self._agents

    def count(self) -> int:
        """Get total number of registered agents."""
        return len(self._agents)

    def clear(self) -> None:
        """Clear all registered agents. Use with caution!"""
        self._agents.clear()
        logger.warning("Cleared all agents from registry")

    def __str__(self) -> str:
        return f"AgentRegistry({self.count()} agents)"

    def __repr__(self) -> str:
        return f"<AgentRegistry({', '.join(self.list_agents())})>"


# Global registry instance
_registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    """Get the global agent registry."""
    return _registry
