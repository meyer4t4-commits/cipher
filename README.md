# Orchid

**Sovereign AI Intelligence Daemon by Elysian Protocol**

Orchid is a background intelligence daemon that routes across multiple LLM providers, stores context locally, and evolves with its operator. It is the foundation of the Elysian Protocol ecosystem.

## Architecture

```
orchid/
  app/
    api/          # FastAPI endpoints (chat, memory, models, system)
    bot/          # Telegram bot integration
    core/         # Config, security, logging
    db/           # SQLAlchemy models + database setup
    models/       # Pydantic schemas
    services/     # LLM router, memory (ChromaDB), orchestrator, Celery tasks
  dashboard/      # React + Tailwind web dashboard
  docker/         # Docker configurations
  scripts/        # Deployment and utility scripts
  tests/          # Pytest test suite
```

## Quick Start

```bash
# 1. Setup
bash scripts/run.sh

# 2. Edit .env with your API keys
nano .env

# 3. Run
uvicorn app.main:app --reload

# 4. Open dashboard
open dashboard/index.html

# 5. API docs
open http://localhost:8000/docs
```

## Docker

```bash
# Copy env and add your keys
cp .env.example .env

# Start everything
docker compose up -d

# View logs
docker compose logs -f orchid
```

## Key Features

- **Multi-LLM Routing**: Claude for reasoning, Llama for speed, local models for sovereignty
- **Persistent Memory**: ChromaDB vector store for long-term context
- **Conversation History**: SQLite with full message history and usage tracking
- **Telegram Bot**: Talk to Orchid from anywhere
- **Web Dashboard**: Real-time chat interface with system monitoring
- **Background Tasks**: Celery + Redis for async document indexing and summarization
- **Docker Ready**: One command to deploy anywhere

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/` | POST | Send a message to Orchid |
| `/api/v1/chat/stream` | POST | Stream a response (SSE) |
| `/api/v1/chat/conversations` | GET | List all conversations |
| `/api/v1/memory/store` | POST | Store a memory |
| `/api/v1/memory/recall` | POST | Search memories semantically |
| `/api/v1/models/` | GET | List configured models |
| `/api/v1/models/usage` | GET | Usage statistics |
| `/api/v1/system/health` | GET | System health check |

## Model Tiers

| Tier | Default Model | Use Case |
|------|--------------|----------|
| reasoning | Claude Sonnet | Complex analysis, planning |
| fast | Groq/Llama 3.3 70B | Quick responses, routine tasks |
| code | Claude Sonnet | Code generation and review |
| local | Ollama/Llama 3.3 | Offline, zero-cost, sovereign |
| default | Claude Sonnet | General purpose |

## License

Proprietary - Elysian Protocol. All rights reserved.
