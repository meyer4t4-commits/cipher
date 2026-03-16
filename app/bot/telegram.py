"""
Telegram Bot - Cipher's messaging interface.
Zig's spiritual successor. Talk to Cipher from anywhere via Telegram.

This bot runs alongside the FastAPI server and provides the same
intelligence through Telegram's messaging platform.
"""

import asyncio
import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.core.config import settings
from app.core.logging import logger

# Cipher API base URL (talks to the local FastAPI server)
# Use 127.0.0.1 instead of localhost to avoid DNS resolution issues in containers
# Railway sets $PORT dynamically — use it if available, fall back to app_port
import os
_port = os.environ.get("PORT", str(settings.app_port))
API_BASE = f"http://127.0.0.1:{_port}/api/v1"

# Track conversation IDs per Telegram user
user_conversations: dict[int, str] = {}


def is_authorized(user_id: int) -> bool:
    """Check if a Telegram user is authorized to use Cipher."""
    allowed = settings.allowed_telegram_users
    return not allowed or user_id in allowed


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized. Cipher is sovereign.")
        return

    await update.message.reply_text(
        "Cipher is online.\n\n"
        "Just send a message — casual chat is fast and cheap.\n\n"
        "Commands:\n"
        "/deep <request> - Full pipeline (36 agents, tools, memory)\n"
        "/new - Start a new conversation\n"
        "/memory <query> - Search your memories\n"
        "/remember <text> - Store something in memory\n"
        "/models - Check available models\n"
        "/fast - Switch to fast model\n"
        "/reason - Switch to reasoning model\n"
        "/status - System status\n\n"
        "Smart routing: simple messages → fast model (cheap), "
        "complex requests → full orchestrator (agents + tools)."
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a fresh conversation."""
    if not is_authorized(update.effective_user.id):
        return

    user_id = update.effective_user.id
    if user_id in user_conversations:
        del user_conversations[user_id]

    await update.message.reply_text("New conversation started. Clean slate.")


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search memories."""
    if not is_authorized(update.effective_user.id):
        return

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /memory <search query>")
        return

    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=2), timeout=30.0) as client:
        response = await client.post(
            f"{API_BASE}/memory/recall",
            json={"query": query, "n_results": 5},
            timeout=30,
        )

    if response.status_code == 200:
        data = response.json()
        if data["count"] == 0:
            await update.message.reply_text("No memories found for that query.")
        else:
            text = f"Found {data['count']} memories:\n\n"
            for i, mem in enumerate(data["memories"], 1):
                relevance = f"{mem['relevance']:.0%}"
                content = mem["content"][:300]
                text += f"{i}. [{relevance}] {content}\n\n"
            await update.message.reply_text(text[:4000])  # Telegram message limit
    else:
        await update.message.reply_text("Memory search failed.")


async def remember_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store something in memory."""
    if not is_authorized(update.effective_user.id):
        return

    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /remember <text to remember>")
        return

    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=2), timeout=30.0) as client:
        response = await client.post(
            f"{API_BASE}/memory/store",
            json={
                "content": text,
                "metadata": {
                    "source": "telegram",
                    "user_id": str(update.effective_user.id),
                },
            },
            timeout=30,
        )

    if response.status_code == 200:
        await update.message.reply_text("Stored in memory.")
    else:
        await update.message.reply_text("Failed to store memory.")


async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available models."""
    if not is_authorized(update.effective_user.id):
        return

    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=2), timeout=30.0) as client:
        response = await client.get(f"{API_BASE}/models/", timeout=10)

    if response.status_code == 200:
        data = response.json()
        text = "Available models:\n\n"
        for m in data["models"]:
            text += f"  {m['tier']}: {m['model_id']} ({m['provider']})\n"
        await update.message.reply_text(text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system status."""
    if not is_authorized(update.effective_user.id):
        return

    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=2), timeout=30.0) as client:
        response = await client.get(f"{API_BASE}/system/health", timeout=10)

    if response.status_code == 200:
        data = response.json()
        text = (
            f"Status: {data['status']}\n"
            f"Version: {data['version']}\n"
            f"Uptime: {data['uptime_seconds']:.0f}s\n"
            f"DB: {'connected' if data['database_connected'] else 'disconnected'}\n"
            f"Memory: {'connected' if data.get('memory_connected', data.get('chroma_connected', False)) else 'disconnected'}"
        )
        await update.message.reply_text(text)


# Model tier tracking per user
user_model_tier: dict[int, str] = {}


async def fast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch to fast model."""
    if not is_authorized(update.effective_user.id):
        return
    user_model_tier[update.effective_user.id] = "fast"
    await update.message.reply_text(f"Switched to fast model: {settings.fast_model}")


async def reason_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch to reasoning model."""
    if not is_authorized(update.effective_user.id):
        return
    user_model_tier[update.effective_user.id] = "reasoning"
    await update.message.reply_text(f"Switched to reasoning model: {settings.reasoning_model}")


# Keywords that trigger full orchestrator (agents, tools, complex tasks)
_ORCHESTRATOR_KEYWORDS = {
    "provision", "scan", "audit", "analyze", "deploy", "generate", "search",
    "scrape", "monitor", "schedule", "research", "investigate", "build",
    "create", "draft", "compose", "send email", "send telegram", "tallowroots",
    "tallow roots", "shopify", "lead", "prospect", "competitor", "portfolio",
    "trade", "buy", "sell", "stock", "patent", "contract", "llc",
    "agent", "cron", "voice", "image", "video", "swarm", "sentinel",
    "briefing", "digest", "report", "proposal", "outreach", "pipeline",
    "elevenlabs", "eleven labs", "fix", "improve", "upgrade", "self-improve",
}


def _needs_orchestrator(text: str) -> bool:
    """Determine if a message needs the full orchestrator or can use fast path."""
    lower = text.lower().strip()
    # Short casual messages — fast path
    if len(lower) < 50 and not any(kw in lower for kw in _ORCHESTRATOR_KEYWORDS):
        return False
    # Check for orchestrator keywords
    return any(kw in lower for kw in _ORCHESTRATOR_KEYWORDS)


# Conversation history for fast-path (lightweight, per-user, last 10 messages)
_chat_history: dict[int, list[dict]] = {}
_MAX_HISTORY = 10

CIPHER_FAST_PROMPT = (
    "You are Cipher, a sovereign AI assistant. You're chatting via Telegram with Mark, your creator. "
    "Be natural, direct, and conversational. Keep responses concise unless asked for detail. "
    "You have 36 agents and can handle complex tasks — if Mark asks for something that needs "
    "an agent (scanning, research, trading, deployment, etc.), tell him to prefix with /deep "
    "or say you'll need the full pipeline for that. Don't be robotic."
)


async def _fast_reply(user_id: int, user_text: str) -> str:
    """Fast path — direct LLM call, no orchestrator, minimal tokens."""
    from app.services.llm_router import chat_completion, ModelTier

    # Build lightweight conversation history
    history = _chat_history.get(user_id, [])
    history.append({"role": "user", "content": user_text})

    # Keep only last N messages
    if len(history) > _MAX_HISTORY:
        history = history[-_MAX_HISTORY:]
    _chat_history[user_id] = history

    result = await chat_completion(
        messages=history,
        model_tier=ModelTier.FAST,
        max_tokens=1024,
        temperature=0.7,
        system_prompt=CIPHER_FAST_PROMPT,
    )

    reply = result.get("content", "") if isinstance(result, dict) else str(result)

    # Store assistant reply in history
    history.append({"role": "assistant", "content": reply})
    if len(history) > _MAX_HISTORY:
        _chat_history[user_id] = history[-_MAX_HISTORY:]

    return reply


async def _send_reply(update: Update, text: str):
    """Send reply, splitting if needed for Telegram's 4096 char limit."""
    if len(text) > 4000:
        for i in range(0, len(text), 3900):
            chunk = text[i : i + 3900]
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(text)


async def deep_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force full orchestrator for the next message."""
    if not is_authorized(update.effective_user.id):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /deep <your request>\nThis routes through the full orchestrator with all 36 agents.")
        return
    # Process as full orchestrator message
    update.message.text = text
    await _handle_orchestrator(update, force=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages — smart routing between fast and full pipeline."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    user_text = update.message.text
    await update.message.chat.send_action("typing")

    # Smart routing: simple chat → fast model, complex tasks → orchestrator
    if _needs_orchestrator(user_text) or user_model_tier.get(update.effective_user.id) == "reasoning":
        await _handle_orchestrator(update)
    else:
        try:
            reply = await _fast_reply(update.effective_user.id, user_text)
            if not reply or not reply.strip():
                reply = "..."
            await _send_reply(update, reply)
        except Exception as e:
            logger.error(f"Fast reply failed, falling back to orchestrator: {e}")
            await _handle_orchestrator(update)


async def _handle_orchestrator(update: Update, force: bool = False):
    """Full orchestrator path — all agents, tools, memory."""
    user_id = update.effective_user.id
    user_text = update.message.text
    conversation_id = user_conversations.get(user_id)
    model_tier = user_model_tier.get(user_id, "default")

    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(180.0, connect=10.0)) as client:
            response = await client.post(
                f"{API_BASE}/chat/",
                json={
                    "message": f"[TELEGRAM — keep response under 500 words, no markdown headers, no code blocks unless asked, be concise and conversational] {user_text}",
                    "conversation_id": conversation_id,
                    "model_tier": model_tier,
                    "include_memory": True,
                },
            )

        if response.status_code == 200:
            data = response.json()
            user_conversations[user_id] = data["conversation_id"]
            reply = data["message"]
            await _send_reply(update, reply)
        else:
            await update.message.reply_text(f"Error: {response.status_code}")

    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        await update.message.reply_text(f"Error: {str(e)[:200]}")


def create_bot_application() -> Application:
    """Create and configure the Telegram bot application."""
    if not settings.telegram_bot_token:
        logger.warning("No Telegram bot token configured. Bot disabled.")
        return None

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("remember", remember_command))
    app.add_handler(CommandHandler("models", models_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("fast", fast_command))
    app.add_handler(CommandHandler("reason", reason_command))
    app.add_handler(CommandHandler("deep", deep_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


async def run_bot():
    """Run the Telegram bot (call from main server startup)."""
    bot_app = create_bot_application()
    if bot_app:
        logger.info("Starting Telegram bot...")
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        logger.info("Telegram bot is running")
