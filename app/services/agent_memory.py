"""
Agent Memory Service — Zep-inspired persistent per-agent memory.

Unlike Cipher's existing memory.py (which stores conversation-level context),
this service gives each AGENT its own long-term memory that persists across
executions. Agents remember what they found last time, spot trends over
days/weeks, and avoid re-searching the same ground.

Inspired by MiroFish's use of Zep for cross-simulation agent memory.

Architecture:
- Each agent has its own memory namespace (agent_name)
- Memories are typed: observation, decision, outcome, pattern, error
- Recency-weighted recall with configurable decay
- Agents can store structured facts and retrieve by relevance
- Memory consolidation merges related memories over time
"""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import logger


class AgentMemoryEntry:
    """A single memory entry for an agent."""

    def __init__(
        self,
        agent_name: str,
        content: str,
        memory_type: str = "observation",
        metadata: Optional[dict] = None,
        importance: float = 0.5,
        memory_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        access_count: int = 0,
        last_accessed: Optional[datetime] = None,
    ):
        self.memory_id = memory_id or uuid.uuid4().hex[:12]
        self.agent_name = agent_name
        self.content = content
        self.memory_type = memory_type  # observation, decision, outcome, pattern, error
        self.metadata = metadata or {}
        self.importance = importance  # 0.0 - 1.0
        self.created_at = created_at or datetime.now(timezone.utc)
        self.access_count = access_count
        self.last_accessed = last_accessed or self.created_at

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "agent_name": self.agent_name,
            "content": self.content,
            "memory_type": self.memory_type,
            "metadata": self.metadata,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMemoryEntry":
        return cls(
            memory_id=data.get("memory_id"),
            agent_name=data["agent_name"],
            content=data["content"],
            memory_type=data.get("memory_type", "observation"),
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
        )


class AgentMemoryStore:
    """
    Persistent per-agent memory store.

    Uses the existing PostgreSQL MemoryEntry table via Cipher's memory service
    with a dedicated collection namespace per agent.
    """

    # Memory types
    OBSERVATION = "observation"  # Raw findings from execution
    DECISION = "decision"  # Choices the agent made and why
    OUTCOME = "outcome"  # Results of actions taken
    PATTERN = "pattern"  # Recurring trends detected
    ERROR = "error"  # Failures and lessons learned

    # In-memory index for fast retrieval (populated from DB on first access)
    _agent_memories: dict[str, list[AgentMemoryEntry]] = {}
    _loaded_agents: set[str] = set()

    @classmethod
    async def store(
        cls,
        agent_name: str,
        content: str,
        memory_type: str = "observation",
        metadata: Optional[dict] = None,
        importance: float = 0.5,
    ) -> str:
        """Store a memory for an agent. Returns memory_id."""
        entry = AgentMemoryEntry(
            agent_name=agent_name,
            content=content,
            memory_type=memory_type,
            metadata=metadata,
            importance=importance,
        )

        # Store in DB via existing memory service
        try:
            from app.services.memory import store_memory
            store_memory(
                content=content,
                metadata={
                    "agent_name": agent_name,
                    "memory_type": memory_type,
                    "importance": importance,
                    "agent_memory_id": entry.memory_id,
                    **(metadata or {}),
                },
                collection_name=f"agent_memory_{agent_name}",
                memory_id=entry.memory_id,
            )
        except Exception as e:
            logger.warning(f"[AgentMemory] DB store failed for {agent_name}: {e}")

        # Also keep in-memory index
        if agent_name not in cls._agent_memories:
            cls._agent_memories[agent_name] = []
        cls._agent_memories[agent_name].append(entry)

        # Cap in-memory storage at 500 per agent
        if len(cls._agent_memories[agent_name]) > 500:
            # Drop lowest importance memories
            cls._agent_memories[agent_name].sort(key=lambda m: m.importance, reverse=True)
            cls._agent_memories[agent_name] = cls._agent_memories[agent_name][:500]

        logger.debug(f"[AgentMemory] {agent_name} stored: {content[:80]}...")
        return entry.memory_id

    @classmethod
    async def recall(
        cls,
        agent_name: str,
        query: str,
        n_results: int = 5,
        memory_type: Optional[str] = None,
        min_importance: float = 0.0,
        max_age_days: Optional[int] = None,
    ) -> list[dict]:
        """
        Recall relevant memories for an agent.
        Uses weighted scoring: term match (40%) + recency (30%) + importance (20%) + access frequency (10%).
        """
        # Load from DB if not yet cached
        if agent_name not in cls._loaded_agents:
            await cls._load_from_db(agent_name)

        memories = cls._agent_memories.get(agent_name, [])
        if not memories:
            return []

        # Filter by type and importance
        candidates = memories
        if memory_type:
            candidates = [m for m in candidates if m.memory_type == memory_type]
        if min_importance > 0:
            candidates = [m for m in candidates if m.importance >= min_importance]
        if max_age_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            candidates = [m for m in candidates if m.created_at >= cutoff]

        if not candidates:
            return []

        # Score each memory
        query_terms = set(query.lower().split())
        scored = []
        now = datetime.now(timezone.utc)

        for mem in candidates:
            content_lower = mem.content.lower()
            content_terms = set(content_lower.split())

            # Term overlap (40%)
            overlap = len(query_terms & content_terms)
            max_possible = max(len(query_terms), 1)
            term_score = min(overlap / max_possible, 1.0) * 0.4

            # Recency (30%) — exponential decay over 30 days
            age_hours = max((now - mem.created_at).total_seconds() / 3600, 0.1)
            recency_score = (1.0 / (1.0 + age_hours / 720)) * 0.3

            # Importance (20%)
            importance_score = mem.importance * 0.2

            # Access frequency (10%) — more accessed = more relevant
            freq_score = min(mem.access_count / 20, 1.0) * 0.1

            total = term_score + recency_score + importance_score + freq_score
            scored.append((total, mem))

        # Sort by score, return top N
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, mem in scored[:n_results]:
            mem.access_count += 1
            mem.last_accessed = now
            results.append({**mem.to_dict(), "relevance_score": round(score, 3)})

        return results

    @classmethod
    async def get_agent_summary(cls, agent_name: str) -> dict:
        """Get a summary of an agent's memory state."""
        if agent_name not in cls._loaded_agents:
            await cls._load_from_db(agent_name)

        memories = cls._agent_memories.get(agent_name, [])
        if not memories:
            return {"agent_name": agent_name, "total_memories": 0, "types": {}}

        type_counts = {}
        for m in memories:
            type_counts[m.memory_type] = type_counts.get(m.memory_type, 0) + 1

        return {
            "agent_name": agent_name,
            "total_memories": len(memories),
            "types": type_counts,
            "avg_importance": round(sum(m.importance for m in memories) / len(memories), 2),
            "oldest": min(m.created_at for m in memories).isoformat(),
            "newest": max(m.created_at for m in memories).isoformat(),
        }

    @classmethod
    async def consolidate(cls, agent_name: str) -> int:
        """
        Consolidate agent memories — merge similar observations into patterns.
        Returns number of patterns created.
        """
        if agent_name not in cls._loaded_agents:
            await cls._load_from_db(agent_name)

        memories = cls._agent_memories.get(agent_name, [])
        observations = [m for m in memories if m.memory_type == cls.OBSERVATION]

        if len(observations) < 3:
            return 0

        # Simple clustering: group by metadata tags
        tag_groups: dict[str, list[AgentMemoryEntry]] = {}
        for obs in observations:
            tags = obs.metadata.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            for tag in tags:
                if tag not in tag_groups:
                    tag_groups[tag] = []
                tag_groups[tag].append(obs)

        patterns_created = 0
        for tag, group in tag_groups.items():
            if len(group) >= 3:
                # Enough observations to form a pattern
                contents = [m.content[:100] for m in group]
                pattern_content = (
                    f"Pattern detected ({tag}): {len(group)} observations. "
                    f"Recent: {contents[-1]}. "
                    f"Frequency: {len(group)} occurrences over "
                    f"{(group[-1].created_at - group[0].created_at).days} days."
                )
                await cls.store(
                    agent_name=agent_name,
                    content=pattern_content,
                    memory_type=cls.PATTERN,
                    metadata={"source_tag": tag, "source_count": len(group)},
                    importance=0.8,
                )
                patterns_created += 1

        logger.info(f"[AgentMemory] Consolidated {agent_name}: {patterns_created} patterns from {len(observations)} observations")
        return patterns_created

    @classmethod
    async def _load_from_db(cls, agent_name: str):
        """Load agent memories from the database."""
        try:
            from app.services.memory import recall_memories
            results = recall_memories(
                query="*",
                n_results=500,
                collection_name=f"agent_memory_{agent_name}",
            )
            if agent_name not in cls._agent_memories:
                cls._agent_memories[agent_name] = []

            for r in results:
                meta = r.get("metadata", {})
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}

                entry = AgentMemoryEntry(
                    agent_name=agent_name,
                    content=r.get("content", ""),
                    memory_type=meta.get("memory_type", "observation"),
                    metadata=meta,
                    importance=meta.get("importance", 0.5),
                    memory_id=meta.get("agent_memory_id", r.get("id", uuid.uuid4().hex[:12])),
                )
                cls._agent_memories[agent_name].append(entry)

        except Exception as e:
            logger.warning(f"[AgentMemory] Failed to load from DB for {agent_name}: {e}")

        cls._loaded_agents.add(agent_name)

    @classmethod
    async def get_all_agents_stats(cls) -> list[dict]:
        """Get memory stats for all agents that have memories."""
        stats = []
        # Check both in-memory and try DB
        for agent_name in list(cls._agent_memories.keys()):
            s = await cls.get_agent_summary(agent_name)
            if s["total_memories"] > 0:
                stats.append(s)
        return stats

    @classmethod
    def clear_cache(cls, agent_name: Optional[str] = None):
        """Clear in-memory cache. Does NOT delete from DB."""
        if agent_name:
            cls._agent_memories.pop(agent_name, None)
            cls._loaded_agents.discard(agent_name)
        else:
            cls._agent_memories.clear()
            cls._loaded_agents.clear()


# Convenience functions for agents to use
async def remember(agent_name: str, content: str, memory_type: str = "observation", **kwargs) -> str:
    """Shortcut for agents to store a memory."""
    return await AgentMemoryStore.store(agent_name, content, memory_type, **kwargs)


async def recall(agent_name: str, query: str, n_results: int = 5, **kwargs) -> list[dict]:
    """Shortcut for agents to recall memories."""
    return await AgentMemoryStore.recall(agent_name, query, n_results, **kwargs)
