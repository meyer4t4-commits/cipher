"""
Memory Service - Orchid's persistent context layer.
Uses ChromaDB for vector storage and semantic retrieval.

This is what makes Orchid sovereign: your memories stay local,
searchable, and never leave your machine.
"""

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logging import logger

# Ensure ChromaDB directory exists
chroma_path = Path(settings.chroma_persist_dir)
chroma_path.mkdir(parents=True, exist_ok=True)

# Initialize ChromaDB client with persistent storage
chroma_client = chromadb.PersistentClient(
    path=str(chroma_path),
    settings=ChromaSettings(anonymized_telemetry=False),
)


def get_collection(name: str = "orchid_memory") -> chromadb.Collection:
    """Get or create a ChromaDB collection."""
    return chroma_client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},  # cosine similarity for text
    )


def store_memory(
    content: str,
    metadata: dict | None = None,
    collection_name: str = "orchid_memory",
    memory_id: str | None = None,
) -> str:
    """
    Store a piece of information in long-term memory.
    Returns the memory ID.
    """
    import uuid

    collection = get_collection(collection_name)
    mem_id = memory_id or str(uuid.uuid4())
    meta = metadata or {}
    meta["source"] = meta.get("source", "conversation")

    collection.add(
        documents=[content],
        metadatas=[meta],
        ids=[mem_id],
    )

    logger.debug(f"Stored memory {mem_id[:8]}... in {collection_name}")
    return mem_id


def recall_memories(
    query: str,
    n_results: int = 5,
    collection_name: str = "orchid_memory",
    where: dict | None = None,
) -> list[dict]:
    """
    Recall relevant memories based on semantic similarity.
    Returns a list of memories with content, metadata, and relevance scores.
    """
    collection = get_collection(collection_name)

    if collection.count() == 0:
        return []

    kwargs = {
        "query_texts": [query],
        "n_results": min(n_results, collection.count()),
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    memories = []
    for i, doc in enumerate(results["documents"][0]):
        memories.append({
            "id": results["ids"][0][i],
            "content": doc,
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            "distance": results["distances"][0][i] if results["distances"] else 0.0,
            "relevance": 1.0 - (results["distances"][0][i] if results["distances"] else 0.0),
        })

    logger.debug(f"Recalled {len(memories)} memories for query: {query[:50]}...")
    return memories


def store_conversation_context(
    conversation_id: str,
    user_message: str,
    assistant_response: str,
) -> str:
    """
    Store a conversation exchange as a memory.
    This enables Orchid to recall past conversations contextually.
    """
    content = f"User: {user_message}\nAssistant: {assistant_response}"
    return store_memory(
        content=content,
        metadata={
            "source": "conversation",
            "conversation_id": conversation_id,
            "type": "exchange",
        },
    )


def get_memory_stats(collection_name: str = "orchid_memory") -> dict:
    """Get statistics about stored memories."""
    collection = get_collection(collection_name)
    return {
        "collection": collection_name,
        "total_memories": collection.count(),
    }


def delete_memory(memory_id: str, collection_name: str = "orchid_memory") -> bool:
    """Delete a specific memory by ID."""
    try:
        collection = get_collection(collection_name)
        collection.delete(ids=[memory_id])
        return True
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {e}")
        return False
