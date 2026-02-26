"""
Voice Service - ElevenLabs TTS integration for Cipher.
Handles voice synthesis, voice cloning, and voice management.

This service integrates with ElevenLabs API v1 for high-quality text-to-speech
and voice cloning capabilities without requiring the elevenlabs pip package.
"""

import asyncio
import httpx
from typing import Optional, AsyncGenerator
from pathlib import Path
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import logger


class VoiceService:
    """ElevenLabs voice service for TTS and voice management."""

    BASE_URL = "https://api.elevenlabs.io/v1"
    DEFAULT_MODEL_ID = "eleven_monolingual_v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize voice service.

        Args:
            api_key: ElevenLabs API key. Falls back to settings if not provided.
        """
        self.api_key = api_key or settings.elevenlabs_api_key
        if not self.api_key:
            logger.warning("ElevenLabs API key not configured")

        self.client: Optional[httpx.AsyncClient] = None
        self._default_voice_id = settings.default_voice_id or "21m00Tcm4TlvDq8ikWAM"  # Rachel

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(timeout=60.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if not self.client:
            self.client = httpx.AsyncClient(timeout=60.0)
        return self.client

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:
        """
        Make authenticated request to ElevenLabs API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "voices")
            **kwargs: Additional arguments for httpx request

        Returns:
            Response JSON as dict

        Raises:
            HTTPException: If API returns error
        """
        if not self.api_key:
            raise ValueError("ElevenLabs API key not configured")

        url = f"{self.BASE_URL}/{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["xi-api-key"] = self.api_key

        client = await self._get_client()

        try:
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()

            # Handle streaming responses
            if response.headers.get("content-type", "").startswith("audio"):
                return {"audio": response.content}

            try:
                return response.json()
            except Exception:
                return {"status": "ok", "content": response.text}

        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("detail", {}).get("status", str(e))
            except Exception:
                error_detail = e.response.text

            logger.error(f"ElevenLabs API error: {e.status_code} - {error_detail}")
            raise RuntimeError(f"ElevenLabs API error: {error_detail}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            raise RuntimeError(f"Request failed: {str(e)}") from e

    async def synthesize_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: str = DEFAULT_MODEL_ID,
        voice_settings: Optional[dict] = None,
    ) -> bytes:
        """
        Synthesize speech from text using ElevenLabs.

        Args:
            text: Text to synthesize
            voice_id: Voice ID to use (defaults to configured default)
            model_id: Model ID to use
            voice_settings: Optional voice settings dict with stability/clarity

        Returns:
            Audio bytes (mp3 format)

        Raises:
            ValueError: If text is empty or invalid
            RuntimeError: If API call fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        if len(text) > 5000:
            logger.warning(f"Text length {len(text)} exceeds recommended 5000 chars")

        voice_id = voice_id or self._default_voice_id

        # Prepare request body
        body = {
            "text": text,
            "model_id": model_id,
        }

        # Add voice settings if provided
        if voice_settings:
            body["voice_settings"] = {
                "stability": voice_settings.get("stability", 0.5),
                "similarity_boost": voice_settings.get("similarity_boost", 0.75),
            }

        logger.info(f"Synthesizing speech: {len(text)} chars, voice_id={voice_id}")

        response = await self._make_request(
            "POST",
            f"text-to-speech/{voice_id}",
            json=body,
        )

        if "audio" in response:
            return response["audio"]

        raise RuntimeError("No audio in response")

    async def synthesize_speech_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: str = DEFAULT_MODEL_ID,
        voice_settings: Optional[dict] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream synthesized speech from text.

        Args:
            text: Text to synthesize
            voice_id: Voice ID to use
            model_id: Model ID to use
            voice_settings: Optional voice settings

        Yields:
            Audio chunks as bytes

        Raises:
            ValueError: If text is empty
            RuntimeError: If API call fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        voice_id = voice_id or self._default_voice_id

        body = {
            "text": text,
            "model_id": model_id,
        }

        if voice_settings:
            body["voice_settings"] = {
                "stability": voice_settings.get("stability", 0.5),
                "similarity_boost": voice_settings.get("similarity_boost", 0.75),
            }

        logger.info(f"Streaming synthesis: {len(text)} chars, voice_id={voice_id}")

        client = await self._get_client()
        headers = {"xi-api-key": self.api_key}

        url = f"{self.BASE_URL}/text-to-speech/{voice_id}/stream"

        async with client.stream("POST", url, json=body, headers=headers) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=8192):
                if chunk:
                    yield chunk

    async def clone_voice(
        self,
        name: str,
        audio_data: bytes,
        description: Optional[str] = None,
        labels: Optional[dict] = None,
        consent_given: bool = False,
    ) -> str:
        """
        Create a new voice from audio samples (voice cloning).

        Args:
            name: Name for the cloned voice
            audio_data: Audio file bytes (supported formats: mp3, wav, etc.)
            description: Optional description of the voice
            labels: Optional labels dict for tagging
            consent_given: Must be True to proceed (consent acknowledgment)

        Returns:
            Voice ID of the cloned voice

        Raises:
            ValueError: If consent not given or invalid parameters
            RuntimeError: If API call fails
        """
        if not consent_given:
            raise ValueError(
                "Voice cloning requires explicit consent. "
                "Set consent_given=True to proceed."
            )

        if not name or not name.strip():
            raise ValueError("Voice name cannot be empty")

        if not audio_data:
            raise ValueError("Audio data cannot be empty")

        logger.info(f"Cloning voice: {name}, audio_size={len(audio_data)} bytes")

        # Prepare multipart form data
        files = {
            "files": ("voice_sample.wav", audio_data, "audio/wav"),
        }

        data = {
            "name": name,
            "description": description or "",
            "labels": labels or {},
        }

        response = await self._make_request(
            "POST",
            "voices/add",
            files=files,
            data=data,
        )

        voice_id = response.get("voice_id")
        if not voice_id:
            raise RuntimeError("No voice_id returned from cloning request")

        logger.info(f"Voice cloned successfully: {voice_id}")
        return voice_id

    async def list_voices(self) -> list[dict]:
        """
        List all available voices in the user's account.

        Returns:
            List of voice dicts with id, name, category, description, etc.

        Raises:
            RuntimeError: If API call fails
        """
        logger.debug("Listing available voices")

        response = await self._make_request("GET", "voices")

        voices = response.get("voices", [])
        logger.info(f"Found {len(voices)} available voices")

        return voices

    async def get_voice_details(self, voice_id: str) -> dict:
        """
        Get detailed information about a specific voice.

        Args:
            voice_id: The voice ID to query

        Returns:
            Voice details dict

        Raises:
            RuntimeError: If API call fails
        """
        logger.debug(f"Getting voice details: {voice_id}")

        response = await self._make_request("GET", f"voices/{voice_id}")

        return response

    async def delete_voice(self, voice_id: str) -> bool:
        """
        Delete a custom cloned voice.

        Args:
            voice_id: The voice ID to delete

        Returns:
            True if deletion successful

        Raises:
            RuntimeError: If API call fails
        """
        logger.info(f"Deleting voice: {voice_id}")

        await self._make_request("DELETE", f"voices/{voice_id}")

        return True

    async def get_usage(self) -> dict:
        """
        Get API usage statistics and subscription info.

        Returns:
            Dict with character_limit, character_count, etc.

        Raises:
            RuntimeError: If API call fails
        """
        logger.debug("Fetching usage statistics")

        response = await self._make_request("GET", "user/subscription")

        # Transform response to match expected format
        return {
            "character_limit": response.get("character_limit", 0),
            "character_count": response.get("character_count", 0),
            "characters_remaining": (
                response.get("character_limit", 0) - response.get("character_count", 0)
            ),
            "tier": response.get("tier", "unknown"),
            "status": response.get("status", "unknown"),
        }

    async def set_default_voice(self, voice_id: str) -> None:
        """
        Set the default voice for future synthesis.

        Args:
            voice_id: Voice ID to set as default
        """
        # Verify voice exists
        await self.get_voice_details(voice_id)
        self._default_voice_id = voice_id
        logger.info(f"Default voice set to: {voice_id}")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()


# Singleton instance
_voice_service: Optional[VoiceService] = None


async def get_voice_service() -> VoiceService:
    """Get or create the voice service singleton."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service


async def close_voice_service() -> None:
    """Close the voice service."""
    global _voice_service
    if _voice_service:
        await _voice_service.close()
        _voice_service = None
