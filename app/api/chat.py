"""
Chat API endpoints - the primary interface to Orchid.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ConversationRecord, MessageRecord
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Conversation,
    ConversationSummary,
    ChatMessage,
    Role,
)
from app.services.orchestrator import process_chat
from app.services.llm_router import stream_completion
from app.services.orchestrator import ORCHID_SYSTEM_PROMPT

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a message to Orchid and receive an intelligent response.
    The orchestrator handles memory retrieval, model routing, and context management.
    """
    try:
        return await process_chat(request, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_message(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Stream a response from Orchid token by token.
    Uses Server-Sent Events (SSE) for real-time streaming.
    """
    # Build messages from conversation history
    messages = []
    if request.conversation_id:
        history = (
            db.query(MessageRecord)
            .filter_by(conversation_id=request.conversation_id)
            .order_by(MessageRecord.created_at)
            .limit(50)
            .all()
        )
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})

    async def event_generator():
        async for chunk in stream_completion(
            messages=messages,
            model_tier=request.model_tier,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system_prompt=request.system_prompt or ORCHID_SYSTEM_PROMPT,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List all conversations, most recent first."""
    conversations = (
        db.query(ConversationRecord)
        .order_by(ConversationRecord.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for conv in conversations:
        msg_count = db.query(MessageRecord).filter_by(conversation_id=conv.id).count()
        last_msg = (
            db.query(MessageRecord)
            .filter_by(conversation_id=conv.id)
            .order_by(MessageRecord.created_at.desc())
            .first()
        )
        results.append(ConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count,
            last_message_preview=last_msg.content[:100] if last_msg else None,
        ))

    return results


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Get a full conversation with all messages."""
    conv = db.query(ConversationRecord).filter_by(id=conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(MessageRecord)
        .filter_by(conversation_id=conversation_id)
        .order_by(MessageRecord.created_at)
        .all()
    )

    return Conversation(
        id=conv.id,
        title=conv.title,
        messages=[
            ChatMessage(role=Role(msg.role), content=msg.content, timestamp=msg.created_at)
            for msg in messages
        ],
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(messages),
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Delete a conversation and all its messages."""
    conv = db.query(ConversationRecord).filter_by(id=conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.query(MessageRecord).filter_by(conversation_id=conversation_id).delete()
    db.delete(conv)
    db.commit()

    return {"status": "deleted", "conversation_id": conversation_id}
