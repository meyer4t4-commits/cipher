# Voice Intelligence System - Implementation Notes

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application (main.py)                 │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├── Voice Router (api/voice.py)
             │   ├── /voice/synthesize (TTS)
             │   ├── /voice/synthesize/stream (Streaming TTS)
             │   ├── /voice/clone (Voice Cloning)
             │   ├── /voice/voices (List/Manage)
             │   ├── /voice/usage (Statistics)
             │   ├── /voice/analyze-emotion (Audio Analysis)
             │   └── /voice/emotion-history (Emotion History)
             │
             ├── Voice Service (services/voice_service.py)
             │   ├── VoiceService class
             │   │   ├── Async HTTP client (httpx)
             │   │   ├── ElevenLabs API v1 integration
             │   │   └── Singleton pattern
             │   └── get_voice_service() helper
             │
             ├── Emotion Service (services/emotion_service.py)
             │   ├── EmotionService class
             │   ├── AudioFeatures dataclass
             │   ├── EmotionProfile dataclass
             │   ├── Librosa-based analysis (if available)
             │   ├── Heuristic fallback analysis
             │   └── History storage (/data/emotions/)
             │
             └── Configuration (core/config.py)
                 ├── elevenlabs_api_key
                 ├── default_voice_id
                 ├── voice_enabled flag
                 └── emotion_detection_enabled flag
```

## Technical Decisions

### 1. No ElevenLabs Pip Package
**Why**: The elevenlabs pip package is a higher-level wrapper. Using httpx directly:
- Provides full control over requests
- Reduces dependency bloat
- Allows custom streaming implementations
- Easier to add rate limiting and caching

**Implementation**: Direct HTTP calls to ElevenLabs API v1 endpoints using httpx AsyncClient.

### 2. Async/Await Throughout
**Why**: FastAPI is async-first; blocking calls would reduce concurrency.

**Implementation**:
- All I/O operations (HTTP, file) are async
- Voice service uses AsyncClient
- Streaming responses use AsyncGenerator
- No blocking librosa calls (audio loading only)

### 3. Graceful Degradation for Librosa
**Why**: Librosa is optional; not all environments have it installed.

**Implementation**:
- Try import librosa at module load
- Fall back to heuristic analysis if unavailable
- Heuristic uses basic signal processing on raw audio bytes
- Both methods return same EmotionProfile dataclass

### 4. Singleton Pattern for Services
**Why**: Services maintain HTTP clients and configuration.

**Implementation**:
```python
_voice_service: Optional[VoiceService] = None

async def get_voice_service() -> VoiceService:
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
```

Benefits:
- Single HTTP client reused (connection pooling)
- Configuration loaded once
- Memory efficient

### 5. PAD (Pleasure-Arousal-Dominance) Emotional Model
**Why**: PAD is well-researched and works well for speech analysis.

**Dimensions**:
- **Arousal** (-1=calm, +1=excited): Energy, intensity
- **Valence** (-1=sad, +1=happy): Emotional tone
- **Dominance** (-1=uncertain, +1=confident): Control/authority

**Mapping to emotions**:
```
calm        = low arousal, positive valence
excited     = high arousal, positive valence
stressed    = high arousal, negative valence
sad         = low arousal, negative valence
focused     = moderate arousal, high dominance
frustrated  = moderate arousal, negative valence, low dominance
happy       = high valence
uncertain   = low dominance
```

### 6. Consent-Based Voice Cloning
**Why**: Voice cloning creates permanent replicas; explicit consent is required.

**Implementation**:
```python
await voice_service.clone_voice(
    name="voice_name",
    audio_data=audio_bytes,
    consent_given=True  # Must be explicitly True
)
```

Raises ValueError if consent_given=False or omitted.

### 7. Streaming for Large Responses
**Why**: TTS audio files can be large; streaming enables real-time playback.

**Implementation**:
- `synthesize_speech()` → returns bytes (for small text)
- `synthesize_speech_stream()` → AsyncGenerator[bytes] (for streaming)
- Streaming endpoint uses FastAPI's StreamingResponse

Benefits:
- Real-time playback on iOS app
- Reduced memory usage
- Better user experience

## Audio Feature Extraction

### With Librosa (Advanced)
```
Raw Audio (wav/mp3)
    ↓
    ├─ Pitch detection (piptrack algorithm)
    ├─ Energy/loudness (RMS)
    ├─ Speaking rate (zero-crossing rate)
    ├─ Silence detection (frame-by-frame)
    ├─ MFCC (Mel-Frequency Cepstral Coefficients)
    └─ Tremor (amplitude variation)
    ↓
AudioFeatures dataclass
```

### Without Librosa (Fallback Heuristics)
```
Raw Audio Bytes (16-bit PCM)
    ↓
    ├─ Parse PCM samples
    ├─ Normalize samples
    ├─ Calculate RMS energy
    ├─ Count zero crossings (pitch proxy)
    ├─ Detect silent frames
    └─ Estimate voice characteristics
    ↓
AudioFeatures dataclass
```

Both produce identical AudioFeatures structure.

## Emotion Profile Generation

```
AudioFeatures
    ↓
Extract 3 dimensions:
    ├─ Arousal = (energy + speaking_rate + pitch_variation) * weights
    ├─ Valence = (energy - tremor) * weights
    └─ Dominance = (pitch_consistency + speaking_rate) * weights
    ↓
Map to emotion scores:
    ├─ calm: low arousal + positive valence
    ├─ excited: high arousal + positive valence
    ├─ stressed: high arousal + negative valence
    ├─ sad: low arousal + negative valence
    ├─ focused: moderate arousal + high dominance
    ├─ frustrated: moderate arousal + negative valence + low dominance
    ├─ happy: high valence
    └─ uncertain: low dominance
    ↓
Select top emotion (highest confidence)
Select secondary emotions (top 3)
    ↓
EmotionProfile dataclass
```

## Data Storage

### Emotion History
Location: `/data/emotions/{user_id}/{timestamp}.json`

Example:
```json
{
  "timestamp": "2026-02-26T14:30:45.123456+00:00",
  "primary_emotion": "calm",
  "confidence": 0.85,
  "secondary_emotions": [["focused", 0.4], ["happy", 0.2]],
  "arousal": -0.7,
  "valence": 0.3,
  "dominance": 0.0,
  "audio_features": {
    "pitch_mean": 120.5,
    "pitch_std": 18.3,
    "energy_mean": -20.1,
    "energy_std": 5.2,
    "speaking_rate": 145.0,
    "pause_count": 3,
    "pause_duration_total": 0.8,
    "zero_crossing_rate": 0.12,
    "vocal_tremor": 0.15,
    "mfcc_mean": [420.1, -18.3, 45.2, -12.1, 8.5]
  }
}
```

Storage is automatic; no additional code needed.

## API Response Examples

### Synthesize Response
```
HTTP/1.1 200 OK
Content-Type: audio/mpeg
Content-Disposition: inline; filename=speech.mp3

[Binary MP3 data...]
```

### Emotion Analysis Response
```json
{
  "status": "success",
  "emotion": {
    "primary": "calm",
    "confidence": 0.85,
    "secondary": [["focused", 0.4], ["happy", 0.2]],
    "arousal": -0.7,
    "valence": 0.3,
    "dominance": 0.0
  },
  "adaptation_prompt": "The user sounds calm and composed. Maintain professional clarity with measured detail. Avoid unnecessary urgency.",
  "audio_features": {
    "pitch_mean": 120.5,
    "pitch_std": 18.3,
    "energy_mean": -20.1,
    "energy_std": 5.2,
    "speaking_rate": 145.0,
    "pause_count": 3,
    "pause_duration_total": 0.8,
    "zero_crossing_rate": 0.12,
    "vocal_tremor": 0.15
  }
}
```

## Performance Considerations

### Voice Service
- **Latency**: ElevenLabs API typically responds in 1-3 seconds
- **Streaming**: First chunk arrives in 0.5-1 second
- **Throughput**: One request per voice_id at a time (no internal queuing)

### Emotion Service
- **Librosa analysis**: 100-500ms per audio (depends on duration)
- **Heuristic analysis**: 5-50ms per audio
- **Storage**: ~2KB per emotion profile

### Optimization Tips
1. Cache common TTS responses
2. Use streaming for long texts
3. Batch emotion analyses
4. Monitor token usage with get_usage()

## Error Scenarios

### API Errors
```
ElevenLabs API rate limit exceeded
→ HTTPException(status_code=429) + logger.error()

Invalid audio format
→ ValueError + HTTPException(status_code=400)

Missing API key
→ ValueError during service init + logger.warning()
```

### Data Errors
```
Empty text
→ ValueError + HTTPException(status_code=400)

Missing consent for voice cloning
→ ValueError + HTTPException(status_code=400)

Invalid audio file
→ Exception caught + HTTPException(status_code=500)
```

All errors are logged with full stack traces for debugging.

## Integration Points

### With Cipher Orchestrator
```python
# In orchestrator.py
emotion_service = await get_emotion_service()
emotion_profile = await emotion_service.analyze_audio(user_audio)
emotion_prompt = await emotion_service.get_adaptation_prompt(emotion_profile)

full_system_prompt = f"{CIPHER_SYSTEM_PROMPT}\n\n{emotion_prompt}"

result = await chat_completion(
    messages=messages,
    system_prompt=full_system_prompt,  # Emotion-aware
    model_tier=model_tier,
    ...
)
```

### With iOS App
```swift
// Receive audio from user microphone
let audioData = recordedAudio.data

// Send for emotion analysis
let emotionResponse = await POST("/api/v1/voice/analyze-emotion", 
    audio: audioData)

// Generate response with emotion adaptation
let cipherResponse = await POST("/api/v1/chat/", 
    message: userMessage,
    systemPrompt: emotionResponse.adaptation_prompt)

// Synthesize response as speech
let speechStream = POST("/api/v1/voice/synthesize/stream", 
    text: cipherResponse.message)

// Stream audio to speaker
speaker.play(speechStream)
```

## Testing Checklist

- [ ] TTS synthesize endpoint works
- [ ] TTS streaming endpoint streams correctly
- [ ] Voice listing returns available voices
- [ ] Voice cloning requires consent
- [ ] Usage endpoint returns accurate stats
- [ ] Emotion analysis detects emotions correctly
- [ ] Emotion history is stored and retrieved
- [ ] API key loading from environment works
- [ ] Voice service is disabled when not configured
- [ ] Error handling returns proper HTTP codes
- [ ] All endpoints handle concurrent requests
- [ ] Streaming doesn't block other requests

## Monitoring

Key metrics to track:

1. **Token Usage**: `GET /api/v1/voice/usage` - character_count vs character_limit
2. **API Latency**: TTS synthesis time (aim for <3s)
3. **Error Rate**: Failed synthesize/clone/analyze requests
4. **Emotion Distribution**: Track user emotions over time
5. **Service Health**: ElevenLabs API availability

## Future Enhancements

1. **Caching Layer**: Redis cache for common TTS requests
2. **Rate Limiting**: Per-user token budgets
3. **Voice Styles**: Professional, casual, dramatic presets
4. **Real-time ASR**: Speech recognition + synthesis loop
5. **Voice Quality Metrics**: Confidence scoring for emotion detection
6. **Multi-language**: Support non-English TTS
7. **Batch Processing**: Synthesize multiple texts efficiently
8. **Voice Analytics**: Historical trends in user emotions
