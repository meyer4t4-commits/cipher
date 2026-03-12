# Cipher Backend — Complete API Reference

**Built by:** Elysian Protocol
**Framework:** FastAPI (Python)
**Entry Point:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/main.py`

---

## Table of Contents

1. [Application Setup & Lifecycle](#application-setup--lifecycle)
2. [Core API Structure](#core-api-structure)
3. [Chat & Conversation API](#chat--conversation-api)
4. [Agents API](#agents-api)
5. [Voice API](#voice-api)
6. [Media Generation API](#media-generation-api)
7. [Scanner API](#scanner-api)
8. [Memory API](#memory-api)
9. [System & Models API](#system--models-api)
10. [Gateway & Premium APIs](#gateway--premium-apis)
11. [Projects & Credentials API](#projects--credentials-api)
12. [Notifications API](#notifications-api)
13. [Research API](#research-api)
14. [Cron & Scheduled Tasks API](#cron--scheduled-tasks-api)
15. [Recommendations API](#recommendations-api)
16. [Streaming & Real-Time Features](#streaming--real-time-features)
17. [Data Models & Schemas](#data-models--schemas)

---

## Application Setup & Lifecycle

**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/main.py`

### Lifespan Management

The app uses FastAPI's `@asynccontextmanager` lifespan hook to:

1. **Initialize services on startup:**
   - Loads all API keys from environment → exports to `os.environ` for agent access
   - Initializes database (SQLite or PostgreSQL)
   - Starts scanner if enabled
   - Logs configured LLM providers (Anthropic, Groq, OpenAI, DeepSeek, xAI)

2. **Configure third-party integrations:**
   - LLM providers: Anthropic, Groq, OpenAI, DeepSeek, xAI
   - Voice: ElevenLabs
   - Media: Stability AI, Replicate, FAL
   - Search: Brave Search API
   - Communication: Twilio (SMS/Voice), SMTP/IMAP (email), Slack
   - Financial: ATTOM Real Estate API
   - News: NewsAPI
   - Social: Twitter/X API

3. **Cleanup on shutdown:**
   - Stops scanner
   - Closes voice service

### Environment Variables Required

See `app/core/config.py` for configuration. Key variables:
- `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`
- `ELEVENLABS_API_KEY` (voice)
- `STABILITY_API_KEY`, `REPLICATE_API_TOKEN`, `FAL_KEY` (media)
- `BRAVE_SEARCH_API_KEY` (critical for anti-hallucination)
- `DATABASE_URL` or local SQLite at `/app/data/cipher.db`

---

## Core API Structure

### Root Endpoint

**GET** `/`
Returns app metadata:
```json
{
  "name": "Cipher",
  "version": "string",
  "status": "operational",
  "by": "Elysian Protocol",
  "gateway": "Elysian Gateway v1.0",
  "mode": "development|production",
  "features": "/api/v1/features/available",
  "pricing": "/api/v1/gateway/tiers",
  "docs": "/docs"
}
```

### Health Check

**GET** `/api/v1/system/health`
Returns system health status.

**GET** `/ping`
Simple liveness probe.

### CORS Configuration

Allow-Origin: `*`
Allow-Methods: `*`
Allow-Headers: `*`

---

## Chat & Conversation API

**Base Path:** `/api/v1/chat`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/chat.py`

### Send Message (Standard)

**POST** `/api/v1/chat/`

Send a chat message and receive a complete response.

**Request (ChatRequest):**
```json
{
  "message": "string",
  "conversation_id": "string|null",
  "model_tier": "reasoning|fast|local|code|default|auto",
  "system_prompt": "string|null",
  "include_memory": true,
  "max_tokens": 4096,
  "temperature": 0.7,
  "stream": false,
  "images": ["base64-encoded-image-1", "base64-encoded-image-2"]
}
```

**Response (ChatResponse):**
```json
{
  "message": "string",
  "conversation_id": "string",
  "model_used": "string (e.g., claude-opus, gpt-4)",
  "tokens_used": 0,
  "cost_usd": 0.0,
  "timestamp": "2026-03-10T12:00:00Z",
  "recommended_agent": {
    "agent_name": "string",
    "display_name": "string",
    "reason": "string",
    "confidence": 0.95,
    "suggested_instruction": "string"
  },
  "images": [
    {
      "url": "string",
      "mime_type": "image/png",
      "analysis": "string|null"
    }
  ],
  "confidence_score": 0.85,
  "validation_warnings": ["string|null"]
}
```

**Features:**
- Optional API key for premium mode (`X-Elysian-Key` header)
- Memory integration (retrieves relevant context)
- Model tier routing
- Image analysis support
- Auto-classification for recommended agents

### Stream Message (Real-Time)

**POST** `/api/v1/chat/stream`

Stream response token-by-token via Server-Sent Events (SSE).

**Request:** Same as above.

**Response:** SSE stream with events:

```
event: token
data: {"type": "token", "content": "word"}

event: token
data: {"type": "token", "content": " or"}

event: image
data: {"type": "image", "url": "...", "mime_type": "image/png", "analysis": "..."}

event: metadata
data: {
  "type": "metadata",
  "model_used": "string",
  "tokens_used": 123,
  "cost_usd": 0.05,
  "conversation_id": "string",
  "confidence_score": 0.9,
  "has_images": 0
}

data: [DONE]
```

**Features:**
- Keepalive pings every 5s (iOS timeout protection)
- Chunked responses (3-char chunks)
- Images streamed separately
- Metadata at end
- Error handling with fallback messages

### Upload Image for Chat

**POST** `/api/v1/chat/upload-image`

Upload image for inclusion in chat.

**Request (multipart/form-data):**
- `file`: Image file (JPEG/PNG/WebP/GIF, max 5MB)

**Response:**
```json
{
  "base64": "string",
  "mime_type": "image/jpeg",
  "size_bytes": 123456,
  "filename": "photo.jpg"
}
```

### List Conversations

**GET** `/api/v1/chat/conversations`

**Query Parameters:**
- `limit` (int, default 20)
- `offset` (int, default 0)

**Response:**
```json
[
  {
    "id": "string",
    "title": "string|null",
    "created_at": "2026-03-10T12:00:00Z",
    "updated_at": "2026-03-10T12:00:00Z",
    "message_count": 42,
    "last_message_preview": "string|null"
  }
]
```

### Get Conversation

**GET** `/api/v1/chat/conversations/{conversation_id}`

**Response (Conversation):**
```json
{
  "id": "string",
  "title": "string|null",
  "messages": [
    {
      "role": "user|assistant|system",
      "content": "string",
      "timestamp": "2026-03-10T12:00:00Z"
    }
  ],
  "created_at": "2026-03-10T12:00:00Z",
  "updated_at": "2026-03-10T12:00:00Z",
  "message_count": 42,
  "model_tier": "default"
}
```

### Delete Conversation

**DELETE** `/api/v1/chat/conversations/{conversation_id}`

**Response:**
```json
{
  "status": "deleted",
  "conversation_id": "string"
}
```

---

## Agents API

**Base Path:** `/api/v1/agents`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/agents.py`

### Key Concepts

**29 Registered Agents** (lazy-loaded on first call):
- ShellAgent, WebAgent, CodeAgent, FileAgent
- TradingAgent, DeployAgent, ResearchAgent, CommunicationAgent
- SchedulerAgent, DataAgent, MonitorAgent, SkillCreatorAgent
- BraveSearchAgent, ImageAgent, VideoAgent, LegalAgent
- ApexArchitectAgent, ScoutAgent, AnalystAgent, OutreachAgent
- ProvisioningAgent, MarketPulseAgent, ProfitabilityAnalystAgent
- NeighborhoodGrowthAgent, DealFlowAgent, ChronosAgent
- ArchivistAgent, SentinelAgent, SynthesisAgent

### Execute Task

**POST** `/api/v1/agents/execute`

Execute a single task with an agent.

**Request (AgentTaskRequest):**
```json
{
  "agent_name": "WebAgent",
  "instruction": "Scrape the homepage and extract the main heading",
  "params": {
    "url": "https://example.com"
  },
  "timeout_seconds": 60,
  "priority": 1
}
```

**Response (AgentResult):**
```json
{
  "task_id": "string",
  "agent_name": "string",
  "success": true,
  "output": "string or object",
  "error": "string|null",
  "execution_time_ms": 2500,
  "verified": true
}
```

### Execute Task with Streaming

**POST** `/api/v1/agents/execute/stream`

Execute task with real-time SSE progress updates.

**Response:** SSE stream with events:

```
event: progress
data: {"type": "progress", "message": "Starting execution..."}

event: bash
data: {"type": "bash", "message": "Running: curl https://example.com"}

event: chain
data: {"type": "chain", "message": "Invoking FileAgent..."}

event: result
data: {
  "task_id": "string",
  "agent_name": "string",
  "success": true,
  "output": "string",
  "error": "string|null",
  "execution_time_ms": 2500,
  "verified": true
}
```

### List All Agents

**GET** `/api/v1/agents/agents`

**Response:**
```json
{
  "agents": [
    {
      "name": "WebAgent",
      "display_name": "Web Crawler",
      "description": "Browse and scrape websites",
      "capabilities": ["web_scraping", "data_extraction"],
      "requires_approval_for": ["dangerous_operations"]
    }
  ],
  "total": 29
}
```

### List Capabilities

**GET** `/api/v1/agents/capabilities`

List all agent capabilities.

**Response:**
```json
{
  "agents": 29,
  "capabilities": [
    {
      "agent": "WebAgent",
      "category": "execution",
      "capability": "web_scraping",
      "description": "Browse and extract data from websites"
    }
  ]
}
```

### Get Capabilities by Category

**GET** `/api/v1/agents/capabilities/{category}`

Filter by category (data, execution, communication, etc.).

### Get Task Status

**GET** `/api/v1/agents/status/{task_id}`

Check status and result of a task.

**Response:**
```json
{
  "task_id": "string",
  "agent_name": "string",
  "status": "pending|running|completed|failed",
  "progress": 0.75,
  "current_step": "string",
  "success": true,
  "output": "string",
  "error": "string|null"
}
```

### Get Execution History

**GET** `/api/v1/agents/history`

**Query Parameters:**
- `limit` (int, default 100)

**Response:**
```json
{
  "total": 42,
  "entries": [
    {
      "task_id": "string",
      "agent_name": "string",
      "instruction": "string",
      "success": true,
      "execution_time_ms": 2500,
      "timestamp": "2026-03-10T12:00:00Z"
    }
  ]
}
```

### Spawn Batch (Concurrent Agents)

**POST** `/api/v1/agents/spawn-batch`

Launch multiple agents concurrently.

**Request:**
```json
{
  "tasks": [
    {
      "agent_name": "WebAgent",
      "instruction": "Scrape X",
      "params": {},
      "timeout_seconds": 60
    },
    {
      "agent_name": "CodeAgent",
      "instruction": "Write Y",
      "params": {},
      "timeout_seconds": 60
    }
  ],
  "spawn_session_id": "string|null"
}
```

**Response:**
```json
{
  "spawn_session_id": "spawn_abc123def456",
  "task_ids": ["task_1", "task_2"],
  "total": 2
}
```

Use `spawn_session_id` to poll progress.

### Get Spawn Session Status

**GET** `/api/v1/agents/spawn-session/{session_id}`

Poll progress of all tasks in a spawn session.

**Response:**
```json
{
  "spawn_session_id": "spawn_abc123def456",
  "created_at": "2026-03-10T12:00:00Z",
  "tasks": [
    {
      "task_id": "string",
      "agent_name": "string",
      "status": "running|completed|failed",
      "progress": 0.5,
      "current_step": "string",
      "error": "string|null",
      "output_preview": "string|null"
    }
  ],
  "summary": {
    "total": 2,
    "running": 1,
    "completed": 0,
    "failed": 0
  }
}
```

### Execute Batch (Sequential or Parallel)

**POST** `/api/v1/agents/batch`

Execute multiple tasks and wait for all results.

**Request:** List of `AgentTaskRequest`

**Response:**
```json
{
  "total": 2,
  "results": [
    {
      "task_id": "string",
      "agent_name": "string",
      "success": true,
      "output": "string",
      "execution_time_ms": 1000
    }
  ]
}
```

### Approval Workflow

**GET** `/api/v1/agents/approvals`

Get all tasks awaiting approval.

**Response:**
```json
{
  "pending": 3,
  "tasks": [
    {
      "task_id": "string",
      "agent_name": "string",
      "instruction": "string",
      "reason_for_approval": "destructive_operation"
    }
  ]
}
```

**POST** `/api/v1/agents/approve/{task_id}`

Approve a pending task.

**Request:**
```json
{
  "approved_by": "user@example.com",
  "notes": "Approved for production"
}
```

**Response:**
```json
{
  "task_id": "string",
  "approved": true,
  "approved_by": "string"
}
```

**POST** `/api/v1/agents/reject/{task_id}`

Reject a pending task.

**Query Parameters:**
- `approved_by` (string)
- `reason` (string, default "User request")

### Agent Interactions (Clarifying Questions)

**GET** `/api/v1/agents/interactions/pending`

Get all pending clarifying questions from agents.

**Response:**
```json
{
  "total": 2,
  "interactions": [
    {
      "interaction_id": "string",
      "task_id": "string",
      "agent_name": "string",
      "question": "Should I use production database?",
      "created_at": "2026-03-10T12:00:00Z"
    }
  ]
}
```

**POST** `/api/v1/agents/interactions/{interaction_id}/answer`

Submit answer to agent's clarifying question.

**Request:**
```json
{
  "response": "Yes, use production database"
}
```

**POST** `/api/v1/agents/interactions/{interaction_id}/dismiss`

Skip/dismiss an agent's question.

### Executor Status

**GET** `/api/v1/agents/status`

Get overall executor and registry status.

**Response:**
```json
{
  "executor": {
    "max_concurrent": 10,
    "pending_approvals": 0,
    "history_entries": 150
  },
  "registry": {
    "agents": 29,
    "agent_names": ["WebAgent", "CodeAgent", ...]
  }
}
```

### Clear History

**DELETE** `/api/v1/agents/history`

Clear execution history. Use with caution!

---

## Voice API

**Base Path:** `/api/v1/voice`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/voice.py`

### Text-to-Speech (TTS)

**POST** `/api/v1/voice/synthesize`

Synthesize speech from text using ElevenLabs.

**Query Parameters:**
- `text` (string, required)
- `voice_id` (string, optional)
- `model_id` (string, default "eleven_monolingual_v1")

**Response:** `audio/mpeg` stream (mp3 file)

### Stream Synthesized Speech

**POST** `/api/v1/voice/synthesize/stream`

Stream synthesized speech with chunked transfer encoding (good for real-time playback).

**Query Parameters:** Same as above.

**Response:** Chunked audio stream.

### List Available Voices

**GET** `/api/v1/voice/voices`

List all ElevenLabs voices in account.

**Response:**
```json
{
  "status": "success",
  "voices": [
    {
      "voice_id": "string",
      "name": "string",
      "category": "premade|cloned",
      "description": "string"
    }
  ],
  "count": 42
}
```

### Get Voice Details

**GET** `/api/v1/voice/voices/{voice_id}`

Get details about a specific voice.

**Response:**
```json
{
  "status": "success",
  "voice": {
    "voice_id": "string",
    "name": "string",
    "category": "premade|cloned",
    "description": "string",
    "labels": {"accent": "american"},
    "preview_url": "string"
  }
}
```

### Voice Cloning

**POST** `/api/v1/voice/clone`

Clone a voice from audio sample.

**Query Parameters:**
- `name` (string, required)
- `description` (string, optional)
- `consent_given` (bool, required, must be true)

**Request (multipart/form-data):**
- `audio`: Audio file (wav or mp3)

**Response:**
```json
{
  "status": "success",
  "voice_id": "string",
  "name": "string",
  "message": "Voice 'John' cloned successfully"
}
```

### Delete Voice

**DELETE** `/api/v1/voice/voices/{voice_id}`

Delete a custom cloned voice.

**Response:**
```json
{
  "status": "success",
  "message": "Voice xyz deleted"
}
```

### Voice Usage Statistics

**GET** `/api/v1/voice/usage`

Get ElevenLabs API usage and subscription info.

**Response:**
```json
{
  "status": "success",
  "usage": {
    "character_limit": 1000000,
    "character_count": 123456,
    "character_remaining": 876544,
    "tier": "pro",
    "billing_period": "monthly"
  }
}
```

### Emotion Detection

**POST** `/api/v1/voice/analyze-emotion`

Analyze audio for emotional cues.

**Query Parameters:**
- `user_id` (string, default "default")

**Request (multipart/form-data):**
- `audio`: Audio file

**Response:**
```json
{
  "status": "success",
  "emotion": {
    "primary": "happy",
    "confidence": 0.95,
    "secondary": ["excited", "energetic"],
    "arousal": 0.8,
    "valence": 0.9,
    "dominance": 0.6
  },
  "adaptation_prompt": "Cipher should match your upbeat energy...",
  "audio_features": {
    "pitch_mean": 120.5,
    "pitch_std": 15.2,
    "energy_mean": 0.75,
    "energy_std": 0.1,
    "speaking_rate": 140,
    "pause_count": 3,
    "pause_duration_total": 2.5,
    "zero_crossing_rate": 0.04,
    "vocal_tremor": 0.02
  }
}
```

### Emotion History

**GET** `/api/v1/voice/emotion-history/{user_id}`

Get emotion history for a user.

**Query Parameters:**
- `limit` (int, 1-1000, default 100)

**Response:**
```json
{
  "status": "success",
  "user_id": "string",
  "history_count": 42,
  "history": [
    {
      "timestamp": "2026-03-10T12:00:00Z",
      "primary": "happy",
      "confidence": 0.95,
      "arousal": 0.8,
      "valence": 0.9
    }
  ]
}
```

### Live Conversational Voice

#### Start Live Session

**POST** `/api/v1/voice/live/start`

Start a live conversational voice session (fast, flowing, interruptible).

**Request:**
```json
{
  "session_id": "string|null",
  "max_response_sentences": 3,
  "max_response_words": 60,
  "silence_timeout_ms": 1500
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "state": "active",
  "config": {
    "max_response_sentences": 3,
    "max_response_words": 60,
    "silence_timeout_ms": 1500
  },
  "message": "Live voice session started. Send turns to /voice/live/turn"
}
```

#### Live Turn

**POST** `/api/v1/voice/live/turn`

Send a user turn in a live voice session.

**Request:**
```json
{
  "session_id": "string",
  "text": "What's the weather?",
  "audio_duration_ms": 3500
}
```

**Response:**
```json
{
  "session_id": "string",
  "state": "active",
  "context": [
    {
      "role": "user",
      "content": "What's the weather?"
    },
    {
      "role": "assistant",
      "content": "(voice-optimized response would come from /chat/stream)"
    }
  ],
  "voice_system_overlay": "Keep responses short. User appears engaged.",
  "config": {
    "max_sentences": 3,
    "max_words": 60
  },
  "latency_ms": 150.5,
  "message": "Use this context + voice overlay with the /chat/stream endpoint..."
}
```

#### Interrupt Live Session

**POST** `/api/v1/voice/live/interrupt`

Interrupt Cipher mid-speech (user is talking over it).

**Query Parameters:**
- `session_id` (string, required)

**Response:**
```json
{
  "session_id": "string",
  "state": "interrupted",
  "interrupt_count": 2
}
```

#### End Live Session

**POST** `/api/v1/voice/live/end`

End a live voice session and get stats.

**Query Parameters:**
- `session_id` (string, required)

**Response:**
```json
{
  "message": "Live voice session ended",
  "session_id": "string",
  "duration_seconds": 120,
  "turns": 5,
  "interrupts": 1,
  "total_response_words": 280
}
```

#### List Active Sessions

**GET** `/api/v1/voice/live/sessions`

List active live voice sessions.

**Response:**
```json
{
  "active_sessions": [
    {
      "session_id": "string",
      "state": "active",
      "started_at": "2026-03-10T12:00:00Z",
      "turn_count": 3
    }
  ]
}
```

---

## Media Generation API

**Base Path:** `/api/v1/media`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/media.py`

### Generate Image

**POST** `/api/v1/media/generate-image`

Generate image from text prompt using ImageAgent.

**Request:**
```json
{
  "prompt": "A serene mountain landscape at sunset",
  "size": "1024x1024",
  "quality": "standard",
  "style": "natural",
  "model": "null|string"
}
```

**Response:**
```json
{
  "success": true,
  "image_url": "https://...",
  "filename": "generated_image_abc123.png",
  "prompt": "string",
  "params": {}
}
```

### Generate Video

**POST** `/api/v1/media/generate-video`

Generate video from text prompt using VideoAgent.

**Request:**
```json
{
  "prompt": "A car driving through a city at night",
  "duration": 5,
  "aspect_ratio": "16:9",
  "model": "null|string"
}
```

**Response:**
```json
{
  "success": true,
  "video_url": "https://...",
  "filename": "generated_video_abc123.mp4",
  "prompt": "string",
  "duration_seconds": 5,
  "params": {}
}
```

### Chain Videos

**POST** `/api/v1/media/chain-video`

Generate longer video by chaining multiple clips.

**Request:**
```json
{
  "scenes": [
    "A person walking into a coffee shop",
    "The person ordering a drink",
    "The person sitting down with their drink"
  ],
  "duration_per_clip": 5,
  "transition": "fade"
}
```

**Response:**
```json
{
  "success": true,
  "video_url": "https://...",
  "filename": "chained_video_abc123.mp4",
  "prompt": "Scene 1 | Scene 2 | Scene 3",
  "duration_seconds": 15,
  "params": {}
}
```

### Get Media File

**GET** `/api/v1/media/file/{filename}`

Serve a generated media file (image or video).

**Response:** File content (image/png or video/mp4)

### Media History

**GET** `/api/v1/media/history`

Get recent generated media files with metadata.

**Query Parameters:**
- `limit` (int, default 50)
- `hours` (int, default 24)

**Response:**
```json
{
  "images": [
    {
      "filename": "string",
      "type": "image",
      "prompt": "string",
      "created_at": "2026-03-10T12:00:00Z",
      "size_bytes": 123456,
      "params": {}
    }
  ],
  "videos": [
    {
      "filename": "string",
      "type": "video",
      "prompt": "string",
      "created_at": "2026-03-10T12:00:00Z",
      "size_bytes": 5242880,
      "duration_seconds": 5,
      "params": {}
    }
  ],
  "total_count": 15
}
```

---

## Scanner API

**Base Path:** `/scanner`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/scanner.py`

The Scanner is Cipher's intelligence gathering system that monitors real-time information.

### Get Scanner Status

**GET** `/scanner/status`

Get current scanner status.

**Response:**
```json
{
  "running": true,
  "last_full_scan": "2026-03-10T12:00:00Z",
  "scan_count": 1234,
  "error_count": 2,
  "last_scan_times": {
    "technology": "2026-03-10T12:00:00Z",
    "news": "2026-03-10T11:55:00Z"
  },
  "enabled_sources": ["technology", "news", "finance"],
  "memory_stats": {
    "cache_hits": 5000,
    "cache_misses": 200
  }
}
```

### Get Latest Briefing

**GET** `/scanner/briefing`

Get the latest intelligence briefing in markdown format.

**Response:**
```json
{
  "content": "# Daily AI Evolution Briefing\n\n## Top Stories\n...",
  "generated_at": "2026-03-10T12:00:00Z"
}
```

### Get Briefing by Date

**GET** `/scanner/briefing/{date}`

Get intelligence briefing for a specific date (YYYY-MM-DD).

**Response:** Same as above.

### Trigger Full Scan

**POST** `/scanner/scan-now`

Trigger an immediate full scan.

**Response:**
```json
{
  "status": "completed",
  "scan_count": 1235,
  "last_full_scan": "2026-03-10T12:05:00Z"
}
```

### Generate Briefing Now

**POST** `/scanner/briefing-now`

Generate a briefing immediately.

**Response:**
```json
{
  "content": "# Latest Intelligence\n\n...",
  "generated_at": "2026-03-10T12:05:00Z"
}
```

### Get Scanner Configuration

**GET** `/scanner/config`

Get current scanner configuration.

**Response:**
```json
{
  "keywords": {
    "technology": ["AI", "machine learning", "neural networks"],
    "finance": ["bitcoin", "stock market"],
    "news": ["breaking", "update"]
  },
  "sources_enabled": {
    "newsapi": true,
    "twitter": true,
    "reddit": false
  },
  "scan_intervals": {
    "technology": 3600,
    "news": 1800
  },
  "relevance_threshold": 0.7,
  "max_results_per_scan": 100
}
```

### Update Scanner Configuration

**PUT** `/scanner/config`

Update scanner configuration.

**Request:** `ScannerConfig` object

**Response:** Updated configuration.

### Add Keyword

**POST** `/scanner/keywords`

Add a keyword to track.

**Query Parameters:**
- `keyword` (string)
- `category` (string, default "technology")

**Response:**
```json
{
  "keywords": {
    "technology": ["AI", "keyword"],
    ...
  }
}
```

### Remove Keyword

**DELETE** `/scanner/keywords`

Remove a keyword from tracking.

**Query Parameters:**
- `keyword` (string)
- `category` (string)

### Scanner Health

**GET** `/scanner/health`

Check scanner health.

**Response:**
```json
{
  "healthy": true,
  "running": true,
  "last_scan": "2026-03-10T12:00:00Z",
  "errors": 0
}
```

---

## Memory API

**Base Path:** `/api/v1/memory`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/memory.py`

Cipher uses vector memory (Chroma) for long-term knowledge management.

### Store Memory

**POST** `/api/v1/memory/store`

Store information in Cipher's long-term memory.

**Request:**
```json
{
  "content": "Mark loves cold brew coffee and prefers evening coding sessions",
  "metadata": {
    "user_id": "mark",
    "category": "preferences",
    "source": "chat_history"
  },
  "collection": "cipher_memory"
}
```

**Response:**
```json
{
  "memory_id": "string",
  "status": "stored"
}
```

### Recall Memories

**POST** `/api/v1/memory/recall`

Search Cipher's memory for relevant information.

**Request:**
```json
{
  "query": "Mark's coffee preferences",
  "n_results": 5,
  "collection": "cipher_memory"
}
```

**Response:**
```json
{
  "memories": [
    {
      "id": "string",
      "content": "string",
      "metadata": {},
      "relevance_score": 0.95,
      "created_at": "2026-03-10T12:00:00Z"
    }
  ],
  "count": 1
}
```

### Memory Statistics

**GET** `/api/v1/memory/stats`

Get memory usage statistics.

**Response:**
```json
{
  "collections": {
    "cipher_memory": {
      "count": 450,
      "size_bytes": 1048576
    }
  },
  "total_memories": 450,
  "cache_utilization": 0.65
}
```

### Delete Memory

**DELETE** `/api/v1/memory/{memory_id}`

Delete a specific memory.

**Response:**
```json
{
  "status": "deleted",
  "memory_id": "string"
}
```

---

## System & Models API

### System Health

**GET** `/api/v1/system/health`

Full system health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600.5,
  "database_connected": true,
  "chroma_connected": true
}
```

### List Models

**GET** `/api/v1/models/`

List all configured models and their routing tiers.

**Response:**
```json
{
  "models": [
    {
      "tier": "reasoning",
      "model_id": "claude-opus-4-6",
      "provider": "anthropic"
    },
    {
      "tier": "fast",
      "model_id": "gpt-4-turbo",
      "provider": "openai"
    }
  ]
}
```

### Model Health Check

**GET** `/api/v1/models/health`

Test connectivity to all LLM providers.

**Response:**
```json
{
  "models": [
    {
      "model_id": "claude-opus-4-6",
      "provider": "anthropic",
      "available": true,
      "latency_ms": 150,
      "error": "null"
    }
  ]
}
```

### Model Usage Statistics

**GET** `/api/v1/models/usage`

Get usage statistics across models.

**Query Parameters:**
- `days` (int, default 30)

**Response:**
```json
{
  "period_days": 30,
  "models": [
    {
      "model": "claude-opus-4-6",
      "provider": "anthropic",
      "request_count": 500,
      "total_tokens": 150000,
      "total_cost_usd": 2.50,
      "avg_latency_ms": 145.5
    }
  ]
}
```

### List System Prompts

**GET** `/api/v1/system/prompts`

List all stored system prompts.

**Response:**
```json
{
  "prompts": [
    {
      "id": "string",
      "name": "default",
      "is_default": true,
      "content_preview": "You are Cipher...",
      "created_at": "2026-03-10T12:00:00Z"
    }
  ]
}
```

### Create System Prompt

**POST** `/api/v1/system/prompts`

Create or update a system prompt.

**Query Parameters:**
- `name` (string)
- `content` (string)
- `is_default` (bool, default false)

**Response:**
```json
{
  "status": "saved",
  "name": "string"
}
```

### Delete System Prompt

**DELETE** `/api/v1/system/prompts/{name}`

Delete a system prompt.

---

## Gateway & Premium APIs

**Base Path:** `/api/v1/gateway`
**Files:**
- `/sessions/admiring-funny-gauss/mnt/cipher-app/app/gateway/api.py`
- `/sessions/admiring-funny-gauss/mnt/cipher-app/app/gateway/premium_routes.py`

### Feature Availability

**GET** `/api/v1/features/available`

Feature availability map (drives iOS app's upgrade UI).

**Query Parameters (optional):**
- `X-Elysian-Key` (header)

**Response:**
```json
{
  "mode": "development|production",
  "has_api_key": true,
  "tiers": {
    "free": {"price": 0, "name": "Free", "tagline": "Meet Cipher"},
    "pro": {"price": 29, "name": "Pro", "tagline": "Cipher adapts to you"},
    "business": {"price": 79, "name": "Business", "tagline": "Build with every voice"},
    "enterprise": {"price": 199, "name": "Enterprise", "tagline": "Own your voice"}
  },
  "features": {
    "chat": {
      "available": true,
      "tier": "free",
      "description": "AI chat — text always works, voice is a layer on top"
    },
    "emotion_detection": {
      "available": false,
      "tier": "pro",
      "description": "Cipher reads your emotional state from voice",
      "upgrade_cta": "Cipher reads the room"
    }
  },
  "upgrade_url": "https://elysianprotocol.com/pricing"
}
```

### Register Account

**POST** `/api/v1/gateway/register`

Create a new Elysian Protocol account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password",
  "display_name": "John"
}
```

**Response:**
```json
{
  "token": "jwt_token",
  "account_id": "string",
  "email": "user@example.com",
  "tier": "free",
  "api_key": "cipher_key_abc123... (only shown once)"
}
```

### Login

**POST** `/api/v1/gateway/login`

Authenticate and receive JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "token": "jwt_token",
  "account_id": "string",
  "email": "user@example.com",
  "tier": "pro"
}
```

### Get Account

**GET** `/api/v1/gateway/account`

Get current account details.

**Headers:**
- `X-Elysian-Key` (API key)

**Response:**
```json
{
  "id": "string",
  "email": "user@example.com",
  "display_name": "John",
  "tier": "pro",
  "is_active": true,
  "is_verified": true,
  "monthly_token_limit": 1000000,
  "monthly_request_limit": 10000,
  "voice_minutes_limit": 300,
  "daily_scanner_scans": 100,
  "api_key_count": 1,
  "created_at": "2026-01-01T00:00:00Z"
}
```

### List API Keys

**GET** `/api/v1/gateway/keys`

List all API keys for current account.

**Headers:**
- `X-Elysian-Key`

**Response:**
```json
[
  {
    "id": "string",
    "name": "Default Key",
    "key_prefix": "cipher_abc...",
    "status": "active",
    "can_chat": true,
    "can_scan": false,
    "can_voice": false,
    "can_cascade": false,
    "can_clone_voice": false,
    "requests_per_minute": 100,
    "requests_per_day": 10000,
    "created_at": "2026-01-01T00:00:00Z",
    "last_used_at": "2026-03-10T12:00:00Z"
  }
]
```

### Create API Key

**POST** `/api/v1/gateway/keys`

Create a new API key.

**Request:**
```json
{
  "name": "Production Key",
  "can_chat": true,
  "can_scan": false,
  "can_voice": false,
  "can_cascade": false
}
```

**Response:**
```json
{
  "id": "string",
  "name": "Production Key",
  "key": "cipher_key_abc123... (only shown once)",
  "status": "active",
  "can_chat": true,
  "created_at": "2026-03-10T12:00:00Z"
}
```

### Usage Statistics

**GET** `/api/v1/gateway/usage`

Get current billing period usage.

**Query Parameters:**
- `month` (string, optional, YYYY-MM)

**Response:**
```json
{
  "billing_month": "2026-03",
  "total_tokens": 50000,
  "total_requests": 500,
  "total_voice_seconds": 1200,
  "total_cost_usd": 25.50,
  "by_feature": {
    "chat": {"tokens": 40000, "requests": 400, "cost": 20.00},
    "voice": {"seconds": 1200, "cost": 5.00}
  },
  "token_limit": 1000000,
  "request_limit": 10000,
  "token_usage_pct": 5.0,
  "request_usage_pct": 5.0
}
```

---

## Projects & Credentials API

**Base Path:** `/api/v1/projects`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/projects.py`

### List Projects

**GET** `/api/v1/projects/`

List all projects.

**Response:**
```json
[
  {
    "id": "string",
    "name": "Cipher Backend",
    "description": "Main FastAPI application",
    "icon": "folder.fill",
    "color": "blue",
    "platform": "python",
    "repo_url": "https://github.com/...",
    "deploy_url": "https://railway.app/...",
    "railway_project_id": "string",
    "services": [
      {
        "id": "string",
        "service_type": "postgres",
        "credential_id": "string",
        "config": {}
      }
    ],
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-03-10T12:00:00Z"
  }
]
```

### Create Project

**POST** `/api/v1/projects/`

Create a new project.

**Request:**
```json
{
  "name": "New Project",
  "description": "Description",
  "icon": "folder.fill",
  "color": "blue",
  "platform": "python",
  "repo_url": "https://github.com/...",
  "deploy_url": "https://railway.app/...",
  "railway_project_id": "string",
  "services": []
}
```

### Get Project

**GET** `/api/v1/projects/{project_id}`

Get a single project by ID.

### Update Project

**PATCH** `/api/v1/projects/{project_id}`

Update project metadata.

### Delete Project

**DELETE** `/api/v1/projects/{project_id}`

Delete a project and its services.

### List Credentials

**GET** `/api/v1/projects/credentials/all`

List all stored credentials (tokens redacted).

**Response:**
```json
[
  {
    "id": "string",
    "name": "Railway Token",
    "service_type": "railway",
    "project_id": "string",
    "additional_fields": {},
    "created_at": "2026-01-01T00:00:00Z",
    "last_used_at": "2026-03-10T12:00:00Z"
  }
]
```

### Create Credential

**POST** `/api/v1/projects/credentials`

Store a new service credential.

**Request:**
```json
{
  "name": "GitHub Token",
  "service_type": "github",
  "token_value": "ghp_xxx...",
  "project_id": "string",
  "additional_fields": {}
}
```

### Delete Credential

**DELETE** `/api/v1/projects/credentials/{credential_id}`

Delete a stored credential.

---

## Notifications API

**Base Path:** `/api/v1/notifications`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/notifications.py`

### Register Device

**POST** `/api/v1/notifications/register-device`

Register a device for push notifications.

**Request:**
```json
{
  "device_token": "ios_fcm_token",
  "user_id": "mark",
  "device_name": "iPhone 15 Pro",
  "platform": "ios"
}
```

**Response:**
```json
{
  "registered": true,
  "device_name": "iPhone 15 Pro",
  "total_devices": 2
}
```

### List Registered Devices

**GET** `/api/v1/notifications/devices`

List all registered devices.

**Query Parameters:**
- `user_id` (string, default "mark")

**Response:**
```json
{
  "user_id": "mark",
  "devices": [
    {
      "token": "ios_fcm_token",
      "device_name": "iPhone 15 Pro",
      "platform": "ios",
      "registered_at": "2026-03-10T12:00:00Z",
      "active": true
    }
  ],
  "total": 1
}
```

### Unregister Device

**DELETE** `/api/v1/notifications/unregister-device`

Remove a device from push notifications.

**Query Parameters:**
- `device_token` (string)
- `user_id` (string, default "mark")

**Response:**
```json
{
  "unregistered": true
}
```

### Send Test Notification

**POST** `/api/v1/notifications/test`

Send a test push notification to all devices.

**Request:**
```json
{
  "title": "Test from Cipher",
  "body": "Push notifications are working!"
}
```

### Get Preferences

**GET** `/api/v1/notifications/preferences`

Get notification preferences.

**Response:**
```json
{
  "push_enabled": true,
  "sms_enabled": false,
  "phone_number": "+1234567890",
  "alert_on_questions": true,
  "alert_on_completions": true,
  "alert_on_failures": true
}
```

### Update Preferences

**PUT** `/api/v1/notifications/preferences`

Update notification preferences.

**Request:**
```json
{
  "push_enabled": true,
  "sms_enabled": false,
  "phone_number": "+1234567890",
  "alert_on_questions": true,
  "alert_on_completions": true,
  "alert_on_failures": true
}
```

---

## Research API

**Base Path:** `/api/v1/research`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/research.py`

Cipher's autonomous self-improvement engine.

### Start Research Loop

**POST** `/api/v1/research/start`

Start autonomous research loop as background task.

**Request:**
```json
{
  "max_experiments": 50,
  "max_hours": 8.0
}
```

**Response:**
```json
{
  "status": "started",
  "task_id": "string",
  "max_experiments": 50,
  "max_hours": 8.0,
  "message": "Autonomous research loop started..."
}
```

### Stop Research Loop

**POST** `/api/v1/research/stop`

Stop the running research loop.

**Response:**
```json
{
  "stopped": 1,
  "message": "Research loop stopped"
}
```

### Get Experiments

**GET** `/api/v1/research/experiments`

Get list of completed experiments.

### Run Self Tests

**POST** `/api/v1/research/self-test`

Run self-test suite.

---

## Cron & Scheduled Tasks API

**Base Path:** `/api/v1/cron`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/cron.py`

### List Cron Tasks

**GET** `/api/v1/cron/tasks`

List all registered cron tasks.

**Response:**
```json
{
  "total": 10,
  "enabled": 8,
  "tasks": [
    {
      "task_id": "scanner_daily",
      "name": "Daily Intelligence Scan",
      "description": "Run full scanner intelligence sweep",
      "schedule": "0 8 * * *",
      "enabled": true,
      "last_run": "2026-03-10T08:00:00Z",
      "next_run": "2026-03-11T08:00:00Z",
      "last_error": null
    }
  ]
}
```

### Get Cron Task

**GET** `/api/v1/cron/tasks/{task_id}`

Get details for a specific cron task.

### Enable Task

**POST** `/api/v1/cron/tasks/{task_id}/enable`

Enable a cron task.

### Disable Task

**POST** `/api/v1/cron/tasks/{task_id}/disable`

Disable a cron task.

### Run Task Now

**POST** `/api/v1/cron/tasks/{task_id}/run`

Manually trigger a task immediately.

**Response:**
```json
{
  "task_id": "string",
  "triggered": true,
  "last_run": "2026-03-10T12:30:00Z",
  "last_error": null
}
```

---

## Recommendations API

**Base Path:** `/api/v1/recommendations`
**File:** `/sessions/admiring-funny-gauss/mnt/cipher-app/app/api/recommendations.py`

Powers the "Let Crawler scrape that for you?" cards in ChatView.

### Get Recommended Agents

**POST** `/api/v1/recommendations/`

Analyze user message and recommend agents.

**Request:**
```json
{
  "message": "Can you scrape the prices from Amazon?",
  "previous_context": []
}
```

**Response:**
```json
{
  "recommendations": [
    {
      "agent_name": "WebAgent",
      "display_name": "Crawler",
      "reason": "Message asks to scrape website data",
      "confidence": 0.95,
      "suggested_instruction": "Scrape product prices from Amazon: [URL]"
    }
  ],
  "analysis": {
    "intent": "web_scraping",
    "entities": ["amazon", "prices"],
    "requires_approval": false
  }
}
```

---

## Streaming & Real-Time Features

### Server-Sent Events (SSE)

Several endpoints use SSE for real-time updates:

1. **`POST /api/v1/chat/stream`** — Token-by-token chat responses
2. **`POST /api/v1/agents/execute/stream`** — Real-time agent execution progress
3. **`POST /api/v1/voice/synthesize/stream`** — Chunked audio streaming

**Common SSE Structure:**
```
event: event_name
data: {"key": "value"}

event: heartbeat
data: {}

data: [DONE]
```

**Client Implementation:**
```javascript
const eventSource = new EventSource('/api/v1/chat/stream');
eventSource.addEventListener('token', (e) => {
  const data = JSON.parse(e.data);
  console.log(data.content); // Append to UI
});
eventSource.addEventListener('metadata', (e) => {
  const meta = JSON.parse(e.data);
  console.log(`Cost: $${meta.cost_usd}`);
  eventSource.close();
});
```

---

## Data Models & Schemas

### ChatRequest
```python
{
  "message": str,
  "conversation_id": str | None,
  "model_tier": ModelTier,  # reasoning|fast|local|code|default|auto
  "system_prompt": str | None,
  "include_memory": bool,
  "max_tokens": int,
  "temperature": float,
  "stream": bool,
  "images": list[str]  # base64-encoded
}
```

### ChatResponse
```python
{
  "message": str,
  "conversation_id": str,
  "model_used": str,
  "tokens_used": int,
  "cost_usd": float,
  "timestamp": datetime,
  "recommended_agent": RecommendedAgentInfo | None,
  "images": list[ImageAttachment],
  "confidence_score": float | None,
  "validation_warnings": list[str] | None
}
```

### AgentTaskRequest
```python
{
  "agent_name": str,
  "instruction": str,
  "params": dict,
  "timeout_seconds": int,
  "priority": int
}
```

### AgentResult
```python
{
  "task_id": str,
  "agent_name": str,
  "success": bool,
  "output": str | dict,
  "error": str | None,
  "execution_time_ms": int,
  "verified": bool
}
```

### ModelTier (Enum)
```python
REASONING = "reasoning"    # claude-opus (slow, expensive, best)
FAST = "fast"             # gpt-4-turbo
LOCAL = "local"           # ollama
CODE = "code"             # code-specific model
DEFAULT = "default"       # router's choice
AUTO = "auto"             # dynamic routing
```

---

## Error Handling

All endpoints follow standard HTTP status codes:

- **200 OK** — Request successful
- **400 Bad Request** — Invalid request format
- **404 Not Found** — Resource doesn't exist
- **409 Conflict** — State conflict (e.g., task already running)
- **500 Internal Server Error** — Server error

**Error Response Format:**
```json
{
  "detail": "Human-readable error message"
}
```

---

## Authentication

### API Key Authentication

Used for premium features and metering.

**Header:**
```
X-Elysian-Key: cipher_key_abc123def456...
```

**Optional for free tier** — omit header to use user's own LLM API keys.

### JWT Authentication

Used for account management (gateway endpoints).

**Header:**
```
Authorization: Bearer jwt_token_abc123...
```

---

## Rate Limiting

**Per API Key (Premium):**
- `requests_per_minute`: Varies by tier
- `requests_per_day`: Varies by tier

**Per User (Free):**
- Soft limit via usage tracking
- No hard rejection, but usage is logged

---

## Orchestrator Flow

The **Orchestrator** (`/sessions/admiring-funny-gauss/mnt/cipher-app/app/services/orchestrator.py`) ties together chat processing:

1. **Data Detection** — Identifies when real data fetch is required (stock prices, news, etc.)
2. **Agent Invocation** — Calls agents for live data before LLM responds
3. **Memory Retrieval** — Recalls relevant context from vector memory
4. **LLM Routing** — Selects model tier based on complexity
5. **Vision Processing** — Analyzes images if included
6. **Tool Calling** — Invokes specialized tools
7. **Response Validation** — Fact-checks and confidence scoring

**Example Flow for "What's Tesla's stock price?":**
```
1. Pattern match: _STOCK_PATTERN matches "Tesla"
2. Fetch live data: Call yfinance for TSLA
3. LLM prompt injection: "TSLA: $250.50 (+2.1%)"
4. Generate response using LIVE data
5. Return with confidence_score and validation warnings
```

---

## Notes for Frontend Integration

### Required Headers
- `Content-Type: application/json` (for POST requests)
- `X-Elysian-Key: cipher_key...` (optional, for premium features)

### Streaming Responses
All streaming endpoints use SSE. iOS should use `URLSessionWebSocketTask` or similar for real-time updates.

### Memory Integration
Chat automatically recalls relevant memories. To suppress:
```json
{
  "message": "...",
  "include_memory": false
}
```

### Image Support
Chat supports images in two ways:
1. **Base64 in request:** Include in `images` array
2. **Multi-turn uploads:** First call `/chat/upload-image`, then reference in `images` array

### Model Tier Selection
- `model_tier: "auto"` — Smart routing (default)
- `model_tier: "reasoning"` — Always use Claude Opus (expensive)
- `model_tier: "fast"` — Always use fast model (cheaper, faster)

### Conversation Management
- `conversation_id: null` — Starts new conversation
- `conversation_id: "abc123"` — Continues existing conversation

---

## Summary

This Cipher backend provides a complete AI system with:

- **29 specialized agents** for execution, analysis, communication
- **Real-time streaming** for chat and media
- **Long-term memory** via vector embeddings
- **Premium tier system** with feature gating
- **Intelligence scanning** for automated briefings
- **Voice synthesis and emotion analysis**
- **Image/video generation**
- **Model routing** across multiple LLM providers
- **Approval workflow** for sensitive operations
- **Usage tracking** and billing

The API is production-ready for iOS integration with comprehensive error handling, auth, and real-time features.
