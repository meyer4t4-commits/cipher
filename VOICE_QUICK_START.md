# Voice Intelligence System - Quick Start Guide

## What Was Built

A complete voice intelligence system for Orchid with:
- **Text-to-Speech (TTS)**: Convert text to audio via ElevenLabs
- **Voice Cloning**: Create custom voices from audio samples
- **Emotion Detection**: Analyze user audio for emotional cues
- **Response Adaptation**: Automatically adjust Cipher's tone based on detected emotions

## Files Created

```
/app/services/voice_service.py      (401 lines) - ElevenLabs integration
/app/services/emotion_service.py    (522 lines) - Audio emotion analysis
/app/api/voice.py                   (347 lines) - FastAPI endpoints
/VOICE_SYSTEM_GUIDE.md              - Complete documentation
/VOICE_IMPLEMENTATION_NOTES.md       - Architecture & design decisions
```

## Configuration

Add to your `.env` file:

```bash
ELEVENLABS_API_KEY=sk_74957f4878f84d47768a2c415184e221c79a7150a8157f04
DEFAULT_VOICE_ID=21m00Tcm4TlvDq8ikWAM
VOICE_ENABLED=true
EMOTION_DETECTION_ENABLED=true
```

## API Endpoints

### Text-to-Speech
```bash
# Single response (full audio)
POST /api/v1/voice/synthesize?text=Hello+world

# Streaming (real-time playback)
POST /api/v1/voice/synthesize/stream?text=Hello+world
```

### Voice Management
```bash
# List available voices
GET /api/v1/voice/voices

# Clone a voice from audio
POST /api/v1/voice/clone -F "name=My Voice" -F "audio=@file.wav" -F "consent_given=true"

# Check token usage
GET /api/v1/voice/usage
```

### Emotion Analysis
```bash
# Analyze audio for emotions
POST /api/v1/voice/analyze-emotion -F "audio=@user_voice.wav"

# Get emotion history
GET /api/v1/voice/emotion-history/{user_id}
```

## How It Works

### Voice Synthesis Flow
```
User Input (text)
    ↓
POST /synthesize
    ↓
VoiceService
    ↓
ElevenLabs API v1
    ↓
MP3 Audio Response
    ↓
Return to iOS app
    ↓
Playback
```

### Emotion Detection Flow
```
User Audio (wav/mp3)
    ↓
POST /analyze-emotion
    ↓
EmotionService
    ↓
Extract Features:
  - Pitch, energy, tempo
  - Pauses, tremor
  - Voice characteristics
    ↓
Calculate Emotions:
  - Arousal (calm to excited)
  - Valence (sad to happy)
  - Dominance (uncertain to confident)
    ↓
Generate Adaptation Prompt
    ↓
Return Profile + Prompt
    ↓
Use prompt with Cipher response
```

## Code Examples

### Python: Synthesize Speech
```python
from app.services.voice_service import get_voice_service

service = await get_voice_service()
audio_bytes = await service.synthesize_speech("Hello world")
```

### Python: Analyze Emotion
```python
from app.services.emotion_service import get_emotion_service

service = await get_emotion_service()
emotion = await service.analyze_audio(audio_data, user_id="user123")
adaptation_prompt = await service.get_adaptation_prompt(emotion)
```

### Swift: iOS App Integration
```swift
// Analyze user audio for emotions
let emotionResponse = await fetchJSON(
    method: "POST",
    url: "/api/v1/voice/analyze-emotion",
    multipart: ["audio": audioData]
)

// Get adaptation prompt
let adaptationPrompt = emotionResponse["adaptation_prompt"]

// Send to Cipher with emotion context
let cipherResponse = await fetchJSON(
    method: "POST",
    url: "/api/v1/chat",
    json: [
        "message": userMessage,
        "system_prompt": adaptationPrompt  // Emotion-aware!
    ]
)

// Synthesize response as speech
let speechStream = URLSession.shared.dataTaskPublisher(
    for: URL(string: "/api/v1/voice/synthesize/stream?text=\(cipherResponse["message"])")!
).stream
```

### cURL: Simple Test
```bash
# Synthesize speech
curl -X POST "http://localhost:8000/api/v1/voice/synthesize?text=Hello" \
  --output speech.mp3

# Check usage
curl "http://localhost:8000/api/v1/voice/usage" | jq

# Analyze emotion
curl -X POST "http://localhost:8000/api/v1/voice/analyze-emotion" \
  -F "audio=@voice.wav" | jq
```

## Key Concepts

### Emotions Detected
- **calm**: Relaxed, composed
- **excited**: Energized, enthusiastic
- **stressed**: Tense, pressured
- **sad**: Down, discouraged
- **focused**: Intense, concentrated
- **frustrated**: Annoyed, irritated
- **happy**: Pleased, joyful
- **uncertain**: Hesitant, unsure

### Adaptation Examples
```
User sounds calm
→ "Maintain professional clarity with measured detail"

User sounds stressed
→ "Cut to core issue. Acknowledge weight, then solutions"

User sounds excited
→ "Match their energy with crisp, impactful responses"

User sounds uncertain
→ "Provide clear guidance with explicit next steps"
```

## Token Budget (11M characters)

Your account has approximately 11 million characters of TTS tokens.

Monitor usage:
```bash
curl http://localhost:8000/api/v1/voice/usage | jq .usage
```

Output:
```json
{
  "character_limit": 11000000,
  "character_count": 2500000,
  "characters_remaining": 8500000,
  "tier": "professional"
}
```

## Emotion History Storage

Emotion profiles are automatically stored in `/data/emotions/{user_id}/`

Each emotion analysis creates a JSON file with:
- Detected emotions and confidence
- Audio features (pitch, energy, speaking rate, etc.)
- PAD dimensions (arousal, valence, dominance)
- Timestamp

Retrieve with:
```bash
GET /api/v1/voice/emotion-history/user123?limit=100
```

## Voice Cloning Consent

Voice cloning requires explicit consent because it creates permanent replicas:

```python
# This will FAIL
await service.clone_voice(name="Voice", audio_data=audio)

# This will SUCCEED
await service.clone_voice(name="Voice", audio_data=audio, consent_given=True)
```

## Troubleshooting

### Missing API Key
```
Error: "ElevenLabs API key not configured"
→ Add ELEVENLABS_API_KEY to .env
```

### Rate Limited
```
Error: "ElevenLabs API error: Rate limit exceeded"
→ Too many requests. Wait or upgrade tier.
→ Check usage: GET /api/v1/voice/usage
```

### Voice Service Disabled
```
Error: "Voice service is disabled"
→ Set VOICE_ENABLED=true in .env
```

### Emotion Detection Disabled
```
Error: "Emotion detection is disabled"
→ Set EMOTION_DETECTION_ENABLED=true in .env
```

### No Librosa
```
Warning: "librosa not installed - emotion detection will use basic heuristics"
→ Optional: pip install librosa
→ System works fine without it
```

## Performance Tips

1. **Use streaming TTS for long texts**
   ```
   /synthesize/stream is better than /synthesize for large responses
   ```

2. **Cache common TTS responses**
   ```
   Same text + voice = same audio
   Consider Redis caching
   ```

3. **Monitor token usage**
   ```
   Each character costs tokens
   Check usage regularly
   ```

4. **Batch emotion analyses**
   ```
   Analyze multiple user audios together when possible
   ```

## Next Steps

1. Set `ELEVENLABS_API_KEY` in your `.env`
2. Restart Orchid
3. Test endpoint: `GET /api/v1/voice/voices`
4. Try synthesize: `POST /api/v1/voice/synthesize?text=test`
5. Try emotion: `POST /api/v1/voice/analyze-emotion` with audio
6. Check usage: `GET /api/v1/voice/usage`

## Documentation Files

- **VOICE_SYSTEM_GUIDE.md**: Complete feature documentation
- **VOICE_IMPLEMENTATION_NOTES.md**: Architecture and technical details
- **VOICE_QUICK_START.md**: This file

## Support

All services are fully typed with docstrings.
Check the code for detailed parameter descriptions and examples.

Review the implementation notes for:
- API response examples
- Error scenarios
- Integration patterns
- Performance considerations
- Testing checklist
