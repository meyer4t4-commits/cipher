"""Scanner configuration and keyword management."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScannerConfig:
    """Configuration for the intelligence scanner."""

    # Keywords to track by category
    keywords: dict[str, list[str]] = field(
        default_factory=lambda: {
            "technology": [
                "artificial intelligence",
                "AI startups",
                "machine learning",
                "sovereign AI",
                "local AI",
                "LLM",
            ],
            "brand": [
                "Elysian Protocol",
                "Orchid",
                "Cipher",
            ],
            "industry": [
                "roofing industry",
                "construction tech",
                "restaurant tech",
                "school safety",
            ],
            "competitors": [
                "OpenAI",
                "Anthropic",
                "Google DeepMind",
                "Meta AI",
            ],
        }
    )

    # Source enable/disable toggles
    sources_enabled: dict[str, bool] = field(
        default_factory=lambda: {
            "news": True,
            "web": True,
            "twitter": True,
            "github": True,
            "reddit": True,
            "evolution": True,
        }
    )

    # Scan intervals (in minutes) - per-source configuration
    # News, Reddit, Twitter: 15 min (frequent updates)
    # GitHub: 30 min (less frequent, less time-sensitive)
    # Model scanner: 360 min / 6 hours (models don't change that fast)
    # Evolution: 120 min (2 hours) - competitor features change regularly
    scan_intervals: dict[str, int] = field(
        default_factory=lambda: {
            "news": 15,      # Check news every 15 minutes
            "web": 15,       # Check web every 15 minutes
            "twitter": 15,   # Check Twitter every 15 minutes
            "github": 30,    # Check GitHub every 30 minutes
            "reddit": 15,    # Check Reddit every 15 minutes
            "models": 360,   # Check models every 6 hours
            "evolution": 120,  # Check competitor features every 2 hours
        }
    )

    # Relevance threshold (0.0 to 1.0)
    relevance_threshold: float = 0.3

    # Max results per scan
    max_results_per_scan: int = 10

    # Max total results to keep in memory
    max_stored_results: int = 100

    # API keys (from environment)
    newsapi_key: Optional[str] = None
    x_bearer_token: Optional[str] = None

    # Briefing settings
    daily_briefing_hour: int = 9  # 9 AM
    briefing_max_items: int = 20

    # Evolution scanner settings
    evolution_proposal_threshold: float = 0.4  # Min relevance for proposals
    evolution_auto_generate_plans: bool = True  # Auto-generate implementation plans
    evolution_monthly_review_day: int = 15  # Day of month for review meeting


def get_config() -> ScannerConfig:
    """Get scanner configuration instance."""
    from app.core.config import settings

    config = ScannerConfig()
    config.newsapi_key = getattr(settings, "newsapi_key", None)
    config.x_bearer_token = getattr(settings, "x_bearer_token", None)
    return config


def get_all_keywords() -> list[str]:
    """Get flattened list of all keywords to track."""
    config = get_config()
    all_keywords = []
    for category_keywords in config.keywords.values():
        all_keywords.extend(category_keywords)
    return list(set(all_keywords))  # deduplicate
