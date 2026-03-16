"""
Cipher - Sovereign AI Intelligence Daemon
Main FastAPI application entry point.

Built by Elysian Protocol.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app import __version__
from app.api import agents, chat, memory, models, system, scanner, voice, notifications, recommendations, media, research, cron, projects, self_improvement, swarm, browser
from app.gateway.api import router as gateway_router
from app.gateway.premium_routes import availability_router
import os
from app.core.config import settings
from app.core.logging import logger
from app.db.database import init_db
from app.services.scanner.orchestrator import start_scanner, stop_scanner
from app.services.voice_service import close_voice_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting Cipher v{__version__} [{settings.app_env}]")
    logger.info(f"Default model: {settings.default_model}")

    # ── Export ALL API keys to environment so every agent can access them ──
    # LLM providers (always set)
    os.environ['ANTHROPIC_API_KEY'] = settings.anthropic_api_key
    os.environ['GROQ_API_KEY'] = settings.groq_api_key
    os.environ['OPENAI_API_KEY'] = settings.openai_api_key
    os.environ['DEEPSEEK_API_KEY'] = settings.deepseek_api_key
    if settings.xai_api_key:
        os.environ['XAI_API_KEY'] = settings.xai_api_key
        logger.info("xAI (Grok) API: ACTIVE")

    # Voice
    if settings.elevenlabs_api_key:
        os.environ['ELEVENLABS_API_KEY'] = settings.elevenlabs_api_key

    # Media generation
    if settings.stability_api_key:
        os.environ['STABILITY_API_KEY'] = settings.stability_api_key
    if settings.replicate_api_key:
        os.environ['REPLICATE_API_TOKEN'] = settings.replicate_api_key
    if settings.fal_api_key:
        os.environ['FAL_KEY'] = settings.fal_api_key

    # Web search (Brave) — CRITICAL for anti-hallucination
    if settings.brave_search_api_key:
        os.environ['BRAVE_SEARCH_API_KEY'] = settings.brave_search_api_key
        logger.info("Brave Search API: ACTIVE")
    else:
        logger.warning("Brave Search API: NOT CONFIGURED — agents will lack real-time search")

    # Communication — Twilio SMS/Voice
    if settings.twilio_account_sid:
        os.environ['TWILIO_ACCOUNT_SID'] = settings.twilio_account_sid
        os.environ['TWILIO_AUTH_TOKEN'] = settings.twilio_auth_token
        os.environ['TWILIO_PHONE_NUMBER'] = settings.twilio_phone_number
        os.environ['TWILIO_MESSAGING_SERVICE_SID'] = settings.twilio_messaging_service_sid
        logger.info("Twilio SMS/Voice: ACTIVE")

    # Communication — Email (SMTP/IMAP)
    if settings.smtp_user:
        os.environ['SMTP_HOST'] = settings.smtp_host
        os.environ['SMTP_PORT'] = str(settings.smtp_port)
        os.environ['SMTP_USER'] = settings.smtp_user
        os.environ['SMTP_PASS'] = settings.smtp_pass
        os.environ['IMAP_HOST'] = settings.imap_host
        os.environ['IMAP_USER'] = settings.imap_user
        os.environ['IMAP_PASS'] = settings.imap_pass
        logger.info("Email SMTP/IMAP: ACTIVE")

    # Communication — Slack
    if settings.slack_bot_token:
        os.environ['SLACK_BOT_TOKEN'] = settings.slack_bot_token
        logger.info("Slack Bot: ACTIVE")

    # Twitter/X API — Mark is PAYING for this
    if settings.x_bearer_token:
        os.environ['X_BEARER_TOKEN'] = settings.x_bearer_token
        logger.info("Twitter/X API: ACTIVE")
    else:
        logger.warning("Twitter/X API: NOT CONFIGURED")
    if settings.x_consumer_key:
        os.environ['X_CONSUMER_KEY'] = settings.x_consumer_key
        os.environ['X_CONSUMER_SECRET'] = settings.x_consumer_secret

    # Real estate — ATTOM
    if settings.attom_api_key:
        os.environ['ATTOM_API_KEY'] = settings.attom_api_key
        logger.info("ATTOM Real Estate API: ACTIVE")

    # News
    if settings.newsapi_key:
        os.environ['NEWSAPI_KEY'] = settings.newsapi_key
        logger.info("NewsAPI: ACTIVE")

    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e} — app will continue but DB features may be limited")
        logger.error("If on Railway, ensure volume is mounted at /app/data or set DATABASE_URL to PostgreSQL")

    # Seed memory with operational playbooks (runs every startup since memory is ephemeral)
    try:
        from app.services.memory_seeds import seed_memory
        seed_count = seed_memory()
        if seed_count:
            logger.info(f"Memory seeded: {seed_count} playbooks loaded")
    except Exception as e:
        logger.debug(f"Memory seeding skipped: {e}")
    providers = []
    if settings.anthropic_api_key:
        providers.append("Anthropic")
    if settings.groq_api_key:
        providers.append("Groq")
    if settings.openai_api_key:
        providers.append("OpenAI")
    providers.append("Ollama (local)")
    logger.info(f"LLM providers configured: {', '.join(providers)}")

    # Initialize Stripe billing (optional — non-fatal if keys not configured)
    if settings.stripe_secret_key:
        try:
            from app.services.billing import init_stripe
            init_stripe()
            logger.info("Stripe billing: ACTIVE")
        except Exception as e:
            logger.warning(f"Stripe init failed (non-fatal): {e}")
    else:
        logger.debug("Stripe not configured — billing in dev mode")

    # Voice service status
    if settings.voice_enabled and settings.elevenlabs_api_key:
        logger.info("Voice service enabled (ElevenLabs)")

    # Emotion detection status
    if settings.emotion_detection_enabled:
        logger.info("Emotion detection enabled")

    # Start scanner if enabled (non-blocking — won't crash server if scanner fails)
    if settings.scanner_enabled:
        try:
            await start_scanner()
            logger.info("Intelligence scanner started")
        except Exception as e:
            logger.warning(f"Scanner failed to start (non-fatal): {e}")

    # ── Start Cron Registry with agent executor wired ──
    try:
        from app.services.cron_registry import get_cron_registry
        from app.agents import get_executor, get_registry, AgentTask
        from app.api.agents import _init_agents

        _init_agents()
        _agent_executor = get_executor()
        _agent_registry = get_registry()

        async def _notify_telegram(message: str):
            """Send cron result to owner via Telegram."""
            try:
                import httpx as _httpx
                bot_token = settings.telegram_bot_token
                # Use first allowed user as owner chat_id
                owner_id = settings.allowed_telegram_users[0] if settings.allowed_telegram_users else None
                if not bot_token or not owner_id:
                    return
                async with _httpx.AsyncClient() as client:
                    await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={
                            "chat_id": owner_id,
                            "text": message[:4000],  # Telegram max ~4096
                            "parse_mode": "HTML",
                        },
                        timeout=15.0,
                    )
            except Exception as e:
                logger.warning(f"Cron Telegram notify failed: {e}")

        async def _cron_execute_agent(agent_name: str, operation: str, params: dict):
            """Bridge between cron registry and agent executor — runs agent + notifies owner."""
            if not _agent_registry.is_registered(agent_name):
                raise ValueError(f"Agent '{agent_name}' not registered")
            task = AgentTask(
                agent_name=agent_name,
                instruction=f"[CRON] Execute operation: {operation}",
                params={"operation": operation, **params},
                timeout_seconds=300,
            )
            result = await _agent_executor.execute(task, db=None)

            # ── Notify owner via Telegram ──
            status = "✅" if result.success else "❌"
            output_preview = str(result.output)[:2000] if result.output else "No output"
            error_text = f"\n\n<b>Error:</b> {result.error}" if result.error else ""
            time_ms = f"{result.execution_time_ms:.0f}ms" if result.execution_time_ms else "?"

            msg = (
                f"{status} <b>Cron: {agent_name}.{operation}</b>\n"
                f"⏱ {time_ms}{error_text}\n\n"
                f"{output_preview}"
            )
            await _notify_telegram(msg)

            return {
                "success": result.success,
                "output": str(result.output)[:500] if result.output else None,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
            }

        cron_registry = get_cron_registry()
        cron_registry.set_executor(_cron_execute_agent)
        await cron_registry.start()
        logger.info(f"Cron registry started: {len(cron_registry._tasks)} tasks, executor wired")
    except Exception as e:
        logger.warning(f"Cron registry failed to start (non-fatal): {e}")

    yield
    logger.info("Cipher shutting down")

    # Stop cron registry on shutdown
    try:
        cron_reg = get_cron_registry()
        await cron_reg.stop()
    except Exception:
        pass

    # Stop scanner on shutdown
    await stop_scanner()

    # Close voice service
    await close_voice_service()


app = FastAPI(
    title="Cipher",
    description="Sovereign AI Intelligence Daemon by Elysian Protocol",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(chat.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(scanner.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(notifications.router)
app.include_router(recommendations.router)
app.include_router(media.router)
app.include_router(research.router)  # CipherResearch autonomous self-improvement
app.include_router(cron.router)  # Scheduled tasks (cron registry)
app.include_router(projects.router)  # Projects filing system + credential vault
app.include_router(self_improvement.router)  # Self-improvement dashboard + idle training
app.include_router(swarm.router)  # Swarm intelligence: prediction, knowledge graph, agent memory
app.include_router(browser.router)  # Headless browser: page visits, screenshots, product scraping
app.include_router(gateway_router, prefix="/api/v1")
app.include_router(availability_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "Cipher",
        "version": __version__,
        "status": "operational",
        "by": "Elysian Protocol",
        "gateway": "Elysian Gateway v1.0",
        "mode": settings.app_env,
        "features": "/api/v1/features/available",
        "pricing": "/api/v1/gateway/tiers",
        "docs": "/docs",
    }


@app.get("/ping")
async def ping():
    return {"pong": True}


DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"


@app.get("/dashboard")
async def dashboard():
    index_file = DASHBOARD_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "Dashboard not found"}
