# Cipher API — Quick Start for Frontend Developers

## Base URL
```
http://localhost:8000  (development)
https://cipher.elysianprotocol.com  (production)
```

## Essential Endpoints (Get These Working First)

### 1. Health Check
```bash
curl http://localhost:8000/ping
# Response: {"pong": true}
```

### 2. Chat (Your Primary Interface)
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello Cipher!",
    "model_tier": "auto"
  }'
```

**Response:**
```json
{
  "message": "Hello! I'm Cipher, your AI assistant...",
  "conversation_id": "conv_abc123",
  "model_used": "claude-opus-4-6",
  "tokens_used": 45,
  "cost_usd": 0.002
}
```

### 3. Stream Chat (Real-Time Tokens)
```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

**Response (SSE):**
```
event: token
data: {"type": "token", "content": "Hello"}

event: token
data: {"type": "token", "content": "!"}

event: metadata
data: {"type": "metadata", "model_used": "claude-opus-4-6", ...}

data: [DONE]
```

## Common Workflows

### Workflow: Chat with Conversation History

```javascript
// 1. Start new conversation (no conversation_id)
const res1 = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "What's 2+2?",
    conversation_id: null  // Start new
  })
});
const data1 = await res1.json();
const convId = data1.conversation_id; // Save this!

// 2. Continue conversation
const res2 = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "What's 3+3?",
    conversation_id: convId  // Reuse
  })
});
```

### Workflow: Stream Response with Spinners

```javascript
const eventSource = new EventSource('/api/v1/chat/stream?...params');

eventSource.addEventListener('token', (e) => {
  const { content } = JSON.parse(e.data);
  document.getElementById('response').textContent += content;
});

eventSource.addEventListener('metadata', (e) => {
  const { model_used, tokens_used, cost_usd } = JSON.parse(e.data);
  console.log(`${model_used}: ${tokens_used} tokens ($${cost_usd})`);
  eventSource.close();
});

eventSource.addEventListener('error', () => {
  eventSource.close();
});
```

### Workflow: Execute Agent Task

```bash
curl -X POST http://localhost:8000/api/v1/agents/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "WebAgent",
    "instruction": "Scrape https://example.com and extract all links",
    "timeout_seconds": 30
  }'
```

**Response:**
```json
{
  "task_id": "task_abc123",
  "agent_name": "WebAgent",
  "success": true,
  "output": "[\"https://example.com/page1\", \"https://example.com/page2\"]",
  "execution_time_ms": 2500
}
```

### Workflow: TTS + Play Audio

```javascript
// 1. Synthesize speech
const audioRes = await fetch('/api/v1/voice/synthesize?text=Hello%20world&voice_id=21m00Tcm4TlvDq8ikWAM');
const audioBlob = await audioRes.blob();

// 2. Play
const audio = new Audio(URL.createObjectURL(audioBlob));
audio.play();
```

### Workflow: Generate Image

```bash
curl -X POST http://localhost:8000/api/v1/media/generate-image \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A beautiful sunset over mountains",
    "size": "1024x1024"
  }'
```

**Response:**
```json
{
  "success": true,
  "image_url": "https://...",
  "filename": "generated_image_abc123.png"
}
```

## Authentication (Premium)

### Using API Key

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Elysian-Key: cipher_key_abc123def456" \
  -d '{"message": "Hello"}'
```

### Check Feature Availability

```bash
curl http://localhost:8000/api/v1/features/available \
  -H "X-Elysian-Key: cipher_key_abc123def456"
```

**Response:**
```json
{
  "has_api_key": true,
  "features": {
    "chat": { "available": true, "tier": "free" },
    "voice_cloning": { "available": true, "tier": "enterprise" },
    "emotion_detection": { "available": false, "tier": "pro" }
  }
}
```

## Debugging Endpoints

### Check System Health
```bash
curl http://localhost:8000/api/v1/system/health
```

### List Models
```bash
curl http://localhost:8000/api/v1/models/
```

### Check Model Health
```bash
curl http://localhost:8000/api/v1/models/health
```

### Get Usage Stats
```bash
curl http://localhost:8000/api/v1/models/usage
```

### List Agents
```bash
curl http://localhost:8000/api/v1/agents/agents
```

### Get Agent Capabilities
```bash
curl http://localhost:8000/api/v1/agents/capabilities
```

## Key Data Types

### ModelTier
```typescript
type ModelTier = 'reasoning' | 'fast' | 'local' | 'code' | 'default' | 'auto'

// reasoning = claude-opus-4-6 (slow, expensive, best)
// fast = gpt-4-turbo (cheaper, faster)
// auto = router decides (recommended)
```

### ChatRequest
```typescript
{
  message: string;
  conversation_id?: string;      // null = new conversation
  model_tier?: ModelTier;        // default: 'auto'
  system_prompt?: string;        // override system prompt
  include_memory?: boolean;      // default: true
  max_tokens?: number;           // default: 4096
  temperature?: number;          // default: 0.7 (0-1)
  stream?: boolean;              // default: false
  images?: string[];             // base64-encoded images
}
```

### ChatResponse
```typescript
{
  message: string;
  conversation_id: string;
  model_used: string;
  tokens_used: number;
  cost_usd: number;
  timestamp: string;             // ISO 8601
  recommended_agent?: {
    agent_name: string;
    display_name: string;
    confidence: number;           // 0-1
    suggested_instruction: string;
  };
  images?: Array<{
    url: string;
    mime_type: string;
    analysis?: string;
  }>;
  confidence_score?: number;      // 0-1, reliability
  validation_warnings?: string[]; // unverified claims
}
```

## Common Patterns

### Pattern: Voice + Chat
```javascript
// 1. Capture user's voice
const audioBlob = await captureAudio(); // Your audio capture

// 2. Send to chat with emotion analysis
const emotionRes = await fetch('/api/v1/voice/analyze-emotion', {
  method: 'POST',
  body: new FormData({ audio: audioBlob })
});
const emotion = await emotionRes.json();

// 3. Get emotion-adapted response
const chatRes = await fetch('/api/v1/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: transcribedText,
    system_prompt: emotion.adaptation_prompt  // Emotion-aware!
  })
});

// 4. Stream tokens + synthesize speech in real-time
const eventSource = new EventSource(chatRes);
let fullText = '';

eventSource.addEventListener('token', (e) => {
  fullText += JSON.parse(e.data).content;
  // Could stream to TTS for continuous playback
});

eventSource.addEventListener('metadata', async (e) => {
  // Synthesize final response
  const ttsRes = await fetch('/api/v1/voice/synthesize?text=' + encodeURIComponent(fullText));
  const audio = new Audio(URL.createObjectURL(await ttsRes.blob()));
  audio.play();
});
```

### Pattern: Spawn Multiple Agents
```bash
curl -X POST http://localhost:8000/api/v1/agents/spawn-batch \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {
        "agent_name": "WebAgent",
        "instruction": "Scrape https://hacker-news.firebaseio.com/v0/topstories.json"
      },
      {
        "agent_name": "DataAgent",
        "instruction": "Analyze top stories and categorize by sentiment"
      }
    ]
  }'
```

**Then poll progress:**
```bash
# Get session ID from response above
SESSION_ID="spawn_abc123..."

curl http://localhost:8000/api/v1/agents/spawn-session/$SESSION_ID
# Repeat until summary.running = 0
```

### Pattern: Conversation Continuation
```javascript
// Load past conversations
const convs = await fetch('/api/v1/chat/conversations?limit=10').then(r => r.json());

// Load specific conversation
const conv = await fetch(`/api/v1/chat/conversations/${convs[0].id}`).then(r => r.json());

// Continue from last message
const newRes = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "Based on our previous discussion, ...",
    conversation_id: conv.id
  })
});
```

## Error Handling

```javascript
async function callCipherAPI(endpoint, options) {
  try {
    const res = await fetch(endpoint, options);

    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return await res.json();
  } catch (err) {
    console.error(`Cipher API Error: ${err.message}`);
    // Show user-friendly message
    return null;
  }
}
```

## Environment Setup

### Development
```bash
# Set LLM API keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# Start server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Test
curl http://localhost:8000/ping
```

### Production
```bash
# Use Railway or Docker
docker build -t cipher .
docker run -e ANTHROPIC_API_KEY=sk-ant-... cipher

# Or use Railway deploy
railway up
```

## Rate Limits

**Free Tier (No API Key):**
- Soft limits, usage logged
- No hard rejection

**Pro Tier ($29/month):**
- 100 requests/minute
- 10,000 requests/day
- 300 minutes voice/month

**Enterprise ($199/month):**
- 1000 requests/minute
- 100,000 requests/day
- Unlimited voice

## Next Steps

1. **Integrate chat:** Get `/api/v1/chat` and `/api/v1/chat/stream` working
2. **Add streaming UI:** Implement SSE event listener
3. **Optional voice:** Add `/api/v1/voice/synthesize` when you have ElevenLabs key
4. **Optional agents:** Recommend agents with `/api/v1/recommendations`
5. **Memory:** Use `/api/v1/memory/recall` for context

## Documentation

Full documentation: See `/sessions/admiring-funny-gauss/mnt/cipher-app/COMPLETE_API_REFERENCE.md`

Interactive docs: Navigate to `http://localhost:8000/docs` (Swagger UI)

---

**Questions?** Check the logs:
```bash
# Docker logs
docker logs cipher-backend

# Or local logs (if running with uvicorn)
# Watch stdout
```
