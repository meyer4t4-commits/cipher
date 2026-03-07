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
from app.api import agents, chat, memory, models, system, scanner, voice
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
    os.environ['ANTHROPIC_API_KEY'] = settings.anthropic_api_key
    os.environ['GROQ_API_KEY'] = settings.groq_api_key
    os.environ['OPENAI_API_KEY'] = settings.openai_api_key
    os.environ['DEEPSEEK_API_KEY'] = settings.deepseek_api_key

    # Export ElevenLabs API key if configured
    if settings.elevenlabs_api_key:
        os.environ['ELEVENLABS_API_KEY'] = settings.elevenlabs_api_key

    init_db()
    logger.info("Database initialized")
    providers = []
    if settings.anthropic_api_key:
        providers.append("Anthropic")
    if settings.groq_api_key:
        providers.append("Groq")
    if settings.openai_api_key:
        providers.append("OpenAI")
    providers.append("Ollama (local)")
    logger.info(f"LLM providers configured: {', '.join(providers)}")

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

    yield
    logger.info("Cipher shutting down")

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
