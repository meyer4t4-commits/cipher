# Orchid Voice Intelligence System Guide

## Overview

The Orchid voice intelligence system provides comprehensive voice synthesis, voice cloning, and emotion detection capabilities powered by ElevenLabs and audio analysis.

## Files Created

### 1. Voice Service (`/app/services/voice_service.py`)
Core ElevenLabs integration for text-to-speech and voice management.

**Key Features:**
- TTS synthesis with ElevenLabs API v1 (no pip package required)
- Voice cloning from audio samples (with consent)
- Voice library management (list, get details, delete)
- Usage statistics tracking
- Streaming audio support for real-time playback
- Full async/await support with httpx

**Main Class: VoiceService**

Methods:
- `synthesize_speech(text, voice_id, model_id, voice_settings)` → bytes (mp3)
- `synthesize_speech_stream(text, voice_id, ...)` → AsyncGenerator[bytes]
- `clone_voice(name, audio_data, description, labels, consent_given)` → voice_id
- `list_voices()` → list[dict]
- `get_voice_details(voice_id)` → dict
- `delete_voice(voice_id)` → bool
- `get_usage()` → dict (character_limit, character_count, etc.)
- `set_default_voice(voice_id)` → None

### 2. Emotion Service (`/app/services/emotion_service.py`)
Audio emotion analysis and Cipher response adaptation.

**Key Features:**
- Audio feature extraction (pitch, energy, tempo, pauses, tremor)
- Emotional state detection (calm, excited, stressed, sad, focused, frustrated, happy, uncertain)
- Supports librosa (advanced) and fallback heuristics
- Graceful degradation if librosa not installed
- PAD (Pleasure-Arousal-Dominance) emotional dimensions
- System prompt generation for response adaptation
- Longitudinal emotion history tracking per user

**Main Classes:**
- `AudioFeatures` - Extracted raw audio features
- `EmotionProfile` - Detected emotional state with confidence scores
- `EmotionService` - Analysis engine

Methods:
- `analyze_audio(audio_data, user_id)` → EmotionProfile
- `get_adaptation_prompt(emotion_profile)` → str
- `get_emotion_history(user_id, limit)` → list[dict]

### 3. Voice API Endpoints (`/app/api/voice.py`)
FastAPI routes for voice and emotion operations.

**Endpoints:**

#### TTS Endpoints
- `POST /api/v1/voice/synthesize` - Single TTS response
  - Query params: `text`, `voice_id`, `model_id`
  - Returns: audio/mpeg stream

- `POST /api/v1/voice/synthesize/stream` - Streaming TTS
  - Query params: `text`, `voice_id`, `model_id`
  - Returns: chunked audio/mpeg stream

#### Voice Management
- `GET /api/v1/voice/voices` - List all available voices
  - Returns: {voices: [...], count: int}

- `GET /api/v1/voice/voices/{voice_id}` - Get voice details
  - Returns: {voice: {...}}

- `POST /api/v1/voice/clone` - Clone a voice from audio
  - Form params: `name`, `audio` (file), `description`, `consent_given`
  - Returns: {voice_id, name, status}

- `DELETE /api/v1/voice/voices/{voice_id}` - Delete a voice
  - Returns: {status, message}

#### Usage & Subscription
- `GET /api/v1/voice/usage` - Get API usage statistics
  - Returns: {character_limit, character_count, characters_remaining, tier, status}

#### Emotion Detection
- `POST /api/v1/voice/analyze-emotion` - Analyze audio emotion
  - Form params: `audio` (file), `user_id`
  - Returns: {emotion: {...}, adaptation_prompt: str, audio_features: {...}}

- `GET /api/v1/voice/emotion-history/{user_id}` - Get emotion history
  - Query params: `limit` (1-1000)
  - Returns: {history_count: int, history: [...]]}

### 4. Configuration Updates (`/app/core/config.py`)
New settings added to `Settings` class:

```python
elevenlabs_api_key: str = ""              # ElevenLabs API key
default_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
voice_enabled: bool = True                 # Enable/disable voice service
emotion_detection_enabled: bool = True     # Enable/disable emotion analysis
```

### 5. Main Application Updates (`/app/main.py`)
- Imported voice router and voice service cleanup
- Added ElevenLabs API key to `os.environ` during startup
- Registered voice router at `/api/v1/voice`
- Added voice and emotion service status logging
- Added voice service cleanup on shutdown

## Configuration

### Environment Variables (`.env`)
```bash
ELEVENLABS_API_KEY=sk_74957f4878f84d47768a2c415184e221c79a7150a8157f04
DEFAULT_VOICE_ID=21m00Tcm4TlvDq8ikWAM
VOICE_ENABLED=true
EMOTION_DETECTION_ENABLED=true
```

### Available Voices
ElevenLabs provides several pre-built voices. Fetch with:
```bash
GET /api/v1/voice/voices
```

Common voices:
- `21m00Tcm4TlvDq8ikWAM` - Rachel (default)
- `EXAVITQu4vr4xnSDxMaL` - Bella
- `g0-OXlnhLIJ4pFfIy5R1` - Giovanni
- `nPczCjzE2ezNuZqLvXRH` - Lily
- `cgSugond9qn7tBZc2OEd` - Patrick

## Usage Examples

### 1. Synthesize Speech
```bash
curl -X POST "http://localhost:8000/api/v1/voice/synthesize?text=Hello%20world" \
  -H "accept: audio/mpeg" \
  --output speech.mp3
```

### 2. Stream Synthesis for Real-Time Playback
```bash
curl -X POST "http://localhost:8000/api/v1/voice/synthesize/stream?text=This%20is%20streaming" \
  -H "accept: audio/mpeg" \
  --output stream.mp3
```

### 3. Clone a Voice
```bash
curl -X POST "http://localhost:8000/api/v1/voice/clone" \
  -F "name=Custom Voice" \
  -F "audio=@sample.wav" \
  -F "description=My custom voice" \
  -F "consent_given=true"
```

### 4. Analyze Emotion
```bash
curl -X POST "http://localhost:8000/api/v1/voice/analyze-emotion" \
  -F "audio=@user_audio.wav" \
  -F "user_id=user123"
```

### 5. Check Usage
```bash
curl -X GET "http://localhost:8000/api/v1/voice/usage"
```

Response example:
```json
{
  "status": "success",
  "usage": {
    "character_limit": 11000000,
    "character_count": 2500000,
    "characters_remaining": 8500000,
    "tier": "professional",
    "status": "active"
  }
}
```

## Integration with Cipher

The emotion analysis system generates adaptation prompts that can be prepended to Cipher's system prompt:

```python
# In orchestrator.py
emotion_profile = await get_emotion_service().analyze_audio(audio_data)
emotion_prompt = await get_emotion_service().get_adaptation_prompt(emotion_profile)

# Use combined system prompt
full_system_prompt = f"{CIPHER_SYSTEM_PROMPT}\n\n{emotion_prompt}"
result = await chat_completion(
    messages=messages,
    system_prompt=full_system_prompt,
    ...
)
```

Example adaptation prompts:
- **Calm user**: "The user sounds calm and composed. Maintain professional clarity with measured detail. Avoid unnecessary urgency."
- **Stressed user**: "The user sounds stressed or under pressure. Respond with extra clarity and conciseness. Cut to the core issue. Acknowledge the weight, then focus on solutions."
- **Excited user**: "The user sounds energized and enthusiastic. Match their energy with crisp, impactful responses. Capitalize on their momentum."

## Audio Feature Analysis

The emotion service extracts these audio features:

```python
AudioFeatures:
  - pitch_mean: Mean fundamental frequency (Hz)
  - pitch_std: Pitch variability/jitter
  - energy_mean: Volume/loudness (dB)
  - energy_std: Loudness variation
  - speaking_rate: Words per minute estimate
  - pause_count: Number of pauses detected
  - pause_duration_total: Total pause time (seconds)
  - zero_crossing_rate: Voice characteristic metric
  - mfcc_mean: Mel-Frequency Cepstral Coefficients (voice timbre)
  - vocal_tremor: Tremor/waviness in voice (0-1)
```

## Emotional Dimensions (PAD Model)

The system uses the Pleasure-Arousal-Dominance model:

- **Arousal** (-1 to 1): Calm to Excited
- **Valence** (-1 to 1): Sad to Happy
- **Dominance** (-1 to 1): Uncertain to Confident

These dimensions map to emotional categories:
- Calm: low arousal, positive valence
- Excited: high arousal, positive valence
- Stressed: high arousal, negative valence
- Sad: low arousal, negative valence
- Focused: moderate arousal, high dominance
- Frustrated: moderate arousal, negative valence, low dominance
- Happy: high valence
- Uncertain: low dominance

## Emotion History Storage

Emotion profiles are automatically stored per user in:
```
/data/emotions/{user_id}/{timestamp}.json
```

Example file content:
```json
{
  "timestamp": "2026-02-26T14:30:45.123456+00:00",
  "primary_emotion": "calm",
  "confidence": 0.85,
  "secondary_emotions": [["focused", 0.4]],
  "arousal": -0.7,
  "valence": 0.3,
  "dominance": 0.0,
  "audio_features": { ... }
}
```

## Voice Cloning Consent

Voice cloning requires explicit consent:
```python
await voice_service.clone_voice(
    name="user_voice",
    audio_data=audio_bytes,
    consent_given=True  # Must be explicitly True
)
```

The consent parameter ensures users understand they're creating a permanent voice clone.

## Dependencies

### Required
- `httpx` (async HTTP client) - for ElevenLabs API
- `fastapi` (already in project)
- `pydantic` (already in project)

### Optional (for advanced emotion analysis)
- `librosa` - Advanced audio feature extraction
- `numpy` - Numerical computation

If librosa is not installed, the system falls back to basic heuristic analysis.

Install optional dependencies:
```bash
pip install librosa numpy
```

## Error Handling

All endpoints handle errors gracefully:

- **400 Bad Request**: Invalid parameters (empty text, invalid audio, etc.)
- **503 Service Unavailable**: Voice service disabled or not configured
- **500 Internal Server Error**: API failures (logged with details)

Example error response:
```json
{
  "detail": "ElevenLabs API error: Rate limit exceeded"
}
```

## Production Considerations

1. **API Key Security**: The ElevenLabs API key is loaded from environment variables, not stored in code.

2. **Rate Limiting**: Implement rate limiting on voice endpoints to prevent token exhaustion.

3. **Token Budgeting**: Monitor usage with `GET /api/v1/voice/usage` to track remaining tokens.

4. **Caching**: Consider caching common TTS responses to save tokens.

5. **Audio Format Support**: Currently supports MP3 and WAV formats.

6. **Async Processing**: All operations are async-safe for high concurrency.

## Testing

```bash
# Test synthesize
curl -X POST "http://localhost:8000/api/v1/voice/synthesize?text=Hello" \
  -H "accept: audio/mpeg" \
  --output test.mp3

# Test usage
curl -X GET "http://localhost:8000/api/v1/voice/usage"

# Test voices list
curl -X GET "http://localhost:8000/api/v1/voice/voices"
```

## Future Enhancements

1. Voice style presets (professional, casual, dramatic, etc.)
2. Real-time speech recognition + synthesis for interactive voice
3. Multi-language support
4. Voice quality metrics and diagnostics
5. Custom voice model fine-tuning
6. Integration with iOS app for seamless voice I/O
