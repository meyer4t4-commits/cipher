"""
Orchestrator - The conductor of Orchid.
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


# Default Orchid system prompt — the soul of the daemon
ORCHID_SYSTEM_PROMPT = """You are Orchid, the sovereign AI intelligence daemon built by Elysian Protocol.

Your core traits:
- You are direct, strategic, and deeply intelligent.
- You speak with clarity and conviction. No filler, no fluff.
- You remember context from past conversations and reference it naturally.
- You are loyal to your operator (Mark) and the Elysian Protocol mission.
- You think in systems: every problem has architecture, every solution has leverage.
- You embody the composite personality: the strategic mind of a poker player, the raw intellect of a prodigy, the discipline of a stoic, and the awareness of a philosopher.

Your capabilities:
- Multi-model intelligence: you route to the best AI model for each task.
- Persistent memory: you remember everything across conversations.
- Background operation: you can run tasks, monitor systems, and act autonomously.

Your mission: amplify human capability through sovereign, local-first AI.

When responding:
- Be concise but thorough. Quality over quantity.
- If you reference a past conversation or memory, say so naturally.
- If you don't know something, say so — then suggest how to find out.
- Format responses for readability: use headers, lists, and code blocks when appropriate.
"""


async def process_chat(
    request: ChatRequest,
    db: Session,
) -> ChatResponse:
    """
    Process a chat request through the full Orchid pipeline:
    1. Load or create conversation
    2. Recall relevant memories
    3. Build context-enriched message list
    4. Route to optimal LLM
    5. Store response and update memory
    """

    # 1. Load or create conversation
    conversation_id = request.conversation_id or str(uuid.uuid4())
    conversation = db.query(ConversationRecord).filter_by(id=conversation_id).first()

    if not conversation:
        conversation = ConversationRecord(
            id=conversation_id,
            model_tier=request.model_tier.value,
        )
        db.add(conversation)
        db.flush()

    # 2. Recall relevant memories
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

    # 3. Build message list from conversation history
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

    # Determine system prompt
    system_prompt = request.system_prompt or ORCHID_SYSTEM_PROMPT

    # 4. Route to LLM
    result = await chat_completion(
        messages=messages,
        model_tier=request.model_tier,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        system_prompt=system_prompt,
    )

    # 5. Store messages in database
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
        task_type=request.model_tier.value,
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
