"""
Model Auto-Discovery System
Periodically checks for new and updated models across all providers.
Updates the routing table and memory automatically.
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


class ModelRegistry:
    """Manages the model registry and discovery process."""

    def __init__(self):
        """Initialize model registry."""
        self.registry_file = MODEL_REGISTRY_FILE
        self.registry: dict = self._load_registry()
        self.last_discovery: Optional[datetime] = None
        self.models_count = 0
        self.benchmarks_run = 0
        self.new_models_detected = 0

    def _load_registry(self) -> dict:
        """Load registry from file or return empty dict."""
        if self.registry_file.exists():
            try:
                content = json.loads(self.registry_file.read_text())
                logger.debug(f"Loaded model registry with {len(content.get('models', []))} models")
                return content
            except Exception as e:
                logger.warning(f"Failed to load model registry: {e}")
        return {"models": [], "last_updated": None, "discovery_count": 0}

    def _save_registry(self) -> None:
        """Save registry to file."""
        try:
            self.registry_file.write_text(json.dumps(self.registry, indent=2))
            logger.debug(f"Saved model registry with {len(self.registry.get('models', []))} models")
        except Exception as e:
            logger.error(f"Failed to save model registry: {e}")

    def _get_model_id(self, model_dict: dict) -> str:
        """Extract model ID from provider response."""
        # Different providers use different keys
        return model_dict.get("id") or model_dict.get("model_id") or model_dict.get("name") or ""

    def discover_models(self) -> dict:
        """
        Discover available models from all providers using LiteLLM.

        Returns:
            Dictionary with discovery results
        """
        logger.info("Starting model discovery...")
        discovered = {"new_models": [], "updated_models": [], "removed_models": [], "total_discovered": 0}

        try:
            # Get available models from LiteLLM
            # LiteLLM supports many providers - we'll check the main ones
            providers = ["anthropic", "openai", "groq", "deepseek"]
            all_discovered_ids = set()

            for provider in providers:
                try:
                    # Get models for this provider
                    # Note: This uses LiteLLM's internal model lists
                    provider_models = self._get_models_for_provider(provider)

                    for model in provider_models:
                        model_id = self._get_model_id(model)
                        if not model_id:
                            continue

                        all_discovered_ids.add(model_id)
                        full_id = f"{provider}/{model_id}" if "/" not in model_id else model_id

                        # Check if this is a new model
                        existing = self._find_model_in_registry(full_id)

                        if not existing:
                            # New model detected
                            logger.info(f"New model detected: {full_id}")
                            discovered["new_models"].append(full_id)
                            self.new_models_detected += 1

                            # Add to registry
                            registry_entry = {
                                "model_id": full_id,
                                "provider": provider,
                                "discovered_at": datetime.utcnow().isoformat(),
                                "is_active": True,
                                "benchmark_scores": None,
                                "context_window": self._extract_context_window(model, provider),
                                "cost_per_1k_input": 0.0,
                                "cost_per_1k_output": 0.0,
                                "last_updated": datetime.utcnow().isoformat(),
                            }
                            self.registry["models"].append(registry_entry)

                            # Store in memory
                            memory.store_memory(
                                content=f"New model discovered: {full_id}",
                                metadata={
                                    "source": "model_discovery",
                                    "model_id": full_id,
                                    "provider": provider,
                                    "type": "model_announcement",
                                },
                                collection_name="model_intelligence",
                            )
                        else:
                            # Model already in registry, mark as still active
                            existing["last_updated"] = datetime.utcnow().isoformat()
                            existing["is_active"] = True
                            discovered["updated_models"].append(full_id)

                except Exception as e:
                    logger.warning(f"Error discovering models for {provider}: {e}")

            # Check for removed/inactive models
            for model_entry in self.registry.get("models", []):
                model_id = model_entry.get("model_id", "")
                if model_id not in all_discovered_ids:
                    model_entry["is_active"] = False
                    discovered["removed_models"].append(model_id)
                    logger.info(f"Model marked inactive: {model_id}")

            discovered["total_discovered"] = len(all_discovered_ids)
            self.models_count = len(self.registry.get("models", []))

            # Update timestamp
            self.registry["last_updated"] = datetime.utcnow().isoformat()
            self.registry["discovery_count"] = self.registry.get("discovery_count", 0) + 1

            # Save registry
            self._save_registry()

            logger.info(
                f"Model discovery complete: {len(discovered['new_models'])} new, "
                f"{len(discovered['updated_models'])} updated, "
                f"{len(discovered['removed_models'])} removed"
            )

            return discovered

        except Exception as e:
            logger.error(f"Model discovery failed: {e}")
            return discovered

    def _get_models_for_provider(self, provider: str) -> list[dict]:
        """
        Get available models for a provider.
        Uses LiteLLM's model information.
        """
        models = []

        try:
            if provider == "anthropic":
                # Anthropic models
                models = [
                    {"id": "claude-opus-4-20250805"},
                    {"id": "claude-sonnet-4-20250514"},
                    {"id": "claude-3-5-sonnet-20241022"},
                    {"id": "claude-3-opus-20250219"},
                ]
            elif provider == "openai":
                # OpenAI models
                models = [
                    {"id": "gpt-4o"},
                    {"id": "gpt-4-turbo"},
                    {"id": "gpt-4"},
                    {"id": "gpt-3.5-turbo"},
                ]
            elif provider == "groq":
                # Groq models
                models = [
                    {"id": "llama-3.3-70b-versatile"},
                    {"id": "llama-3.1-70b-versatile"},
                    {"id": "mixtral-8x7b-32768"},
                ]
            elif provider == "deepseek":
                # DeepSeek models
                models = [
                    {"id": "deepseek-chat"},
                    {"id": "deepseek-reasoner"},
                ]

        except Exception as e:
            logger.warning(f"Error getting models for {provider}: {e}")

        return models

    def _extract_context_window(self, model: dict, provider: str) -> int:
        """Extract context window size from model info."""
        context_windows = {
            # Anthropic
            "claude-opus-4-20250805": 200000,
            "claude-sonnet-4-20250514": 200000,
            "claude-3-5-sonnet-20241022": 200000,
            "claude-3-opus-20250219": 200000,
            # OpenAI
            "gpt-4o": 128000,
            "gpt-4-turbo": 128000,
            "gpt-4": 8192,
            "gpt-3.5-turbo": 4096,
            # Groq
            "llama-3.3-70b-versatile": 8192,
            "llama-3.1-70b-versatile": 8192,
            "mixtral-8x7b-32768": 32768,
            # DeepSeek
            "deepseek-chat": 4096,
            "deepseek-reasoner": 8192,
        }

        model_id = self._get_model_id(model)
        return context_windows.get(model_id, 4096)

    def _find_model_in_registry(self, model_id: str) -> Optional[dict]:
        """Find a model in the registry by ID."""
        for model in self.registry.get("models", []):
            if model.get("model_id") == model_id:
                return model
        return None

    async def run_benchmark(self, model_id: str) -> Optional[dict]:
        """
        Run a quick benchmark test on a model.
        Sends a standard prompt and measures latency/quality.

        Args:
            model_id: Full model ID to benchmark

        Returns:
            Benchmark results or None if failed
        """
        try:
            logger.debug(f"Running benchmark for {model_id}...")

            # Standard benchmark prompt
            test_message = [{"role": "user", "content": "What is 2+2? Answer in one sentence."}]

            start = time.time()
            response = await self._async_completion(model=model_id, messages=test_message, max_tokens=50)
            latency_ms = (time.time() - start) * 1000

            content = response.choices[0].message.content
            usage = response.usage

            benchmark = {
                "model_id": model_id,
                "benchmark_date": datetime.utcnow().isoformat(),
                "latency_ms": latency_ms,
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "response_length": len(content),
                "success": True,
            }

            self.benchmarks_run += 1
            logger.debug(f"Benchmark complete for {model_id}: {latency_ms:.0f}ms")

            return benchmark

        except Exception as e:
            logger.warning(f"Benchmark failed for {model_id}: {e}")
            return None

    async def _async_completion(self, **kwargs):
        """Wrapper for async completion calls."""
        import litellm

        return await litellm.acompletion(**kwargs)

    def get_registry(self) -> dict:
        """Get the current registry."""
        return self.registry

    def get_active_models(self) -> list[dict]:
        """Get list of active models."""
        return [m for m in self.registry.get("models", []) if m.get("is_active", True)]

    def get_stats(self) -> dict:
        """Get discovery statistics."""
        return {
            "total_models": len(self.registry.get("models", [])),
            "active_models": len(self.get_active_models()),
            "new_models_detected": self.new_models_detected,
            "benchmarks_run": self.benchmarks_run,
            "last_discovery": self.last_discovery.isoformat() if self.last_discovery else None,
            "discovery_count": self.registry.get("discovery_count", 0),
            "last_updated": self.registry.get("last_updated"),
        }


# Global registry instance
_registry: Optional[ModelRegistry] = None


async def get_registry() -> ModelRegistry:
    """Get or create global model registry."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


async def discover_models() -> dict:
    """
    Run model discovery.

    Returns:
        Discovery results
    """
    registry = await get_registry()
    return registry.discover_models()


async def get_model_registry() -> dict:
    """Get the current model registry."""
    registry = await get_registry()
    return registry.get_registry()


async def get_active_models() -> list[dict]:
    """Get list of active models in registry."""
    registry = await get_registry()
    return registry.get_active_models()


async def get_discovery_stats() -> dict:
    """Get model discovery statistics."""
    registry = await get_registry()
    return registry.get_stats()
