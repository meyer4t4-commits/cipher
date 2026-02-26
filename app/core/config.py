"""
Orchid Configuration
Loads from environment variables with sensible defaults.
"""

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
    app_name: str = "orchid"
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
    ollama_base_url: str = "http://localhost:11434"

    # --- Model Routing ---
    default_model: str = "claude-sonnet-4-20250514"
    reasoning_model: str = "claude-sonnet-4-20250514"
    fast_model: str = "groq/llama-3.3-70b-versatile"
    local_model: str = "ollama/llama3.3"
    code_model: str = "claude-sonnet-4-20250514"

    # --- Database ---
    database_url: str = "sqlite:///./data/orchid.db"
    chroma_persist_dir: str = "./data/chroma"

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Voice ---
    elevenlabs_api_key: str = ""
    default_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
    voice_enabled: bool = True
    emotion_detection_enabled: bool = True

    # --- Payments ---
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    btcpay_url: str = ""
    btcpay_api_key: str = ""

    # --- Security ---
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440

    # --- Scanner ---
    newsapi_key: str = ""
    x_bearer_token: str = ""
    scanner_enabled: bool = True
    scanner_interval_minutes: int = 60

    # --- Cascade Routing (FrugalGPT) ---
    cascade_routing_enabled: bool = True  # Enable cascade routing for cost optimization

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
