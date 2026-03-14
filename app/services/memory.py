"""
Memory Service - Cipher's persistent context layer.

ALL memory is stored in the PostgreSQL database so it survives Railway deploys.
Everything discussed in conversation — learnings, playbooks, brand profiles,
user preferences, agent discoveries — persists permanently.

No more JSON files. No more in-memory dicts that wipe on restart.
"""

import json
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from app.core.logging import logger


def _get_db():
    """Get a database session. Returns None if DB is unavailable."""
    try:
        from app.db.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        logger.debug(f"Database unavailable for memory: {e}")
        return None


def _relevance_score(query: str, document: str) -> float:
    """Score how relevant a document is to a query using keyword overlap + sequence matching."""
    query_lower = query.lower()
    doc_lower = document.lower()
    query_words = set(query_lower.split())
    doc_words = set(doc_lower.split())
    if not query_words:
        return 0.0
    overlap = len(query_words & doc_words) / len(query_words)
    seq_score = SequenceMatcher(None, query_lower[:200], doc_lower[:200]).ratio()
    return (overlap * 0.6) + (seq_score * 0.4)


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
            # Update content if it changed
            if existing.content != content:
                existing.content = content
                existing.metadata_json = json.dumps(meta, default=str)
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

        entries = q.all()

        if not entries:
            db.close()
            return []

        # Score and rank by relevance
        scored = []
        for entry in entries:
            score = _relevance_score(query, entry.content)
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
    This is called after every chat exchange so Cipher remembers ALL context."""
    # Truncate to avoid storing massive responses but keep enough context
    user_msg = user_message[:2000] if user_message else ""
    asst_resp = assistant_response[:3000] if assistant_response else ""

    content = f"User: {user_msg}\nAssistant: {asst_resp}"
    return store_memory(
        content=content,
        metadata={
            "source": "conversation",
            "conversation_id": conversation_id,
            "type": "exchange",
            "priority": "normal",
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
