# Orchid

**A sovereign, multi-agent AI operating system.**

Orchid is the cognitive layer of a personal AI system: a FastAPI-backed daemon that routes tasks across multiple LLM providers, maintains persistent memory, and dispatches work to specialized skill agents. It powers the communication interface **Cipher** and runs on the **Elysian Protocol** runtime layer.

> This repository is a personal engineering project I built as proof of work for agentic AI / LLM systems roles.

---

## What it does

Orchid sits between you and a fleet of AI providers / tools:

1. **Route** every request to the right model via LiteLLM (Claude, GPT-4o, Groq/Llama, local Ollama).
2. **Remember** conversations and facts in ChromaDB + SQLite.
3. **Act** through skill agents that can run shell commands, browse the web, write code, send messages, trade (paper), deploy code, research, schedule, and more.
4. **Verify** every agent result before surfacing it.
5. **Gate** dangerous actions behind operator approval.

It exposes this over a REST/WebSocket API, a Telegram bot, a React dashboard, and a Swift iOS app.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Clients                              │
│   Telegram bot    Web dashboard    iOS app (CipherApp)     │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                        Orchid Core                           │
│  FastAPI  ·  LiteLLM router  ·  ChromaDB memory  ·  SQLite   │
│  Celery + Redis async tasks  ·  Pydantic settings            │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                     Agent Framework                            │
│  registry → executor → skill agents → verify → history      │
│  shell · web · code · file · deploy · research · trading ·   │
│  scheduler · monitor · communication · swarm                │
└─────────────────────────────────────────────────────────────┘
```

Repository layout:

| Directory | Purpose |
|-----------|---------|
| `app/api` | 15+ FastAPI routers: chat, memory, agents, voice, scanner, cron, swarm |
| `app/agents` | Agent base classes, registry, executor, intent classifier, 20+ skills |
| `app/services` | LLM router, memory service, scanner orchestrator, tool calling |
| `app/bot` | Telegram integration |
| `app/db` | SQLAlchemy models + Alembic |
| `CipherApp` | Swift iOS client |
| `dashboard` | Standalone HTML dashboard |
| `frontend` | Next.js + Tailwind dashboard |
| `desktop` | Desktop app shell |
| `docs` | Deep-dive architecture docs |
| `infra` | Deployment configs (Railway, Fly, launchd, nginx) |
| `scripts` | Deployment and utility scripts |
| `tests` | Pytest suite |

---

## Tech stack

- **Backend:** Python 3.12, FastAPI, Uvicorn, Pydantic, SQLAlchemy + Alembic
- **LLM routing:** LiteLLM (Anthropic, OpenAI, Groq, DeepSeek, local Ollama)
- **Memory:** ChromaDB vector store + SQLite conversation history
- **Async tasks:** Celery + Redis
- **Auth:** JWT via python-jose + passlib
- **Integrations:** Telegram bot, Twilio SMS/voice, email (SMTP/IMAP), Slack, X/Twitter
- **Frontend:** Next.js, React, Tailwind CSS
- **Mobile:** Swift, SwiftUI
- **Deployment:** Docker, Railway, Fly.io, launchd

---

## Key design decisions

- **Model-agnostic routing.** LiteLLM lets the system swap providers per task tier — reasoning, fast, code, local — without changing agent code.
- **Mandatory verification.** Every skill agent implements `verify()` so hallucinated or partial output never reaches the user silently.
- **Approval gates.** Trades, git pushes, destructive shell/file ops, and outbound messages require explicit operator approval.
- **Self-improvement hooks.** Research and swarm routers can propose system upgrades; execution history feeds back into routing decisions.
- **Local-first option.** Models can fall back to Ollama for zero-cloud, fully sovereign operation.

---

## Quick start

```bash
git clone https://github.com/meyer4t4-commits/orchid.git
cd orchid
cp .env.example .env
# Fill in your API keys, then:

# Option A: Python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Option B: Docker
docker compose up -d
```

Open the API docs at `http://localhost:8000/docs`.

---

## Tests

```bash
pytest
```

Includes agent registry tests, API tests, and upgrade-path validation.

---

## Project status

Built as a solo engineering project. The backend agent framework is functional; the iOS client reached TestFlight. Not actively monetized — this repo exists as proof of work.
