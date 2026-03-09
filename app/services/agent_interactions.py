"""
Agent Interaction Queue — Allows agents to ask clarifying questions mid-task.

Agents post questions → user gets notified (push/SMS) → user answers →
agent resumes with the response. Persistence via JSON file.
"""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

from app.core.logging import logger

INTERACTIONS_DIR = "./data/interactions"
INTERACTIONS_FILE = os.path.join(INTERACTIONS_DIR, "queue.json")


@dataclass
class AgentInteraction:
    interaction_id: str
    task_id: str
    agent_name: str
    question: str
    options: list[str] = field(default_factory=list)  # empty = free text
    status: str = "awaiting"  # awaiting | answered | timeout | dismissed
    user_response: Optional[str] = None
    created_at: str = ""
    responded_at: Optional[str] = None
    timeout_seconds: int = 300  # 5 minutes default

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    @property
    def timeout_at(self) -> str:
        created = datetime.fromisoformat(self.created_at)
        return (created + timedelta(seconds=self.timeout_seconds)).isoformat()

    @property
    def is_expired(self) -> bool:
        timeout = datetime.fromisoformat(self.timeout_at)
        return datetime.utcnow() > timeout and self.status == "awaiting"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timeout_at"] = self.timeout_at
        return d


class InteractionQueue:
    """Manages agent clarifying questions with JSON persistence."""

    def __init__(self):
        self._interactions: dict[str, AgentInteraction] = {}
        self._load()

    def _load(self):
        """Load interactions from disk."""
        if os.path.exists(INTERACTIONS_FILE):
            try:
                with open(INTERACTIONS_FILE, "r") as f:
                    data = json.load(f)
                for item in data:
                    interaction = AgentInteraction(**{
                        k: v for k, v in item.items()
                        if k != "timeout_at"
                    })
                    self._interactions[interaction.interaction_id] = interaction
                logger.info(f"Loaded {len(self._interactions)} interactions from disk")
            except Exception as e:
                logger.error(f"Failed to load interactions: {e}")
                self._interactions = {}

    def _save(self):
        """Persist interactions to disk."""
        os.makedirs(INTERACTIONS_DIR, exist_ok=True)
        try:
            data = [i.to_dict() for i in self._interactions.values()]
            with open(INTERACTIONS_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save interactions: {e}")

    def post_question(
        self,
        task_id: str,
        agent_name: str,
        question: str,
        options: list[str] | None = None,
        timeout_seconds: int = 300,
    ) -> str:
        """
        Agent posts a clarifying question. Returns interaction_id.
        The agent should then poll check_response() in a loop.
        """
        interaction_id = f"inter_{uuid.uuid4().hex[:12]}"
        interaction = AgentInteraction(
            interaction_id=interaction_id,
            task_id=task_id,
            agent_name=agent_name,
            question=question,
            options=options or [],
            timeout_seconds=timeout_seconds,
        )
        self._interactions[interaction_id] = interaction
        self._save()
        logger.info(
            f"Agent '{agent_name}' asked: '{question[:80]}...' "
            f"(interaction={interaction_id}, task={task_id})"
        )
        return interaction_id

    def get_pending(self, task_id: str | None = None) -> list[AgentInteraction]:
        """Get all pending (awaiting) interactions, optionally filtered by task."""
        self.cleanup_expired()
        pending = [
            i for i in self._interactions.values()
            if i.status == "awaiting"
        ]
        if task_id:
            pending = [i for i in pending if i.task_id == task_id]
        return sorted(pending, key=lambda i: i.created_at)

    def get_all_pending(self) -> list[AgentInteraction]:
        """Get all pending interactions across all tasks."""
        return self.get_pending()

    def answer(self, interaction_id: str, response: str) -> bool:
        """User answers a question. Returns True if successful."""
        interaction = self._interactions.get(interaction_id)
        if not interaction:
            logger.warning(f"Interaction {interaction_id} not found")
            return False
        if interaction.status != "awaiting":
            logger.warning(f"Interaction {interaction_id} status is {interaction.status}, not awaiting")
            return False

        interaction.user_response = response
        interaction.status = "answered"
        interaction.responded_at = datetime.utcnow().isoformat()
        self._save()
        logger.info(f"Interaction {interaction_id} answered: '{response[:80]}'")
        return True

    def dismiss(self, interaction_id: str) -> bool:
        """User dismisses/skips a question."""
        interaction = self._interactions.get(interaction_id)
        if not interaction:
            return False
        interaction.status = "dismissed"
        interaction.responded_at = datetime.utcnow().isoformat()
        self._save()
        return True

    def check_response(self, interaction_id: str) -> tuple[bool, str | None]:
        """
        Agent polls this to see if user has responded.
        Returns (has_response, response_text).
        """
        interaction = self._interactions.get(interaction_id)
        if not interaction:
            return False, None
        if interaction.status == "answered":
            return True, interaction.user_response
        if interaction.is_expired:
            interaction.status = "timeout"
            self._save()
            return False, None
        return False, None

    def cleanup_expired(self):
        """Mark expired interactions as timed out."""
        changed = False
        for interaction in self._interactions.values():
            if interaction.is_expired:
                interaction.status = "timeout"
                changed = True
        if changed:
            self._save()

    def get_interaction(self, interaction_id: str) -> AgentInteraction | None:
        return self._interactions.get(interaction_id)

    def clear_completed(self, max_age_hours: int = 24):
        """Remove old answered/timeout/dismissed interactions."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_remove = []
        for iid, interaction in self._interactions.items():
            if interaction.status in ("answered", "timeout", "dismissed"):
                created = datetime.fromisoformat(interaction.created_at)
                if created < cutoff:
                    to_remove.append(iid)
        for iid in to_remove:
            del self._interactions[iid]
        if to_remove:
            self._save()
            logger.info(f"Cleaned up {len(to_remove)} old interactions")


# Singleton
_global_queue: InteractionQueue | None = None


def get_interaction_queue() -> InteractionQueue:
    global _global_queue
    if _global_queue is None:
        _global_queue = InteractionQueue()
    return _global_queue
