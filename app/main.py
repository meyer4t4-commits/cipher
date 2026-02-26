"""
Orchid - Sovereign AI Intelligence Daemon
Main FastAPI application entry point.

Built by Elysian Protocol.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import chat, memory, models, system
from app.core.config import settings
from app.core.logging import logger
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info(f"Starting Orchid v{__version__} [{settings.app_env}]")
    logger.info(f"Default model: {settings.default_model}")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Log available providers
    providers = []
    if settings.anthropic_api_key:
        providers.append("Anthropic")
    if settings.groq_api_key:
        providers.append("Groq")
    if settings.openai_api_key:
        providers.append("OpenAI")
    providers.append("Ollama (local)")
    logger.info(f"LLM providers configured: {', '.join(providers)}")

    yield

    # Shutdown
    logger.info("Orchid shutting down")


# Create application
app = FastAPI(
    title="Orchid",
    description="Sovereign AI Intelligence Daemon by Elysian Protocol",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(chat.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "Orchid",
        "version": __version__,
        "status": "operational",
        "by": "Elysian Protocol",
        "docs": "/docs",
    }


@app.get("/ping")
async def ping():
    return {"pong": True}
