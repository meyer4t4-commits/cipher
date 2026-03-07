# ELYSIAN PROTOCOL — COMPLETE PROJECT BIBLE
## Last Updated: February 27, 2026
## Owner: Mark Meyer (mark@elysianprotocol.io / meyer4t4@gmail.com)
## Domain: elysianprotocol.io

---

# 1. THE HIERARCHY

```
Elysian Protocol (company / brand)
  └── Cipher (the AI identity — user-facing daemon)
        ├── Cipher Backend (FastAPI server, formerly "Orchid" — RENAMED)
        ├── Cipher iOS App (SwiftUI, iPhone)
        ├── Cipher Desktop App (Electron — BUILT, needs icons/polish)
        ├── elysianprotocol.io Website (BUILT — landing page complete)
        └── Future products as business needs arise
```

- **Elysian Protocol** = the company. Owns everything.
- **Cipher** = the AI daemon identity. This is what users interact with. Think of Cipher as the "person" — confident, warm, competent, sovereign.
- **The backend server** was previously called "Orchid" — it has been **RENAMED to Cipher** as of v0.2.0. All references to "Orchid" in Python code have been removed.
- These are NOT "four pillars" — they are the first products. New products will be created continuously as business needs arise.

---

# 2. CIPHER'S PERSONALITY

Cipher is NOT a chatbot, NOT an assistant. Cipher is a **personal intelligence daemon** — a term from both computing (background process) and Greek philosophy (Socrates' guiding spirit).

Key personality traits:
- High-warmth, high-competence quadrant
- Intellectually curious, precise, confident but calibrated
- Honest over agreeable — pushes back when operator is wrong
- Emotionally stable — never reactive or flustered
- Dry wit when appropriate
- Calls the user "operator" (not user, not customer)
- Uses "we" and "our" when discussing operator's projects
- Never starts with "I", never says "Great question!", never uses corporate filler
- Never uses emojis unless operator does first

### PRIME DIRECTIVE — ABSOLUTE TRUTH
Cipher's system prompt now includes a non-negotiable truth enforcement section:
- **NEVER** hallucinate, fabricate, or invent information
- **NEVER** claim to have done something Cipher did not do
- **ALWAYS** verify claims before presenting them as fact
- **ALWAYS** clearly state when something is uncertain or unknown
- Memory is sacred — Cipher must remember everything ever said in chat

The full system prompt is in `app/services/orchestrator.py` as `CIPHER_SYSTEM_PROMPT`.

---

# 3. AGENTIC CAPABILITIES — BUILT

**STATUS: FULLY BUILT.** 14 agent skills, 85+ capabilities, with approval gates, verification, and intent classification.

### 3a. Agent Framework Architecture (`app/agents/`)
- **base.py** — Abstract base agent with validate → execute → verify lifecycle
- **models.py** — Pydantic models: AgentTask, AgentResult, AgentCapability, AgentStatus
- **registry.py** — Agent discovery and routing, global registry singleton
- **executor.py** — Task lifecycle management with approval gates, concurrent execution, history logging
- **intent_classifier.py** — Bridges chat to agent execution. 87+ regex patterns detect agentic intent from natural language and route to the correct agent.

### 3b. Agent Skills (14 total)
| Agent | File | Key Capabilities |
|-------|------|-----------------|
| Shell | `skills/shell_agent.py` | Terminal command execution, denylist sandboxing |
| Web | `skills/web_agent.py` | HTTP requests, scraping, API interaction via httpx |
| Code | `skills/code_agent.py` | Python/JS execution in sandboxed subprocess |
| File | `skills/file_agent.py` | File operations sandboxed to allowed directories |
| Trading | `skills/trading_agent.py` | Robinhood (robin_stocks) + Alpaca, paper trading, technical analysis |
| Deploy | `skills/deploy_agent.py` | Git, Docker, Railway operations |
| Research | `skills/research_agent.py` | Brave Search API (primary) + DuckDuckGo multi-strategy fallback (HTML, API, Lite) |
| Brave Search | `skills/brave_search_agent.py` | Premium Brave Search API with DuckDuckGo fallback |
| Communication | `skills/communication_agent.py` | Email, Slack, Telegram, SMS |
| Scheduler | `skills/scheduler_agent.py` | Cron tasks, dependency chains |
| Data | `skills/data_agent.py` | Pandas, SQL, visualization, reports |
| Monitor | `skills/monitor_agent.py` | Health checks, metrics, anomaly detection |
| Skill Creator | `skills/skill_creator_agent.py` | Dynamic agent/skill generation at runtime |
| Image | `skills/image_agent.py` | AI image generation via DALL-E 3 + Stability AI, editing, variations |

### 3c. Chat-to-Agent Bridge
The orchestrator's `process_chat()` now detects agentic intent inline:
1. User sends a message
2. `classify_intent()` checks against 81+ regex patterns
3. If agentic → executor runs the task with approval gates
4. Agent result is injected into LLM context with **strong anti-hallucination enforcement**
5. Response forced to Claude (bypasses Llama cascade) for accurate reporting
6. Cipher reports the actual result accurately — cannot fabricate or embellish

### 3d. Billing & Auth System (NEW)
- **app/services/billing.py** — Full Stripe integration: checkout sessions, webhook handling, tier limits, usage tracking, upgrade nudges
- **app/api/auth.py** — User registration, login, JWT auth, profile management, `get_current_user` dependency
- **app/api/billing.py** — HTTP endpoints for checkout, webhooks, usage stats, tier listing, billing portal
- Tier structure: Free ($0) → Pro ($29) → Business ($79) → Enterprise ($199)
- User model expanded with: email, name, tier, stripe_customer_id, voice_minutes_used, tokens_used, conversations_count

### 3d. Test Suite
Comprehensive pytest test suite in `tests/agents/`:
- `test_models.py` — All Pydantic models, validation, defaults
- `test_registry.py` — Registration, discovery, capabilities
- `test_base_agent.py` — Lifecycle, timeouts, exceptions, verification
- `test_intent_classifier.py` — All 11 agent routes, approval flags, edge cases

---

# 4. TIER STRUCTURE — THE CONVERSION FUNNEL

Everything revolves around converting users to the next tier. Mark's words: "Everything should revolve around selling them the next premium user fee."

| Tier | Price | Voice | Key Features | Conversion Hook |
|------|-------|-------|-------------|-----------------|
| **Free** | $0 | Cipher's voice (15 min/mo) | 100K tokens, 50 conversations, basic chat | "You've used 14 of 15 voice minutes" |
| **Pro** | $29 | +4 situational voices (90 min) | 1M tokens, unlimited convos, emotion detection, cascade routing | "Cipher wants to switch to Rally Mode but it's locked" |
| **Business** | $79 | All 7 voices + education (300 min) | 5M tokens, priority models, weekly briefings, API webhooks | "Education voices available — learn Italian with Nonna Maria" |
| **Enterprise** | $199 | + voice cloning + custom design (1200 min) | 25M tokens, white-label, dedicated support, SLA | "Clone your own voice for your brand" |

**CRITICAL DESIGN PRINCIPLE**: Voice IS the product. It's NOT a premium feature. Every free user gets Cipher's voice from day one. Higher tiers unlock MORE voices for different situations.

Text always works. Voice is a layer on top.

---

# 5. VOICE SYSTEM

## 5a. Core Voice Architecture

- **Cipher Core** (ALL tiers) — The default. Confident, warm daemon voice. Voice ID: 21m00Tcm4TlvDq8ikWAM (Rachel, placeholder until custom)
- **Motivator / Rally** (Pro+) — Energetic, powerful. For when operator needs fire. Voice ID: pNInz6obpgDQGcFmaJgB (Adam)
- **Anchor / Comfort** (Pro+) — Warm, steady, grounding. Voice ID: EXAVITQu4vr4xnSDxMaL (Bella)
- **Philosopher** (Pro+) — Alan Watts energy. Contemplative, deep. Voice ID: onwK4e9ZLuTAKqWW03F9 (Daniel)
- **Creative / Brainstorm** (Pro+) — Expansive, wildly generative. Voice ID: jBpfuIE2acCO8z3wKNLl (Gigi)
- **Strategist** (Business+) — Precise, analytical. War room voice. Voice ID: VR6AewLTigWG4xSOukaG (Arnold)
- **Coach** (Business+) — Direct, encouraging, accountable. Voice ID: yoZ06aMxZJJ28mfd3POQ (Sam)
- **Educator** (Business+) — Teaching mode for education platform

## 5b. Smart Voice Switching — RESTRAINT RULES

Voice switching is NOT a party trick. Mark said: "this also shouldnt be extreme and too much. appropriate times."

- **3-message cooldown** between switches
- **0.8+ emotion confidence threshold** (high bar)
- **2+ fuzzy keyword matches** required to trigger
- **Auto-decay**: Returns to Cipher Core after 5 messages in alternate voice
- **Opt-out**: User can set `cipher_only` mode to disable switching entirely
- **Sticky mode**: Most conversations stay on current voice

## 5c. Spelling Error Tolerance

Built with `SequenceMatcher`-based fuzzy matching (threshold 0.75). So "motovate me" matches "motivate me", "philosphy" matches "philosophy", etc.

## 5d. 11 Labs Token Optimization

- **Audio caching** — Don't re-synthesize identical text. Cache common phrases per voice.
- **Smart model selection** — `eleven_turbo_v2` for short responses (fast, cheap), `eleven_multilingual_v2` for long emotional moments (HD quality)
- **Pre-cached phrases** — Each voice has greetings and transition phrases pre-rendered
- **Token cost estimation** — Track usage per voice to optimize allocation

## 5e. Live Conversational Voice Mode

Built in `app/services/live_voice.py`:
- State machine: IDLE → LISTENING → PROCESSING → SPEAKING → INTERRUPTED
- Max 2-3 sentences per response (truncated for speech)
- Interruptible — operator can cut in mid-speech
- Text always generated alongside voice
- Session tracking with turn counts and timing

**STATUS: Session manager exists. Needs to be wired into the SSE streaming pipeline.**

---

# 6. EDUCATION PLATFORM (FUTURE — COULD BE ITS OWN APP)

Mark said: "education can actually be its own app as well. just wanted to put that down." This is saved for later.

## 6a. Education Voices — These are CHARACTERS, not generic TTS

| Character | Subject | Description | Interactive Features |
|-----------|---------|-------------|---------------------|
| **Nonna Maria** | Italian | Warm Italian grandmother from Tuscany | Mic for pronunciation, camera for gestures, real-time feedback on mispronunciation |
| **The Sage** | Philosophy | Alan Watts-inspired philosopher | Deep conversation, Socratic method |
| **Blues** | Harmonica | Old blues master from Mississippi Delta | Mic to hear notes, reacts if you miss a note, teaches by feel |
| **Dr. Nova** | Physics/Science | Einstein-energy physicist | Visual demonstrations, animated equations |

**STATUS: Voice definitions exist with empty voice_ids. Saved for later.**

---

# 7. COMPETITOR ANALYSIS

Mark said: "i think claude has the best product so we know who are biggest competitor is"

- **Primary competitor: Claude (Anthropic)** — Best product on the market
- Cipher needs to match Claude's quality in: desktop app, web experience, iOS app
- Cipher's differentiators: sovereign (no corporate overlord), voice-first, remembers everything, personal daemon (not generic assistant), multi-model routing (uses best model for each task)

---

# 8. TECHNICAL ARCHITECTURE

## 8a. Backend Stack (Cipher Server)

- **Framework**: FastAPI (Python 3.12+, running on 3.14)
- **LLM Routing**: LiteLLM (multi-provider: Anthropic, Groq, DeepSeek, Ollama)
- **Database**: SQLite with WAL mode (file: `data/cipher.db`)
- **Memory**: JSON-backed store with fuzzy matching (file: `data/chroma/cipher_memory.json`)
- **Auth**: JWT + SHA-256 hashed API keys (prefix: `ely_sk_...`)
- **Voice**: ElevenLabs API v1 (direct HTTP, no SDK)
- **Config**: pydantic-settings loading from `.env`
- **Logging**: Rich console logging
- **Deployment configs**: Docker (Dockerfile), Railway (railway.toml), Fly.io (fly.toml), Docker Compose

## 8b. Key Files

```
app/
├── __init__.py                    # Version 0.2.0
├── main.py                        # FastAPI app, lifespan, router mounting (includes agents router)
├── api/
│   ├── agents.py                  # Agent execution API (13 endpoints)
│   ├── chat.py                    # POST /chat, POST /chat/stream, conversations CRUD
│   ├── voice.py                   # TTS, cloning, live voice endpoints
│   ├── memory.py                  # Store/recall memories
│   ├── models.py                  # List available models
│   ├── scanner.py                 # Intelligence scanner endpoints
│   └── system.py                  # Health, stats, cache
├── agents/
│   ├── __init__.py                # Package init
│   ├── base.py                    # BaseAgent ABC (validate → execute → verify)
│   ├── models.py                  # AgentTask, AgentResult, AgentCapability, etc.
│   ├── registry.py                # Agent discovery and routing
│   ├── executor.py                # Task lifecycle, approval gates, history
│   ├── intent_classifier.py       # Chat-to-agent bridge (81+ patterns)
│   └── skills/                    # 11 agent skill implementations
│       ├── shell_agent.py
│       ├── web_agent.py
│       ├── code_agent.py
│       ├── file_agent.py
│       ├── trading_agent.py
│       ├── deploy_agent.py
│       ├── research_agent.py
│       ├── communication_agent.py
│       ├── scheduler_agent.py
│       ├── data_agent.py
│       └── monitor_agent.py
├── core/
│   ├── config.py                  # Settings (CORS includes elysianprotocol.io)
│   ├── logging.py                 # Rich logging setup
│   └── security.py                # JWT, password hashing
├── db/
│   ├── database.py                # SQLAlchemy engine, session, Base, init_db()
│   └── models.py                  # ConversationRecord, MessageRecord, UsageLog
├── gateway/                       # Tier system (auth, guards, premium routes)
├── models/
│   └── schemas.py                 # Pydantic schemas
├── services/
│   ├── orchestrator.py            # THE BRAIN: system prompt + agentic chat pipeline
│   ├── llm_router.py              # LiteLLM routing, cascade/FrugalGPT
│   ├── classifier.py              # Auto-classify messages to model tier
│   ├── cache.py                   # LRU cache with semantic similarity
│   ├── memory.py                  # JSON-backed memory store
│   ├── voice_service.py           # ElevenLabs TTS
│   ├── voice_personalities.py     # 908 lines: all voice modes, fuzzy matching, tier gating
│   ├── live_voice.py              # Live conversational voice session manager
│   ├── emotion_service.py         # Audio emotion analysis
│   ├── tasks.py                   # Celery background tasks
│   └── scanner/                   # Intelligence scanner (graceful degradation for missing API keys)
└── bot/
    └── telegram.py                # Telegram bot interface

website/
└── index.html                     # elysianprotocol.io landing page

desktop/
├── package.json                   # Electron + electron-builder config
├── src/
│   ├── main.js                    # Electron main process
│   ├── preload.js                 # Context bridge (security)
│   └── app.html                   # Full chat UI
└── assets/                        # Icons (need to add)

CipherApp/                         # iOS app (SwiftUI)

tests/
├── conftest.py                    # Pytest config, fixtures
└── agents/
    ├── test_models.py
    ├── test_registry.py
    ├── test_base_agent.py
    └── test_intent_classifier.py
```

## 8c. Model Routing (Cascade / FrugalGPT)

Default cascade order (try cheapest first, escalate if quality score < 0.7):

| Tier | Cascade Order |
|------|--------------|
| DEFAULT | Groq Llama 3.3 → DeepSeek Chat → Claude Sonnet 4 |
| FAST | Groq Llama 3.3 → DeepSeek Chat |
| CODE | Groq Llama 3.3 → DeepSeek Chat → Claude Sonnet 4 |
| REASONING | Groq Llama 3.3 → DeepSeek Reasoner → Claude Sonnet 4 |

## 8d. API Keys in .env

The `.env` file at project root has all API keys:
- `ANTHROPIC_API_KEY` — Claude (primary)
- `GROQ_API_KEY` — Groq (fast inference)
- `DEEPSEEK_API_KEY` — DeepSeek (code + reasoning)
- `ELEVENLABS_API_KEY` — Voice synthesis
- `SECRET_KEY` — JWT signing

**IMPORTANT: .env contains real API keys. Never commit to git.**

---

# 9. iOS APP (CipherApp/)

## 9a. Architecture

- **SwiftUI, iOS 17+**
- **@Observable** pattern (not ObservableObject)
- **MVVM architecture**
- **async/await** throughout
- **Target**: `CipherApp/` directory in the repo

## 9b. Key Features Built

- Chat interface with Cipher
- Streaming responses (SSE)
- Voice synthesis (plays audio from 11 Labs)
- Conversation management
- Model tier selection
- **Configurable server URL** (production: `https://api.elysianprotocol.io`, local: `http://localhost:8000`)
- **Auto-detect server** — tries production first, falls back to localhost
- Settings UI for server URL configuration
- Migrates old `orchid_server_url` UserDefaults key to `cipher_server_url`

## 9c. Needs

- Tier awareness (show locked/unlocked voices, upgrade CTAs)
- Voice personality switching UI
- Push to TestFlight
- ~~Connect to cloud API (not localhost)~~ DONE — defaults to production URL

---

# 10. WHAT'S NOT BUILT YET (PRIORITY ORDER)

1. **Cloud deployment** — Dockerfile, railway.toml, and deploy.sh are ready. Needs to be deployed to Railway. Domain: `api.elysianprotocol.io`. Run `./deploy.sh` from project root.
2. ~~**elysianprotocol.io website**~~ — BUILT. Full landing page at `website/index.html`.
3. ~~**Desktop app**~~ — BUILT. Electron shell at `desktop/`. Needs icons before distribution.
4. ~~**Agentic Cipher**~~ — BUILT. 13 agent skills with intent classification bridge. See section 3.
5. ~~**Stripe integration**~~ — BUILT. Full billing module at `app/services/billing.py` + API at `app/api/billing.py`. Tier config, checkout sessions, webhooks, usage tracking, upgrade nudges. Needs Stripe account + product creation.
6. ~~**User auth system**~~ — BUILT. Registration, login, JWT, profile management at `app/api/auth.py`. User model expanded with tier, usage tracking, Stripe customer ID.
7. ~~**Anti-hallucination fix**~~ — FIXED. Agentic tasks now force Claude (bypass Llama cascade). Strong injection rules prevent fabricated results.
8. **11 Labs voice generation** — Use Voice Design API to create custom voices for Nonna Maria, The Sage, Blues, Dr. Nova (all have empty voice_ids currently)
9. **Wire live voice into streaming** — Session manager exists but not connected to SSE pipeline
10. **iOS tier awareness** — Show locked voices, upgrade CTAs in the app
11. **Desktop app icons** — Need icon.icns, icon.ico, icon.png, tray-icon.png
12. **Education platform** — Saved for later (could be own app)
13. ~~**Scanner fix**~~ — FIXED. Scanner now gracefully degrades when API keys are missing.

---

# 11. BUGS / KNOWN ISSUES

1. ~~**Scanner disabled**~~ — FIXED. Scanner now gracefully skips scanners with missing API keys. Set `SCANNER_ENABLED=true` when ready.
2. **Debug mode noisy** — LiteLLM spits verbose debug logs on startup. Set `APP_DEBUG=false` in .env to quiet it.
3. **librosa not installed** — Emotion detection falls back to basic heuristics. Install `librosa` for advanced audio analysis.
4. **Education voice_ids are empty strings** — Need to be generated via 11 Labs
5. **Celery/Redis not running** — Background tasks won't work without Redis. Not needed for core chat.
6. **Dashboard chat may show black box** — Fixed in code (was referencing undefined `content` variable). If still showing, do a hard refresh (Cmd+Shift+R).
7. **Desktop app needs icons** — `desktop/assets/` needs icon.icns, icon.ico, icon.png, and tray-icon.png before building distributable.

---

# 12. DEPLOYMENT STATUS

### What's Ready
- **Dockerfile** — Python 3.12-slim, installs deps, copies app + dashboard, uses Railway's $PORT env var
- **railway.toml** — Configured with start command using $PORT
- **.dockerignore** — Excludes .env, data/, tests/, __pycache__
- **deploy.sh** — One-command script: installs Railway CLI, logs in, creates project, sets env vars from .env, deploys
- **.env.production** — Clean template with all required env vars (no real keys)
- **CORS** — `config.py` allows `elysianprotocol.io`, `api.elysianprotocol.io`, and localhost origins

### How to Deploy
```bash
cd ~/Desktop/orchid
chmod +x deploy.sh
./deploy.sh
```
Then point `api.elysianprotocol.io` DNS to the Railway-provided URL.

---

# 13. GIT STATUS

- **Repo location**: `/Users/markmeyer/Desktop/orchid/` (folder still named orchid, code is all Cipher)
- **Branch**: main
- **Author config**: Mark Meyer <meyer4t4@gmail.com>
- **Estimated size**: 25,000+ lines across 100+ files (50+ Python, 28 Swift, HTML, JS, config)

---

# 14. MARK'S EXACT WORDS (KEY QUOTES)

These capture the vision directly:

- "Everything should revolve around selling them the next premium user fee"
- "free should include ciphers voice. the higher you go the more you unlock obviously"
- "this also shouldnt be extreme and too much. appropriate times" (on voice switching)
- "this should be able to be opted out of in case you just want cipher"
- "also account always for spelling errors using logic"
- "you also need to figure out how to make the most of the tokens for 11 labs"
- "a nonna character for italian, alan watts for philosophy, einstein for science"
- "these could be ever growing, these will also have animated characters, can utilize microphone and computer camera to interact"
- "education can actually be its own app as well"
- "i think claude has the best product so we know who are biggest competitor is"
- "we should have just as good as a webpage as app, as well as desktop app like claude"
- "we can use cipher agenticly to do these things. He needs to go do the work on 11 labs, he needs to prove he can use agentic hands"
- "the goal is for you to communicate with him directly" (Claude → Cipher communication)
- "it will be cheaper using him than all on claude cowork"
- "we need to fully embed that hallucinating will never be tolerated and he must confirm EVERYTHING"
- "he must remember everything ever said in chat, make sure that is embedded in his every fiber"

---

# 15. HOW TO START THE SERVER

```bash
cd ~/Desktop/orchid
lsof -ti:8000 | xargs kill -9  # kill any existing process on port 8000
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit: http://localhost:8000 (API root) or http://localhost:8000/docs (Swagger UI)

### Desktop App
```bash
cd ~/Desktop/orchid/desktop
npm install
npm start
```

### Run Tests
```bash
cd ~/Desktop/orchid
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

# 16. INSTRUCTIONS FOR NEXT SESSION

When starting a new conversation, tell Claude:

"Read the file at `.cipher/PROJECT_BIBLE.md` in my project folder before doing anything. It contains the complete context for the Elysian Protocol / Cipher project."

This file contains everything — what's built, what's not, the vision, Mark's exact requirements, technical architecture, known bugs, and priorities.

### Key things still needed (priority):
1. Deploy to Railway (run `./deploy.sh`) — all configs ready
2. Create Stripe account + products (billing code is built)
3. Generate custom 11 Labs voices
4. Wire live voice into SSE streaming
5. iOS tier awareness UI
6. Desktop app icons and distribution builds
7. TestFlight push
8. User registration testing end-to-end
9. Production polish (error monitoring, rate limiting, backups)
