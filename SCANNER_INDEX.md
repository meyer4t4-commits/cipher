# Orchid Scanner Service - Complete Index

All files created for the Bloomberg-style intelligence scanner service.

## Core Scanner Service Files

### Base Infrastructure
- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/__init__.py`**
  - Package initialization file

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/base.py`** (4.5 KB)
  - `ScanResult` dataclass with standardized result format
  - `BaseScanner` abstract base class for all scanners
  - Common functionality: rate limiting, error handling, relevance calculation
  - Exception classes: `ScannerError`, `ScannerConnectionError`, `ScannerParseError`

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/config.py`** (2.6 KB)
  - `ScannerConfig` dataclass for configuration management
  - Keywords organized by category: technology, brand, industry, competitors
  - Source enable/disable toggles
  - Scan intervals per source (in minutes)
  - Relevance thresholds and result limits
  - Helper functions: `get_config()`, `get_all_keywords()`

### Individual Scanner Implementations

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/news_scanner.py`** (11 KB)
  - `NewsScanner` class scanning news from multiple sources
  - Primary: NewsAPI.org (optional, free tier: 100/day)
  - Fallback: Free RSS feeds (TechCrunch, HackerNews, ArsTechnica, TheVerge, Reuters)
  - Full XML parsing for both Atom and RSS formats
  - Dual-source strategy with automatic fallback
  - Keyword tracking for AI, technology, and industry terms

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/web_scanner.py`** (5.9 KB)
  - `WebScanner` class for web intelligence
  - Reddit scanner: 5+ subreddits (r/artificial, r/LocalLLaMA, r/machinelearning, etc.)
  - Public JSON API (no authentication required)
  - Keyword relevance filtering
  - Preparation for Google Trends integration

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/x_scanner.py`** (11 KB)
  - `XScanner` class for Twitter/X intelligence
  - Official Twitter API v2 (if bearer token provided)
  - Nitter RSS fallback (multiple instances for redundancy)
  - Monitors accounts: @markmeyeragi, @OpenAI, @AnthropicAI, @GoogleDeepMind
  - Monitors topics: "sovereign AI", "local AI", "open source LLM"
  - Full RSS parsing for tweet feeds

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/github_scanner.py`** (9.5 KB)
  - `GitHubScanner` class for GitHub trends
  - Monitors key repositories: litellm, ollama, chroma, langchain, etc.
  - Discovers trending AI/ML projects via search
  - Tracks stars, forks, language, and recent releases
  - Public API (no authentication, 60 requests/hour)

### Main Orchestrator

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/orchestrator.py`** (13 KB)
  - `ScannerOrchestrator` class coordinating all scanners
  - Initializes all scanners based on configuration
  - Runs continuous background scanning with async support
  - Manages scan intervals and timing (checks every minute)
  - Deduplicates results by URL
  - Stores results in Orchid's memory service
  - Maintains maximum result limits with auto-pruning
  - Generates daily intelligence briefings in markdown
  - Tracks status: running, scan count, error count
  - Supports runtime configuration updates
  - Global orchestrator instance management
  - Background task startup/shutdown functions

## API and Integration Files

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/api/scanner.py`** (8.5 KB)
  - 10 REST API endpoints for scanner control and monitoring
  - Pydantic models: `ScannerStatus`, `ScannerConfig`, `BriefingResponse`
  - Full error handling and validation
  - Endpoints:
    - `GET /api/v1/scanner/status` - Current status
    - `GET /api/v1/scanner/briefing` - Latest briefing
    - `GET /api/v1/scanner/briefing/{date}` - Briefing by date
    - `POST /api/v1/scanner/scan-now` - Trigger immediate scan
    - `POST /api/v1/scanner/briefing-now` - Generate briefing
    - `GET /api/v1/scanner/config` - View configuration
    - `PUT /api/v1/scanner/config` - Update configuration
    - `POST /api/v1/scanner/keywords` - Add keyword
    - `DELETE /api/v1/scanner/keywords` - Remove keyword
    - `GET /api/v1/scanner/health` - Health check

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/core/config.py`** (UPDATED)
  - Added scanner-related settings:
    - `newsapi_key: str = ""`
    - `x_bearer_token: str = ""`
    - `scanner_enabled: bool = True`
    - `scanner_interval_minutes: int = 60`

- **`/sessions/inspiring-funny-rubin/mnt/orchid/app/main.py`** (UPDATED)
  - Imported scanner router and orchestrator functions
  - Added `start_scanner()` on app startup
  - Added `stop_scanner()` on app shutdown
  - Registered scanner router: `app.include_router(scanner.router, prefix="/api/v1")`
  - Proper lifecycle management in lifespan context manager

## Documentation Files

- **`/sessions/inspiring-funny-rubin/mnt/orchid/SCANNER_README.md`** (600+ lines)
  - Comprehensive feature guide and user manual
  - Architecture overview with detailed diagrams
  - Complete description of each scanner source
  - Configuration options and defaults
  - Full API endpoint reference with curl examples
  - Memory integration guide
  - Performance characteristics and benchmarks
  - Extension guide for adding new scanners
  - Debugging and troubleshooting guide
  - Usage examples in Python and REST

- **`/sessions/inspiring-funny-rubin/mnt/orchid/SCANNER_IMPLEMENTATION.md`**
  - Technical implementation details
  - Complete file-by-file code breakdown
  - Design decisions explained
  - Performance specifications
  - Error resilience and fallback strategies
  - Production considerations and deployment
  - Testing procedures and verification
  - The vision and transformation

- **`/sessions/inspiring-funny-rubin/mnt/orchid/SCANNER_QUICKSTART.md`**
  - Quick start guide for developers
  - Installation instructions
  - Quick API tests with curl examples
  - Programmatic usage in Python
  - Common tasks and solutions
  - Troubleshooting guide
  - Debug logging tips

- **`/sessions/inspiring-funny-rubin/mnt/orchid/SCANNER_INDEX.md`** (this file)
  - Complete index of all files with absolute paths
  - Brief description of each file
  - Quick reference guide

## Testing File

- **`/sessions/inspiring-funny-rubin/mnt/orchid/test_scanner_integration.py`**
  - Comprehensive integration test suite
  - Tests all major components: imports, config, ScanResult, orchestrator, memory, API models, scanners
  - Can run without full dependencies installed
  - Covers error cases and validates functionality

## File Statistics

| Category | Files | Size |
|----------|-------|------|
| Scanner Core | 8 | ~60 KB |
| API & Integration | 2 | 8.5 KB |
| Configuration | 1 | - |
| Documentation | 4 | ~20 KB |
| Tests | 1 | 4 KB |
| **Total** | **16** | **~92 KB** |

## All Absolute Paths

### Scanner Service
```
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/__init__.py
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/base.py
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/config.py
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/news_scanner.py
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/web_scanner.py
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/x_scanner.py
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/github_scanner.py
/sessions/inspiring-funny-rubin/mnt/orchid/app/services/scanner/orchestrator.py
```

### API & Integration
```
/sessions/inspiring-funny-rubin/mnt/orchid/app/api/scanner.py
/sessions/inspiring-funny-rubin/mnt/orchid/app/core/config.py (UPDATED)
/sessions/inspiring-funny-rubin/mnt/orchid/app/main.py (UPDATED)
```

### Documentation
```
/sessions/inspiring-funny-rubin/mnt/orchid/SCANNER_README.md
/sessions/inspiring-funny-rubin/mnt/orchid/SCANNER_IMPLEMENTATION.md
/sessions/inspiring-funny-rubin/mnt/orchid/SCANNER_QUICKSTART.md
/sessions/inspiring-funny-rubin/mnt/orchid/SCANNER_INDEX.md
```

### Testing
```
/sessions/inspiring-funny-rubin/mnt/orchid/test_scanner_integration.py
```

## Quick Reference

### Start the scanner
```bash
cd /sessions/inspiring-funny-rubin/mnt/orchid
uvicorn app.main:app --reload
```

### Check scanner status
```bash
curl http://localhost:8000/api/v1/scanner/status
```

### View latest briefing
```bash
curl http://localhost:8000/api/v1/scanner/briefing
```

### Trigger immediate scan
```bash
curl -X POST http://localhost:8000/api/v1/scanner/scan-now
```

### Check API docs
```
http://localhost:8000/docs
```

### Access intelligence in code
```python
from app.services import memory

intelligence = memory.recall_memories(
    query="AI news",
    n_results=10,
    collection_name="intelligence"
)
```

## Key Features by File

### base.py
- ScanResult standardization
- BaseScanner abstract class
- Rate limiting (per-source configurable)
- Relevance calculation
- Error handling framework
- Context manager support

### config.py
- Keyword management by category
- Source configuration
- Scan interval management
- Threshold settings
- API key configuration

### news_scanner.py
- NewsAPI integration
- RSS feed parsing (Atom + RSS)
- Free RSS sources fallback
- Dual-source strategy

### web_scanner.py
- Reddit subreddit monitoring
- Public API access (no auth)
- Keyword filtering

### x_scanner.py
- Twitter API v2 integration
- Nitter RSS fallback
- Multiple Nitter instances
- Tweet parsing

### github_scanner.py
- Key repo monitoring
- Trending search
- Release tracking
- Public API access

### orchestrator.py
- All scanner coordination
- Background async operation
- Memory service integration
- Deduplication
- Briefing generation
- Status tracking

### scanner.py (API)
- 10 REST endpoints
- Full validation
- Error handling
- Configuration management
- Keyword control

## Integration Points

1. **Memory Service**: `/app/services/memory.py`
   - Stores all intelligence in "intelligence" collection
   - Uses `store_memory()` for results
   - Uses `recall_memories()` to retrieve for Cipher

2. **Configuration**: `/app/core/config.py`
   - Loads API keys from environment
   - Manages scanner settings
   - All overridable at runtime

3. **Logging**: `/app/core/logging.py`
   - All operations logged
   - Rich console output
   - Debug mode support

4. **FastAPI**: `/app/main.py`
   - Routes registered
   - Startup/shutdown lifecycle
   - CORS configured
   - Swagger docs auto-generated

## Dependencies

All dependencies already in pyproject.toml:
- fastapi
- httpx (for HTTP requests)
- pydantic / pydantic-settings
- rich (logging)
- python-dotenv

No new dependencies added.

## Environment Variables

Optional (service works without them):
```bash
NEWSAPI_KEY=your_api_key              # Free tier: 100/day
X_BEARER_TOKEN=your_bearer_token      # Twitter API v2
```

Default (configurable):
```bash
SCANNER_ENABLED=true
SCANNER_INTERVAL_MINUTES=60
```

All overridable at runtime via API.

---

For detailed information, see:
- **SCANNER_README.md** - Full feature guide
- **SCANNER_QUICKSTART.md** - Quick start for developers
- **SCANNER_IMPLEMENTATION.md** - Technical details
