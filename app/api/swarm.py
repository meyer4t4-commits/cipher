"""
Swarm Intelligence API — prediction, knowledge graph, and agent memory endpoints.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/v1/swarm", tags=["swarm"])


# ── Request Models ──────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    scenario: str = Field(..., description="The scenario/question to analyze")
    agents: list[str] = Field(
        default=["research_agent", "synthesis_agent"],
        description="Agent names to participate in the swarm",
    )
    stances: Optional[list[str]] = Field(
        default=None,
        description="Stances to include: optimistic, conservative, adversarial, neutral",
    )
    timeout: int = Field(default=120, ge=10, le=300)


class GraphExtractRequest(BaseModel):
    text: str = Field(..., description="Text to extract entities/relations from")


class GraphQueryRequest(BaseModel):
    entity: Optional[str] = Field(default=None, description="Entity name to look up")
    query: Optional[str] = Field(default=None, description="Search query for entities")
    source: Optional[str] = Field(default=None, description="Source entity for path finding")
    target: Optional[str] = Field(default=None, description="Target entity for path finding")
    relation_type: Optional[str] = Field(default=None, description="Filter by relation type")


class MemoryRecallRequest(BaseModel):
    agent_name: str = Field(..., description="Agent to recall memories for")
    query: str = Field(..., description="Search query")
    n_results: int = Field(default=5, ge=1, le=50)


class MemoryStoreRequest(BaseModel):
    agent_name: str = Field(..., description="Agent to store memory for")
    content: str = Field(..., description="Memory content")
    memory_type: str = Field(default="observation", description="Type: observation, decision, outcome, pattern, error")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Optional[dict] = Field(default=None)


class GraphAddEntityRequest(BaseModel):
    name: str = Field(..., description="Entity name")
    entity_type: str = Field(default="concept", description="Entity type")
    properties: Optional[dict] = Field(default=None)


class GraphAddRelationRequest(BaseModel):
    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    relation_type: str = Field(default="related_to", description="Relationship type")
    properties: Optional[dict] = Field(default=None)


# ── Prediction Swarm ────────────────────────────────────────────────

@router.post("/predict")
async def run_prediction(req: PredictionRequest):
    """Run a multi-agent prediction swarm on a scenario."""
    from app.services.swarm import get_prediction_swarm

    swarm = get_prediction_swarm()
    result = await swarm.predict(
        scenario=req.scenario,
        agents=req.agents,
        stances=req.stances,
        timeout=req.timeout,
    )
    return result.to_dict()


@router.get("/predict/history")
async def prediction_history(limit: int = 10):
    """Get recent prediction swarm results."""
    from app.services.swarm import get_prediction_swarm
    return {"predictions": get_prediction_swarm().get_history(limit)}


# ── Knowledge Graph ─────────────────────────────────────────────────

@router.post("/graph/extract")
async def extract_to_graph(req: GraphExtractRequest):
    """Extract entities and relationships from text into the knowledge graph."""
    from app.services.knowledge_graph import get_knowledge_graph
    kg = get_knowledge_graph()
    result = await kg.extract_from_text(req.text, source_agent="api")
    return result


@router.post("/graph/query")
async def query_graph(req: GraphQueryRequest):
    """Query the knowledge graph for entities and relationships."""
    from app.services.knowledge_graph import get_knowledge_graph
    kg = get_knowledge_graph()

    if req.entity:
        entity = kg.get_entity(req.entity)
        if not entity:
            return {"error": f"Entity '{req.entity}' not found", "suggestions": [
                e.name for e in kg.search_entities(req.entity, limit=5)
            ]}
        neighbors = kg.get_neighbors(req.entity, req.relation_type)
        return {"entity": entity.to_dict(), "connections": neighbors}

    if req.query:
        results = kg.search_entities(req.query)
        return {"query": req.query, "results": [e.to_dict() for e in results]}

    if req.source and req.target:
        path = kg.find_path(req.source, req.target)
        return {"source": req.source, "target": req.target, "path": path}

    return {"error": "Provide entity, query, or source+target"}


@router.post("/graph/entity")
async def add_entity(req: GraphAddEntityRequest):
    """Add or update an entity in the knowledge graph."""
    from app.services.knowledge_graph import get_knowledge_graph
    kg = get_knowledge_graph()
    entity = kg.add_entity(req.name, req.entity_type, req.properties, source_agent="api")
    kg._save_state()
    return entity.to_dict()


@router.post("/graph/relation")
async def add_relation(req: GraphAddRelationRequest):
    """Add a relationship between two entities."""
    from app.services.knowledge_graph import get_knowledge_graph
    kg = get_knowledge_graph()
    rel = kg.add_relation(req.source, req.target, req.relation_type, req.properties, source_agent="api")
    kg._save_state()
    return rel.to_dict() if rel else {"error": "Failed to create relation"}


@router.get("/graph/stats")
async def graph_stats():
    """Get knowledge graph statistics."""
    from app.services.knowledge_graph import get_knowledge_graph
    return get_knowledge_graph().get_stats()


# ── Agent Memory ────────────────────────────────────────────────────

@router.post("/memory/store")
async def store_memory(req: MemoryStoreRequest):
    """Store a memory for an agent."""
    from app.services.agent_memory import AgentMemoryStore
    memory_id = await AgentMemoryStore.store(
        agent_name=req.agent_name,
        content=req.content,
        memory_type=req.memory_type,
        importance=req.importance,
        metadata=req.metadata,
    )
    return {"memory_id": memory_id, "stored": True}


@router.post("/memory/recall")
async def recall_memory(req: MemoryRecallRequest):
    """Recall relevant memories for an agent."""
    from app.services.agent_memory import AgentMemoryStore
    memories = await AgentMemoryStore.recall(
        agent_name=req.agent_name,
        query=req.query,
        n_results=req.n_results,
    )
    return {"agent_name": req.agent_name, "memories": memories}


@router.get("/memory/stats")
async def memory_stats():
    """Get memory statistics across all agents."""
    from app.services.agent_memory import AgentMemoryStore
    stats = await AgentMemoryStore.get_all_agents_stats()
    return {"agents": stats, "total_agents_with_memory": len(stats)}


@router.post("/memory/consolidate")
async def consolidate_memories(agent_name: Optional[str] = None):
    """Consolidate agent memories into patterns."""
    from app.services.agent_memory import AgentMemoryStore
    if agent_name:
        count = await AgentMemoryStore.consolidate(agent_name)
        return {"agent_name": agent_name, "patterns_created": count}

    all_stats = await AgentMemoryStore.get_all_agents_stats()
    total = 0
    for stat in all_stats:
        total += await AgentMemoryStore.consolidate(stat["agent_name"])
    return {"total_patterns_created": total}
