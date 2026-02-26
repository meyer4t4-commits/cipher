"""
Memory API endpoints - Cipher's long-term knowledge management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.memory import (
    store_memory,
    recall_memories,
    get_memory_stats,
    delete_memory,
)

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryStoreRequest(BaseModel):
    content: str
    metadata: dict = {}
    collection: str = "cipher_memory"


class MemorySearchRequest(BaseModel):
    query: str
    n_results: int = 5
    collection: str = "cipher_memory"


@router.post("/store")
async def store(request: MemoryStoreRequest):
    """Store a piece of information in Cipher's long-term memory."""
    memory_id = store_memory(
        content=request.content,
        metadata=request.metadata,
        collection_name=request.collection,
    )
    return {"memory_id": memory_id, "status": "stored"}


@router.post("/recall")
async def recall(request: MemorySearchRequest):
    """Search Cipher's memory for relevant information."""
    memories = recall_memories(
        query=request.query,
        n_results=request.n_results,
        collection_name=request.collection,
    )
    return {"memories": memories, "count": len(memories)}


@router.get("/stats")
async def stats():
    """Get memory statistics."""
    return get_memory_stats()


@router.delete("/{memory_id}")
async def remove(memory_id: str):
    """Delete a specific memory."""
    success = delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found or delete failed")
    return {"status": "deleted", "memory_id": memory_id}
