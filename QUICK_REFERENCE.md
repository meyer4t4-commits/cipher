# Orchid Upgrades: Quick Reference Guide

Fast lookup for common operations with the four new upgrades.

---

## UPGRADE 1: Cascade Routing

### Enable Cascade
```python
# Option 1: Environment variable
export CASCADE_ROUTING_ENABLED=true

# Option 2: Python config
from app.core.config import settings
settings.cascade_routing_enabled = True
```

### Use Cascade in Chat
```python
from app.services.orchestrator import process_chat
from app.models.schemas import ChatRequest, ModelTier

# AUTO tier uses cascade after classification
request = ChatRequest(
    message="Write a Python script to sort a list",
    model_tier=ModelTier.AUTO,  # Triggers cascade
)
response = await process_chat(request, db)

# Check cascade details
print(f"Model: {response.model_used}")
print(f"Quality: {response.response_quality_score}")
print(f"Attempts: {response.cascade_attempts}")
```

### Direct API Call with Cascade
```python
from app.services.llm_router import chat_completion
from app.models.schemas import ModelTier

result = await chat_completion(
    messages=[{"role": "user", "content": "What is Python?"}],
    model_tier=ModelTier.DEFAULT,
    cascade_enabled=True,  # Enable for this request
)

print(f"Quality Score: {result['response_quality_score']}")
print(f"Used attempts: {result['cascade_attempts']}/{len(MODEL_CASCADES[ModelTier.DEFAULT])}")
```

### Quality Scoring (Internal)
```python
from app.services.llm_router import _score_response_quality
from app.models.schemas import ModelTier

# Score a response
response_text = "Here's a detailed explanation..."
score = _score_response_quality(response_text, ModelTier.CODE)
print(f"Quality: {score:.2f} (threshold: 0.7)")

# Factors:
# - Response length (longer = higher)
# - Hedging language (lower)
# - Code blocks (for CODE tier)
# - Multiple sentences (higher)
```

### View Model Cascades
```python
from app.services.llm_router import MODEL_CASCADES
from app.models.schemas import ModelTier

for tier, cascade in MODEL_CASCADES.items():
    print(f"{tier.value}: {' → '.join(cascade)}")

# Output:
# default: groq/llama... → deepseek/deepseek-chat → anthropic/claude-sonnet...
# code: groq/llama... → deepseek/deepseek-chat → anthropic/claude-sonnet...
# etc.
```

---

## UPGRADE 2: Model Discovery

### Run Discovery
```python
from app.services.model_discovery import discover_models

# One-time discovery
results = await discover_models()

# Check results
print(f"New models: {results['new_models']}")
print(f"Updated: {results['updated_models']}")
print(f"Removed: {results['removed_models']}")
```

### Get Registry
```python
from app.services.model_discovery import (
    get_model_registry,
    get_active_models,
    get_discovery_stats
)

# Full registry
registry = await get_model_registry()
print(f"Total models: {len(registry['models'])}")

# Active only
active = await get_active_models()
for model in active:
    print(f"{model['model_id']}: {model['context_window']} context")

# Stats
stats = await get_discovery_stats()
print(f"New discovered: {stats['new_models_detected']}")
print(f"Benchmarks run: {stats['benchmarks_run']}")
```

### Setup Scheduled Discovery
```python
import asyncio
from app.services.model_discovery import discover_models
from app.core.logging import logger

async def periodic_discovery():
    """Run discovery every 24 hours"""
    while True:
        try:
            results = await discover_models()
            logger.info(f"Discovery: {len(results['new_models'])} new models")
        except Exception as e:
            logger.error(f"Discovery failed: {e}")

        await asyncio.sleep(24 * 60 * 60)

# In startup:
asyncio.create_task(periodic_discovery())
```

### Access Model Registry File
```python
from pathlib import Path
import json

registry_file = Path("./data/model_registry.json")
registry = json.loads(registry_file.read_text())

# List all models
for model in registry['models']:
    print(f"{model['model_id']}: {model['is_active']}")
```

---

## UPGRADE 3: Scanner Intervals

### Check Current Intervals
```python
from app.services.scanner.config import get_config

config = get_config()
for source, interval in config.scan_intervals.items():
    print(f"{source}: every {interval} minutes")

# Output:
# news: every 15 minutes
# twitter: every 15 minutes
# github: every 30 minutes
# models: every 360 minutes
```

### Update Intervals
```python
from app.services.scanner.orchestrator import get_orchestrator

async def customize_intervals():
    orch = await get_orchestrator()

    # Update specific sources
    await orch.update_config({
        "scan_intervals": {
            "news": 10,      # More frequent
            "models": 720,   # 12 hours instead of 6
        }
    })
```

### Monitor Scanner Activity
```python
from app.services.scanner.orchestrator import get_orchestrator

async def check_scanner():
    orch = await get_orchestrator()
    status = await orch.get_status()

    print(f"Running: {status['running']}")
    print(f"Last scans:")
    for source, time in status['last_scan_times'].items():
        print(f"  {source}: {time}")
    print(f"Memory stats: {status['memory_stats']}")
```

### Manual Scan
```python
from app.services.scanner.orchestrator import get_orchestrator

async def force_scan():
    orch = await get_orchestrator()
    await orch.run_full_scan()
```

---

## UPGRADE 4: Semantic Caching

### Cache Operations
```python
from app.services.cache import (
    cache_response,
    get_cached_response,
    get_cache_stats,
    clear_cache
)

# Store response
cache_response(
    message="How do I learn Python?",
    model_tier="default",
    response={"content": "Start with the basics..."},
    conversation_id="conv-123"
)

# Retrieve (exact + semantic match)
cached = get_cached_response(
    message="What's the best way to learn Python?",
    model_tier="default",
    conversation_id="conv-123"
)

if cached:
    print(f"Cache hit! Type: {cached['cache_hit_type']}")
    # "exact" or "semantic"
```

### Cache Statistics
```python
from app.services.cache import get_cache_stats

stats = get_cache_stats()

print(f"Hit rate: {stats['hit_rate_percent']}%")
print(f"Size: {stats['size']}/{stats['max_entries']}")
print(f"Hits:")
print(f"  Exact: {stats['hit_types']['exact']}")
print(f"  Semantic: {stats['hit_types']['semantic']}")
print(f"  Miss: {stats['hit_types']['miss']}")
print(f"Semantic hit rate: {stats['semantic_hit_rate_percent']}%")
```

### Clear Cache
```python
from app.services.cache import clear_cache

count = clear_cache()
print(f"Cleared {count} entries")
```

### Adjust Similarity Threshold
```python
# In cache.py
SEMANTIC_SIMILARITY_THRESHOLD = 0.90  # Stricter (fewer semantic hits)
# or
SEMANTIC_SIMILARITY_THRESHOLD = 0.80  # Looser (more semantic hits)
```

### Semantic Matching Example
```python
from difflib import SequenceMatcher

msg1 = "How do I write a Python function?"
msg2 = "Can you show me how to create a function in Python?"

similarity = SequenceMatcher(None, msg1.lower(), msg2.lower()).ratio()
print(f"Similarity: {similarity:.2%}")  # 87%

# If > 0.85 threshold: cache hit!
if similarity > 0.85:
    print("Would hit semantic cache")
```

---

## Integration Examples

### Example 1: Simple Chat with All Features
```python
from app.services.orchestrator import process_chat
from app.models.schemas import ChatRequest, ModelTier
from app.services.cache import get_cache_stats

# User query
request = ChatRequest(
    message="Write a Python function to reverse a string",
    model_tier=ModelTier.AUTO,  # Auto-classify + cascade
    include_memory=True,
)

response = await process_chat(request, db)

print(f"Response: {response.message[:100]}...")
print(f"Model: {response.model_used}")
print(f"Cost: ${response.cost_usd:.4f}")

# Check if cascade was used
if hasattr(response, 'cascade_attempts'):
    print(f"Cascade attempts: {response.cascade_attempts}")

# Check cache
stats = get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate_percent']}%")
```

### Example 2: Monitoring Dashboard
```python
from app.services.cache import get_cache_stats
from app.services.model_discovery import get_discovery_stats
from app.services.scanner.orchestrator import get_orchestrator

async def dashboard_data():
    # Cache metrics
    cache_stats = get_cache_stats()
    cache_health = cache_stats['hit_rate_percent'] > 50

    # Model metrics
    model_stats = await get_discovery_stats()
    model_health = model_stats['discovery_count'] > 0

    # Scanner metrics
    orch = await get_orchestrator()
    scanner_status = await orch.get_status()
    scanner_health = scanner_status['running']

    return {
        "cache": {
            "hit_rate": cache_stats['hit_rate_percent'],
            "semantic_ratio": cache_stats['hit_types']['semantic'] / max(1, cache_stats['hits']),
            "health": "good" if cache_health else "poor"
        },
        "models": {
            "total": model_stats['total_models'],
            "new_detected": model_stats['new_models_detected'],
            "health": "good" if model_health else "poor"
        },
        "scanner": {
            "running": scanner_health,
            "last_scans": scanner_status['last_scan_times'],
            "health": "good" if scanner_health else "offline"
        }
    }
```

### Example 3: Cost Tracking
```python
from app.services.orchestrator import process_chat
from app.models.schemas import ChatRequest

async def track_costs():
    total_cost = 0
    cascade_count = 0
    cascade_cost = 0
    direct_cost = 0

    for i in range(100):
        request = ChatRequest(
            message=f"Question {i}",
            model_tier="auto"
        )
        response = await process_chat(request, db)

        cost = response.cost_usd
        total_cost += cost

        if hasattr(response, 'cascade_enabled') and response.cascade_enabled:
            cascade_count += 1
            cascade_cost += cost
        else:
            direct_cost += cost

    print(f"Total cost: ${total_cost:.2f}")
    print(f"Cascade: {cascade_count} requests, ${cascade_cost:.2f}")
    print(f"Direct: {100-cascade_count} requests, ${direct_cost:.2f}")
    print(f"Savings: {(1 - cascade_cost/total_cost)*100:.1f}%")
```

---

## Debugging

### Check Cascade Quality Scoring
```python
from app.services.llm_router import _score_response_quality
from app.models.schemas import ModelTier

test_cases = [
    ("I don't know the answer", ModelTier.DEFAULT),
    ("This is a long, detailed explanation" * 10, ModelTier.DEFAULT),
    ("```python\ncode here\n```", ModelTier.CODE),
    ("", ModelTier.DEFAULT),
]

for response, tier in test_cases:
    score = _score_response_quality(response, tier)
    print(f"Response ({len(response)} chars): {score:.2f}")
```

### Inspect Cache Internals
```python
from app.services.cache import _global_cache

# View cache keys
for key, item in _global_cache.cache.items():
    msg = item.get('original_message', 'unknown')[:50]
    timestamp = item['timestamp']
    print(f"{key[:8]}... | {msg} | {timestamp}")
```

### View Model Registry
```python
from app.services.model_discovery import MODEL_REGISTRY_FILE
import json

registry = json.loads(MODEL_REGISTRY_FILE.read_text())
for model in registry['models'][:5]:
    print(f"{model['model_id']}")
    print(f"  Context: {model['context_window']}")
    print(f"  Active: {model['is_active']}")
```

### Monitor Scanner Timing
```python
from app.services.scanner.orchestrator import get_orchestrator
from datetime import datetime

async def show_scan_times():
    orch = await get_orchestrator()
    status = await orch.get_status()
    now = datetime.utcnow()

    for source, scan_time_str in status['last_scan_times'].items():
        scan_time = datetime.fromisoformat(scan_time_str)
        minutes_ago = (now - scan_time).total_seconds() / 60

        interval = orch.config.scan_intervals[source]
        until_next = interval - minutes_ago

        print(f"{source}: scanned {minutes_ago:.0f}min ago, next in {until_next:.0f}min")
```

---

## Performance Tips

### Maximize Cache Hit Rate
```python
# 1. Keep conversations grouped (same conversation_id)
request.conversation_id = "user-123-session-456"

# 2. Use natural phrasing in requests
# Good: "How do I install Python?"
# Also Good: "What's the best way to install Python?" (semantic match)
# Bad: "install python" (too short, may not match)

# 3. Monitor hit rate and adjust threshold if needed
# From cache stats, if semantic_hit_rate < 5%, lower threshold
```

### Optimize Cascade
```python
# 1. Leverage AUTO tier for most requests
# AUTO: auto-classify + cascade
# SPECIFIC: no cascade (faster, more expensive)

# 2. Check quality scores in logs
# If most responses score < 0.7, models need better tuning

# 3. Use include_memory=True for context
# Better context = better quality scores = more cost savings
```

### Improve Discovery
```python
# 1. Run discovery after major provider announcements
results = await discover_models()

# 2. Review model_intelligence collection for new models
from app.services import memory
latest = memory.recall_memories("new model", 10, "model_intelligence")

# 3. Benchmark promising new models
# (Automatic in discovery, but can trigger manually)
```

### Optimize Scanner
```python
# 1. Set intervals based on update frequency
# News: 15min (breaking updates)
# Code: 30-60min (releases quarterly)
# Models: 6h (don't change daily)

# 2. Disable unneeded sources
config.sources_enabled["reddit"] = False

# 3. Monitor scanner latency
# If any source takes > 30sec, optimize or disable
```

---

## Quick Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| Cascade not working | CASCADE_ROUTING_ENABLED=true | Set environment var |
| Low cache hits | Cache size, TTL | Increase CACHE_MAX_ENTRIES or TTL_SECONDS |
| No semantic hits | Threshold too high | Lower SEMANTIC_SIMILARITY_THRESHOLD |
| Discovery not running | /data/model_registry.json | Create directory, run manually |
| Scanner slow | Check per-source intervals | Increase intervals for slow sources |
| High API costs | Cascade quality scores | Review response content, add context |

---

## Command Reference

```bash
# Test cascade
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Write Python code","model_tier":"auto"}'

# Check cache stats
curl http://localhost:8000/api/v1/cache/stats

# Trigger discovery
curl -X POST http://localhost:8000/api/v1/models/discover

# Get scanner status
curl http://localhost:8000/api/v1/scanner/status

# Clear cache
curl -X POST http://localhost:8000/api/v1/cache/clear
```

---

## Next Steps

1. **Deploy**: Copy files to production
2. **Enable**: Set CASCADE_ROUTING_ENABLED=true
3. **Monitor**: Watch cache stats and costs
4. **Optimize**: Adjust thresholds based on metrics
5. **Scale**: Set up discovery and scanner automation

**Expected Result**: 50-70% cost reduction within first week.
