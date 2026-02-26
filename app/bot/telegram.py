"""
Telegram Bot - Orchid's messaging interface.
Zig's spiritual successor. Talk to Orchid from anywhere via Telegram.

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

# Orchid API base URL (talks to the local FastAPI server)
API_BASE = f"http://localhost:{settings.app_port}/api/v1"

# Track conversation IDs per Telegram user
user_conversations: dict[int, str] = {}


def is_authorized(user_id: int) -> bool:
    """Check if a Telegram user is authorized to use Orchid."""
    allowed = settings.allowed_telegram_users
    return not allowed or user_id in allowed


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized. Orchid is sovereign.")
        return

    await update.message.reply_text(
        "Orchid is online.\n\n"
        "Commands:\n"
        "/new - Start a new conversation\n"
        "/memory <query> - Search your memories\n"
        "/remember <text> - Store something in memory\n"
        "/models - Check available models\n"
        "/fast - Switch to fast model\n"
        "/reason - Switch to reasoning model\n"
        "/status - System status\n\n"
        "Or just send a message."
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

    async with httpx.AsyncClient() as client:
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

    async with httpx.AsyncClient() as client:
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

    async with httpx.AsyncClient() as client:
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

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/system/health", timeout=10)

    if response.status_code == 200:
        data = response.json()
        text = (
            f"Status: {data['status']}\n"
            f"Version: {data['version']}\n"
            f"Uptime: {data['uptime_seconds']:.0f}s\n"
            f"DB: {'connected' if data['database_connected'] else 'disconnected'}\n"
            f"Memory: {'connected' if data['chroma_connected'] else 'disconnected'}"
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages — the main chat interface."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    user_id = update.effective_user.id
    user_text = update.message.text

    # Send typing indicator
    await update.message.chat.send_action("typing")

    # Get or create conversation ID
    conversation_id = user_conversations.get(user_id)
    model_tier = user_model_tier.get(user_id, "default")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/chat/",
                json={
                    "message": user_text,
                    "conversation_id": conversation_id,
                    "model_tier": model_tier,
                    "include_memory": True,
                },
                timeout=120,
            )

        if response.status_code == 200:
            data = response.json()
            # Store conversation ID for continuity
            user_conversations[user_id] = data["conversation_id"]

            # Format response
            reply = data["message"]
            model_tag = data["model_used"].split("/")[-1][:20]
            footer = f"\n\n[{model_tag} | {data['tokens_used']} tokens | ${data['cost_usd']:.4f}]"

            # Telegram has a 4096 char limit
            full_reply = reply + footer
            if len(full_reply) > 4000:
                # Split long messages
                for i in range(0, len(reply), 3900):
                    chunk = reply[i : i + 3900]
                    if i + 3900 >= len(reply):
                        chunk += footer
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(full_reply)
        else:
            await update.message.reply_text(f"Error: {response.status_code}")

    except Exception as e:
        logger.error(f"Telegram message error: {e}")
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
