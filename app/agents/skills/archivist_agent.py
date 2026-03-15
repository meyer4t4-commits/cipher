"""
Archivist Agent - Contextual Memory and RAG System for Cipher AI

The Archivist Hand indexes every conversation, document, and thought across all
25+ agents to provide instant context retrieval on demand. It maintains a searchable
knowledge base with semantic organization and temporal awareness.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from collections import Counter
import re

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


@dataclass
class MemoryEntry:
    """Represents a single indexed entry in the knowledge base."""
    id: str
    source_agent: str
    content: str
    summary: str
    tags: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    embedding_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create entry from dictionary."""
        return cls(**data)


class ArchivistAgent(BaseAgent):
    """
    Contextual Memory and RAG Agent for the Cipher AI system.

    Indexes conversations, documents, and agent outputs to provide
    instant context retrieval across all connected agents.
    """

    def __init__(self):
        """Initialize the Archivist Agent with memory infrastructure."""
        super().__init__(
            name="archivist_agent",
            description="Contextual memory and RAG — indexes all conversations, documents, "
                       "and agent outputs for instant recall",
            version="1.0.0",
        )

        # Initialize capabilities
        self.capabilities = [
            AgentCapability(
                name="index_document",
                description="Index a document or conversation into the knowledge base",
                category="memory",
                timeout=30,
            ),
            AgentCapability(
                name="recall",
                description="Retrieve contextual information from memory",
                category="memory",
                timeout=20,
            ),
            AgentCapability(
                name="cross_agent_search",
                description="Search across all agent outputs and logs",
                category="memory",
                timeout=45,
            ),
            AgentCapability(
                name="timeline_query",
                description="Query events and decisions by time range",
                category="memory",
                timeout=30,
            ),
            AgentCapability(
                name="context_brief",
                description="Generate a context brief on any topic from stored memory",
                category="memory",
                timeout=60,
            ),
        ]

        # Initialize paths
        self.data_dir = Path("data/archivist/")
        self.index_path = self.data_dir / "index.json"
        self.embeddings_dir = self.data_dir / "embeddings"

        # Agent log directories mapping — use /tmp fallback for Railway
        _data_base = Path("/tmp/cipher_data") if not Path("data").exists() or not os.access("data", os.W_OK) else Path("data")
        self.agent_log_dirs: Dict[str, Path] = {
            "apex_asset_hunter": _data_base / "apex_asset_hunter",
            "chronos": _data_base / "chronos",
            # Add other agent directories as needed
        }

        # Initialize data directories
        self._initialize_storage()

        # In-memory index for fast access (loaded from disk on init)
        self.memory_index: List[MemoryEntry] = []
        self._load_index()

        logger.info(f"Archivist Agent initialized with {len(self.memory_index)} indexed entries")

    def _initialize_storage(self) -> None:
        """Create necessary data directories if they don't exist."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.data_dir = Path("/tmp/cipher_data/archivist")
            self.index_path = self.data_dir / "index.json"
            self.embeddings_dir = self.data_dir / "embeddings"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)

        # Initialize index file if it doesn't exist
        if not self.index_path.exists():
            self.index_path.write_text(json.dumps([], indent=2))

    def _load_index(self) -> None:
        """Load memory index from disk into memory."""
        try:
            if self.index_path.exists():
                data = json.loads(self.index_path.read_text())
                self.memory_index = [MemoryEntry.from_dict(entry) for entry in data]
                logger.debug(f"Loaded {len(self.memory_index)} entries from index")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            self.memory_index = []

    def _save_index(self) -> None:
        """Persist memory index to disk."""
        try:
            data = [entry.to_dict() for entry in self.memory_index]
            self.index_path.write_text(json.dumps(data, indent=2))
            logger.debug(f"Persisted {len(self.memory_index)} entries to index")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    async def validate(self, task: AgentTask) -> bool:
        """
        Validate that the task has required parameters for the operation.

        Args:
            task: The task to validate

        Returns:
            True if task is valid, False otherwise
        """
        operation = task.params.get("operation")

        if not operation:
            logger.warning("Task missing 'operation' parameter")
            return False

        if operation not in ["index_document", "recall", "cross_agent_search",
                           "timeline_query", "context_brief"]:
            logger.warning(f"Unknown operation: {operation}")
            return False

        # Operation-specific validation
        if operation == "index_document":
            if not task.params.get("content") or not task.params.get("source_agent"):
                logger.warning("index_document requires 'content' and 'source_agent'")
                return False
        elif operation in ["recall", "context_brief"]:
            if not task.params.get("query"):
                logger.warning(f"{operation} requires 'query' parameter")
                return False
        elif operation == "timeline_query":
            if not task.params.get("start_date") or not task.params.get("end_date"):
                logger.warning("timeline_query requires 'start_date' and 'end_date'")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """
        Execute the specified memory operation.

        Args:
            task: The task containing operation and parameters

        Returns:
            AgentResult with operation results
        """
        operation = task.params.get("operation")

        try:
            if operation == "index_document":
                result = await self._index_document(task)
            elif operation == "recall":
                result = await self._recall(task)
            elif operation == "cross_agent_search":
                result = await self._cross_agent_search(task)
            elif operation == "timeline_query":
                result = await self._timeline_query(task)
            elif operation == "context_brief":
                result = await self._context_brief(task)
            else:
                result = AgentResult(
                    agent_name=self.name,
                    task_id=task.task_id,
                    success=False,
                    output={"error": f"Unknown operation: {operation}"},
                )

            return result
        except Exception as e:
            logger.error(f"Error executing {operation}: {e}")
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                output={"error": str(e)},
            )

    async def verify(self, task: AgentTask, result: AgentResult) -> AgentResult:
        """
        Verify the result of an operation.

        Args:
            task: The original task
            result: The execution result to verify

        Returns:
            Verified result
        """
        if not result.success:
            return result

        operation = task.params.get("operation")
        output = result.output

        # Operation-specific verification
        if operation == "index_document":
            if "entry_id" not in output:
                result.success = False
                result.output = {"error": "Missing entry_id in output"}
        elif operation in ["recall", "cross_agent_search", "timeline_query"]:
            if "results" not in output:
                result.success = False
                result.output = {"error": "Missing results in output"}
        elif operation == "context_brief":
            if "brief" not in output:
                result.success = False
                result.output = {"error": "Missing brief in output"}

        return result

    async def _index_document(self, task: AgentTask) -> AgentResult:
        """
        Index a document or conversation into the knowledge base.

        Args:
            task: Task with content, source_agent, and optional tags

        Returns:
            AgentResult with indexed entry metadata
        """
        content = task.params.get("content", "")
        source_agent = task.params.get("source_agent", "unknown")
        tags = task.params.get("tags", [])
        metadata = task.params.get("metadata", {})

        # Generate entry ID
        entry_id = f"{source_agent}_{len(self.memory_index)}_{int(datetime.utcnow().timestamp())}"

        # Generate summary — use LLM for longer content, truncate for short
        if len(content) > 500:
            try:
                from app.services.llm_router import chat_completion
                from app.models.schemas import ModelTier

                summary_response = await chat_completion(
                    messages=[{
                        "role": "user",
                        "content": (
                            "Summarize the following content in 2-3 concise sentences. "
                            "Focus on the key facts, decisions, or insights. "
                            "Be specific, not generic.\n\n"
                            f"Content:\n{content[:3000]}"
                        ),
                    }],
                    model_tier=ModelTier.FAST,
                    max_tokens=200,
                    temperature=0.2,
                )
                summary = summary_response.get("content", content[:500])
            except Exception as e:
                logger.debug(f"LLM summarization fell back to truncation: {e}")
                summary = content[:500] + "..."
        else:
            summary = content

        # Create memory entry
        entry = MemoryEntry(
            id=entry_id,
            source_agent=source_agent,
            content=content,
            summary=summary,
            tags=tags,
            metadata=metadata,
        )

        # Add to index
        self.memory_index.append(entry)
        self._save_index()

        logger.info(f"Indexed document {entry_id} from {source_agent}")

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={
                "entry_id": entry_id,
                "source_agent": source_agent,
                "summary": summary,
                "tags": tags,
                "timestamp": entry.timestamp,
            },
        )

    async def _recall(self, task: AgentTask) -> AgentResult:
        """
        Retrieve contextual information from memory using keyword search.

        Args:
            task: Task with query string

        Returns:
            AgentResult with top matching memory entries
        """
        query = task.params.get("query", "").lower()
        limit = task.params.get("limit", 10)

        if not query:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                output={"error": "Empty query"},
            )

        # Score all entries
        scored_entries: List[Tuple[MemoryEntry, float]] = []
        for entry in self.memory_index:
            score = self._relevance_score(entry, query)
            if score > 0:
                scored_entries.append((entry, score))

        # Sort by relevance
        scored_entries.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results = []
        for entry, score in scored_entries[:limit]:
            # Create snippet with context
            snippet = entry.content[:200] + ("..." if len(entry.content) > 200 else "")
            results.append({
                "entry_id": entry.id,
                "source_agent": entry.source_agent,
                "summary": entry.summary,
                "snippet": snippet,
                "tags": entry.tags,
                "timestamp": entry.timestamp,
                "relevance_score": round(score, 3),
            })

        logger.info(f"Recall query '{query}' returned {len(results)} results")

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={
                "query": query,
                "results": results,
                "total_matched": len(scored_entries),
            },
        )

    async def _cross_agent_search(self, task: AgentTask) -> AgentResult:
        """
        Search across all agent outputs and logs.

        Args:
            task: Task with query string

        Returns:
            AgentResult with results grouped by agent source
        """
        query = task.params.get("query", "").lower()
        limit = task.params.get("limit", 5)

        if not query:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                output={"error": "Empty query"},
            )

        results_by_agent: Dict[str, List[Dict[str, Any]]] = {}

        # Scan each agent directory
        for agent_name, agent_dir in self.agent_log_dirs.items():
            agent_results = self._scan_agent_outputs(agent_dir, query, limit)
            if agent_results:
                results_by_agent[agent_name] = agent_results

        logger.info(f"Cross-agent search for '{query}' found results in {len(results_by_agent)} agents")

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={
                "query": query,
                "results_by_agent": results_by_agent,
                "agents_searched": list(results_by_agent.keys()),
            },
        )

    async def _timeline_query(self, task: AgentTask) -> AgentResult:
        """
        Query events and decisions by time range.

        Args:
            task: Task with start_date, end_date, and optional topic filter

        Returns:
            AgentResult with timeline entries sorted chronologically
        """
        start_date_str = task.params.get("start_date")
        end_date_str = task.params.get("end_date")
        topic_filter = task.params.get("topic")

        try:
            start_date = datetime.fromisoformat(start_date_str)
            end_date = datetime.fromisoformat(end_date_str)
        except (ValueError, TypeError) as e:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                output={"error": f"Invalid date format: {e}"},
            )

        # Filter entries by date range
        timeline_entries = []
        for entry in self.memory_index:
            entry_time = datetime.fromisoformat(entry.timestamp)
            if start_date <= entry_time <= end_date:
                # Apply topic filter if provided
                if topic_filter:
                    if topic_filter.lower() not in entry.content.lower() and \
                       topic_filter.lower() not in [tag.lower() for tag in entry.tags]:
                        continue
                timeline_entries.append(entry)

        # Sort chronologically
        timeline_entries.sort(key=lambda x: x.timestamp)

        # Build results
        results = [
            {
                "entry_id": entry.id,
                "source_agent": entry.source_agent,
                "summary": entry.summary,
                "tags": entry.tags,
                "timestamp": entry.timestamp,
            }
            for entry in timeline_entries
        ]

        logger.info(f"Timeline query ({start_date_str} to {end_date_str}) returned {len(results)} entries")

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={
                "start_date": start_date_str,
                "end_date": end_date_str,
                "topic_filter": topic_filter,
                "results": results,
                "total_count": len(results),
            },
        )

    async def _context_brief(self, task: AgentTask) -> AgentResult:
        """
        Generate a context brief on any topic from stored memory.

        Compiles results into an Executive Brief format: Background,
        Key Decisions, Current Status, Open Items.

        Args:
            task: Task with topic string

        Returns:
            AgentResult with structured executive brief
        """
        topic = task.params.get("query", "").strip()

        if not topic:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                output={"error": "Topic query required"},
            )

        # Run recall to get relevant entries
        recall_task = AgentTask(
            task_id=f"{task.task_id}_recall",
            agent_name=self.name,
            params={"operation": "recall", "query": topic, "limit": 20},
        )
        recall_result = await self._recall(recall_task)

        if not recall_result.success:
            return recall_result

        recall_entries = recall_result.output.get("results", [])

        # Organize by agent and extract key information
        background_entries = []
        decision_entries = []
        status_entries = []

        for entry in recall_entries:
            if any(tag in ["background", "context", "history"] for tag in entry.get("tags", [])):
                background_entries.append(entry)
            elif any(tag in ["decision", "action", "change"] for tag in entry.get("tags", [])):
                decision_entries.append(entry)
            else:
                status_entries.append(entry)

        # Ensure balanced distribution
        if not background_entries and recall_entries:
            background_entries = recall_entries[:len(recall_entries) // 3]
        if not decision_entries and recall_entries:
            decision_entries = recall_entries[len(recall_entries) // 3:2 * len(recall_entries) // 3]
        if not status_entries and recall_entries:
            status_entries = recall_entries[2 * len(recall_entries) // 3:]

        # Build brief
        brief = {
            "topic": topic,
            "generated_at": datetime.utcnow().isoformat(),
            "background": {
                "entries": background_entries[:5],
                "summary": f"Found {len(background_entries)} background entries on '{topic}'",
            },
            "key_decisions": {
                "entries": decision_entries[:5],
                "summary": f"Found {len(decision_entries)} key decisions related to '{topic}'",
            },
            "current_status": {
                "entries": status_entries[:5],
                "summary": f"Found {len(status_entries)} current status entries",
            },
            "open_items": {
                "count": len(recall_entries) - len(background_entries) - len(decision_entries) - len(status_entries),
                "total_indexed": len(recall_entries),
            },
        }

        logger.info(f"Generated context brief for topic: '{topic}'")

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={"brief": brief},
        )

    def _build_search_index(self, content: str) -> List[str]:
        """
        Tokenize content into searchable terms.

        Args:
            content: Text to tokenize

        Returns:
            List of searchable tokens
        """
        # Simple tokenization: lowercase, split, remove special chars
        tokens = re.findall(r'\b\w+\b', content.lower())
        return tokens

    def _relevance_score(self, entry: MemoryEntry, query: str) -> float:
        """
        Calculate relevance score with recency weighting.

        Newer entries receive a boost. Matches in summary are weighted
        higher than in full content. Tag matches are weighted highest.

        Args:
            entry: Memory entry to score
            query: Query string

        Returns:
            Relevance score (higher = more relevant)
        """
        score = 0.0
        query_terms = self._build_search_index(query)

        if not query_terms:
            return score

        # Tag matches (highest weight)
        for term in query_terms:
            tag_matches = sum(1 for tag in entry.tags if term in tag.lower())
            score += tag_matches * 5.0

        # Summary matches (high weight)
        summary_tokens = self._build_search_index(entry.summary)
        term_counter = Counter(summary_tokens)
        for term in query_terms:
            score += term_counter[term] * 2.0

        # Content matches (base weight)
        content_tokens = self._build_search_index(entry.content)
        term_counter = Counter(content_tokens)
        for term in query_terms:
            score += term_counter[term] * 1.0

        # Recency boost
        entry_time = datetime.fromisoformat(entry.timestamp)
        now = datetime.utcnow()
        age_days = (now - entry_time).days

        # Entries from last week get 1.5x boost, last month 1.2x, etc.
        if age_days <= 7:
            score *= 1.5
        elif age_days <= 30:
            score *= 1.2
        elif age_days <= 90:
            score *= 1.0
        else:
            score *= 0.9

        return score

    def _scan_agent_outputs(
        self,
        agent_dir: Path,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Walk agent data directories, find .json and .md files, and search content.

        Args:
            agent_dir: Path to agent directory
            query: Search query
            limit: Maximum results per agent

        Returns:
            List of matching results from this agent
        """
        results = []

        if not agent_dir.exists():
            return results

        try:
            for file_path in agent_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                if file_path.suffix not in [".json", ".md", ".txt"]:
                    continue

                try:
                    content = file_path.read_text(errors="ignore")

                    if query.lower() in content.lower():
                        # Extract snippet around query
                        idx = content.lower().find(query.lower())
                        start = max(0, idx - 100)
                        end = min(len(content), idx + len(query) + 100)
                        snippet = content[start:end]

                        results.append({
                            "file": str(file_path.relative_to(agent_dir)),
                            "snippet": snippet.strip(),
                            "file_type": file_path.suffix,
                        })

                        if len(results) >= limit:
                            break
                except Exception as e:
                    logger.debug(f"Error reading {file_path}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error scanning {agent_dir}: {e}")

        return results
