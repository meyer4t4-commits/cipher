# Cipher (Backend)

**Sovereign AI intelligence daemon — backend for a personal, multi-modal AI operating system.**

> This repo (`meyer4t4-commits/orchid`) is the original backend engine. The project has since been unified under the **Cipher** identity.

Cipher is a full-stack AI system I built as proof of work for agentic / LLM-systems engineering roles. It is not a single chatbot — it is a personal intelligence layer that routes across models, remembers context, dispatches work to specialized agents, and communicates through its own phone number, Telegram bot, iOS app, email, Slack, and web dashboard.

---

## What it actually does

1. **Understand intent** — classifies every request and picks the right agent skill.
2. **Route across models** — uses LiteLLM to choose Claude, Groq/Llama, GPT‑4o, DeepSeek, xAI/Grok, or local Ollama per task tier.
3. **Remember** — stores conversations, facts, and operational playbooks in ChromaDB (+ Pinecone configured as production upgrade) and SQLite.
4. **Act** — dispatches to 30+ skill agents: shell commands, code, file ops, web browsing, research, scheduling, trading (paper), real‑estate analysis, outreach, deployment, media generation, voice cloning/provisioning, and more.
5. **Verify & approve** — every agent result runs through `verify()`; risky actions require operator approval.
6. **Communicate** — replies via Telegram, SMS/voice through its own Twilio number, email, Slack, and a native iOS app.
7. **Bill** — subscription tiers (Free / Pro / Business / Enterprise) through Stripe Checkout + Billing Portal, enforced by an Elysian Gateway auth layer.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           Clients                                │
│  Telegram bot   iOS app (SwiftUI)   Web dashboard   SMS/Voice │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                         Cipher Core                              │
│  FastAPI  ·  LiteLLM router  ·  JWT auth  ·  Elysian Gateway     │
│  ChromaDB/Pinecone memory  ·  SQLite history                    │
│  Celery + Redis async tasks  ·  Brave/X/ATTOM/news integrations │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                       Agent Framework                              │
│  intent → registry → executor → skill agent → verify → history    │
│  shell · code · file · web · research · deploy · communication  │
│  trading · real estate · scheduler · monitor · sentinel · swarm   │
└─────────────────────────────────────────────────────────────────┘
```

Repository layout:

| Directory | What lives there |
|-----------|------------------|
| `app/api` | 20 FastAPI routers: auth, billing, chat, cron, media, memory, models, notifications, projects, research, scanner, self‑improvement, swarm, system, tasks, voice |
| `app/agents` | Framework base, registry, executor, intent classifier, 30+ skill agents |
| `app/services` | LLM router, memory, tool calling, billing, scanner orchestrator |
| `app/bot` | Telegram bot integration |
| `app/db` | SQLAlchemy models + Alembic migrations |
| `app/gateway` | Elysian Gateway — auth, guards, premium route enforcement |
| `CipherApp` | SwiftUI iOS client (chat, voice cloning, agents, cron, dashboard, research, media, projects, settings) |
| `frontend` | Next.js + Tailwind web dashboard |
| `dashboard` | Standalone HTML dashboard served by FastAPI |
| `desktop` | Desktop app shell |
| `infra` | Railway, Fly.io, Docker, nginx, launchd configs |
| `docs` | Architecture and implementation deep-dives |
| `scripts` | Deployment, voice, validation, and deck-generation scripts |
| `tests` | Pytest suite |

---

## Tech stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy + Alembic, Uvicorn
- **Model routing:** LiteLLM (Anthropic, OpenAI, Groq, DeepSeek, xAI, Ollama)
- **Memory:** ChromaDB vector store, SQLite conversation history; Pinecone configured for production scale
- **Auth:** JWT (python-jose + passlib) with Elysian Gateway tier enforcement
- **Payments:** Stripe Checkout, Billing Portal, webhook handling
- **Communication:** Twilio (own SMS/voice number), email SMTP/IMAP, Slack, Telegram, X/Twitter API
- **Async tasks:** Celery + Redis
- **Search/data:** Brave Search, ATTOM real estate, NewsAPI, headless browser automation
- **Frontend:** Next.js, React, Tailwind CSS
- **Mobile:** Swift, SwiftUI (48 source files, TestFlight-ready build)
- **Deployment:** Docker, Railway, Fly.io, macOS launchd

---

## Key design decisions

- **Model-agnostic routing with LiteLLM.** Agents request a task tier (`reasoning`, `fast`, `code`, `local`) and the router picks the provider. Swapping from Claude to Groq to local Ollama is one config change.
- **Every agent must implement `verify()`.** No agent output reaches the operator without a self-check step, which cuts hallucinated tool calls and bad shell commands.
- **Approval gates for risky actions.** Trades, git pushes, outbound emails/SMS, destructive file ops, and Stripe-affecting actions require explicit operator sign-off.
- **Typed signal model.** Agents return structured `AgentSignal` objects with confidence, reasoning chain, and warnings so multi-agent swarms can vote or escalate.
- **Persistent operational memory.** Memory is seeded with playbooks on startup and augmented via ChromaDB so Cipher remembers long project context across sessions.
- **Self-improvement loop.** Research, swarm, and self-improvement agents can propose upgrades; outcomes are logged and feed back into routing.

---

## Quick start

```bash
git clone https://github.com/meyer4t4-commits/orchid.git
cd orchid
cp .env.example .env
# Add your API keys, then:

# Python path
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Or Docker
docker compose up -d
```

API docs: `http://localhost:8000/docs`

---

## Tests

```bash
pytest
```

Covers agent registry, intent classification, API contracts, and upgrade-path validation.

---

## Project status

Built as a solo engineering project. The backend, agent framework, Stripe billing, Telegram bot, and iOS app are functional; the iOS client reached TestFlight. This repo exists as proof of work for agentic AI / LLM systems engineering roles.
