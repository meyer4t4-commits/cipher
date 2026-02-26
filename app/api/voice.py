"""
Voice API endpoints - TTS, voice cloning, emotion analysis, and voice management.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.voice_service import get_voice_service
from app.services.emotion_service import get_emotion_service

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/synthesize", response_class=StreamingResponse)
async def synthesize_speech(
    text: str = Query(..., description="Text to synthesize"),
    voice_id: Optional[str] = Query(None, description="Voice ID (optional)"),
    model_id: str = Query("eleven_monolingual_v1", description="Model to use"),
):
    """
    Synthesize speech from text using ElevenLabs TTS.

    Returns audio in mp3 format.
    """
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice service is disabled")

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        service = await get_voice_service()

        audio_bytes = await service.synthesize_speech(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
        )

        return StreamingResponse(
            iter([audio_bytes]),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail="Speech synthesis failed")
    except Exception as e:
        logger.error(f"Unexpected error in synthesize: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/synthesize/stream")
async def synthesize_speech_stream(
    text: str = Query(..., description="Text to synthesize"),
    voice_id: Optional[str] = Query(None, description="Voice ID (optional)"),
    model_id: str = Query("eleven_monolingual_v1", description="Model to use"),
):
    """
    Stream synthesized speech from text using chunked transfer encoding.

    Useful for real-time playback in the iOS app.
    """
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice service is disabled")

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        service = await get_voice_service()

        async def audio_stream():
            async for chunk in service.synthesize_speech_stream(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
            ):
                yield chunk

        return StreamingResponse(
            audio_stream(),
            media_type="audio/mpeg",
            headers={
                "Transfer-Encoding": "chunked",
                "Content-Disposition": "inline; filename=speech.mp3",
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Stream synthesis error: {e}")
        raise HTTPException(status_code=500, detail="Speech synthesis failed")
    except Exception as e:
        logger.error(f"Unexpected error in synthesize_stream: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/clone")
async def clone_voice(
    name: str = Query(..., description="Name for the cloned voice"),
    audio: UploadFile = File(..., description="Audio file (wav or mp3)"),
    description: Optional[str] = Query(None, description="Optional voice description"),
    consent_given: bool = Query(
        ..., description="Must be true to proceed with voice cloning"
    ),
):
    """
    Clone a voice from an audio sample.

    Requires explicit consent_given=true parameter.
    """
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice service is disabled")

    if not consent_given:
        raise HTTPException(
            status_code=400,
            detail="Voice cloning requires explicit consent (consent_given=true)",
        )

    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Voice name is required")

    try:
        audio_data = await audio.read()
        if not audio_data:
            raise HTTPException(status_code=400, detail="Audio file is empty")

        service = await get_voice_service()

        voice_id = await service.clone_voice(
            name=name,
            audio_data=audio_data,
            description=description,
            consent_given=True,
        )

        return {
            "status": "success",
            "voice_id": voice_id,
            "name": name,
            "message": f"Voice '{name}' cloned successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Clone error: {e}")
        raise HTTPException(status_code=500, detail="Voice cloning failed")
    except Exception as e:
        logger.error(f"Unexpected error in clone: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/voices")
async def list_voices():
    """
    List all available voices in the user's ElevenLabs account.
    """
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice service is disabled")

    try:
        service = await get_voice_service()
        voices = await service.list_voices()

        return {
            "status": "success",
            "voices": voices,
            "count": len(voices),
        }

    except RuntimeError as e:
        logger.error(f"List voices error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list voices")
    except Exception as e:
        logger.error(f"Unexpected error in list_voices: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/voices/{voice_id}")
async def get_voice_details(voice_id: str):
    """
    Get details about a specific voice.
    """
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice service is disabled")

    try:
        service = await get_voice_service()
        voice = await service.get_voice_details(voice_id)

        return {
            "status": "success",
            "voice": voice,
        }

    except RuntimeError as e:
        logger.error(f"Get voice details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get voice details")
    except Exception as e:
        logger.error(f"Unexpected error in get_voice_details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    """
    Delete a custom cloned voice.
    """
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice service is disabled")

    try:
        service = await get_voice_service()
        await service.delete_voice(voice_id)

        return {
            "status": "success",
            "message": f"Voice {voice_id} deleted",
        }

    except RuntimeError as e:
        logger.error(f"Delete voice error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete voice")
    except Exception as e:
        logger.error(f"Unexpected error in delete_voice: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/usage")
async def get_voice_usage():
    """
    Get ElevenLabs API usage statistics and subscription info.

    Shows character limit, character count, remaining characters, and tier.
    """
    if not settings.voice_enabled:
        raise HTTPException(status_code=503, detail="Voice service is disabled")

    try:
        service = await get_voice_service()
        usage = await service.get_usage()

        return {
            "status": "success",
            "usage": usage,
        }

    except RuntimeError as e:
        logger.error(f"Get usage error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage statistics")
    except Exception as e:
        logger.error(f"Unexpected error in get_voice_usage: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/analyze-emotion")
async def analyze_emotion(
    audio: UploadFile = File(..., description="Audio file to analyze"),
    user_id: str = Query("default", description="User ID for emotion history"),
):
    """
    Analyze audio for emotional cues.

    Returns emotional profile including primary emotion, confidence, and audio features.
    """
    if not settings.emotion_detection_enabled:
        raise HTTPException(status_code=503, detail="Emotion detection is disabled")

    try:
        audio_data = await audio.read()
        if not audio_data:
            raise HTTPException(status_code=400, detail="Audio file is empty")

        service = await get_emotion_service()
        emotion_profile = await service.analyze_audio(audio_data, user_id)

        # Get adaptation prompt
        adaptation_prompt = await service.get_adaptation_prompt(emotion_profile)

        return {
            "status": "success",
            "emotion": {
                "primary": emotion_profile.primary_emotion,
                "confidence": emotion_profile.confidence,
                "secondary": emotion_profile.secondary_emotions,
                "arousal": emotion_profile.arousal,
                "valence": emotion_profile.valence,
                "dominance": emotion_profile.dominance,
            },
            "adaptation_prompt": adaptation_prompt,
            "audio_features": {
                "pitch_mean": emotion_profile.audio_features.pitch_mean,
                "pitch_std": emotion_profile.audio_features.pitch_std,
                "energy_mean": emotion_profile.audio_features.energy_mean,
                "energy_std": emotion_profile.audio_features.energy_std,
                "speaking_rate": emotion_profile.audio_features.speaking_rate,
                "pause_count": emotion_profile.audio_features.pause_count,
                "pause_duration_total": emotion_profile.audio_features.pause_duration_total,
                "zero_crossing_rate": emotion_profile.audio_features.zero_crossing_rate,
                "vocal_tremor": emotion_profile.audio_features.vocal_tremor,
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Emotion analysis error: {e}")
        raise HTTPException(status_code=500, detail="Emotion analysis failed")


@router.get("/emotion-history/{user_id}")
async def get_emotion_history(
    user_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
):
    """
    Get emotion history for a user.

    Returns list of emotion profiles (most recent first).
    """
    if not settings.emotion_detection_enabled:
        raise HTTPException(status_code=503, detail="Emotion detection is disabled")

    try:
        service = await get_emotion_service()
        history = await service.get_emotion_history(user_id, limit)

        return {
            "status": "success",
            "user_id": user_id,
            "history_count": len(history),
            "history": history,
        }

    except Exception as e:
        logger.error(f"Emotion history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve emotion history")


# ──────────────────────────────────────────────
# Live Conversational Voice
# ──────────────────────────────────────────────

from pydantic import BaseModel
from app.services.live_voice import get_live_voice_manager, VoiceSessionConfig


class LiveSessionRequest(BaseModel):
    session_id: Optional[str] = None
    max_response_sentences: int = 3
    max_response_words: int = 60
    silence_timeout_ms: int = 1500


class LiveTurnRequest(BaseModel):
    session_id: str
    text: str
    audio_duration_ms: int = 0


@router.post("/live/start")
async def start_live_session(req: LiveSessionRequest):
    """
    Start a live conversational voice session.
    Returns session_id for subsequent turns.
    Live mode = short responses, interruptible, fast, flowing.
    """
    import uuid
    mgr = get_live_voice_manager()
    session_id = req.session_id or str(uuid.uuid4())

    config = VoiceSessionConfig(
        max_response_sentences=req.max_response_sentences,
        max_response_words=req.max_response_words,
        silence_timeout_ms=req.silence_timeout_ms,
    )

    session = mgr.create_session(session_id, config)
    return {
        "session_id": session_id,
        "state": session.state.value,
        "config": {
            "max_response_sentences": config.max_response_sentences,
            "max_response_words": config.max_response_words,
            "silence_timeout_ms": config.silence_timeout_ms,
        },
        "message": "Live voice session started. Send turns to /voice/live/turn",
    }


@router.post("/live/turn")
async def live_voice_turn(req: LiveTurnRequest):
    """
    Send a user turn in a live voice session.
    Returns Cipher's conversational response (truncated for voice delivery).
    The full text is always preserved for history.
    """
    mgr = get_live_voice_manager()
    session = mgr.get_session(req.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Start one at /voice/live/start")

    import time as _time
    turn_start = _time.time()

    # Record user turn
    session.add_user_turn(req.text, req.audio_duration_ms)

    # Get voice system prompt overlay
    voice_prompt = session.build_voice_system_prompt("")

    # Get conversation context (short window for speed)
    context = session.get_conversation_context(max_turns=8)

    # Generate response (in production, this streams from the orchestrator)
    # For now, return the structure the iOS app needs
    latency_ms = (_time.time() - turn_start) * 1000

    return {
        "session_id": req.session_id,
        "state": session.state.value,
        "context": context,
        "voice_system_overlay": voice_prompt,
        "config": {
            "max_sentences": session.config.max_response_sentences,
            "max_words": session.config.max_response_words,
        },
        "latency_ms": round(latency_ms, 1),
        "message": "Use this context + voice overlay with the /chat/stream endpoint for voice-optimized responses",
    }


@router.post("/live/interrupt")
async def interrupt_live_session(session_id: str = Query(...)):
    """Interrupt Cipher mid-speech. User is talking over it."""
    mgr = get_live_voice_manager()
    session = mgr.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.interrupt()
    return {
        "session_id": session_id,
        "state": session.state.value,
        "interrupt_count": session.interrupt_count,
    }


@router.post("/live/end")
async def end_live_session(session_id: str = Query(...)):
    """End a live voice session and get stats."""
    mgr = get_live_voice_manager()
    stats = mgr.end_session(session_id)

    if not stats:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "message": "Live voice session ended",
        **stats,
    }


@router.get("/live/sessions")
async def list_live_sessions():
    """List active live voice sessions."""
    mgr = get_live_voice_manager()
    return {"active_sessions": mgr.get_active_sessions()}
