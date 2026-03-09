"""
Chat API endpoints - the primary interface to Cipher.

Supports both free (local) and premium (Elysian Gateway) modes:
- Without API key: uses user's own LLM API keys (free tier)
- With Elysian API key: uses managed infrastructure with metering
"""

import base64
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, File
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

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload an image for inclusion in chat. Returns base64-encoded data.
    Validates format (JPEG/PNG/WebP/GIF) and size (max 5MB).
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {file.content_type}. Supported: JPEG, PNG, WebP, GIF"
        )

    data = await file.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large ({len(data) / 1024 / 1024:.1f}MB). Max: 5MB"
        )

    b64 = base64.b64encode(data).decode("utf-8")
    return {
        "base64": b64,
        "mime_type": file.content_type,
        "size_bytes": len(data),
        "filename": file.filename,
    }


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
    Sends keepalive pings while the orchestrator processes so iOS doesn't timeout.
    """
    import json as _json
    import asyncio

    async def event_generator():
        try:
            # Send heartbeat IMMEDIATELY so iOS knows we're alive
            yield f"data: {_json.dumps({'type': 'token', 'content': ''})}\n\n"

            # Run orchestrator in background, send keepalives every 5s
            chat_task = asyncio.create_task(process_chat(request, db))

            while not chat_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(chat_task), timeout=5.0)
                except asyncio.TimeoutError:
                    # Still processing — keepalive so connection stays open
                    yield f"data: {_json.dumps({'type': 'token', 'content': ''})}\n\n"

            response = chat_task.result()

            # Stream the response in small chunks for smooth word-by-word
            content = response.message or ""

            # BLANK MESSAGE GUARD: If the orchestrator returned empty content,
            # send a meaningful fallback so iOS never shows a blank bubble
            if not content.strip():
                content = (
                    "Something went wrong generating a response. "
                    "This could be a temporary API issue — try again in a moment, "
                    "or switch to a different model tier."
                )

            chunk_size = 3
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                yield f"data: {_json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.01)

            # Send images if any were generated
            if response.images:
                for img in response.images:
                    yield f"data: {_json.dumps({'type': 'image', 'url': img.url or '', 'mime_type': img.mime_type or 'image/png', 'analysis': img.analysis or ''})}\n\n"

            # Metadata at end
            meta = {
                'type': 'metadata',
                'model_used': response.model_used or 'unknown',
                'tokens_used': response.tokens_used or 0,
                'cost_usd': response.cost_usd or 0.0,
                'conversation_id': response.conversation_id or '',
                'confidence_score': response.confidence_score,
                'has_images': len(response.images) if response.images else 0,
            }
            yield f"data: {_json.dumps(meta)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            import traceback
            error_detail = str(e)[:500]
            # Log full traceback server-side
            try:
                from app.core.logging import logger
                logger.error(f"Stream error: {traceback.format_exc()}")
            except Exception:
                pass
            # Send user-friendly error content as actual tokens (not error type)
            # so iOS renders it as a message instead of failing silently
            fallback = f"Hit an error processing your message: {error_detail[:200]}. Try again or switch model tiers."
            for i in range(0, len(fallback), 3):
                yield f"data: {_json.dumps({'type': 'token', 'content': fallback[i:i+3]})}\n\n"
            yield f"data: {_json.dumps({'type': 'metadata', 'model_used': 'error', 'tokens_used': 0, 'cost_usd': 0.0, 'conversation_id': ''})}\n\n"
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
