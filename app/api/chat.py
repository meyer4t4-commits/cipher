"""
Chat API endpoints - the primary interface to Cipher.

Supports both free (local) and premium (Elysian Gateway) modes:
- Without API key: uses user's own LLM API keys (free tier)
- With Elysian API key: uses managed infrastructure with metering
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
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
from app.core.system_prompt import get_system_prompt_for_mode, CIPHER_SYSTEM_PROMPT
from app.gateway.auth import optional_api_key, GatewayAuth, record_usage

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    req: Request = None,
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Send a message to Cipher and receive an intelligent response.
    The orchestrator handles memory retrieval, model routing, and context management.

    Works in both free (no API key) and premium (Elysian API key) modes.
    """
    # Optional gateway auth — meter usage if key present
    auth = None
    try:
        auth = await optional_api_key(req, x_elysian_key, authorization, db)
    except Exception:
        pass  # No key or invalid key — continue in free mode

    try:
        response = await process_chat(request, db)

        # Record usage if authenticated
        if auth:
            record_usage(
                db=db,
                auth=auth,
                feature="chat",
                input_tokens=0,  # Populated by orchestrator
                output_tokens=response.tokens_used,
                cost_usd=response.cost_usd,
                model=response.model_used,
            )

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_message(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Stream a response from Cipher token by token.
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
            system_prompt=request.system_prompt or CIPHER_SYSTEM_PROMPT,
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
