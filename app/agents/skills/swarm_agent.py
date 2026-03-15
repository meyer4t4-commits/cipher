"""
Swarm Intelligence Agent — Multi-perspective prediction & knowledge graph agent.

Combines all MiroFish-inspired capabilities:
1. Prediction Swarm: Multi-agent debate with consensus scoring
2. Knowledge Graph: Entity/relationship extraction and querying
3. Agent Memory: Per-agent long-term memory management
4. Multi-Perspective Analysis: Same question analyzed from multiple stances

This is the "brain" agent that orchestrates Cipher's collective intelligence.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class SwarmAgent(BaseAgent):
    """
    Swarm Intelligence Agent — orchestrates multi-agent prediction,
    knowledge graph queries, and collective analysis.
    """

    name = "swarm_agent"
    description = "Swarm intelligence — multi-agent prediction, knowledge graph, and collective analysis"
    version = "1.0.0"

    def __init__(self):
        super().__init__(
            name="swarm_agent",
            description="Swarm intelligence — multi-agent prediction, knowledge graph, and collective analysis",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="predict",
                    description="Run a prediction swarm with multiple perspectives on a scenario",
                    category="intelligence",
                    requires_approval=False,
                    timeout_seconds=180,
                ),
                AgentCapability(
                    name="graph_query",
                    description="Query the knowledge graph for entity relationships",
                    category="intelligence",
                    requires_approval=False,
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="graph_extract",
                    description="Extract entities and relationships from text into the knowledge graph",
                    category="intelligence",
                    requires_approval=False,
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="memory_recall",
                    description="Recall memories for a specific agent",
                    category="intelligence",
                    requires_approval=False,
                    timeout_seconds=15,
                ),
                AgentCapability(
                    name="memory_consolidate",
                    description="Consolidate agent memories into patterns",
                    category="intelligence",
                    requires_approval=False,
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="graph_stats",
                    description="Get knowledge graph statistics",
                    category="intelligence",
                    requires_approval=False,
                    timeout_seconds=10,
                ),
            ],
        )

    async def validate(self, task: AgentTask) -> bool:
        operation = task.params.get("operation", "")
        valid = {"predict", "graph_query", "graph_extract", "memory_recall", "memory_consolidate", "graph_stats"}
        if operation not in valid:
            logger.warning(f"[swarm_agent] Unknown operation '{operation}'")
            return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        operation = task.params.get("operation", "")
        try:
            if operation == "predict":
                output = await self._predict(task)
            elif operation == "graph_query":
                output = await self._graph_query(task)
            elif operation == "graph_extract":
                output = await self._graph_extract(task)
            elif operation == "memory_recall":
                output = await self._memory_recall(task)
            elif operation == "memory_consolidate":
                output = await self._memory_consolidate(task)
            elif operation == "graph_stats":
                output = await self._graph_stats(task)
            else:
                output = {"error": f"Unknown operation: {operation}"}

            success = "error" not in output
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=success,
                output=output,
                error=output.get("error") if isinstance(output, dict) else None,
            )
        except Exception as e:
            logger.error(f"[swarm_agent] Execution failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def verify(self, result: AgentResult) -> bool:
        return result.success and result.output is not None

    # ── Operations ──────────────────────────────────────────────────

    async def _predict(self, task: AgentTask) -> dict:
        """Run a prediction swarm."""
        from app.services.swarm import get_prediction_swarm

        scenario = task.params.get("scenario") or task.instruction
        agents = task.params.get("agents", ["research_agent", "synthesis_agent"])
        stances = task.params.get("stances")

        swarm = get_prediction_swarm()
        result = await swarm.predict(
            scenario=scenario,
            agents=agents,
            stances=stances,
            timeout=task.timeout_seconds,
        )

        # Store in knowledge graph
        try:
            from app.services.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            kg.add_entity(
                name=f"Prediction: {scenario[:50]}",
                entity_type="event",
                properties={
                    "confidence": result.confidence,
                    "risk_level": result.risk_level,
                    "recommendation": result.recommendation,
                },
                source_agent="swarm_agent",
            )
        except Exception:
            pass

        return result.to_dict()

    async def _graph_query(self, task: AgentTask) -> dict:
        """Query the knowledge graph."""
        from app.services.knowledge_graph import get_knowledge_graph

        kg = get_knowledge_graph()
        entity_name = task.params.get("entity")
        search_query = task.params.get("query", "")
        relation_type = task.params.get("relation_type")

        if entity_name:
            entity = kg.get_entity(entity_name)
            if not entity:
                return {"error": f"Entity '{entity_name}' not found"}

            neighbors = kg.get_neighbors(entity_name, relation_type)
            return {
                "entity": entity.to_dict(),
                "connections": neighbors,
                "total_connections": len(neighbors),
            }
        elif search_query:
            results = kg.search_entities(search_query)
            return {
                "query": search_query,
                "results": [e.to_dict() for e in results],
                "total": len(results),
            }

        # Find path between two entities
        source = task.params.get("source")
        target = task.params.get("target")
        if source and target:
            path = kg.find_path(source, target)
            return {"source": source, "target": target, "path": path}

        return {"error": "Provide 'entity', 'query', or 'source'+'target'"}

    async def _graph_extract(self, task: AgentTask) -> dict:
        """Extract entities/relations from text into knowledge graph."""
        from app.services.knowledge_graph import get_knowledge_graph

        kg = get_knowledge_graph()
        text = task.params.get("text") or task.instruction

        result = await kg.extract_from_text(text, source_agent="swarm_agent")
        stats = kg.get_stats()
        return {**result, "graph_stats": stats}

    async def _memory_recall(self, task: AgentTask) -> dict:
        """Recall memories for a specific agent."""
        from app.services.agent_memory import AgentMemoryStore

        agent_name = task.params.get("agent_name", "swarm_agent")
        query = task.params.get("query", task.instruction)
        n_results = task.params.get("n_results", 5)

        memories = await AgentMemoryStore.recall(agent_name, query, n_results)
        summary = await AgentMemoryStore.get_agent_summary(agent_name)

        return {
            "agent_name": agent_name,
            "memories": memories,
            "summary": summary,
        }

    async def _memory_consolidate(self, task: AgentTask) -> dict:
        """Consolidate agent memories into patterns."""
        from app.services.agent_memory import AgentMemoryStore

        agent_name = task.params.get("agent_name")
        if agent_name:
            count = await AgentMemoryStore.consolidate(agent_name)
            return {"agent_name": agent_name, "patterns_created": count}

        # Consolidate all agents
        all_stats = await AgentMemoryStore.get_all_agents_stats()
        total = 0
        results = []
        for stat in all_stats:
            count = await AgentMemoryStore.consolidate(stat["agent_name"])
            total += count
            results.append({"agent": stat["agent_name"], "patterns": count})

        return {"agents_consolidated": len(results), "total_patterns": total, "details": results}

    async def _graph_stats(self, task: AgentTask) -> dict:
        """Get knowledge graph statistics."""
        from app.services.knowledge_graph import get_knowledge_graph
        from app.services.agent_memory import AgentMemoryStore

        kg = get_knowledge_graph()
        graph_stats = kg.get_stats()
        memory_stats = await AgentMemoryStore.get_all_agents_stats()

        return {
            "knowledge_graph": graph_stats,
            "agent_memories": memory_stats,
        }
