# Auto-Routing System API Reference

## Classifier Module

### Import
```python
from app.services.classifier import auto_classify, MessageClassifier
```

### Functions

#### `auto_classify(message: str) -> Tuple[ModelTier, float]`

Auto-classify a message to the optimal model tier.

**Parameters:**
- `message` (str): The user's message to classify

**Returns:**
- Tuple of (ModelTier, confidence_score)
- confidence_score ranges from 0.0 to 1.0

**Example:**
```python
tier, confidence = auto_classify("Write a Python function to sort a list")
# Returns: (ModelTier.CODE, 0.95)

print(f"Tier: {tier.value}, Confidence: {confidence:.2f}")
# Output: Tier: code, Confidence: 0.95
```

**Tier Mapping:**
- `ModelTier.CODE`: Technical/programming requests (confidence > 0.7)
- `ModelTier.REASONING`: Analytical/strategic requests (confidence > 0.7)
- `ModelTier.FAST`: Simple queries or short messages (confidence > 0.7)
- `ModelTier.DEFAULT`: General/mixed content (default fallback)

---

### MessageClassifier Class

#### `MessageClassifier.classify(message: str) -> Tuple[ModelTier, float]`

Core classification method (same as `auto_classify`).

**Example:**
```python
tier, confidence = MessageClassifier.classify("What is Python?")
# Returns: (ModelTier.FAST, 0.85)
```

#### `MessageClassifier.get_classification_details(message: str) -> dict`

Get detailed classification information for debugging.

**Returns:**
```python
{
    "tier": "code",                          # Selected tier
    "confidence": 0.95,                      # Confidence score
    "message_length": 45,                    # Character count
    "code_keywords_found": ["write", ...],   # Top 5 keywords
    "reasoning_keywords_found": [],          # Top 5 keywords
    "simple_keywords_found": [],             # Top 5 keywords
    "is_short_message": False,               # Length check
    "matches_simple_pattern": False,         # Pattern match
}
```

**Example:**
```python
details = MessageClassifier.get_classification_details(
    "Debug this error: NameError at line 42"
)

print(details["tier"])  # "code"
print(details["confidence"])  # 0.88
print(details["code_keywords_found"])  # ["debug", "error"]
```

---

## Cache Module

### Import
```python
from app.services.cache import (
    get_cached_response,
    cache_response,
    clear_cache,
    get_cache_stats,
    get_cache_size,
    prune_expired,
)
```

### Functions

#### `get_cached_response(message: str, model_tier: str, conversation_id: str = None) -> Optional[dict]`

Retrieve a cached response if it exists and hasn't expired.

**Parameters:**
- `message` (str): The user message
- `model_tier` (str): The model tier (e.g., "code", "reasoning")
- `conversation_id` (str, optional): Conversation ID

**Returns:**
- Cached response dict, or None if not found/expired
- Response dict has keys: `content`, `model_used`, `total_tokens`, `cost_usd`, etc.

**Example:**
```python
cached = get_cached_response(
    message="What is Python?",
    model_tier="fast",
    conversation_id="conv_123"
)

if cached:
    print(f"Found cached response: {cached['content']}")
else:
    print("Not in cache, will fetch from API")
```

#### `cache_response(message: str, model_tier: str, response: dict, conversation_id: str = None) -> None`

Store a response in the cache.

**Parameters:**
- `message` (str): The user message
- `model_tier` (str): The model tier used
- `response` (dict): The response to cache
- `conversation_id` (str, optional): Conversation ID

**Example:**
```python
response = {
    "content": "Python is a programming language",
    "model_used": "groq/llama-3.3-70b-versatile",
    "total_tokens": 150,
    "cost_usd": 0.0001,
}

cache_response(
    message="What is Python?",
    model_tier="fast",
    response=response,
    conversation_id="conv_123"
)
```

#### `clear_cache() -> int`

Clear all cached entries.

**Returns:** Number of entries cleared

**Example:**
```python
count = clear_cache()
print(f"Cleared {count} cache entries")
```

#### `get_cache_stats() -> dict`

Get cache statistics for monitoring.

**Returns:**
```python
{
    "size": 342,                    # Current entries
    "max_entries": 1000,            # Max capacity
    "hits": 1250,                   # Cache hits
    "misses": 450,                  # Cache misses
    "total_accesses": 1700,         # Total requests
    "hit_rate_percent": 73.53,      # Hit rate
    "ttl_seconds": 3600             # Time-to-live
}
```

**Example:**
```python
stats = get_cache_stats()

if stats["hit_rate_percent"] > 50:
    print("Good cache performance!")
else:
    print("Cache hit rate is low, check for variations in messages")

print(f"Cache: {stats['size']}/{stats['max_entries']} entries")
```

#### `get_cache_size() -> int`

Get current number of cached entries.

**Example:**
```python
size = get_cache_size()
print(f"Cache has {size} entries")
```

#### `prune_expired() -> int`

Remove all expired entries from the cache.

**Returns:** Number of entries pruned

**Example:**
```python
pruned = prune_expired()
print(f"Pruned {pruned} expired entries")
```

---

## LRUCache Class

### Import
```python
from app.services.cache import LRUCache
```

### Constructor

#### `LRUCache(max_entries: int = 1000, ttl_seconds: int = 3600)`

Create a new LRU cache instance.

**Parameters:**
- `max_entries` (int): Maximum cached entries (default: 1000)
- `ttl_seconds` (int): Time-to-live in seconds (default: 3600 = 1 hour)

**Example:**
```python
# Create custom cache
cache = LRUCache(max_entries=5000, ttl_seconds=7200)

# All methods same as global cache
cached = cache.get_cached_response("msg", "code")
cache.cache_response("msg", "code", response)
stats = cache.get_cache_stats()
```

---

## Usage Examples

### Complete Classification + Caching Pipeline

```python
from app.services.classifier import auto_classify
from app.services.cache import get_cached_response, cache_response

# User sends a message
user_message = "Write a Python function to validate email addresses"

# 1. Auto-classify the message
model_tier, confidence = auto_classify(user_message)
print(f"Classified as: {model_tier.value} (confidence: {confidence:.2f})")
# Output: Classified as: code (confidence: 0.93)

# 2. Check cache
cached_response = get_cached_response(
    message=user_message,
    model_tier=model_tier.value,
    conversation_id="conv_456"
)

if cached_response:
    print("Cache hit! Using cached response")
    response = cached_response
else:
    print("Cache miss, calling API")
    # Call API (simulated)
    response = {
        "content": "Here's a Python email validator...",
        "model_used": "deepseek/deepseek-chat",
        "total_tokens": 256,
        "cost_usd": 0.0008,
    }
    
    # 3. Cache the response
    cache_response(
        message=user_message,
        model_tier=model_tier.value,
        response=response,
        conversation_id="conv_456"
    )
    print("Response cached for future use")

print(f"Response: {response['content'][:100]}...")
```

### Monitoring Cache Health

```python
from app.services.cache import get_cache_stats
from app.services.classifier import MessageClassifier

# Monitor cache
stats = get_cache_stats()

print(f"Cache Statistics:")
print(f"  Size: {stats['size']}/{stats['max_entries']}")
print(f"  Hit rate: {stats['hit_rate_percent']:.1f}%")
print(f"  Hits: {stats['hits']}, Misses: {stats['misses']}")

# If hit rate is low, check classification
message = "What is the weather in New York?"
details = MessageClassifier.get_classification_details(message)

print(f"Classification Details:")
print(f"  Tier: {details['tier']}")
print(f"  Confidence: {details['confidence']}")
print(f"  Keywords: {details['code_keywords_found']}")
```

### Debugging Classification

```python
from app.services.classifier import MessageClassifier

# Test various messages
test_messages = [
    "What is Python?",
    "Write a function to sort a list",
    "Compare microservices vs monolithic architecture",
    "Hello, how are you?",
]

for msg in test_messages:
    details = MessageClassifier.get_classification_details(msg)
    print(f"Message: {msg}")
    print(f"  → Tier: {details['tier']} (confidence: {details['confidence']})")
    print()
```

---

## Configuration Examples

### Adjust Cache Settings

```python
# In cache.py, modify these constants:
CACHE_MAX_ENTRIES = 5000    # Increase for more storage
CACHE_TTL_SECONDS = 7200    # 2 hours instead of 1 hour
```

### Add Custom Keywords

```python
# In classifier.py, add to CODE_KEYWORDS:
CODE_KEYWORDS = {
    "write", "build", ...,
    "postgresql",  # New keyword
    "typescript",  # New keyword
}

# Or add to REASONING_KEYWORDS:
REASONING_KEYWORDS = {
    "analyze", "compare", ...,
    "prediction",  # New keyword
    "forecast",    # New keyword
}
```

---

## Integration with Orchestrator

```python
# In orchestrator.py, the system automatically:

# 1. Auto-classifies (if model_tier == AUTO)
model_tier = request.model_tier
if model_tier == ModelTier.AUTO:
    model_tier, confidence = auto_classify(request.message)

# 2. Checks cache before expensive operations
cached = get_cached_response(
    message=request.message,
    model_tier=model_tier.value,
    conversation_id=conversation_id,
)
if cached:
    return ChatResponse(...)

# 3. Caches response after API call
result = await chat_completion(...)
cache_response(
    message=request.message,
    model_tier=model_tier.value,
    response=result,
    conversation_id=conversation_id,
)
```

---

## Error Handling

```python
from app.services.classifier import auto_classify
from app.services.cache import get_cached_response

# Classifier handles edge cases gracefully
tier, conf = auto_classify("")  # Empty string → DEFAULT, 0.5
tier, conf = auto_classify(None)  # None → DEFAULT, 0.5
tier, conf = auto_classify("x" * 10000)  # Very long → still works

# Cache handles missing entries gracefully
result = get_cached_response(
    message="nonexistent",
    model_tier="code"
)
assert result is None  # Returns None, doesn't raise exception
```

---

## Performance Tips

1. **Cache hits**: Ensure consistent message formatting (no extra spaces, timestamps)
2. **Classification**: Run on every request (sub-millisecond, negligible cost)
3. **Cache size**: Monitor with `get_cache_stats()`, prune if needed
4. **TTL**: Adjust based on conversation duration (default 1 hour is good)
5. **Keywords**: Add domain-specific keywords for better accuracy

---

## Version Info

- Created: 2024-02-26
- Status: Production-ready
- Python: 3.7+
- Dependencies: None (stdlib only)
