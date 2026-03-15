"""
Knowledge Graph Service — GraphRAG-inspired entity/relationship mapping.

Instead of treating agent discoveries as flat text, this service extracts
entities (people, companies, properties, events) and their relationships,
then lets agents query the graph for connected insights.

Inspired by MiroFish's use of GraphRAG for building structured world models.

Architecture:
- Entities: Nodes with type, name, properties, and confidence scores
- Relations: Directed edges between entities with relationship type
- Persistence: JSON-backed with periodic DB sync
- Query: Traverse relationships, find paths, get entity neighborhoods
- LLM-powered extraction: Parse unstructured text into graph triples
"""

import json
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.logging import logger

# ── Entity Types ────────────────────────────────────────────────────
ENTITY_TYPES = {
    "person", "company", "property", "location", "event", "policy",
    "market", "agent", "technology", "financial_instrument", "concept",
}

# ── Relationship Types ──────────────────────────────────────────────
RELATION_TYPES = {
    "owns", "manages", "located_in", "related_to", "competes_with",
    "influences", "depends_on", "produces", "consumes", "affects",
    "part_of", "invested_in", "discovered_by", "monitors", "targets",
    "associated_with", "causes", "precedes", "follows",
}


class Entity:
    """A node in the knowledge graph."""

    def __init__(
        self,
        name: str,
        entity_type: str,
        properties: Optional[dict] = None,
        confidence: float = 0.8,
        source_agent: Optional[str] = None,
        entity_id: Optional[str] = None,
    ):
        self.entity_id = entity_id or uuid.uuid4().hex[:10]
        self.name = name
        self.entity_type = entity_type
        self.properties = properties or {}
        self.confidence = confidence
        self.source_agent = source_agent
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.mention_count = 1

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "properties": self.properties,
            "confidence": self.confidence,
            "source_agent": self.source_agent,
            "mention_count": self.mention_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Relation:
    """A directed edge between two entities."""

    def __init__(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: Optional[dict] = None,
        confidence: float = 0.8,
        source_agent: Optional[str] = None,
    ):
        self.relation_id = uuid.uuid4().hex[:10]
        self.source_id = source_id
        self.target_id = target_id
        self.relation_type = relation_type
        self.properties = properties or {}
        self.confidence = confidence
        self.source_agent = source_agent
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "properties": self.properties,
            "confidence": self.confidence,
            "source_agent": self.source_agent,
            "created_at": self.created_at.isoformat(),
        }


class KnowledgeGraph:
    """
    In-memory knowledge graph with JSON persistence.

    Supports:
    - Entity CRUD with deduplication
    - Relationship management
    - Neighborhood queries (what's connected to X?)
    - Path finding (how are X and Y related?)
    - LLM-powered triple extraction from text
    """

    _instance = None

    def __init__(self):
        self.entities: dict[str, Entity] = {}  # entity_id -> Entity
        self.relations: list[Relation] = []
        self._name_index: dict[str, str] = {}  # lowercase name -> entity_id
        self._type_index: dict[str, set[str]] = defaultdict(set)  # type -> {entity_ids}
        self._adjacency: dict[str, list[Relation]] = defaultdict(list)  # entity_id -> [relations from/to]
        self._data_dir = Path("data/knowledge_graph")
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self._data_dir = Path("/tmp/cipher_data/knowledge_graph")
            self._data_dir.mkdir(parents=True, exist_ok=True)
        self._load_state()

    @classmethod
    def get_instance(cls) -> "KnowledgeGraph":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Entity Operations ───────────────────────────────────────────

    def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[dict] = None,
        confidence: float = 0.8,
        source_agent: Optional[str] = None,
    ) -> Entity:
        """Add or update an entity. Deduplicates by name."""
        key = name.lower().strip()

        if key in self._name_index:
            # Update existing entity
            existing = self.entities[self._name_index[key]]
            existing.mention_count += 1
            existing.updated_at = datetime.now(timezone.utc)
            if properties:
                existing.properties.update(properties)
            existing.confidence = max(existing.confidence, confidence)
            return existing

        entity = Entity(
            name=name,
            entity_type=entity_type,
            properties=properties,
            confidence=confidence,
            source_agent=source_agent,
        )
        self.entities[entity.entity_id] = entity
        self._name_index[key] = entity.entity_id
        self._type_index[entity_type].add(entity.entity_id)
        return entity

    def get_entity(self, name: str) -> Optional[Entity]:
        """Find an entity by name."""
        key = name.lower().strip()
        eid = self._name_index.get(key)
        return self.entities.get(eid) if eid else None

    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)

    def get_entities_by_type(self, entity_type: str) -> list[Entity]:
        """Get all entities of a given type."""
        ids = self._type_index.get(entity_type, set())
        return [self.entities[eid] for eid in ids if eid in self.entities]

    def search_entities(self, query: str, limit: int = 10) -> list[Entity]:
        """Search entities by name substring."""
        q = query.lower()
        matches = []
        for name_lower, eid in self._name_index.items():
            if q in name_lower:
                matches.append(self.entities[eid])
        matches.sort(key=lambda e: e.mention_count, reverse=True)
        return matches[:limit]

    # ── Relationship Operations ─────────────────────────────────────

    def add_relation(
        self,
        source_name: str,
        target_name: str,
        relation_type: str,
        properties: Optional[dict] = None,
        confidence: float = 0.8,
        source_agent: Optional[str] = None,
    ) -> Optional[Relation]:
        """Add a relationship between two entities (by name). Creates entities if they don't exist."""
        source = self.get_entity(source_name)
        target = self.get_entity(target_name)

        if not source:
            source = self.add_entity(source_name, "concept", source_agent=source_agent)
        if not target:
            target = self.add_entity(target_name, "concept", source_agent=source_agent)

        # Check for duplicate relation
        for r in self._adjacency.get(source.entity_id, []):
            if r.target_id == target.entity_id and r.relation_type == relation_type:
                r.confidence = max(r.confidence, confidence)
                return r

        rel = Relation(
            source_id=source.entity_id,
            target_id=target.entity_id,
            relation_type=relation_type,
            properties=properties,
            confidence=confidence,
            source_agent=source_agent,
        )
        self.relations.append(rel)
        self._adjacency[source.entity_id].append(rel)
        self._adjacency[target.entity_id].append(rel)
        return rel

    def get_neighbors(self, entity_name: str, relation_type: Optional[str] = None) -> list[dict]:
        """Get all entities connected to a given entity."""
        entity = self.get_entity(entity_name)
        if not entity:
            return []

        results = []
        for rel in self._adjacency.get(entity.entity_id, []):
            if relation_type and rel.relation_type != relation_type:
                continue
            other_id = rel.target_id if rel.source_id == entity.entity_id else rel.source_id
            other = self.entities.get(other_id)
            if other:
                results.append({
                    "entity": other.to_dict(),
                    "relation": rel.relation_type,
                    "direction": "outgoing" if rel.source_id == entity.entity_id else "incoming",
                    "confidence": rel.confidence,
                })
        return results

    def find_path(self, source_name: str, target_name: str, max_hops: int = 3) -> Optional[list[dict]]:
        """Find shortest path between two entities via BFS."""
        source = self.get_entity(source_name)
        target = self.get_entity(target_name)
        if not source or not target:
            return None

        # BFS
        visited = {source.entity_id}
        queue = [(source.entity_id, [])]

        while queue:
            current_id, path = queue.pop(0)
            if len(path) >= max_hops:
                continue

            for rel in self._adjacency.get(current_id, []):
                next_id = rel.target_id if rel.source_id == current_id else rel.source_id
                if next_id in visited:
                    continue
                visited.add(next_id)

                new_path = path + [{
                    "from": self.entities.get(current_id, Entity("?", "?")).name,
                    "relation": rel.relation_type,
                    "to": self.entities.get(next_id, Entity("?", "?")).name,
                }]

                if next_id == target.entity_id:
                    return new_path

                queue.append((next_id, new_path))

        return None

    # ── LLM-Powered Extraction ──────────────────────────────────────

    async def extract_from_text(self, text: str, source_agent: Optional[str] = None) -> dict:
        """
        Extract entities and relationships from unstructured text using LLM.
        Returns counts of entities and relations added.
        """
        try:
            from app.services.llm_router import chat_completion

            prompt = f"""Extract entities and relationships from this text. Return ONLY valid JSON.

Text: {text[:2000]}

Return format:
{{
  "entities": [
    {{"name": "...", "type": "person|company|property|location|event|policy|market|technology|financial_instrument|concept", "properties": {{}}}}
  ],
  "relations": [
    {{"source": "entity_name", "target": "entity_name", "type": "owns|manages|located_in|related_to|competes_with|influences|depends_on|affects|part_of|invested_in|associated_with|causes"}}
  ]
}}"""

            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="fast",
                temperature=0.1,
                max_tokens=1000,
            )

            content = response.get("content", "")
            # Extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
            else:
                return {"entities_added": 0, "relations_added": 0}

            entities_added = 0
            relations_added = 0

            for e in data.get("entities", []):
                self.add_entity(
                    name=e["name"],
                    entity_type=e.get("type", "concept"),
                    properties=e.get("properties", {}),
                    source_agent=source_agent,
                )
                entities_added += 1

            for r in data.get("relations", []):
                self.add_relation(
                    source_name=r["source"],
                    target_name=r["target"],
                    relation_type=r.get("type", "related_to"),
                    source_agent=source_agent,
                )
                relations_added += 1

            self._save_state()
            return {"entities_added": entities_added, "relations_added": relations_added}

        except Exception as e:
            logger.warning(f"[KnowledgeGraph] Extraction failed: {e}")
            return {"entities_added": 0, "relations_added": 0, "error": str(e)}

    # ── Stats & Persistence ─────────────────────────────────────────

    def get_stats(self) -> dict:
        type_counts = {}
        for etype, ids in self._type_index.items():
            type_counts[etype] = len(ids)
        return {
            "total_entities": len(self.entities),
            "total_relations": len(self.relations),
            "entity_types": type_counts,
            "top_entities": sorted(
                [{"name": e.name, "type": e.entity_type, "mentions": e.mention_count}
                 for e in self.entities.values()],
                key=lambda x: x["mentions"], reverse=True
            )[:10],
        }

    def _save_state(self):
        try:
            state = {
                "entities": {eid: e.to_dict() for eid, e in self.entities.items()},
                "relations": [r.to_dict() for r in self.relations],
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            path = self._data_dir / "graph_state.json"
            path.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.warning(f"[KnowledgeGraph] Save failed: {e}")

    def _load_state(self):
        path = self._data_dir / "graph_state.json"
        if not path.exists():
            return
        try:
            state = json.loads(path.read_text())

            for eid, edata in state.get("entities", {}).items():
                entity = Entity(
                    name=edata["name"],
                    entity_type=edata["entity_type"],
                    properties=edata.get("properties", {}),
                    confidence=edata.get("confidence", 0.8),
                    source_agent=edata.get("source_agent"),
                    entity_id=eid,
                )
                entity.mention_count = edata.get("mention_count", 1)
                self.entities[eid] = entity
                self._name_index[entity.name.lower().strip()] = eid
                self._type_index[entity.entity_type].add(eid)

            for rdata in state.get("relations", []):
                rel = Relation(
                    source_id=rdata["source_id"],
                    target_id=rdata["target_id"],
                    relation_type=rdata["relation_type"],
                    properties=rdata.get("properties", {}),
                    confidence=rdata.get("confidence", 0.8),
                    source_agent=rdata.get("source_agent"),
                )
                self.relations.append(rel)
                self._adjacency[rel.source_id].append(rel)
                self._adjacency[rel.target_id].append(rel)

            logger.info(f"[KnowledgeGraph] Loaded: {len(self.entities)} entities, {len(self.relations)} relations")
        except Exception as e:
            logger.warning(f"[KnowledgeGraph] Load failed: {e}")


# Convenience singleton
def get_knowledge_graph() -> KnowledgeGraph:
    return KnowledgeGraph.get_instance()
