"""
Celery task definitions for background processing.
These run in the worker container asynchronously.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "cipher",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minute max per task
)


@celery_app.task(name="cipher.summarize_conversation")
def summarize_conversation(conversation_id: str) -> dict:
    """
    Summarize a long conversation into key points.
    Stores the summary in PostgreSQL memory for future retrieval.
    """
    # Import here to avoid circular imports
    from app.db.database import SessionLocal
    from app.db.models import MessageRecord
    from app.services.memory import store_memory

    db = SessionLocal()
    try:
        messages = (
            db.query(MessageRecord)
            .filter_by(conversation_id=conversation_id)
            .order_by(MessageRecord.created_at)
            .all()
        )

        if not messages:
            return {"status": "no_messages"}

        # Build conversation text
        text = "\n".join([f"{m.role}: {m.content}" for m in messages])

        # Store as a memory with summary metadata
        memory_id = store_memory(
            content=f"Conversation summary ({len(messages)} messages): {text[:2000]}",
            metadata={
                "source": "conversation_summary",
                "conversation_id": conversation_id,
                "message_count": len(messages),
            },
        )

        return {"status": "summarized", "memory_id": memory_id}
    finally:
        db.close()


@celery_app.task(name="cipher.index_document")
def index_document(content: str, metadata: dict = None) -> dict:
    """
    Index a document into memory for RAG retrieval.
    Splits content into chunks and stores each with embeddings.
    """
    from app.services.memory import store_memory
    import uuid

    # Simple chunking: split by paragraphs, max 500 chars each
    paragraphs = content.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) < 500:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    # Store each chunk
    doc_id = str(uuid.uuid4())[:8]
    stored_ids = []
    for i, chunk in enumerate(chunks):
        chunk_meta = {
            "source": "document",
            "doc_id": doc_id,
            "chunk_index": i,
            "total_chunks": len(chunks),
            **(metadata or {}),
        }
        mem_id = store_memory(
            content=chunk,
            metadata=chunk_meta,
            collection_name="cipher_documents",
        )
        stored_ids.append(mem_id)

    return {
        "status": "indexed",
        "doc_id": doc_id,
        "chunks": len(chunks),
        "memory_ids": stored_ids,
    }
