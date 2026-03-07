"""
Orchestrator - The conductor of Cipher.
Ties together LLM routing, memory, conversation history, and response generation.
This is where the magic happens.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import ConversationRecord, MessageRecord, UsageLog
from app.models.schemas import ChatRequest, ChatResponse, ModelTier
from app.services.llm_router import chat_completion
from app.services.memory import recall_memories, store_conversation_context
from app.services.classifier import auto_classify
from app.services.cache import get_cached_response, cache_response
from app.services.voice_personalities import get_personality_manager


# Import the comprehensive system prompt from the dedicated module
from app.core.system_prompt import CIPHER_SYSTEM_PROMPT


async def process_chat(
    request: ChatRequest,
    db: Session,
) -> ChatResponse:
    """
    Process a chat request through the full Cipher pipeline:
    1. Load or create conversation
    2. Auto-classify if using AUTO tier
    3. Check cache for existing response
    4. Recall relevant memories
    5. Build context-enriched message list
    6. Route to optimal LLM
    7. Store response and update memory
    """

    # 1. Load or create conversation
    conversation_id = request.conversation_id or str(uuid.uuid4())
    conversation = db.query(ConversationRecord).filter_by(id=conversation_id).first()

    # Auto-classify if using AUTO tier
    model_tier = request.model_tier
    if model_tier == ModelTier.AUTO:
        model_tier, confidence = auto_classify(request.message)
        logger.info(f"Auto-classified message to {model_tier.value} (confidence: {confidence:.2f})")
    else:
        confidence = None

    if not conversation:
        conversation = ConversationRecord(
            id=conversation_id,
            model_tier=model_tier.value,
        )
        db.add(conversation)
        db.flush()

    # 2. Check cache for existing response (before expensive operations)
    cached = get_cached_response(
        message=request.message,
        model_tier=model_tier.value,
        conversation_id=conversation_id,
    )
    if cached:
        logger.info(f"Cache hit for message in conversation {conversation_id}")
        return ChatResponse(
            message=cached["content"],
            conversation_id=conversation_id,
            model_used=cached["model_used"],
            tokens_used=cached.get("total_tokens", 0),
            cost_usd=cached.get("cost_usd", 0.0),
        )

    # 3. Recall relevant memories
    memory_context = ""
    if request.include_memory:
        memories = recall_memories(request.message, n_results=5)
        if memories:
            memory_parts = []
            for mem in memories:
                if mem["relevance"] > 0.3:  # Only include relevant memories
                    memory_parts.append(f"- {mem['content'][:500]}")
            if memory_parts:
                memory_context = (
                    "\n\n[Relevant context from memory]\n"
                    + "\n".join(memory_parts)
                    + "\n[End memory context]\n"
                )

    # 4. Build message list from conversation history
    messages = []
    history = (
        db.query(MessageRecord)
        .filter_by(conversation_id=conversation_id)
        .order_by(MessageRecord.created_at)
        .limit(50)  # Keep last 50 messages for context
        .all()
    )

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # Add memory context to the user message
    enriched_message = request.message
    if memory_context:
        enriched_message = f"{request.message}\n{memory_context}"

    messages.append({"role": "user", "content": enriched_message})

    # Determine system prompt with voice personality overlay
    system_prompt = request.system_prompt or CIPHER_SYSTEM_PROMPT

    # Voice personality detection — seamless voice transitions
    try:
        personality_mgr = get_personality_manager()
        voice_personality = personality_mgr.detect_voice_mode(
            text=request.message,
            emotion=getattr(request, 'detected_emotion', None),
            emotion_confidence=getattr(request, 'emotion_confidence', 0.0),
            explicit_mode=getattr(request, 'voice_mode', None),
        )
        # Apply personality overlay to system prompt
        if voice_personality.system_prompt_overlay:
            system_prompt = f"{system_prompt}\n\n{voice_personality.system_prompt_overlay}"
            logger.info(f"Voice personality active: {voice_personality.name}")
    except Exception as e:
        logger.warning(f"Voice personality detection skipped: {e}")

    # 5. Route to LLM
    result = await chat_completion(
        messages=messages,
        model_tier=model_tier,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        system_prompt=system_prompt,
    )

    # 6. Cache the response
    cache_response(
        message=request.message,
        model_tier=model_tier.value,
        response=result,
        conversation_id=conversation_id,
    )

    # 7. Store messages in database
    user_msg = MessageRecord(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )
    assistant_msg = MessageRecord(
        conversation_id=conversation_id,
        role="assistant",
        content=result["content"],
        model_used=result["model_used"],
        tokens_used=result["total_tokens"],
        cost_usd=result["cost_usd"],
    )
    db.add_all([user_msg, assistant_msg])

    # Update conversation
    conversation.updated_at = datetime.now(timezone.utc)
    if not conversation.title and len(request.message) > 0:
        # Auto-title from first message
        conversation.title = request.message[:100]

    # Log usage
    usage_log = UsageLog(
        model=result["model_used"],
        provider=result["provider"],
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        total_tokens=result["total_tokens"],
        cost_usd=result["cost_usd"],
        latency_ms=result["latency_ms"],
        task_type=model_tier.value,
    )
    db.add(usage_log)
    db.commit()

    # Store in long-term memory (async-safe)
    try:
        store_conversation_context(
            conversation_id=conversation_id,
            user_message=request.message,
            assistant_response=result["content"],
        )
    except Exception as e:
        logger.warning(f"Failed to store memory: {e}")

    return ChatResponse(
        message=result["content"],
        conversation_id=conversation_id,
        model_used=result["model_used"],
        tokens_used=result["total_tokens"],
        cost_usd=result["cost_usd"],
    )
