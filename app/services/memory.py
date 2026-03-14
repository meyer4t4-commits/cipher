"""
Memory Service - Cipher's persistent context layer.

ALL memory is stored in the PostgreSQL database so it survives Railway deploys.
Everything discussed in conversation — learnings, playbooks, brand profiles,
user preferences, agent discoveries — persists permanently.

No more JSON files. No more in-memory dicts that wipe on restart.
"""

import json
import math
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from app.core.logging import logger

# --- Importance scoring keywords ---
# Phrases that indicate high-value content worth remembering
_HIGH_IMPORTANCE_SIGNALS = [
    "remember", "always", "never", "important", "rule", "target audience",
    "brand", "strategy", "pricing", "competitor", "playbook", "framework",
    "apply to everything", "from now on", "going forward", "for all",
    "tallowroots", "tallow roots", "shopify", "seo", "ad campaign",
    "product", "customer", "revenue", "conversion",
]
_LOW_IMPORTANCE_SIGNALS = [
    "what time", "hello", "hi", "hey", "thanks", "thank you", "ok",
    "got it", "sure", "sounds good",
]


def _get_db():
    """Get a database session. Returns None if DB is unavailable."""
    try:
        from app.db.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        logger.debug(f"Database unavailable for memory: {e}")
        return None


def _relevance_score(query: str, document: str, created_at: datetime | None = None) -> float:
    """Score how relevant a document is to a query.
    Combines keyword overlap (40%), sequence matching (30%), and recency (30%)."""
    query_lower = query.lower()
    doc_lower = document.lower()
    query_words = set(query_lower.split())
    doc_words = set(doc_lower.split())
    if not query_words:
        return 0.0

    # Keyword overlap
    overlap = len(query_words & doc_words) / len(query_words)

    # Sequence similarity
    seq_score = SequenceMatcher(None, query_lower[:200], doc_lower[:200]).ratio()

    # Recency boost — newer memories score higher (decay over 30 days)
    recency = 0.5  # default for entries without timestamp
    if created_at:
        now = datetime.now(timezone.utc)
        age_hours = max(0, (now - created_at).total_seconds() / 3600)
        # Exponential decay: 1.0 at 0h, ~0.5 at 720h (30 days), ~0.1 at 2000h
        recency = math.exp(-age_hours / 1000)

    return (overlap * 0.4) + (seq_score * 0.3) + (recency * 0.3)


def _score_importance(text: str) -> str:
    """Auto-score the importance of a piece of content.
    Returns: 'critical', 'high', 'normal', or 'low'."""
    text_lower = text.lower()

    # Check for low-importance signals (greetings, acknowledgments)
    low_count = sum(1 for sig in _LOW_IMPORTANCE_SIGNALS if sig in text_lower)
    if low_count >= 2 and len(text) < 100:
        return "low"

    # Check for high-importance signals
    high_count = sum(1 for sig in _HIGH_IMPORTANCE_SIGNALS if sig in text_lower)
    if high_count >= 3:
        return "critical"
    if high_count >= 1:
        return "high"

    # Longer content with substance is more important
    if len(text) > 500:
        return "high"

    return "normal"


def get_collection(name: str = "cipher_memory") -> str:
    """Collections are just a filter on the collection_name column now."""
    return name


def store_memory(
    content: str,
    metadata: dict | None = None,
    collection_name: str = "cipher_memory",
    memory_id: str | None = None,
) -> str:
    """Store a memory entry in the database. Persists across deploys."""
    mem_id = memory_id or str(uuid.uuid4())
    meta = metadata or {}
    meta["source"] = meta.get("source", "conversation")

    db = _get_db()
    if not db:
        logger.warning(f"Memory store failed — no DB connection. Memory {mem_id[:8]} lost.")
        return mem_id

    try:
        from app.db.models import MemoryEntry

        # Check for existing entry with same ID (idempotent for seeds)
        existing = db.query(MemoryEntry).filter(MemoryEntry.id == mem_id).first()
        if existing:
            # Update content or metadata if anything changed
            new_meta_json = json.dumps(meta, default=str)
            changed = False
            if existing.content != content:
                existing.content = content
                changed = True
            if existing.metadata_json != new_meta_json:
                existing.metadata_json = new_meta_json
                changed = True
            if existing.priority != meta.get("priority", "normal"):
                existing.priority = meta.get("priority", "normal")
                changed = True
            if changed:
                db.commit()
                logger.debug(f"Updated existing memory {mem_id[:8]}...")
            db.close()
            return mem_id

        entry = MemoryEntry(
            id=mem_id,
            collection_name=collection_name,
            content=content,
            metadata_json=json.dumps(meta, default=str),
            source=meta.get("source", "conversation"),
            memory_type=meta.get("type", "general"),
            priority=meta.get("priority", "normal"),
        )
        db.add(entry)
        db.commit()
        logger.debug(f"Stored memory {mem_id[:8]}... in {collection_name} [DB]")
    except Exception as e:
        logger.warning(f"Memory store DB write failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass

    return mem_id


def recall_memories(
    query: str,
    n_results: int = 5,
    collection_name: str = "cipher_memory",
    where: dict | None = None,
) -> list[dict]:
    """Recall memories from database, ranked by relevance to the query."""
    db = _get_db()
    if not db:
        return []

    try:
        from app.db.models import MemoryEntry

        # Build query
        q = db.query(MemoryEntry).filter(MemoryEntry.collection_name == collection_name)

        # Apply metadata filters
        if where:
            for key, value in where.items():
                # Filter on dedicated columns first, fall back to JSON search
                if key == "source":
                    q = q.filter(MemoryEntry.source == value)
                elif key == "type":
                    q = q.filter(MemoryEntry.memory_type == value)
                elif key == "priority":
                    q = q.filter(MemoryEntry.priority == value)
                # For other keys, we'd need JSON search — skip for now

        # Limit to prevent loading entire DB into memory
        entries = q.order_by(MemoryEntry.created_at.desc()).limit(1000).all()

        if not entries:
            db.close()
            return []

        # Score and rank by relevance (with recency weighting)
        scored = []
        for entry in entries:
            score = _relevance_score(query, entry.content, entry.created_at)
            meta = {}
            if entry.metadata_json:
                try:
                    meta = json.loads(entry.metadata_json)
                except Exception:
                    pass

            # Boost priority memories
            if entry.priority == "critical":
                score = min(1.0, score + 0.15)
            elif entry.priority == "high":
                score = min(1.0, score + 0.08)

            scored.append({
                "id": entry.id,
                "content": entry.content,
                "metadata": meta,
                "distance": 1.0 - score,
                "relevance": score,
            })

        scored.sort(key=lambda x: x["relevance"], reverse=True)
        memories = scored[:n_results]
        logger.debug(f"Recalled {len(memories)} memories for query: {query[:50]}... [DB]")
        return memories

    except Exception as e:
        logger.warning(f"Memory recall failed: {e}")
        return []
    finally:
        try:
            db.close()
        except Exception:
            pass


def store_conversation_context(
    conversation_id: str,
    user_message: str,
    assistant_response: str,
) -> str:
    """Store a conversation exchange as a memory entry.
    This is called after every chat exchange so Cipher remembers ALL context.
    Auto-scores importance based on content."""
    # Truncate to avoid storing massive responses but keep enough context
    user_msg = user_message[:2000] if user_message else ""
    asst_resp = assistant_response[:3000] if assistant_response else ""

    content = f"User: {user_msg}\nAssistant: {asst_resp}"

    # Auto-score importance based on user message content
    importance = _score_importance(user_msg)

    return store_memory(
        content=content,
        metadata={
            "source": "conversation",
            "conversation_id": conversation_id,
            "type": "exchange",
            "priority": importance,
        },
    )


def store_agent_result(
    agent_name: str,
    task_description: str,
    result_summary: str,
    success: bool = True,
    user_query: str = "",
) -> str:
    """Store an agent execution result as a memory entry.
    Called when agents complete work so Cipher remembers what it did and learned."""
    content = (
        f"Agent: {agent_name}\n"
        f"Task: {task_description}\n"
        f"Result: {result_summary[:2000]}\n"
        f"Success: {success}"
    )
    importance = "high" if success else "normal"
    # Boost importance if the user query was important
    if user_query:
        query_importance = _score_importance(user_query)
        if query_importance in ("critical", "high"):
            importance = query_importance

    return store_memory(
        content=content,
        metadata={
            "source": "agent",
            "type": "agent_result",
            "agent_name": agent_name,
            "success": str(success),
            "priority": importance,
        },
    )


def store_learning(
    content: str,
    category: str = "general",
    priority: str = "high",
    source: str = "self_improvement",
) -> str:
    """Store a learned insight or operational knowledge.
    Use this when Cipher discovers something it should remember permanently."""
    return store_memory(
        content=content,
        metadata={
            "source": source,
            "type": "learning",
            "category": category,
            "priority": priority,
        },
    )


def get_memory_stats(collection_name: str = "cipher_memory") -> dict:
    """Get stats about the memory database."""
    db = _get_db()
    if not db:
        return {"collection": collection_name, "total_memories": 0, "storage": "unavailable"}

    try:
        from sqlalchemy import func
        from app.db.models import MemoryEntry

        total = db.query(func.count(MemoryEntry.id)).filter(
            MemoryEntry.collection_name == collection_name
        ).scalar() or 0

        by_type = db.query(
            MemoryEntry.memory_type,
            func.count(MemoryEntry.id),
        ).filter(
            MemoryEntry.collection_name == collection_name
        ).group_by(MemoryEntry.memory_type).all()

        by_source = db.query(
            MemoryEntry.source,
            func.count(MemoryEntry.id),
        ).filter(
            MemoryEntry.collection_name == collection_name
        ).group_by(MemoryEntry.source).all()

        return {
            "collection": collection_name,
            "total_memories": total,
            "storage": "postgresql",
            "by_type": {t: c for t, c in by_type if t},
            "by_source": {s: c for s, c in by_source if s},
        }
    except Exception as e:
        logger.warning(f"Memory stats failed: {e}")
        return {"collection": collection_name, "total_memories": 0, "error": str(e)}
    finally:
        try:
            db.close()
        except Exception:
            pass


def initialize_memory():
    """No-op — memory is now backed by PostgreSQL, initialized via init_db().
    Kept for backward compatibility with self_diagnostic.py."""
    logger.debug("Memory system is database-backed — no initialization needed")


def delete_memory(memory_id: str, collection_name: str = "cipher_memory") -> bool:
    """Delete a specific memory entry."""
    db = _get_db()
    if not db:
        return False

    try:
        from app.db.models import MemoryEntry

        deleted = db.query(MemoryEntry).filter(
            MemoryEntry.id == memory_id,
            MemoryEntry.collection_name == collection_name,
        ).delete()
        db.commit()
        return deleted > 0
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            db.close()
        except Exception:
            pass
