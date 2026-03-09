"""
Model Auto-Discovery System — Cipher's Model Intelligence Network

Discovers new models across ALL providers using multiple intelligence sources:
1. X/Twitter monitoring — @AnthropicAI, @OpenAI, @xaborai, @DeepSeek, @GoogleAI
2. Web search — Brave API for release announcements and changelogs
3. LiteLLM model lists — direct provider API queries
4. Browser scraping — provider docs and pricing pages as fallback

When a new model is discovered:
- It's registered in the discovery registry
- The model_evaluator benchmarks it against Cipher's task suite
- If it beats the current model for any tier/agent, routing updates are proposed
- Changes are saved to model_benchmarks.json and applied on next restart

This runs nightly at 3 AM via the cron_registry "model-registry-update" task.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import litellm

from app.core.config import settings
from app.core.logging import logger
from app.services import memory


# Model registry file location
MODEL_REGISTRY_FILE = Path(settings.data_dir) / "model_registry.json"

# Discovery interval (24 hours by default)
DISCOVERY_INTERVAL_SECONDS = 24 * 60 * 60


# ═══════════════════════════════════════════════════════════════════════════════
# X/TWITTER ACCOUNTS TO MONITOR FOR MODEL RELEASES
# ═══════════════════════════════════════════════════════════════════════════════

X_MONITOR_ACCOUNTS = [
    "AnthropicAI",      # Claude releases
    "OpenAI",           # GPT releases
    "xaborai",          # Grok releases (xAI)
    "xaboraiapi",       # xAI API announcements
    "DeepSeek",         # DeepSeek releases (actually deepseek_ai)
    "deepseek_ai",      # DeepSeek official
    "GoogleAI",         # Gemini releases
    "GoogleDeepMind",   # Gemini research
    "MistralAI",        # Mistral releases
    "ollaborai",        # Ollama/local model releases
    "GroqInc",          # Groq inference updates
    "LiteLLM",          # LiteLLM model support updates
]

# Keywords that indicate a new model release
MODEL_RELEASE_KEYWORDS = [
    "releasing", "released", "launching", "launched", "introducing",
    "announcing", "announced", "available now", "now available",
    "new model", "API access", "available in the API", "in the API",
    "context window", "tokens", "benchmark", "outperforms",
    "gpt-5", "gpt-6", "claude", "opus", "sonnet", "haiku",
    "grok", "gemini", "deepseek", "mistral", "llama",
    "o3", "o4", "o5",  # OpenAI reasoning models
]


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWN MODELS PER PROVIDER — Updated March 2026
# These are the CURRENT models. The auto-discovery adds new ones.
# ═══════════════════════════════════════════════════════════════════════════════

KNOWN_MODELS = {
    "anthropic": [
        {"id": "claude-opus-4-20250514", "context": 200_000, "released": "2025-05-14"},
        {"id": "claude-sonnet-4-20250514", "context": 200_000, "released": "2025-05-14"},
    ],
    "openai": [
        {"id": "gpt-5.4", "context": 1_050_000, "released": "2026-03-05"},
        {"id": "gpt-5.3", "context": 128_000, "released": "2026-02-01"},
        {"id": "gpt-5", "context": 400_000, "released": "2025-12-01"},
        {"id": "gpt-5-mini", "context": 400_000, "released": "2025-12-01"},
        {"id": "gpt-4.1", "context": 1_050_000, "released": "2025-04-14"},
        {"id": "o3", "context": 200_000, "released": "2025-04-01"},
        {"id": "o3-pro", "context": 200_000, "released": "2025-06-01"},
        {"id": "o4-mini", "context": 200_000, "released": "2025-04-01"},
    ],
    "xai": [
        {"id": "grok-4-latest", "context": 131_072, "released": "2026-02-01"},
        {"id": "grok-3-latest", "context": 131_072, "released": "2025-04-01"},
        {"id": "grok-3-mini-latest", "context": 131_072, "released": "2025-04-01"},
    ],
    "deepseek": [
        {"id": "deepseek-chat", "context": 64_000, "released": "2025-01-20"},
        {"id": "deepseek-reasoner", "context": 64_000, "released": "2025-01-20"},
    ],
    "google": [
        {"id": "gemini-2.5-pro", "context": 1_000_000, "released": "2025-12-01"},
        {"id": "gemini-2.5-flash", "context": 1_000_000, "released": "2025-12-01"},
    ],
    "perplexity": [
        {"id": "sonar-pro", "context": 200_000, "released": "2025-09-01"},
    ],
    "groq": [
        {"id": "llama-3.3-70b-versatile", "context": 128_000, "released": "2024-12-01"},
    ],
}


class ModelRegistry:
    """Manages the model registry and multi-source discovery process."""

    def __init__(self):
        self.registry_file = MODEL_REGISTRY_FILE
        self.registry: dict = self._load_registry()
        self.last_discovery: Optional[datetime] = None
        self.models_count = 0
        self.benchmarks_run = 0
        self.new_models_detected = 0

    def _load_registry(self) -> dict:
        if self.registry_file.exists():
            try:
                content = json.loads(self.registry_file.read_text())
                logger.debug(f"Loaded model registry with {len(content.get('models', []))} models")
                return content
            except Exception as e:
                logger.warning(f"Failed to load model registry: {e}")
        return {"models": [], "last_updated": None, "discovery_count": 0, "x_intel": []}

    def _save_registry(self) -> None:
        try:
            self.registry_file.write_text(json.dumps(self.registry, indent=2))
        except Exception as e:
            logger.error(f"Failed to save model registry: {e}")

    def _find_model_in_registry(self, model_id: str) -> Optional[dict]:
        for model in self.registry.get("models", []):
            if model.get("model_id") == model_id:
                return model
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # DISCOVERY SOURCE 1: X/Twitter Scanning
    # ═══════════════════════════════════════════════════════════════════════

    async def scan_x_for_model_releases(self) -> list[dict]:
        """
        Scan X/Twitter for model release announcements.
        Uses the browser service to scrape monitored accounts.
        Returns list of potential model release signals.
        """
        signals = []

        try:
            from app.services.browser_service import scrape_x_feed

            # Search for model release keywords
            search_queries = [
                "new model API release from:AnthropicAI OR from:OpenAI OR from:xaborai",
                "launching today model API available",
                "claude gpt grok new model benchmark",
            ]

            for query in search_queries:
                try:
                    result = await scrape_x_feed(query=query, max_tweets=15)
                    if result.get("success") and result.get("tweets"):
                        for tweet in result["tweets"]:
                            text = tweet.get("text", "").lower()
                            # Check if this tweet is about a model release
                            keyword_hits = sum(1 for kw in MODEL_RELEASE_KEYWORDS if kw.lower() in text)
                            if keyword_hits >= 2:
                                signals.append({
                                    "source": "x_twitter",
                                    "query": query,
                                    "text": tweet.get("text", "")[:500],
                                    "user": tweet.get("user", ""),
                                    "timestamp": tweet.get("timestamp", ""),
                                    "url": tweet.get("url", ""),
                                    "keyword_hits": keyword_hits,
                                    "discovered_at": datetime.utcnow().isoformat(),
                                })
                except Exception as e:
                    logger.debug(f"X scan query failed: {e}")

            # Also check specific accounts
            for account in X_MONITOR_ACCOUNTS[:6]:  # Top 6 most important
                try:
                    result = await scrape_x_feed(account=account, max_tweets=10)
                    if result.get("success") and result.get("tweets"):
                        for tweet in result["tweets"]:
                            text = tweet.get("text", "").lower()
                            keyword_hits = sum(1 for kw in MODEL_RELEASE_KEYWORDS if kw.lower() in text)
                            if keyword_hits >= 2:
                                signals.append({
                                    "source": "x_twitter",
                                    "account": account,
                                    "text": tweet.get("text", "")[:500],
                                    "user": tweet.get("user", ""),
                                    "timestamp": tweet.get("timestamp", ""),
                                    "url": tweet.get("url", ""),
                                    "keyword_hits": keyword_hits,
                                    "discovered_at": datetime.utcnow().isoformat(),
                                })
                except Exception as e:
                    logger.debug(f"X account scan {account} failed: {e}")

            if signals:
                logger.info(f"X Intelligence: Found {len(signals)} potential model release signals")
                # Store signals in registry for analysis
                self.registry.setdefault("x_intel", [])
                self.registry["x_intel"] = signals[-50:]  # Keep last 50

        except ImportError:
            logger.debug("Browser service not available for X scanning")
        except Exception as e:
            logger.warning(f"X scanning failed: {e}")

        return signals

    # ═══════════════════════════════════════════════════════════════════════
    # DISCOVERY SOURCE 2: Web Search (Brave API)
    # ═══════════════════════════════════════════════════════════════════════

    async def search_web_for_model_releases(self) -> list[dict]:
        """
        Search the web for recent model releases using Brave Search API.
        Returns list of potential new model info.
        """
        signals = []

        try:
            from app.services.tool_calling import execute_tool

            search_queries = [
                "new AI model release API available 2026",
                "OpenAI GPT new model API March 2026",
                "Anthropic Claude new model 2026",
                "xAI Grok new model API 2026",
                "LiteLLM new model support",
            ]

            for query in search_queries:
                try:
                    result = await execute_tool("search_web", {"query": query, "count": 5})
                    if isinstance(result, str):
                        result = json.loads(result)

                    results_list = result.get("results", [])
                    for r in results_list[:3]:
                        title = r.get("title", "").lower()
                        snippet = r.get("description", "").lower()
                        combined = title + " " + snippet

                        keyword_hits = sum(1 for kw in MODEL_RELEASE_KEYWORDS if kw.lower() in combined)
                        if keyword_hits >= 2:
                            signals.append({
                                "source": "web_search",
                                "query": query,
                                "title": r.get("title", ""),
                                "snippet": r.get("description", "")[:300],
                                "url": r.get("url", ""),
                                "keyword_hits": keyword_hits,
                                "discovered_at": datetime.utcnow().isoformat(),
                            })
                except Exception as e:
                    logger.debug(f"Web search query failed: {e}")

        except Exception as e:
            logger.warning(f"Web search for models failed: {e}")

        if signals:
            logger.info(f"Web Intelligence: Found {len(signals)} potential model release signals")

        return signals

    # ═══════════════════════════════════════════════════════════════════════
    # DISCOVERY SOURCE 3: LiteLLM Provider Lists
    # ═══════════════════════════════════════════════════════════════════════

    def discover_from_known_lists(self) -> dict:
        """
        Discover models from the known model lists.
        This is the baseline — catches models we already know about.
        """
        discovered = {"new_models": [], "updated_models": [], "total": 0}

        for provider, models in KNOWN_MODELS.items():
            for model_info in models:
                model_id = model_info["id"]
                full_id = f"{provider}/{model_id}" if "/" not in model_id else model_id

                existing = self._find_model_in_registry(full_id)

                if not existing:
                    logger.info(f"New model registered: {full_id}")
                    discovered["new_models"].append(full_id)
                    self.new_models_detected += 1

                    self.registry["models"].append({
                        "model_id": full_id,
                        "provider": provider,
                        "discovered_at": datetime.utcnow().isoformat(),
                        "is_active": True,
                        "context_window": model_info.get("context", 4096),
                        "released": model_info.get("released", ""),
                        "benchmark_scores": None,
                        "source": "known_list",
                    })
                else:
                    existing["last_updated"] = datetime.utcnow().isoformat()
                    existing["is_active"] = True
                    discovered["updated_models"].append(full_id)

        discovered["total"] = len(discovered["new_models"]) + len(discovered["updated_models"])
        return discovered

    # ═══════════════════════════════════════════════════════════════════════
    # DISCOVERY SOURCE 4: LiteLLM Dynamic Model Probe
    # ═══════════════════════════════════════════════════════════════════════

    async def probe_litellm_models(self) -> list[str]:
        """
        Probe LiteLLM for available models by trying to get model info.
        This catches models that LiteLLM has added support for but
        we haven't manually registered yet.
        """
        new_models = []

        # Candidate model IDs to probe (speculative — based on naming patterns)
        candidates = [
            # OpenAI next-gen
            "openai/gpt-5.5", "openai/gpt-6", "openai/o5-mini", "openai/o5",
            "openai/gpt-5.4-mini", "openai/gpt-5.4-pro",
            # Anthropic next-gen
            "anthropic/claude-opus-4.5", "anthropic/claude-sonnet-5",
            "anthropic/claude-4-opus-20260101",
            # xAI next-gen
            "xai/grok-4-mini-latest", "xai/grok-5-latest",
            # DeepSeek
            "deepseek/deepseek-v3", "deepseek/deepseek-coder-v3",
            # Google
            "google/gemini-2.5-pro", "google/gemini-2.5-flash",
        ]

        for model_id in candidates:
            try:
                # Check if LiteLLM knows about this model
                info = litellm.get_model_info(model_id)
                if info:
                    existing = self._find_model_in_registry(model_id)
                    if not existing:
                        logger.info(f"LiteLLM probe discovered: {model_id}")
                        provider = model_id.split("/")[0] if "/" in model_id else "unknown"
                        self.registry["models"].append({
                            "model_id": model_id,
                            "provider": provider,
                            "discovered_at": datetime.utcnow().isoformat(),
                            "is_active": True,
                            "context_window": info.get("max_tokens", 4096),
                            "source": "litellm_probe",
                        })
                        new_models.append(model_id)
                        self.new_models_detected += 1

                        # Store in memory
                        memory.store_memory(
                            content=f"New model discovered via LiteLLM probe: {model_id}",
                            metadata={
                                "source": "model_discovery_litellm",
                                "model_id": model_id,
                                "type": "model_announcement",
                            },
                            collection_name="model_intelligence",
                        )
            except Exception:
                pass  # Model doesn't exist — expected for speculative probes

        if new_models:
            logger.info(f"LiteLLM probe discovered {len(new_models)} new models: {new_models}")

        return new_models

    # ═══════════════════════════════════════════════════════════════════════
    # MASTER DISCOVERY — Runs all sources
    # ═══════════════════════════════════════════════════════════════════════

    async def full_discovery(self) -> dict:
        """
        Run complete model discovery from all sources.
        Called by the cron task "model-registry-update" at 3 AM.
        """
        logger.info("=" * 60)
        logger.info("CIPHER MODEL DISCOVERY — FULL SCAN STARTING")
        logger.info("=" * 60)

        results = {
            "known_list": {},
            "x_signals": [],
            "web_signals": [],
            "litellm_probe": [],
            "total_new": 0,
            "discovery_time": datetime.utcnow().isoformat(),
        }

        # Source 1: Known model lists (fast, reliable)
        results["known_list"] = self.discover_from_known_lists()
        logger.info(f"Known lists: {len(results['known_list'].get('new_models', []))} new models")

        # Source 2: X/Twitter scanning (requires browser login)
        try:
            results["x_signals"] = await self.scan_x_for_model_releases()
        except Exception as e:
            logger.warning(f"X scanning skipped: {e}")

        # Source 3: Web search (requires Brave API key)
        try:
            results["web_signals"] = await self.search_web_for_model_releases()
        except Exception as e:
            logger.warning(f"Web search skipped: {e}")

        # Source 4: LiteLLM speculative probe
        try:
            results["litellm_probe"] = await self.probe_litellm_models()
        except Exception as e:
            logger.warning(f"LiteLLM probe skipped: {e}")

        # Update registry metadata
        results["total_new"] = self.new_models_detected
        self.registry["last_updated"] = datetime.utcnow().isoformat()
        self.registry["discovery_count"] = self.registry.get("discovery_count", 0) + 1
        self.models_count = len(self.registry.get("models", []))

        self._save_registry()
        self.last_discovery = datetime.utcnow()

        # Store discovery report in memory
        if results["total_new"] > 0 or results["x_signals"] or results["web_signals"]:
            memory.store_memory(
                content=f"Model discovery completed: {results['total_new']} new models found. "
                        f"X signals: {len(results['x_signals'])}, Web signals: {len(results['web_signals'])}",
                metadata={
                    "source": "model_discovery",
                    "type": "discovery_report",
                    "new_count": results["total_new"],
                },
                collection_name="model_intelligence",
            )

        logger.info(f"DISCOVERY COMPLETE: {results['total_new']} new models, "
                     f"{len(results['x_signals'])} X signals, "
                     f"{len(results['web_signals'])} web signals")

        return results

    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS
    # ═══════════════════════════════════════════════════════════════════════

    async def run_benchmark(self, model_id: str) -> Optional[dict]:
        """Quick benchmark — latency and basic quality check."""
        try:
            test_message = [{"role": "user", "content": "What is 2+2? Answer in one sentence."}]
            start = time.time()
            response = await litellm.acompletion(model=model_id, messages=test_message, max_tokens=50)
            latency_ms = (time.time() - start) * 1000

            content = response.choices[0].message.content
            usage = response.usage

            self.benchmarks_run += 1
            return {
                "model_id": model_id,
                "benchmark_date": datetime.utcnow().isoformat(),
                "latency_ms": latency_ms,
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "response_length": len(content),
                "success": True,
            }
        except Exception as e:
            logger.warning(f"Benchmark failed for {model_id}: {e}")
            return None

    def get_registry(self) -> dict:
        return self.registry

    def get_active_models(self) -> list[dict]:
        return [m for m in self.registry.get("models", []) if m.get("is_active", True)]

    def get_stats(self) -> dict:
        return {
            "total_models": len(self.registry.get("models", [])),
            "active_models": len(self.get_active_models()),
            "new_models_detected": self.new_models_detected,
            "benchmarks_run": self.benchmarks_run,
            "last_discovery": self.last_discovery.isoformat() if self.last_discovery else None,
            "discovery_count": self.registry.get("discovery_count", 0),
            "last_updated": self.registry.get("last_updated"),
            "x_signals_count": len(self.registry.get("x_intel", [])),
        }


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
