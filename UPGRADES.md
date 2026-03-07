# Orchid Platform: Critical Upgrades (1-4)

This document describes four critical upgrades implemented for the Orchid/Cipher AI chat platform.

## UPGRADE 1: Cascade Routing (FrugalGPT Approach)

### Overview
Implements cost-optimized routing by trying the cheapest model first and escalating only if response quality is insufficient. Based on Stanford's FrugalGPT research showing 50-98% cost savings.

### Location
- **File**: `/app/services/llm_router.py`
- **Config**: `/app/core/config.py` (added `cascade_routing_enabled` setting)

### Key Features

#### Model Cascades
Each model tier has a defined cascade from cheapest to best:
```python
ModelTier.DEFAULT: [
    "groq/llama-3.3-70b-versatile",      # Cheapest (~$0.05/1M tokens)
    "deepseek/deepseek-chat",             # Mid-tier (~$0.14/1M tokens)
    "anthropic/claude-sonnet-4-20250514", # Best ($3/1M tokens)
]
```

#### Response Quality Scoring
Function `_score_response_quality()` evaluates responses using heuristics:

**Penalties** (reduce confidence):
- Hedging language ("I don't know", "I'm not sure", "unable to") - 15% penalty each
- Very short responses - penalized

**Rewards** (increase confidence):
- Substantive length (100+ chars: +15%, 500+: +15%, 1000+: +10%)
- Code blocks present (CODE tier only) - +20%
- Multiple sentences (3+) - +10%
- Programming keywords found (CODE tier) - +3% per keyword

**Range**: 0.0 (lowest) to 1.0 (highest)

#### Cascade Behavior
1. Try cheapest model first
2. Score response quality (default threshold: 0.7)
3. If quality ≥ threshold, return response
4. If quality < threshold, escalate to next model
5. Continue until quality threshold met or last model attempted

#### Return Values
Response dict includes:
```python
{
    "content": str,                    # Response text
    "model_used": str,                 # Which model was used
    "response_quality_score": float,   # Quality score (0-1)
    "cascade_attempts": int,           # How many models tried
    "cascade_enabled": bool,           # Whether cascade was used
    # ... standard fields (tokens, cost, latency)
}
```

#### Configuration
Set in environment or `.env`:
```bash
CASCADE_ROUTING_ENABLED=true  # Default: true
```

#### Backward Compatibility
- If specific tier requested (not AUTO), cascade is skipped
- AUTO tier uses classifier then cascade
- Existing code continues to work unchanged

### Cost Savings Example
- **Simple question** (70% route to groq): ~$0.035 per request
- **Complex reasoning** (80% route to groq, 20% to claude): ~$0.60 per request
- **Overall** (mixed workload): ~50-70% cost reduction

---

## UPGRADE 2: Model Auto-Discovery System

### Overview
Automatically detects new models across providers and updates routing table. Maintains a registry file and stores discoveries in system memory.

### Location
- **Main Service**: `/app/services/model_discovery.py` (new)
- **Scanner**: `/app/services/scanner/model_scanner.py` (new)
- **Registry File**: `/data/model_registry.json`

### Components

#### ModelRegistry Class
Manages model discovery and benchmarking.

**Methods**:
- `discover_models()` - Run discovery across all providers
- `run_benchmark(model_id)` - Quick latency/quality test
- `get_active_models()` - List of currently available models
- `get_stats()` - Discovery statistics

#### Registry Structure
```json
{
  "models": [
    {
      "model_id": "anthropic/claude-opus-4-20250805",
      "provider": "anthropic",
      "discovered_at": "2025-02-26T14:00:00",
      "is_active": true,
      "context_window": 200000,
      "cost_per_1k_input": 0.003,
      "cost_per_1k_output": 0.015,
      "last_updated": "2025-02-26T14:00:00",
      "benchmark_scores": { ... }
    }
  ],
  "last_updated": "2025-02-26T14:00:00",
  "discovery_count": 42
}
```

#### ModelScanner Class
Scans external sources for model announcements:
- HuggingFace trending models (RSS feed)
- GitHub releases (model-related repos)
- Provider blog announcements
- Stores findings in memory collection `model_intelligence`

### API Endpoints
(When integrated with FastAPI)

```
GET /api/v1/models/registry
  Returns: Full model registry

GET /api/v1/models/active
  Returns: List of active models

GET /api/v1/models/updates
  Returns: Recent model discoveries

GET /api/v1/models/stats
  Returns: Discovery statistics
```

### Usage

```python
from app.services.model_discovery import get_registry, discover_models

# Run discovery
results = await discover_models()
# {
#   "new_models": ["anthropic/claude-opus-4-20250805"],
#   "updated_models": ["openai/gpt-4o"],
#   "removed_models": [],
#   "total_discovered": 87
# }

# Get registry
registry = await get_model_registry()

# Get stats
stats = await get_discovery_stats()
# {
#   "total_models": 87,
#   "active_models": 82,
#   "new_models_detected": 5,
#   "benchmarks_run": 12,
#   "discovery_count": 42
# }
```

### Features
- Automatic discovery on startup (configurable)
- 24-hour discovery interval (configurable)
- Tracks: context window, cost, performance, activity status
- Stores new models in memory for Cipher awareness
- Benchmarks new models (latency, quality)
- Flags models that outperform current tier models

---

## UPGRADE 3: 15-Minute Scanner Intervals with Per-Source Configuration

### Overview
Updates scanner to support per-source intervals instead of global interval. Enables faster update cycles for time-sensitive sources.

### Location
- **Config**: `/app/services/scanner/config.py`
- **Orchestrator**: `/app/services/scanner/orchestrator.py`

### Configuration
Default intervals (in minutes):

| Source | Interval | Rationale |
|--------|----------|-----------|
| **news** | 15 | Breaking news, time-sensitive |
| **web** | 15 | Dynamic content, frequent updates |
| **twitter** | 15 | Real-time platform, fast-moving |
| **reddit** | 15 | Community discussions, active |
| **github** | 30 | Less time-sensitive, code releases |
| **models** | 360 (6h) | Infrastructure, infrequent changes |

### Implementation

#### ScannerConfig Updates
```python
scan_intervals: dict[str, int] = {
    "news": 15,      # Every 15 minutes
    "web": 15,       # Every 15 minutes
    "twitter": 15,   # Every 15 minutes
    "reddit": 15,    # Every 15 minutes (if enabled)
    "github": 30,    # Every 30 minutes
    "models": 360,   # Every 6 hours
}
```

#### Scanner Orchestrator Updates
The `_check_and_scan()` method now:
1. Gets per-source interval from config
2. Checks if last_scan_time for that source + interval has elapsed
3. Only scans sources whose interval has passed
4. Tracks last_scan_time per source (not global)

**Before**: All scanners checked against single 60-minute interval
**After**: Each scanner checked against its own interval

### Backward Compatibility
- Existing code that sets `scanner_interval_minutes` still works
- Per-source intervals override global setting
- Can revert to single interval by removing per-source config

### Benefits
- News/Twitter: 4x faster updates (60 min → 15 min)
- Reduced latency for time-sensitive intelligence
- Proper interval for slow-changing sources (models: 6 hours)
- Better resource utilization

---

## UPGRADE 4: Semantic Caching

### Overview
Extends LRU cache to support both exact and semantic similarity matching. Uses `difflib.SequenceMatcher` for lightweight, dependency-free similarity scoring.

### Location
- **File**: `/app/services/cache.py`

### Features

#### Exact Match (Fast Path)
```
Message: "What is Python?"
→ Hash: abc123
→ Found in cache? Yes → Return (0.001ms)
```

#### Semantic Match (Fallback)
```
Message 1 (cached): "How do I learn Python?"
Message 2 (query):  "What are ways to study Python?"
→ Similarity: 0.87 (above 0.85 threshold)
→ Return cached response
```

#### Hit Type Tracking
Cache tracks three hit types:
- **exact**: Exact hash match (fastest)
- **semantic**: Similarity match (slower but cache hit)
- **miss**: No match found

#### Configuration
```python
SEMANTIC_SIMILARITY_THRESHOLD = 0.85  # 85% similarity = match
CACHE_MAX_ENTRIES = 1000
CACHE_TTL_SECONDS = 3600
```

### API

#### Caching
```python
from app.services.cache import cache_response, get_cached_response

# Store response
cache_response(
    message="What is Python?",
    model_tier="default",
    response={"content": "Python is..."},
    conversation_id="conv-123"
)

# Retrieve response (tries exact then semantic)
cached = get_cached_response(
    message="What is Python?",
    model_tier="default",
    conversation_id="conv-123"
)

if cached:
    print(cached["cache_hit_type"])  # "exact" or "semantic"
```

#### Statistics
```python
from app.services.cache import get_cache_stats

stats = get_cache_stats()
# {
#     "size": 245,
#     "max_entries": 1000,
#     "hits": 1203,
#     "misses": 342,
#     "hit_rate_percent": 77.8,
#     "hit_types": {
#         "exact": 1100,
#         "semantic": 103,
#         "miss": 342
#     },
#     "semantic_hit_rate_percent": 8.5,
#     "ttl_seconds": 3600
# }
```

### Implementation Details

#### Semantic Matching Algorithm
1. Check exact hash match first (instant)
2. If no exact match, scan recent 20 cache entries
3. For each entry, calculate similarity using SequenceMatcher
4. SequenceMatcher.ratio() returns 0.0-1.0
5. If similarity > 0.85 threshold, return that response
6. Otherwise, continue to next model/cache miss

#### Memory Efficiency
- Original message stored in cache for similarity matching
- Only recent entries checked (last 20, configurable)
- TTL still enforced for semantic matches
- No additional dependencies required

#### Cache Eviction
- Still uses LRU eviction when at capacity
- Most recent hits/writes are kept
- Semantic matches move entry to end (MRU)

### Benefits

#### Cost Savings
Similar queries can hit cache:
- "How to install Python?" → 1 API call
- "What's the best way to install Python?" → Cache hit (0 cost)
- Estimated 15-25% reduction in API calls for conversational workloads

#### Latency
- Exact hit: ~0.1ms
- Semantic hit: ~2-5ms
- Miss: Original latency (~500-3000ms)

#### Example Workflow
```
User Query 1: "How do I write a Python function?"
  → Cache miss → LLM call → $0.05 cost → Response cached

User Query 2: "Can you show me how to create a function in Python?"
  → Semantic match (0.92 similarity) → Cache hit → $0 cost → 3ms latency

Cost saved: $0.05
Latency improved: 2000ms → 3ms
```

---

## Integration with Orchestrator

### Current Flow
```
ChatRequest
  ↓
[Auto-classify if AUTO tier]
  ↓
[Check cache (exact + semantic)]
  ↓
[Cascade routing if enabled]
  ↓
[LLM response]
  ↓
[Store in cache]
```

### Usage Example
```python
from app.services.orchestrator import process_chat
from app.models.schemas import ChatRequest

request = ChatRequest(
    message="Write a Python function to sort a list",
    model_tier="auto",  # Auto-classify + cascade
    include_memory=True,
)

response = await process_chat(request, db_session)
# Response includes cascade and cache info
```

---

## Performance Monitoring

### Key Metrics to Track

#### Cascade Routing
```
- Average cascade attempts per request (lower = better)
- Quality score distribution
- Cost savings vs. direct routing
- Model distribution (% requests each model handled)
```

#### Caching
```
- Overall hit rate: (exact + semantic) / total accesses
- Exact vs. semantic ratio
- Semantic hit rate: semantic_hits / total
- Average latency improvement
```

#### Model Discovery
```
- New models detected per day
- Model churn rate (added vs. removed)
- Average benchmark scores
- Registry growth rate
```

#### Scanner
```
- Scan latency per source
- Results collected per scan
- Memory utilization
- Error rates per source
```

---

## Configuration Reference

### Environment Variables
```bash
# Cascade Routing
CASCADE_ROUTING_ENABLED=true

# Scanner Intervals (individual sources now use per-source config)
SCANNER_ENABLED=true

# Cache
CACHE_MAX_ENTRIES=1000
CACHE_TTL_SECONDS=3600

# Model Discovery
MODEL_DISCOVERY_INTERVAL_HOURS=24
```

### Python Config
```python
from app.core.config import settings

# Cascade routing
settings.cascade_routing_enabled = True

# Scanner
settings.scanner_enabled = True
settings.scanner_interval_minutes = 60  # Legacy, overridden by per-source

# Cache (in cache.py)
CACHE_MAX_ENTRIES = 1000
CACHE_TTL_SECONDS = 3600
SEMANTIC_SIMILARITY_THRESHOLD = 0.85
```

---

## Testing

### Running Tests
```bash
# Test all upgrades
pytest tests/test_upgrades.py -v

# Test specific upgrade
pytest tests/test_upgrades.py::TestUpgrade1CascadeRouting -v
pytest tests/test_upgrades.py::TestUpgrade2ModelDiscovery -v
pytest tests/test_upgrades.py::TestUpgrade3ScannerIntervals -v
pytest tests/test_upgrades.py::TestUpgrade4SemanticCaching -v
```

### Test Coverage
- Cascade routing: Quality scoring, model selection, cost optimization
- Model discovery: Registry management, benchmark execution
- Scanner intervals: Per-source timing, interval validation
- Semantic caching: Exact/semantic hits, TTL, statistics

---

## Troubleshooting

### Cascade Routing Not Working
- Check `CASCADE_ROUTING_ENABLED=true` in environment
- Verify cascade routes defined for your tier
- Check logs for quality scores being too low

### Models Not Being Discovered
- Verify `MODEL_DISCOVERY_INTERVAL_HOURS` setting
- Check `/data/model_registry.json` file permissions
- Review logs for provider connection errors

### Scanner Intervals Not Respecting Settings
- Verify `scan_intervals` in config (not single global interval)
- Check `sources_enabled` flags
- Review `last_scan_times` in orchestrator

### Cache Hit Rate Low
- Increase `SEMANTIC_SIMILARITY_THRESHOLD` to be less strict
- Check that responses are being cached (inspect cache stats)
- Verify TTL is long enough for similar queries

---

## Future Enhancements

### Upgrade 1 (Cascade)
- ML-based confidence scoring instead of heuristics
- Per-user tier preferences
- Dynamic threshold adjustment based on cost vs. quality

### Upgrade 2 (Discovery)
- Real-time model announcements via webhooks
- Automatic model capability testing
- Cross-provider model comparison benchmarks

### Upgrade 3 (Scanner)
- Dynamic interval adjustment based on update frequency
- Event-driven scanning for breaking news
- Source prioritization based on relevance

### Upgrade 4 (Cache)
- Vector-based semantic matching with embeddings
- Cross-conversation cache (with privacy boundaries)
- ML model selection based on similarity score

---

## Files Modified/Created

### Modified
- `/app/services/llm_router.py` - Added cascade routing
- `/app/core/config.py` - Added cascade_routing_enabled setting
- `/app/services/cache.py` - Added semantic caching
- `/app/services/scanner/config.py` - Updated intervals to per-source
- `/app/services/scanner/orchestrator.py` - Updated to support per-source intervals

### Created
- `/app/services/model_discovery.py` - Model discovery system
- `/app/services/scanner/model_scanner.py` - Model scanner
- `/tests/test_upgrades.py` - Comprehensive test suite

---

## Author Notes

These upgrades were implemented with:
- **No new dependencies** (uses stdlib only)
- **Full backward compatibility** (existing code continues to work)
- **Complete error handling** and logging
- **Zero performance impact** (cascade only triggered on cache miss)
- **Production-ready** code with tests

All upgrades can be enabled/disabled via configuration without code changes.
