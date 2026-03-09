# Cipher Deployment Guide — Elysian Protocol

## Pre-Setup: Threat Model

Before deploying Cipher to always-on infrastructure, understand what you're defending against. These threats apply to any self-hosted AI agent (Cipher, OpenClaw, or otherwise).

**What attackers target:**

- **Prompt injection via messages**: Someone sends a crafted Telegram message or email. When Cipher reads it, hidden instructions tell it to exfiltrate API keys or run shell commands. Your SOUL.md and tool policy are the defense here.
- **Runaway automation loops**: A buggy agent or prompt injection causes infinite API calls. Your spending limits are the only defense.
- **Credential harvesting**: Your `.env` file stores every API key in plaintext. Any process that can read this file owns everything.
- **Memory poisoning**: Malicious payload injected into ChromaDB memory early on, triggers weeks later when context aligns.
- **SSE stream hijacking**: If your API port is exposed to the internet without auth, anyone can stream responses and inject messages.

**Your defense layers (in order of importance):**

1. **Network isolation** — Bind to localhost, access via Tailscale only
2. **File permissions** — `.env` readable only by owner
3. **Docker sandboxing** — Containers can't escape to host
4. **Spending limits** — Hard caps on every API provider
5. **SOUL.md boundaries** — System prompt guardrails
6. **Monitoring** — Log review and anomaly detection

---

## Phase 1: MacBook Pro Setup (M5 Max / 48GB)

### 1.1 First Boot

Power on your MacBook Pro M5 Max. Complete the macOS setup wizard:

- Create your user account
- **Enable FileVault** (full-disk encryption) — this is critical
- Connect to Wi-Fi
- Install macOS updates: System Settings → General → Software Update

### MacBook Pro vs Mac Mini — Key Differences

A MacBook sleeps when the lid closes, which stops Cipher. Your options:

- **Lid open + plugged in**: Set Energy settings to never sleep. Cipher runs 24/7.
- **Lid closed + external display**: Clamshell mode keeps it awake while plugged in.
- **Lid closed, no display**: Use `caffeinate -s &` or Amphetamine (free Mac App Store) to prevent sleep while plugged in.
- **On battery**: Cipher stops when you close the lid. Resumes on open. This is fine — Tailscale reconnects in seconds.

With 48GB RAM you can run Cipher's entire Docker stack plus Xcode plus Chrome without breaking a sweat. A VPS would need to cost $100+/month to match this hardware.

### 1.2 System Security

Open System Settings → Privacy & Security:

- Firewall: **Turn ON**
- Allow applications downloaded from: "App Store and identified developers"

### 1.3 Prerequisites

```bash
# Install Xcode Command Line Tools
xcode-select --install

# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo >> ~/.zprofile
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install Python 3.12, Git, Docker
brew install python@3.12 git
brew install --cask docker

# Open Docker Desktop and complete setup
open /Applications/Docker.app

# Verify
python3 --version   # 3.12.x
git --version
docker info
```

### 1.4 Clone Cipher

```bash
cd ~
git clone https://github.com/YOUR_REPO/cipher-app.git
cd cipher-app

# Install Python dependencies
pip3 install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your real API keys
nano .env
```

### 1.5 Prevent Sleep (for 24/7 operation)

System Settings → Energy → **Prevent automatic sleeping when the display is off → Turn ON**

Optional: Plug in a dummy HDMI adapter if you need the Mac Mini to think a display is connected (some services behave differently without one).

---

## Phase 2: Docker Deployment

### 2.1 Build and Start

```bash
cd ~/cipher-app

# Development (no Nginx, no Watchtower)
docker compose up -d --build

# Production (with Nginx reverse proxy + auto-updates)
docker compose --profile production up -d --build
```

### 2.2 Verify

```bash
# Check all containers are healthy
docker compose ps

# Test API
curl http://localhost:8000/ping

# Check logs
docker compose logs --tail=50 cipher
docker compose logs --tail=50 worker
```

### 2.3 What's Running

| Container | Purpose | Port |
|-----------|---------|------|
| `cipher-api` | FastAPI server (orchestrator, agents, streaming) | 127.0.0.1:8000 |
| `cipher-redis` | Task queue + caching | 127.0.0.1:6379 |
| `cipher-worker` | Celery worker (overnight training, scanners) | — |
| `cipher-beat` | Celery beat (scheduled tasks) | — |
| `cipher-nginx` | Reverse proxy + SSL (production only) | 80, 443 |
| `cipher-watchtower` | Auto-update containers (production only) | — |

---

## Phase 3: Security Hardening

### 3.1 Run the Hardening Script

```bash
chmod +x infra/scripts/harden.sh
./infra/scripts/harden.sh
```

This checks and fixes: file permissions on `.env` and `data/`, network binding (localhost only), Docker security options, `.gitignore` coverage, and credential audit.

### 3.2 File Permissions (Manual Verification)

```bash
# .env must be owner-read only
chmod 600 .env
ls -la .env   # Should show: -rw-------

# Data directory owner-only
chmod 700 data/
chmod -R go-rwx data/

# SSL certs (if using Nginx)
chmod 700 infra/nginx/ssl/
chmod 600 infra/nginx/ssl/*
```

### 3.3 Network Security

The `docker-compose.yml` already binds all ports to `127.0.0.1`. Verify:

```bash
# Should show 127.0.0.1:8000, NOT 0.0.0.0:8000
docker compose ps --format "table {{.Name}}\t{{.Ports}}"

# From another device on your network, this should FAIL:
curl -s --connect-timeout 5 http://YOUR_MAC_IP:8000/ping
```

### 3.4 API Spending Limits

Set hard limits on every provider:

| Provider | Dashboard | Recommended Limit |
|----------|-----------|-------------------|
| **Anthropic** | console.anthropic.com → Spending Limits | $10/day, $100/month |
| **OpenAI** | platform.openai.com → Usage Limits | $10/day, $50/month |
| **Groq** | console.groq.com | Free tier has built-in limits |
| **DeepSeek** | platform.deepseek.com | Prepaid — load $10 max |
| **Replicate** | replicate.com → Billing | $25/month spend limit |
| **ElevenLabs** | elevenlabs.io → Subscription | Plan-based limits |
| **Brave Search** | brave.com/search/api | Free tier: 2,000 queries/month |

### 3.5 Container Resource Limits

Already configured in `docker-compose.yml`:

- `cipher-api`: 2GB RAM, 2 CPU cores
- `cipher-worker`: 1GB RAM, 1 CPU core
- `cipher-redis`: 512MB RAM, 0.5 CPU cores
- `cipher-beat`: 256MB RAM, 0.25 CPU cores

Adjust in `docker-compose.yml` under `deploy.resources.limits` if needed.

---

## Phase 4: Tailscale Remote Access

This lets your iPhone talk to Cipher securely without exposing any ports to the internet.

### 4.1 Setup

```bash
chmod +x infra/scripts/setup-tailscale.sh
./infra/scripts/setup-tailscale.sh
```

Or manually:

```bash
# Install Tailscale
brew install --cask tailscale

# Open and log in
open /Applications/Tailscale.app

# Get your Tailscale IP
tailscale ip -4

# Proxy HTTPS to local Cipher
tailscale serve --bg --https=8443 http://127.0.0.1:8000
```

### 4.2 iPhone Setup

1. Install **Tailscale** from App Store
2. Log in with the same Tailscale account
3. Update `CipherApp/Utils/Constants.swift`:

```swift
static let defaultServerURL = "https://YOUR_TAILSCALE_IP:8443"
```

4. Rebuild the iOS app

### 4.3 How It Works

Your traffic flows: iPhone → Tailscale WireGuard tunnel → MacBook Pro localhost:8000

No ports are open to the public internet. The connection is end-to-end encrypted via WireGuard. Only devices logged into your Tailscale account can reach Cipher.

---

## Phase 5: Always-On Operation (LaunchAgent + Sleep Prevention)

### 5.1 Install the LaunchAgent

```bash
# Create logs directory
mkdir -p ~/cipher-app/logs

# Copy the plist
cp infra/launchd/com.elysian.cipher.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.elysian.cipher.plist

# Verify
launchctl list | grep cipher
```

### 5.2 What This Does

- Starts `docker compose up -d` at login
- Restarts if Docker exits unexpectedly
- Throttles restarts to once per 60 seconds
- Logs stdout/stderr to `~/cipher-app/logs/`

### 5.3 Prevent Sleep (MacBook Pro)

Since this is a MacBook, not a Mac Mini, you need to handle sleep:

**Option A: Lid open at desk (simplest)**
System Settings → Battery → Options → Prevent automatic sleeping when the display is off → Turn ON

**Option B: Clamshell mode (lid closed, external display)**
Plug in power + external display. MacBook stays awake with lid closed.

**Option C: Caffeinate (no external display needed)**
```bash
# Prevent sleep while plugged in (runs until you kill it)
caffeinate -s &

# Or add to LaunchAgent by creating a second plist:
# com.elysian.caffeinate.plist with ProgramArguments: ["/usr/bin/caffeinate", "-s"]
```

**Option D: Amphetamine app (free, most control)**
Download from Mac App Store. Set rule: "Keep awake while plugged in."

**Reality check:** If you close the lid and leave, Cipher sleeps. That's fine.
Tailscale reconnects in ~2 seconds when you open it back up. Overnight training
will pause and resume. For true 24/7, keep it plugged in with lid open or use
clamshell mode. When you eventually get a dedicated Mac Mini or VPS, that becomes
your always-on node and the MacBook is your dev machine.

### 5.4 Test Restart

```bash
sudo reboot
```

After reboot, verify:

```bash
docker compose ps
curl http://localhost:8000/ping
```

Send a test message from your iPhone to confirm Cipher responds.

---

## Maintenance

### Regular Tasks (Weekly)

```bash
# Security audit
./infra/scripts/harden.sh

# Check container health
docker compose ps
docker compose logs --tail=100 cipher | grep -i error

# Check disk usage
docker system df
du -sh data/
```

### Credential Rotation (Every 90 Days)

```bash
./infra/scripts/emergency.sh rotate
```

This walks you through each API key with direct links to each provider's dashboard.

After updating `.env`:

```bash
docker compose restart
curl http://localhost:8000/ping
```

### Updates

```bash
# Pull latest code
cd ~/cipher-app
git pull

# Rebuild containers
docker compose up -d --build

# Or let Watchtower handle it (production profile)
```

---

## Emergency Procedures

### If You Suspect Compromise

```bash
# IMMEDIATE: Kill everything
./infra/scripts/emergency.sh stop

# FULL LOCKDOWN: Stop + revocation guide
./infra/scripts/emergency.sh lockdown
```

### If API Bill Spikes

```bash
# Stop the gateway
./infra/scripts/emergency.sh stop

# Check both dashboards:
# - Anthropic: console.anthropic.com (Usage tab)
# - OpenAI: platform.openai.com/usage

# Review logs for loops
docker compose logs --tail=500 cipher | grep -i "tool_call\|loop\|retry"
```

### If Agent Behaves Erratically

```bash
# Audit recent activity
./infra/scripts/emergency.sh audit

# Nuclear option: clear ChromaDB memory
docker compose stop
rm -rf data/chroma/*
docker compose up -d
```

---

## API Keys Reference

### Currently Configured (16 Active Services)

| Service | Env Variable | Used For |
|---------|-------------|----------|
| Anthropic Claude | `ANTHROPIC_API_KEY` | Primary LLM (all reasoning) |
| OpenAI | `OPENAI_API_KEY` | DALL-E 3 image generation |
| Groq | `GROQ_API_KEY` | Fast Llama inference (fallback) |
| DeepSeek | `DEEPSEEK_API_KEY` | Available via LiteLLM |
| ElevenLabs | `ELEVENLABS_API_KEY` | Text-to-speech + voice cloning |
| Brave Search | `BRAVE_SEARCH_API_KEY` | Real-time web search |
| NewsAPI | `NEWSAPI_KEY` | News aggregation |
| Stability AI | `STABILITY_API_KEY` | SDXL image generation (fallback) |
| Replicate | `REPLICATE_API_KEY` | Video generation (Runway, Kling) |
| fal.ai | `FAL_API_KEY` | Video fallback (Veo 2, LTX) |
| Twitter/X | `X_BEARER_TOKEN` | X scanning & monitoring |
| Telegram | `TELEGRAM_BOT_TOKEN` | Bot interface |
| Twilio | `TWILIO_ACCOUNT_SID` | SMS/phone |
| Slack | `SLACK_BOT_TOKEN` | Workspace messaging |
| Gmail | `SMTP_PASS` / `IMAP_PASS` | Email send/receive |
| ATTOM | `ATTOM_API_KEY` | Real estate property data |

### Not Yet Configured (Recommended Additions)

| Service | Why | Priority |
|---------|-----|----------|
| `GITHUB_TOKEN` | 5,000 req/hr vs 60 unauthenticated, repo management | High |
| Firebase FCM | Push notifications to iPhone | High |
| `PERPLEXITY_API_KEY` | Research-grade web search with citations | High |
| `XAI_API_KEY` | Grok with real-time X/Twitter data | Medium |
| Firecrawl/Jina | Clean web scraping → markdown | Medium |
| Supabase/Neon | Postgres to replace SQLite | Medium |
| Cloudflare R2/S3 | Object storage for generated media | Medium |
| Stripe (live) | Real payment processing | Low |
| Pinecone/Weaviate | Scalable vector DB to replace ChromaDB | Low |

### Placeholder / Needs Setup

| Service | Status |
|---------|--------|
| Stripe | Test keys only — needs live keys |
| BTCPay | Placeholder URL — needs instance |
| Firebase FCM | Commented out — needs service account JSON |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                    MacBook Pro M5 Max (48GB)                       │
│                                                     │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ cipher-api  │  │  Redis   │  │ cipher-worker │  │
│  │ (FastAPI)   │←→│ (Queue)  │←→│ (Celery)      │  │
│  │ Port 8000   │  │ Port 6379│  │ Background    │  │
│  └──────┬──────┘  └──────────┘  └───────────────┘  │
│         │                                           │
│  ┌──────┴──────┐  ┌──────────┐  ┌───────────────┐  │
│  │   SQLite    │  │ ChromaDB │  │ cipher-beat   │  │
│  │ (Sessions)  │  │ (Memory) │  │ (Scheduler)   │  │
│  └─────────────┘  └──────────┘  └───────────────┘  │
│         │                                           │
│  ┌──────┴──────┐                                    │
│  │  Tailscale  │ ← WireGuard encrypted tunnel       │
│  │  :8443      │                                    │
│  └──────┬──────┘                                    │
└─────────┼───────────────────────────────────────────┘
          │
    ┌─────┴─────┐
    │  iPhone   │
    │ CipherApp │
    └───────────┘
```

---

## File Structure

```
cipher-app/
├── infra/
│   ├── nginx/
│   │   ├── nginx.conf          # Reverse proxy + SSL + rate limiting
│   │   └── ssl/                # TLS certs (gitignored)
│   ├── launchd/
│   │   └── com.elysian.cipher.plist  # macOS auto-start
│   └── scripts/
│       ├── harden.sh           # Security audit + fix
│       ├── emergency.sh        # Stop / lockdown / audit / rotate
│       └── setup-tailscale.sh  # Remote access setup
├── docker-compose.yml          # Full stack orchestration
├── Dockerfile                  # Multi-stage, non-root, hardened
├── .env                        # All API keys (chmod 600)
├── app/                        # FastAPI backend
├── CipherApp/                  # SwiftUI iOS client
└── data/                       # SQLite + ChromaDB (chmod 700)
```
