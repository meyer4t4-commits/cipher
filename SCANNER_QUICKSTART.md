# Scanner Service - Quick Start Guide

## Installation

The scanner is built into Orchid and requires no additional dependencies. All required packages are already in `pyproject.toml`:

```bash
cd /sessions/inspiring-funny-rubin/mnt/orchid
pip install -e .  # Install in development mode
```

## Starting Orchid with Scanner

```bash
# Scanner is enabled by default
uvicorn app.main:app --reload

# Disable scanner if needed
SCANNER_ENABLED=false uvicorn app.main:app --reload
```

The scanner will:
1. Start automatically on app startup
2. Run initial scan of all sources
3. Continue scanning based on configured intervals (default: every 60 minutes for news)
4. Store results in Orchid's memory for Cipher to use

## Quick API Tests

### Check Scanner Status
```bash
curl http://localhost:8000/api/v1/scanner/status | python3 -m json.tool
```

Response:
```json
{
  "running": true,
  "last_full_scan": "2026-02-26T12:00:00",
  "scan_count": 1,
  "error_count": 0,
  "enabled_sources": ["news", "web", "twitter", "github"],
  "memory_stats": {
    "collection": "intelligence",
    "total_memories": 25
  }
}
```

### Get Latest Briefing
```bash
curl http://localhost:8000/api/v1/scanner/briefing
```

Returns markdown briefing with latest intelligence grouped by source.

### Trigger Immediate Scan
```bash
curl -X POST http://localhost:8000/api/v1/scanner/scan-now
```

### View Configuration
```bash
curl http://localhost:8000/api/v1/scanner/config | python3 -m json.tool
```

### Add Keyword to Track
```bash
curl -X POST "http://localhost:8000/api/v1/scanner/keywords?keyword=quantum+computing&category=technology"
```

### Check Health
```bash
curl http://localhost:8000/api/v1/scanner/health | python3 -m json.tool
```

## Programmatic Usage in Python

### Check Scanner Status
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()
status = await orchestrator.get_status()
print(f"Scanner running: {status['running']}")
print(f"Scan count: {status['scan_count']}")
```

### Get Intelligence from Memory
```python
from app.services import memory

# Get recent AI news
intelligence = memory.recall_memories(
    query="artificial intelligence news",
    n_results=10,
    collection_name="intelligence"
)

for item in intelligence:
    print(f"- {item['content'][:100]}...")
    print(f"  Source: {item['metadata']['source']}")
    print(f"  Relevance: {item['metadata']['relevance_score']:.2f}")
```

### Trigger Manual Scan
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()
await orchestrator.run_full_scan()
print("Scan complete!")
```

### Generate Briefing
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()
briefing = await orchestrator.generate_briefing()
print(briefing)
```

### Update Configuration
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()

config_updates = {
    "keywords": {
        "technology": [
            "artificial intelligence",
            "quantum computing",  # New keyword
            "sovereign AI"
        ]
    }
}

await orchestrator.update_config(config_updates)
```

## Using Intelligence in Cipher Conversations

When someone asks Cipher a question, Cipher can access the scanner intelligence:

```python
# In a chat handler
from app.services import memory

def get_context_for_ai_question():
    """Get recent AI intelligence to inform Cipher's response."""
    intelligence = memory.recall_memories(
        query="artificial intelligence news today",
        n_results=5,
        collection_name="intelligence"
    )

    briefing = "\n".join([
        f"- {item['content'][:150]}..."
        for item in intelligence
    ])

    return f"Recent intelligence:\n{briefing}"

# Use this in system prompt or context
```

## Environment Configuration

Create `.env` file (optional):

```bash
# Enable/disable scanner
SCANNER_ENABLED=true

# Scan interval (minutes)
SCANNER_INTERVAL_MINUTES=60

# Optional API keys (scanner works without them)
NEWSAPI_KEY=your_key_here
X_BEARER_TOKEN=your_token_here
```

## Common Tasks

### Add a New Keyword
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()
if "technology" not in orchestrator.config.keywords:
    orchestrator.config.keywords["technology"] = []

orchestrator.config.keywords["technology"].append("new keyword")
```

### Disable a Source
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()
orchestrator.config.sources_enabled["twitter"] = False

# Or via API
config = {
    "sources_enabled": {"twitter": False}
}
await orchestrator.update_config(config)
```

### Change Scan Interval
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()
orchestrator.config.scan_intervals["news"] = 30  # Check every 30 minutes

# Or via API
config = {
    "scan_intervals": {"news": 30}
}
await orchestrator.update_config(config)
```

### View All Stored Intelligence
```python
from app.services import memory

all_intelligence = memory.recall_memories(
    query="",  # Empty query returns all
    n_results=100,
    collection_name="intelligence"
)

for item in all_intelligence:
    print(f"Source: {item['metadata']['source']}")
    print(f"URL: {item['metadata']['url']}")
    print(f"Score: {item['metadata']['relevance_score']:.2f}")
    print()
```

### Clear Old Intelligence
```python
from app.services import memory

all_intelligence = memory.recall_memories(
    query="",
    n_results=1000,
    collection_name="intelligence"
)

# Remove old entries (keep last 50)
for item in all_intelligence[50:]:
    memory.delete_memory(item['id'], "intelligence")
```

## Debugging

### Enable Debug Logging
```python
import logging
from app.core.logging import logger

logger.setLevel(logging.DEBUG)
```

### Check Scanner Internals
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()
print(f"Enabled scanners: {list(orchestrator.scanners.keys())}")
print(f"Last scan times: {orchestrator.last_scan_times}")
print(f"Error count: {orchestrator.error_count}")
```

### Monitor Scan in Real-time
```python
import asyncio
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()

# Check status every 30 seconds
for _ in range(10):
    status = await orchestrator.get_status()
    print(f"Scans: {status['scan_count']}, Errors: {status['error_count']}")
    print(f"Intelligence stored: {status['memory_stats']['total_memories']}")
    await asyncio.sleep(30)
```

## Performance Tips

1. **Adjust Intervals**: If getting too much data, increase interval times
2. **Raise Threshold**: Increase `relevance_threshold` to filter more strictly
3. **Disable Sources**: Turn off sources you don't need
4. **Limit Keywords**: Fewer keywords = faster scanning
5. **Check Health**: Use health endpoint to monitor efficiency

## Troubleshooting

### Scanner Not Starting
```bash
# Check if SCANNER_ENABLED is true
echo $SCANNER_ENABLED  # Should be true or unset

# Check logs
# Should see "Intelligence scanner started" on startup
```

### No Results Appearing
```python
from app.services.scanner.orchestrator import get_orchestrator

orchestrator = await get_orchestrator()
status = await orchestrator.get_status()

# Check if running
print(f"Running: {status['running']}")

# Check error count
print(f"Errors: {status['error_count']}")

# Check if any sources enabled
print(f"Enabled: {status['enabled_sources']}")

# Trigger manual scan
await orchestrator.run_full_scan()
```

### API Key Issues
```python
from app.core.config import settings

print(f"NewsAPI key: {settings.newsapi_key or 'NOT SET'}")
print(f"Twitter token: {settings.x_bearer_token or 'NOT SET'}")
# Scanner works without these - just uses free sources
```

## Next Steps

1. **Check Status**: `GET /api/v1/scanner/status`
2. **View Briefing**: `GET /api/v1/scanner/briefing`
3. **Add Keywords**: `POST /api/v1/scanner/keywords`
4. **Integrate with Cipher**: Use memory.recall_memories() in chat handlers
5. **Monitor**: Check health endpoint periodically

## Full Documentation

- `SCANNER_README.md` - Complete feature guide
- `SCANNER_IMPLEMENTATION.md` - Technical details
- API docs at `http://localhost:8000/docs` (interactive)

---

The scanner runs silently in the background, continuously gathering intelligence. Cipher always knows what's happening because the scanner keeps the memory fresh.
