"""
Cipher Configuration
Loads from environment variables with sensible defaults.

IMPORTANT: All API keys are exported to os.environ immediately when settings loads.
This ensures agents that use os.getenv() at init time (before lifespan() runs) can
access the keys. Without this, agents get empty strings and fall back to mock data.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "cipher"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-this-in-production"

    # --- LLM Providers ---
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    xai_api_key: str = ""               # xAI (Grok) — fast reasoning, real-time X/Twitter knowledge
    google_api_key: str = ""             # Google Gemini — multimodal, 1M+ context
    perplexity_api_key: str = ""         # Perplexity — research-grade search + answers
    ollama_base_url: str = "http://localhost:11434"

    # --- Model Routing ---
    default_model: str = "anthropic/claude-sonnet-4-20250514"
    reasoning_model: str = "anthropic/claude-opus-4-6"
    fast_model: str = "xai/grok-3-mini-latest"
    local_model: str = "ollama/llama3.3"
    code_model: str = "anthropic/claude-sonnet-4-20250514"

    # --- Database ---
    database_url: str = "sqlite:///./data/cipher.db"
    chroma_persist_dir: str = "./data/chroma"  # Deprecated: memory now uses PostgreSQL. Kept for env compat.

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Image Generation ---
    stability_api_key: str = ""        # Stability AI (SDXL)
    # openai_api_key above also used for DALL-E 3

    # --- Video Generation ---
    replicate_api_key: str = ""        # Replicate (Runway, Kling, Hailuo, Wan)
    fal_api_key: str = ""              # fal.ai (Veo 2, LTX Video, Minimax)

    # --- Voice ---
    elevenlabs_api_key: str = ""
    default_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
    voice_enabled: bool = True
    emotion_detection_enabled: bool = True

    # --- Web Search & Scraping ---
    brave_search_api_key: str = ""     # Brave Search API for real-time web search
    firecrawl_api_key: str = ""        # Firecrawl — structured web scraping

    # --- Communication (Twilio) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_messaging_service_sid: str = ""

    # --- Communication (Email) ---
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    imap_host: str = "imap.gmail.com"
    imap_user: str = ""
    imap_pass: str = ""

    # --- Communication (Slack) ---
    slack_bot_token: str = ""

    # --- GitHub ---
    github_token: str = ""             # GitHub PAT for repo management, code push, issues

    # --- Real Estate ---
    attom_api_key: str = ""            # ATTOM API for property data
    census_api_key: str = ""           # US Census API (free) — demographics, economics
    propstream_api_key: str = ""       # PropStream — property data + skip tracing

    # --- Twitter/X API ---
    x_bearer_token: str = ""
    x_consumer_key: str = ""
    x_consumer_secret: str = ""

    # --- Payments ---
    stripe_publishable_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    btcpay_url: str = ""
    btcpay_api_key: str = ""

    # --- Storage (Cloudflare R2) ---
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""     # Cloudflare API bearer token (Workers/R2 access)
    cloudflare_r2_access_key: str = ""
    cloudflare_r2_secret_key: str = ""

    # --- Transactional Email ---
    resend_api_key: str = ""           # Resend — better deliverability than SMTP

    # --- Supabase (Postgres + Auth + Realtime) ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""     # Full backend access — bypasses RLS

    # --- Pinecone (Vector DB) ---
    pinecone_api_key: str = ""         # Production vector search upgrade from ChromaDB

    # --- Firebase Cloud Messaging ---
    fcm_service_account_path: str = ""  # Path to Firebase service account JSON
    fcm_project_id: str = ""            # Firebase project ID

    # --- Security ---
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000,https://elysianprotocol.io,https://www.elysianprotocol.io,https://api.elysianprotocol.io"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440

    # --- Scanner ---
    newsapi_key: str = ""
    scanner_enabled: bool = True
    scanner_interval_minutes: int = 60

    # --- Model Routing Strategy ---
    cascade_routing_enabled: bool = False  # DEPRECATED — quality-first routing, failover only on errors

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def allowed_telegram_users(self) -> list[int]:
        if not self.telegram_allowed_users:
            return []
        return [int(uid.strip()) for uid in self.telegram_allowed_users.split(",")]

    @property
    def data_dir(self) -> Path:
        path = Path("./data")
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()


def _export_api_keys_to_env():
    """
    Export ALL API keys from settings to os.environ immediately.

    WHY: Many agents read keys via os.getenv() in their __init__() at import time,
    which runs BEFORE FastAPI's lifespan() function. If keys aren't in os.environ
    by then, agents get empty strings and fall back to mock/hallucinated data.

    This function runs at module load time, ensuring every agent has access to
    real API keys from the moment they're instantiated.
    """
    _exports = {
        # LLM providers
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "GROQ_API_KEY": settings.groq_api_key,
        "OPENAI_API_KEY": settings.openai_api_key,
        "DEEPSEEK_API_KEY": settings.deepseek_api_key,
        "XAI_API_KEY": settings.xai_api_key,
        "GOOGLE_API_KEY": settings.google_api_key,
        "PERPLEXITY_API_KEY": settings.perplexity_api_key,
        # Web search — CRITICAL for anti-hallucination
        "BRAVE_SEARCH_API_KEY": settings.brave_search_api_key,
        "FIRECRAWL_API_KEY": settings.firecrawl_api_key,
        # Media generation
        "STABILITY_API_KEY": settings.stability_api_key,
        "REPLICATE_API_TOKEN": settings.replicate_api_key,
        "FAL_KEY": settings.fal_api_key,
        # Voice
        "ELEVENLABS_API_KEY": settings.elevenlabs_api_key,
        # Communication — Twilio
        "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
        "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
        "TWILIO_PHONE_NUMBER": settings.twilio_phone_number,
        "TWILIO_MESSAGING_SERVICE_SID": settings.twilio_messaging_service_sid,
        # Communication — Email
        "SMTP_HOST": settings.smtp_host,
        "SMTP_PORT": str(settings.smtp_port),
        "SMTP_USER": settings.smtp_user,
        "SMTP_PASS": settings.smtp_pass,
        "IMAP_HOST": settings.imap_host,
        "IMAP_USER": settings.imap_user,
        "IMAP_PASS": settings.imap_pass,
        # Communication — Slack
        "SLACK_BOT_TOKEN": settings.slack_bot_token,
        # Twitter/X
        "X_BEARER_TOKEN": settings.x_bearer_token,
        "X_CONSUMER_KEY": settings.x_consumer_key,
        "X_CONSUMER_SECRET": settings.x_consumer_secret,
        # GitHub
        "GITHUB_TOKEN": settings.github_token,
        # Real estate
        "ATTOM_API_KEY": settings.attom_api_key,
        "CENSUS_API_KEY": settings.census_api_key,
        "PROPSTREAM_API_KEY": settings.propstream_api_key,
        # News
        "NEWSAPI_KEY": settings.newsapi_key,
        # Storage
        "CLOUDFLARE_ACCOUNT_ID": settings.cloudflare_account_id,
        "CLOUDFLARE_API_TOKEN": settings.cloudflare_api_token,
        "CLOUDFLARE_R2_ACCESS_KEY": settings.cloudflare_r2_access_key,
        "CLOUDFLARE_R2_SECRET_KEY": settings.cloudflare_r2_secret_key,
        # Email
        "RESEND_API_KEY": settings.resend_api_key,
        # Supabase
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_ANON_KEY": settings.supabase_anon_key,
        "SUPABASE_SERVICE_KEY": settings.supabase_service_key,
        # Vector DB
        "PINECONE_API_KEY": settings.pinecone_api_key,
        # Firebase
        "FCM_SERVICE_ACCOUNT_PATH": settings.fcm_service_account_path,
        "FCM_PROJECT_ID": settings.fcm_project_id,
    }
    for key, value in _exports.items():
        if value and not os.environ.get(key):
            os.environ[key] = value


# Run immediately — agents depend on env vars being set at import time
_export_api_keys_to_env()
