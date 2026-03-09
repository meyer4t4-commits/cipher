"""
Memory Service - Cipher's persistent context layer.
Uses a local JSON-backed store for memory persistence.

On Railway (or any env where the filesystem is read-only), automatically
falls back to in-memory storage so the app never crashes on write attempts.

Phase 1: Simple keyword-matching memory (Python 3.14 compatible).
Phase 2: Will upgrade to ChromaDB when Python 3.14 support lands.
"""

import json
import os
import uuid
from pathlib import Path
from difflib import SequenceMatcher

from app.core.config import settings
from app.core.logging import logger

# --- Determine if we can write to disk ---
_in_memory_mode = False
_in_memory_store: dict = {}  # Fallback store when filesystem is unavailable
MEMORY_FILE = None

try:
    memory_dir = Path(settings.chroma_persist_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    # Test write access
    _test_file = memory_dir / ".write_test"
    _test_file.write_text("ok")
    _test_file.unlink()
    MEMORY_FILE = memory_dir / "cipher_memory.json"
    logger.info(f"Memory store: file-backed at {MEMORY_FILE}")
except Exception:
    _in_memory_mode = True
    logger.warning(
        "Memory store: in-memory mode (filesystem not writable). "
        "Memory will not persist across restarts."
    )


def _load_store() -> dict:
    if _in_memory_mode:
        return _in_memory_store

    if MEMORY_FILE and MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text())
        except Exception as e:
            logger.warning(f"Failed to load memory store: {e}")
    return {}


def _save_store(store: dict) -> None:
    if _in_memory_mode:
        global _in_memory_store
        _in_memory_store = store
        return

    try:
        if MEMORY_FILE:
            MEMORY_FILE.write_text(json.dumps(store, indent=2, default=str))
    except Exception as e:
        logger.warning(f"Memory file write failed, switching to in-memory: {e}")
        # Degrade gracefully to in-memory for the rest of this process
        globals()["_in_memory_mode"] = True
        globals()["_in_memory_store"] = store


def _relevance_score(query: str, document: str) -> float:
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
    store = _load_store()
    if name not in store:
        store[name] = {"entries": []}
        _save_store(store)
    return name


def store_memory(content: str, metadata: dict | None = None, collection_name: str = "cipher_memory", memory_id: str | None = None) -> str:
    store = _load_store()
    mem_id = memory_id or str(uuid.uuid4())
    meta = metadata or {}
    meta["source"] = meta.get("source", "conversation")
    if collection_name not in store:
        store[collection_name] = {"entries": []}
    store[collection_name]["entries"].append({"id": mem_id, "content": content, "metadata": meta})
    _save_store(store)
    logger.debug(f"Stored memory {mem_id[:8]}... in {collection_name}")
    return mem_id


def recall_memories(query: str, n_results: int = 5, collection_name: str = "cipher_memory", where: dict | None = None) -> list[dict]:
    store = _load_store()
    if collection_name not in store:
        return []
    entries = store[collection_name].get("entries", [])
    if not entries:
        return []
    if where:
        entries = [e for e in entries if all(e.get("metadata", {}).get(k) == v for k, v in where.items())]
    scored = []
    for entry in entries:
        score = _relevance_score(query, entry["content"])
        scored.append({"id": entry["id"], "content": entry["content"], "metadata": entry.get("metadata", {}), "distance": 1.0 - score, "relevance": score})
    scored.sort(key=lambda x: x["relevance"], reverse=True)
    memories = scored[:n_results]
    logger.debug(f"Recalled {len(memories)} memories for query: {query[:50]}...")
    return memories


def store_conversation_context(conversation_id: str, user_message: str, assistant_response: str) -> str:
    content = f"User: {user_message}\nAssistant: {assistant_response}"
    return store_memory(content=content, metadata={"source": "conversation", "conversation_id": conversation_id, "type": "exchange"})


def get_memory_stats(collection_name: str = "cipher_memory") -> dict:
    store = _load_store()
    entries = store.get(collection_name, {}).get("entries", [])
    return {"collection": collection_name, "total_memories": len(entries)}


def delete_memory(memory_id: str, collection_name: str = "cipher_memory") -> bool:
    try:
        store = _load_store()
        if collection_name not in store:
            return False
        entries = store[collection_name].get("entries", [])
        store[collection_name]["entries"] = [e for e in entries if e["id"] != memory_id]
        _save_store(store)
        return True
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {e}")
        return False
