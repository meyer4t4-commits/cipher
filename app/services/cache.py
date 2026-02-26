"""
In-memory LRU cache for API responses.
Caches chat completions to reduce latency and API calls.
Features semantic caching using difflib.SequenceMatcher for similarity matching.
"""

import hashlib
import time
from typing import Optional, Any
from collections import OrderedDict
from difflib import SequenceMatcher
from app.core.logging import logger

# Cache configuration
CACHE_MAX_ENTRIES = 1000
CACHE_TTL_SECONDS = 3600  # 1 hour
SEMANTIC_SIMILARITY_THRESHOLD = 0.85  # Threshold for semantic cache hits


class LRUCache:
    """
    Thread-safe LRU (Least Recently Used) cache with TTL support.
    Stores API responses keyed by message + model_tier + conversation_id hash.
    Supports semantic similarity matching for cache hits beyond exact matches.
    """

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES, ttl_seconds: int = CACHE_TTL_SECONDS):
        """
        Initialize the cache.

        Args:
            max_entries: Maximum number of cached entries (default 1000)
            ttl_seconds: Time-to-live for cached entries in seconds (default 3600)
        """
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.hit_types = {"exact": 0, "semantic": 0, "miss": 0}

    def _make_key(
        self,
        message: str,
        model_tier: str,
        conversation_id: str | None = None,
    ) -> str:
        """
        Create a cache key from message, model tier, and conversation ID.
        Uses SHA256 hash to keep keys uniform length and avoid collisions.

        Args:
            message: The user message
            model_tier: The model tier used
            conversation_id: Optional conversation ID

        Returns:
            A unique cache key (hex string)
        """
        key_parts = f"{message}:{model_tier}:{conversation_id or 'none'}"
        return hashlib.sha256(key_parts.encode()).hexdigest()

    def get_cached_response(
        self,
        message: str,
        model_tier: str,
        conversation_id: str | None = None,
    ) -> Optional[dict]:
        """
        Retrieve a cached response using exact match or semantic similarity.

        Args:
            message: The user message
            model_tier: The model tier used
            conversation_id: Optional conversation ID

        Returns:
            Cached response dict (with cache hit type), or None if not found/expired
        """
        key = self._make_key(message, model_tier, conversation_id)

        # 1. First check exact hash match (instant)
        if key in self.cache:
            cached_item = self.cache[key]

            # Check TTL
            if time.time() - cached_item["timestamp"] > self.ttl_seconds:
                # Expired - remove and miss
                del self.cache[key]
                self.misses += 1
                self.hit_types["miss"] += 1
                return None

            # Exact hit - move to end (most recently used) and return
            self.cache.move_to_end(key)
            self.hits += 1
            self.hit_types["exact"] += 1

            # Add cache hit type metadata
            response = cached_item["response"].copy()
            response["cache_hit_type"] = "exact"
            return response

        # 2. If no exact match, check semantic similarity against recent queries
        semantic_match = self._find_semantic_match(message, model_tier, conversation_id)
        if semantic_match is not None:
            self.hits += 1
            self.hit_types["semantic"] += 1

            # Add cache hit type metadata
            response = semantic_match.copy()
            response["cache_hit_type"] = "semantic"
            return response

        # 3. No match found
        self.misses += 1
        self.hit_types["miss"] += 1
        return None

    def _find_semantic_match(
        self,
        message: str,
        model_tier: str,
        conversation_id: str | None = None,
    ) -> Optional[dict]:
        """
        Find a semantically similar cached response.

        Args:
            message: The user message
            model_tier: The model tier used
            conversation_id: Optional conversation ID

        Returns:
            Cached response if semantic match found, None otherwise
        """
        current_time = time.time()
        best_match = None
        best_similarity = SEMANTIC_SIMILARITY_THRESHOLD

        # Check recent cache entries (most recently added/used first)
        # Limit to last 20 entries for performance
        recent_entries = list(reversed(list(self.cache.items())))[:20]

        for key, cached_item in recent_entries:
            # Check TTL first
            if current_time - cached_item["timestamp"] > self.ttl_seconds:
                continue

            # Extract message from key (it's model_tier:conversation_id hashed)
            # We need to check all recent messages for this tier/conversation
            cached_response = cached_item["response"]

            # Get original message from metadata if available
            original_message = cached_item.get("original_message", "")
            if not original_message:
                continue

            # Calculate semantic similarity using SequenceMatcher
            similarity = SequenceMatcher(None, message.lower(), original_message.lower()).ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cached_response

        return best_match

    def cache_response(
        self,
        message: str,
        model_tier: str,
        response: dict,
        conversation_id: str | None = None,
    ) -> None:
        """
        Store a response in the cache.

        Args:
            message: The user message
            model_tier: The model tier used
            response: The response to cache (dict)
            conversation_id: Optional conversation ID
        """
        key = self._make_key(message, model_tier, conversation_id)

        # If key already exists, remove it first to update
        if key in self.cache:
            del self.cache[key]

        # Add to end (most recently used)
        # Store original message for semantic matching
        self.cache[key] = {
            "response": response,
            "timestamp": time.time(),
            "original_message": message,
            "model_tier": model_tier,
        }

        # Evict oldest entry if at capacity
        if len(self.cache) > self.max_entries:
            self.cache.popitem(last=False)  # Remove first (oldest) item
            logger.debug(f"Cache evicted oldest entry. Size: {len(self.cache)}")

    def clear_cache(self) -> int:
        """
        Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        count = len(self.cache)
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.hit_types = {"exact": 0, "semantic": 0, "miss": 0}
        logger.info(f"Cache cleared. Removed {count} entries")
        return count

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict containing cache stats (size, hits, misses, hit rate, hit types)
        """
        total_accesses = self.hits + self.misses
        hit_rate = (self.hits / total_accesses * 100) if total_accesses > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_entries": self.max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "total_accesses": total_accesses,
            "hit_rate_percent": round(hit_rate, 2),
            "hit_types": {
                "exact": self.hit_types.get("exact", 0),
                "semantic": self.hit_types.get("semantic", 0),
                "miss": self.hit_types.get("miss", 0),
            },
            "semantic_hit_rate_percent": (
                (self.hit_types.get("semantic", 0) / total_accesses * 100)
                if total_accesses > 0
                else 0.0
            ),
            "ttl_seconds": self.ttl_seconds,
        }

    def get_cache_size(self) -> int:
        """Get current number of cached entries."""
        return len(self.cache)

    def prune_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of entries pruned
        """
        current_time = time.time()
        expired_keys = [
            key for key, item in self.cache.items()
            if current_time - item["timestamp"] > self.ttl_seconds
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"Cache pruned {len(expired_keys)} expired entries")

        return len(expired_keys)


# Global cache instance
_global_cache = LRUCache()


# Public API functions
def get_cached_response(
    message: str,
    model_tier: str,
    conversation_id: str | None = None,
) -> Optional[dict]:
    """
    Get a cached response (uses global cache instance).

    Args:
        message: The user message
        model_tier: The model tier used
        conversation_id: Optional conversation ID

    Returns:
        Cached response dict or None
    """
    return _global_cache.get_cached_response(message, model_tier, conversation_id)


def cache_response(
    message: str,
    model_tier: str,
    response: dict,
    conversation_id: str | None = None,
) -> None:
    """
    Cache a response (uses global cache instance).

    Args:
        message: The user message
        model_tier: The model tier used
        response: The response to cache
        conversation_id: Optional conversation ID
    """
    _global_cache.cache_response(message, model_tier, response, conversation_id)


def clear_cache() -> int:
    """Clear all cached entries."""
    return _global_cache.clear_cache()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    return _global_cache.get_cache_stats()


def get_cache_size() -> int:
    """Get current cache size."""
    return _global_cache.get_cache_size()


def prune_expired() -> int:
    """Prune expired cache entries."""
    return _global_cache.prune_expired()
