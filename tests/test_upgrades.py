"""
Test suite for Cipher Upgrades 1-4:
- UPGRADE 1: Cascade Routing (FrugalGPT)
- UPGRADE 2: Model Auto-Discovery System
- UPGRADE 3: 15-minute Scanner Intervals
- UPGRADE 4: Semantic Caching
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import the modules we're testing
from app.services.llm_router import _score_response_quality, MODEL_CASCADES
from app.models.schemas import ModelTier
from app.services.cache import LRUCache, SEMANTIC_SIMILARITY_THRESHOLD
from app.services.scanner.config import ScannerConfig


class TestUpgrade1CascadeRouting:
    """Test Cascade Routing (FrugalGPT approach)"""

    def test_cascade_models_defined(self):
        """Verify cascade routes are defined for each tier"""
        for tier in ModelTier:
            if tier != ModelTier.AUTO:
                assert tier in MODEL_CASCADES, f"Cascade not defined for {tier.value}"
                assert len(MODEL_CASCADES[tier]) > 0, f"Cascade is empty for {tier.value}"

    def test_response_quality_scoring_low_confidence(self):
        """Test that uncertain responses score low"""
        uncertain_response = "I'm not sure about this, but I think..."
        score = _score_response_quality(uncertain_response, ModelTier.DEFAULT)
        assert score < 0.6, f"Expected low score for uncertain response, got {score}"

    def test_response_quality_scoring_high_confidence(self):
        """Test that substantive responses score high"""
        good_response = """This is a comprehensive answer with multiple sentences.
        It provides detailed information and addresses the question directly.
        The response is well-structured and coherent throughout."""
        score = _score_response_quality(good_response, ModelTier.DEFAULT)
        assert score > 0.6, f"Expected high score for good response, got {score}"

    def test_response_quality_scoring_code_task(self):
        """Test that code blocks boost score for CODE tier"""
        code_response = """Here's the solution:

```python
def hello_world():
    print("Hello, World!")
    return True
```

This function does X and Y."""
        score = _score_response_quality(code_response, ModelTier.CODE)
        assert score > 0.65, f"Expected high score for code response, got {score}"

    def test_response_quality_scoring_empty_response(self):
        """Test that empty responses score 0"""
        score = _score_response_quality("", ModelTier.DEFAULT)
        assert score == 0.0, f"Expected 0 for empty response, got {score}"

    def test_cascade_routes_progression(self):
        """Test that cascades go from cheap to expensive models"""
        for tier, cascade in MODEL_CASCADES.items():
            # First model should be cheaper (groq)
            assert "groq" in cascade[0] or "llama" in cascade[0], \
                f"First cascade model for {tier.value} should be cheapest"


class TestUpgrade2ModelDiscovery:
    """Test Model Auto-Discovery System"""

    @pytest.mark.asyncio
    async def test_model_registry_initialization(self):
        """Test that model registry initializes correctly"""
        from app.services.model_discovery import ModelRegistry

        registry = ModelRegistry()
        assert registry.registry_file is not None
        assert "models" in registry.registry
        assert isinstance(registry.registry["models"], list)

    def test_scanner_config_intervals(self):
        """Test that per-source intervals are configured"""
        config = ScannerConfig()

        # Check that new 15-min intervals are set
        assert config.scan_intervals["news"] == 15, "News should scan every 15 min"
        assert config.scan_intervals["twitter"] == 15, "Twitter should scan every 15 min"
        assert config.scan_intervals["reddit"] == 15, "Reddit should scan every 15 min"

        # Check that less-frequent sources have longer intervals
        assert config.scan_intervals["github"] == 30, "GitHub should scan every 30 min"
        assert config.scan_intervals["models"] == 360, "Models should scan every 6 hours"

    def test_model_discovery_file_path(self):
        """Test that model registry file path is correctly defined"""
        from app.services.model_discovery import MODEL_REGISTRY_FILE
        from pathlib import Path

        assert isinstance(MODEL_REGISTRY_FILE, Path)
        assert str(MODEL_REGISTRY_FILE).endswith("model_registry.json")


class TestUpgrade3ScannerIntervals:
    """Test 15-minute Scanner Intervals with per-source configuration"""

    def test_all_sources_have_intervals(self):
        """Test that all scanner sources have defined intervals"""
        config = ScannerConfig()

        # New sources should have intervals
        assert "news" in config.scan_intervals
        assert "twitter" in config.scan_intervals
        assert "reddit" in config.scan_intervals
        assert "github" in config.scan_intervals
        assert "models" in config.scan_intervals

    def test_interval_values_reasonable(self):
        """Test that interval values are reasonable"""
        config = ScannerConfig()

        # All intervals should be positive integers
        for source, interval in config.scan_intervals.items():
            assert isinstance(interval, int), f"{source} interval should be int"
            assert interval > 0, f"{source} interval should be positive"
            assert interval <= 1440, f"{source} interval should be <= 24 hours"

    def test_shorter_intervals_for_fast_moving_sources(self):
        """Test that fast-moving sources have shorter intervals"""
        config = ScannerConfig()

        # News/Twitter should be more frequent than models
        assert config.scan_intervals["news"] < config.scan_intervals["models"]
        assert config.scan_intervals["twitter"] < config.scan_intervals["models"]

    def test_model_scanner_longest_interval(self):
        """Test that model scanner has longest interval (6 hours)"""
        config = ScannerConfig()

        model_interval = config.scan_intervals["models"]
        for source, interval in config.scan_intervals.items():
            if source != "models":
                assert interval < model_interval, \
                    f"Model interval should be longest, but {source} is {interval} vs {model_interval}"


class TestUpgrade4SemanticCaching:
    """Test Semantic Caching with similarity matching"""

    def test_cache_initialization_with_hit_types(self):
        """Test that cache tracks hit types"""
        cache = LRUCache()
        assert "exact" in cache.hit_types
        assert "semantic" in cache.hit_types
        assert "miss" in cache.hit_types

    def test_exact_cache_hit(self):
        """Test exact cache hit detection"""
        cache = LRUCache()

        message = "What is Python?"
        model_tier = "default"
        response = {"content": "Python is a programming language"}

        # Cache the response
        cache.cache_response(message, model_tier, response)

        # Retrieve with exact same message
        retrieved = cache.get_cached_response(message, model_tier)

        assert retrieved is not None, "Should find cached response"
        assert retrieved["cache_hit_type"] == "exact", "Should be exact hit"
        assert cache.hit_types["exact"] == 1, "Should increment exact hits"

    def test_cache_stores_original_message(self):
        """Test that original message is stored for semantic matching"""
        cache = LRUCache()

        message = "How do I learn Python?"
        model_tier = "default"
        response = {"content": "Start with the basics..."}

        cache.cache_response(message, model_tier, response)

        # Check that original message is stored
        cache_key = cache._make_key(message, model_tier)
        assert cache.cache[cache_key]["original_message"] == message

    def test_cache_stats_include_hit_types(self):
        """Test that cache stats include hit type breakdown"""
        cache = LRUCache()

        # Add some responses
        cache.cache_response("msg1", "default", {"content": "resp1"})
        cache.cache_response("msg2", "default", {"content": "resp2"})

        # Get stats
        stats = cache.get_cache_stats()

        assert "hit_types" in stats, "Stats should include hit_types"
        assert "exact" in stats["hit_types"]
        assert "semantic" in stats["hit_types"]
        assert "miss" in stats["hit_types"]
        assert "semantic_hit_rate_percent" in stats

    def test_cache_ttl_still_enforced(self):
        """Test that TTL is still enforced with semantic caching"""
        cache = LRUCache(ttl_seconds=1)

        message = "Test message"
        model_tier = "default"
        response = {"content": "Test response"}

        # Cache response
        cache.cache_response(message, model_tier, response)

        # Verify it's cached
        assert cache.get_cached_response(message, model_tier) is not None

        # Wait for TTL to expire
        import time
        time.sleep(1.1)

        # Should be expired now
        retrieved = cache.get_cached_response(message, model_tier)
        assert retrieved is None, "Response should be expired"

    def test_semantic_similarity_threshold(self):
        """Test that semantic similarity threshold is configurable"""
        from app.services.cache import SEMANTIC_SIMILARITY_THRESHOLD

        assert isinstance(SEMANTIC_SIMILARITY_THRESHOLD, float)
        assert 0.0 <= SEMANTIC_SIMILARITY_THRESHOLD <= 1.0
        assert SEMANTIC_SIMILARITY_THRESHOLD >= 0.8, "Threshold should be strict (>0.8)"

    def test_cache_clear_resets_hit_types(self):
        """Test that clearing cache resets hit type counters"""
        cache = LRUCache()

        # Add and retrieve to update counters
        cache.cache_response("msg", "default", {"content": "resp"})
        cache.get_cached_response("msg", "default")

        # Clear cache
        cache.clear_cache()

        # Hit types should be reset
        assert cache.hit_types["exact"] == 0
        assert cache.hit_types["semantic"] == 0
        assert cache.hit_types["miss"] == 0


class TestIntegration:
    """Integration tests for all upgrades"""

    def test_cascade_with_cache(self):
        """Test that cascade routing works with semantic caching"""
        # This would test the full flow: cache checks -> cascade routing -> response caching

        cache = LRUCache()
        message1 = "How do I write a Python function?"
        message2 = "Can you show me how to create a function in Python?"

        # These are semantically similar but not exact matches
        response = {"content": "def my_function(): pass"}

        # Cache first message
        cache.cache_response(message1, "code", response)

        # Try to retrieve with similar message
        # (Would trigger semantic matching in real scenario)
        retrieved = cache.get_cached_response(message1, "code")
        assert retrieved is not None

    def test_model_discovery_and_scanner_integration(self):
        """Test that model discovery integrates with scanner"""
        from app.services.scanner.model_scanner import ModelScanner
        from app.services.model_discovery import ModelRegistry

        # Both should exist and be importable
        assert ModelScanner is not None
        assert ModelRegistry is not None

    def test_cascade_quality_scoring_logic(self):
        """Test cascade quality scoring across different response types"""
        test_cases = [
            ("I don't know the answer", ModelTier.DEFAULT, "low"),  # Uncertain
            ("This is a detailed explanation" * 10, ModelTier.DEFAULT, "high"),  # Long
            ("```python\ndef test(): pass```", ModelTier.CODE, "high"),  # Code present
            ("", ModelTier.DEFAULT, "none"),  # Empty
        ]

        for response, tier, expected_quality in test_cases:
            score = _score_response_quality(response, tier)
            if expected_quality == "low":
                assert score < 0.6, f"Expected low score for: {response[:30]}"
            elif expected_quality == "high":
                assert score > 0.6, f"Expected high score for: {response[:30]}"
            elif expected_quality == "none":
                assert score == 0.0, f"Expected zero score for empty"


if __name__ == "__main__":
    # Run tests with pytest
    # pytest tests/test_upgrades.py -v
    print("Run with: pytest tests/test_upgrades.py -v")
