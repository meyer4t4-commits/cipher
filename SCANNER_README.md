# Orchid Intelligence Scanner Service

A Bloomberg-style background intelligence service that continuously scans multiple data sources, filters for relevance, and feeds intelligence into Cipher's memory. This ensures Cipher always knows what's happening without needing to search.

## Architecture Overview

The scanner service consists of:

1. **Base Scanner** (`base.py`) - Abstract base class for all scanners
2. **Individual Scanners** - Specialized scanners for each data source
3. **Orchestrator** (`orchestrator.py`) - Coordinates all scanners and manages flows
4. **API Endpoints** (`api/scanner.py`) - REST API for status, configuration, and briefings
5. **Configuration** (`config.py`) - Scanner settings and keywords

## Scanner Sources

### News Scanner (`news_scanner.py`)
Scans news from multiple sources with NO API key required (RSS fallback always available):

- **Primary**: NewsAPI.org (if API key provided)
  - Free tier: 100 requests/day
  - Full article content

- **Fallback**: Free RSS Feeds (no key needed)
  - TechCrunch
  - Hacker News
  - Ars Technica
  - The Verge
  - Reuters Technology

**Tracked Keywords**:
- Artificial intelligence, AI startups, machine learning
- Sovereign AI, local AI, LLM
- Elysian Protocol, Orchid, Cipher
- Roofing industry, construction tech
- Restaurant tech, school safety

### Web Scanner (`web_scanner.py`)
Lightweight web intelligence from social and collaborative platforms:

- **Reddit**: Scans 5+ AI/tech subreddits
  - r/artificial, r/LocalLLaMA, r/machinelearning, r/LanguageModels, r/ChatGPT
  - Public API (no auth required)
  - Rate limited

- **Google Trends**: (Optional, requires pytrends)
  - Trending topics
  - Search volume changes

### X/Twitter Scanner (`x_scanner.py`)
Social media intelligence with graceful fallback:

- **Official API** (if X_BEARER_TOKEN provided)
  - Twitter API v2
  - Real-time search
  - Metrics included

- **Nitter Fallback** (always available)
  - Privacy-friendly RSS feeds
  - Multiple Nitter instances for redundancy
  - No authentication needed

**Monitored Accounts**:
- @markmeyeragi (you)
- @OpenAI, @AnthropicAI, @GoogleDeepMind (competitors)

**Topics**: "sovereign AI", "local AI", "open source LLM", "AI safety"

### GitHub Scanner (`github_scanner.py`)
Track open source trends and project activity:

- **Key Repositories**: Actively monitors
  - litellm, ollama, chroma, langchain
  - anthropic-sdk, openai-python
  - vllm, ChatGLM3

- **Trending Search**: Discovers new relevant projects
  - Language: Python
  - Topics: ML, LLM, AI

**Public API**: 60 requests/hour (no auth required for public data)

## Configuration

### Environment Variables

```bash
# Optional API keys (service works without them)
NEWSAPI_KEY=your_api_key_here
X_BEARER_TOKEN=your_twitter_bearer_token

# Scanner settings
SCANNER_ENABLED=true
SCANNER_INTERVAL_MINUTES=60
```

### Programmatic Configuration

Access `/api/v1/scanner/config` to view and update:

```json
{
  "keywords": {
    "technology": ["artificial intelligence", "machine learning", ...],
    "brand": ["Elysian Protocol", "Orchid", ...],
    "industry": ["roofing industry", "construction tech", ...],
    "competitors": ["OpenAI", "Anthropic", ...]
  },
  "sources_enabled": {
    "news": true,
    "web": true,
    "twitter": true,
    "github": true
  },
  "scan_intervals": {
    "news": 60,
    "web": 120,
    "twitter": 30,
    "github": 240,
    "reddit": 90
  },
  "relevance_threshold": 0.3,
  "max_results_per_scan": 10,
  "max_stored_results": 100
}
```

## API Endpoints

### Scanner Status
```
GET /api/v1/scanner/status
```
Returns operational status, last run time, scan count, errors, enabled sources.

### Intelligence Briefing
```
GET /api/v1/scanner/briefing
GET /api/v1/scanner/briefing/{date}
```
Get latest or historical briefings (YYYY-MM-DD format). Returns markdown-formatted intelligence summary grouped by source.

### Trigger Scans
```
POST /api/v1/scanner/scan-now
POST /api/v1/scanner/briefing-now
```
Trigger immediate full scan or briefing generation.

### Configuration Management
```
GET /api/v1/scanner/config
PUT /api/v1/scanner/config
```
View and update scanner configuration.

### Keyword Management
```
POST /api/v1/scanner/keywords?keyword=term&category=technology
DELETE /api/v1/scanner/keywords?keyword=term&category=technology
```
Add/remove keywords from tracking.

### Health Check
```
GET /api/v1/scanner/health
```
Check scanner operational status (considers healthy if running and scanned within 3 hours).

## Memory Integration

All scan results are stored in Orchid's memory service with metadata:

```python
memory.store_memory(
    content=f"{title}\n\n{content}",
    metadata={
        "source": "news",
        "url": "https://...",
        "relevance_score": 0.75,
        "tags": ["news", "ai"],
        "timestamp": "2026-02-26T12:00:00"
    },
    collection_name="intelligence",
)
```

When Cipher is asked "what's happening in AI today?", it can recall relevant memories using:

```python
memory.recall_memories(
    query="AI news today",
    n_results=10,
    collection_name="intelligence"
)
```

## How It Works

### Continuous Scanning
1. Scanner starts on application startup (if `SCANNER_ENABLED=true`)
2. Runs initial full scan of all enabled sources
3. Checks every minute if any scanner needs to run based on configured intervals
4. Each scanner operates independently - if one fails, others continue
5. Results are deduplicated and stored in memory with metadata

### Relevance Scoring
Each result gets a relevance score (0.0 to 1.0):
- Keyword matching: 70% weight
- Base source score: 30% weight
- Only results above `relevance_threshold` (default 0.3) are stored

### Deduplication
Results are deduplicated by URL to avoid storing duplicate intelligence.

### Daily Briefing
Generated on demand (or scheduled):
- Groups results by source
- Shows top results with relevance scores
- Saved as markdown to `/data/briefings/YYYY-MM-DD.md`
- Used by Cipher for context in conversations

## Usage Examples

### Python/FastAPI Integration

```python
from app.services.scanner.orchestrator import get_orchestrator

# Get current status
orchestrator = await get_orchestrator()
status = await orchestrator.get_status()

# Run immediate scan
await orchestrator.run_full_scan()

# Generate briefing
briefing = await orchestrator.generate_briefing()

# Update keywords
config_updates = {
    "keywords": {
        "technology": [...new keywords...],
    }
}
await orchestrator.update_config(config_updates)
```

### REST API Examples

```bash
# Check scanner status
curl http://localhost:8000/api/v1/scanner/status

# Get latest briefing
curl http://localhost:8000/api/v1/scanner/briefing

# Trigger immediate scan
curl -X POST http://localhost:8000/api/v1/scanner/scan-now

# View current config
curl http://localhost:8000/api/v1/scanner/config

# Add keyword
curl -X POST "http://localhost:8000/api/v1/scanner/keywords?keyword=quantum%20computing&category=technology"

# Get briefing for specific date
curl http://localhost:8000/api/v1/scanner/briefing/2026-02-25

# Check health
curl http://localhost:8000/api/v1/scanner/health
```

## Error Handling

The scanner is resilient:

- **Individual scanner failure**: Other scanners continue, error is logged
- **API rate limits**: Respects rate limits with backoff
- **Network issues**: Graceful fallbacks (e.g., RSS when NewsAPI fails)
- **Parsing failures**: Individual items skipped, process continues
- **Memory limits**: Oldest entries pruned when max results exceeded

All errors are logged with full context for debugging.

## Performance Characteristics

- **Memory**: Stores up to 100 results by default (configurable)
- **CPU**: Light async operations, no blocking calls
- **Network**:
  - News: 1 request every 60 minutes (or fallback to RSS)
  - Web: 2 requests every 120 minutes
  - Twitter: 3 requests every 30 minutes
  - GitHub: 1 request every 240 minutes

Total: ~15-20 network requests per hour (well within any rate limits)

## Extending the Scanner

Add a new scanner by:

1. Create `app/services/scanner/your_scanner.py`
2. Inherit from `BaseScanner`
3. Implement `scan()`, `parse_results()`, `filter_relevant()`
4. Add to `orchestrator.py` initialization
5. Add to config intervals and toggles

Example:

```python
from .base import BaseScanner, ScanResult

class YourScanner(BaseScanner):
    def __init__(self):
        super().__init__("your_source", rate_limit_delay=2.0)

    async def scan(self, keywords: list[str]) -> list[ScanResult]:
        # Fetch data
        raw_results = await self._fetch_data(keywords)

        # Parse
        parsed = await self.parse_results(raw_results)

        # Filter
        filtered = await self.filter_relevant(parsed)

        return filtered
```

## Debugging

Enable debug logging:

```python
from app.core.logging import logger
logger.setLevel(logging.DEBUG)
```

Check the orchestrator status:
```
GET /api/v1/scanner/status
```

View stored intelligence:
```python
from app.services import memory

memories = memory.recall_memories(
    query="AI",
    n_results=20,
    collection_name="intelligence"
)
```

## Files Created

```
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/
├── __init__.py                  # Package init
├── base.py                      # BaseScanner abstract class
├── config.py                    # Configuration management
├── news_scanner.py              # News from NewsAPI/RSS
├── web_scanner.py               # Web intelligence (Reddit, Trends)
├── x_scanner.py                 # X/Twitter scanner
├── github_scanner.py            # GitHub trends
└── orchestrator.py              # Main orchestrator

/sessions/inspiring-funny-rubin/mnt/orchid/app/api/
└── scanner.py                   # REST API endpoints

/sessions/inspiring-funny-rubin/mnt/orchid/app/core/
└── config.py                    # Updated with scanner settings

/sessions/inspiring-funny-rubin/mnt/orchid/app/
└── main.py                      # Updated with scanner startup
```

## Key Design Decisions

1. **No Heavy Dependencies**: Uses only stdlib + httpx (already installed via litellm)
2. **Graceful Degradation**: Fallback to RSS when API fails, no single point of failure
3. **Async Throughout**: All I/O is non-blocking
4. **Memory-Based Storage**: Leverages Orchid's existing JSON memory system
5. **Flexible Configuration**: Keywords, intervals, thresholds all configurable
6. **Background Task**: Runs independently, never blocks main application
7. **Deduplication**: Avoids duplicate intelligence in memory
8. **Relevance Scoring**: Only keeps high-signal results

## The Vision

When someone asks Cipher "what's happening in AI today?" — Cipher doesn't search the web. It already knows because the scanner has been feeding it fresh intelligence all day. The briefing is ready, the memories are warm, and the response is contextual and immediate.

This is what makes it a daemon, not a chatbot.
