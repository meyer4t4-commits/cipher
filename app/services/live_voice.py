"""
Live Conversational Voice — Cipher's real-time voice mode.

PHILOSOPHY:
Text is the foundation. It always works. Voice is a layer on top.
Live voice mode is how Cipher becomes a CONVERSATION, not a search engine.

This is NOT "read my paragraph out loud." This is:
- Short, punchy responses (2-3 sentences max in voice mode)
- Fast — latency is everything. Sub-second response starts.
- Interruptible — user talks over Cipher, Cipher stops and listens
- Turn-taking — natural conversational rhythm
- Text always generated alongside voice (accessibility, search, history)
- Falls back to text-only gracefully if voice fails

LIKE GEMINI LIVE / CLAUDE VOICE:
The best voice AI feels like talking to someone smart on the phone.
Short turns. Quick responses. Natural interruptions. Not a lecture.

ARCHITECTURE:
1. User speaks → speech-to-text (streaming, partial results)
2. Partial text → LLM starts generating (don't wait for full sentence)
3. LLM generates short response → TTS synthesis starts immediately
4. Audio streams back while LLM is still finishing
5. User interrupts → cancel TTS, start listening again
6. All text saved to conversation history (both sides)

RESPONSE STYLE IN VOICE MODE:
- Max 3 sentences per turn (hard limit)
- Conversational tone — contractions, casual phrasing
- No bullet points, no headers, no formatting (it's speech)
- If the answer needs more depth: "Want me to go deeper on that?"
- Mirror the user's energy and pace
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional, Callable

from app.core.logging import logger


class VoiceSessionState(str, Enum):
    """State machine for live voice conversation."""
    IDLE = "idle"                   # Not in voice mode
    LISTENING = "listening"         # Cipher is listening to user
    PROCESSING = "processing"       # LLM is generating
    SPEAKING = "speaking"           # Cipher is speaking (TTS playing)
    INTERRUPTED = "interrupted"     # User interrupted, switching to listen


@dataclass
class VoiceSessionConfig:
    """Configuration for a live voice session."""
    max_response_sentences: int = 3      # Keep it short and conversational
    max_response_words: int = 60         # Hard word limit for voice responses
    silence_timeout_ms: int = 1500       # How long to wait after user stops talking
    interrupt_sensitivity: float = 0.5   # How easily user can interrupt (0-1)
    voice_speed: float = 1.0             # Playback speed multiplier
    auto_follow_up: bool = True          # Ask follow-up if response was truncated
    text_always: bool = True             # Always generate text alongside voice


@dataclass
class VoiceTurn:
    """A single turn in the voice conversation."""
    role: str                            # "user" or "assistant"
    text: str                            # Full text content
    audio_duration_ms: int = 0           # Duration of audio
    was_interrupted: bool = False        # Was this turn cut short?
    latency_ms: float = 0.0             # Time from end of user speech to start of response
    timestamp: float = field(default_factory=time.time)


class LiveVoiceSession:
    """
    Manages a live conversational voice session with Cipher.

    Think of this like a phone call state machine:
    IDLE → LISTENING → PROCESSING → SPEAKING → LISTENING → ...
    At any point during SPEAKING, user can interrupt → LISTENING
    """

    def __init__(self, session_id: str, config: Optional[VoiceSessionConfig] = None):
        self.session_id = session_id
        self.config = config or VoiceSessionConfig()
        self.state = VoiceSessionState.IDLE
        self.turns: list[VoiceTurn] = []
        self._interrupt_flag = False
        self._started_at: Optional[float] = None
        self._current_generation_task: Optional[asyncio.Task] = None

        # Metrics
        self.total_user_speech_ms = 0
        self.total_cipher_speech_ms = 0
        self.total_latency_ms = 0.0
        self.interrupt_count = 0

    def start(self):
        """Begin a live voice session."""
        self.state = VoiceSessionState.LISTENING
        self._started_at = time.time()
        logger.info(f"Live voice session started: {self.session_id}")

    def end(self):
        """End the voice session."""
        self.state = VoiceSessionState.IDLE
        duration = time.time() - (self._started_at or time.time())
        logger.info(
            f"Live voice session ended: {self.session_id} | "
            f"duration={duration:.1f}s | turns={len(self.turns)} | "
            f"interrupts={self.interrupt_count}"
        )

    def interrupt(self):
        """User interrupted Cipher while it was speaking."""
        if self.state == VoiceSessionState.SPEAKING:
            self._interrupt_flag = True
            self.state = VoiceSessionState.INTERRUPTED
            self.interrupt_count += 1

            # Mark the last assistant turn as interrupted
            if self.turns and self.turns[-1].role == "assistant":
                self.turns[-1].was_interrupted = True

            logger.debug(f"Voice interrupted (count: {self.interrupt_count})")
            # Cancel any ongoing generation
            if self._current_generation_task and not self._current_generation_task.done():
                self._current_generation_task.cancel()

            self.state = VoiceSessionState.LISTENING

    def is_interrupted(self) -> bool:
        """Check and clear interrupt flag."""
        if self._interrupt_flag:
            self._interrupt_flag = False
            return True
        return False

    def truncate_for_voice(self, text: str) -> tuple[str, bool]:
        """
        Truncate LLM response for conversational voice delivery.

        Rules:
        - Max N sentences (default 3)
        - Max M words (default 60)
        - No bullet points, headers, or formatting
        - If truncated, return flag so we can offer "want me to go deeper?"

        Returns: (truncated_text, was_truncated)
        """
        # Strip any markdown formatting
        clean = text
        for prefix in ["# ", "## ", "### ", "- ", "* ", "1. ", "2. ", "3. "]:
            clean = clean.replace(prefix, "")
        clean = clean.replace("**", "").replace("__", "").replace("`", "")
        clean = clean.replace("\n\n", ". ").replace("\n", " ")

        # Split into sentences
        sentences = []
        current = ""
        for char in clean:
            current += char
            if char in ".!?" and len(current.strip()) > 5:
                sentences.append(current.strip())
                current = ""
        if current.strip():
            sentences.append(current.strip())

        # Apply limits
        result_sentences = sentences[:self.config.max_response_sentences]
        result = " ".join(result_sentences)

        # Word limit
        words = result.split()
        if len(words) > self.config.max_response_words:
            result = " ".join(words[:self.config.max_response_words])
            # Find last sentence end
            for end_char in [".", "!", "?"]:
                last_end = result.rfind(end_char)
                if last_end > len(result) // 2:
                    result = result[:last_end + 1]
                    break
            was_truncated = True
        else:
            was_truncated = len(sentences) > self.config.max_response_sentences

        return result, was_truncated

    def build_voice_system_prompt(self, base_prompt: str) -> str:
        """
        Modify the system prompt for conversational voice mode.
        Short, natural, flowing responses.
        """
        voice_overlay = """

LIVE VOICE MODE ACTIVE — CONVERSATIONAL RULES:

You are in a live voice conversation. This changes everything about how you respond:

1. BREVITY IS KING. 2-3 sentences max per turn. This is a conversation, not a lecture.
2. CONVERSATIONAL TONE. Use contractions. Speak naturally. "Here's the thing" not "The following points are relevant."
3. NO FORMATTING. No bullet points, no headers, no numbered lists. You're TALKING.
4. MIRROR THEIR ENERGY. If they're quick and punchy, match it. If they're slow and thoughtful, match that.
5. ASK DON'T DUMP. If the topic needs depth, say "Want me to go deeper on that?" Don't info-dump.
6. NATURAL PAUSES. End turns at natural stopping points. Let them respond.
7. HANDLE INTERRUPTIONS. If they interrupt, acknowledge and pivot. "Got it—" or "Sure, let's—"
8. THINK OUT LOUD. Brief thinking is fine: "Hmm, let me think about that..." feels natural.
9. NO FILLER. Don't say "Great question!" or "That's interesting!" Just answer.
10. LEAD WITH THE ANSWER. First sentence is the answer. Context after, if they want it.
"""
        return base_prompt + voice_overlay

    def add_user_turn(self, text: str, audio_duration_ms: int = 0):
        """Record a user's voice turn."""
        self.turns.append(VoiceTurn(
            role="user",
            text=text,
            audio_duration_ms=audio_duration_ms,
        ))
        self.total_user_speech_ms += audio_duration_ms
        self.state = VoiceSessionState.PROCESSING

    def add_assistant_turn(
        self,
        text: str,
        audio_duration_ms: int = 0,
        latency_ms: float = 0.0,
        was_interrupted: bool = False,
    ):
        """Record Cipher's voice response."""
        self.turns.append(VoiceTurn(
            role="assistant",
            text=text,
            audio_duration_ms=audio_duration_ms,
            latency_ms=latency_ms,
            was_interrupted=was_interrupted,
        ))
        self.total_cipher_speech_ms += audio_duration_ms
        self.total_latency_ms += latency_ms
        self.state = VoiceSessionState.SPEAKING

    def get_conversation_context(self, max_turns: int = 10) -> list[dict]:
        """
        Get recent conversation history for LLM context.
        Voice mode keeps a shorter context window for speed.
        """
        recent = self.turns[-max_turns:]
        return [{"role": t.role, "content": t.text} for t in recent]

    def get_session_stats(self) -> dict:
        """Get metrics for this voice session."""
        duration = time.time() - (self._started_at or time.time())
        avg_latency = (
            self.total_latency_ms / max(sum(1 for t in self.turns if t.role == "assistant"), 1)
        )
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "duration_seconds": round(duration, 1),
            "total_turns": len(self.turns),
            "user_turns": sum(1 for t in self.turns if t.role == "user"),
            "assistant_turns": sum(1 for t in self.turns if t.role == "assistant"),
            "interrupt_count": self.interrupt_count,
            "avg_latency_ms": round(avg_latency, 1),
            "total_user_speech_ms": self.total_user_speech_ms,
            "total_cipher_speech_ms": self.total_cipher_speech_ms,
        }


# ============================================================================
# Live Voice Session Manager
# ============================================================================

class LiveVoiceManager:
    """Manages active live voice sessions."""

    def __init__(self):
        self._sessions: dict[str, LiveVoiceSession] = {}

    def create_session(
        self,
        session_id: str,
        config: Optional[VoiceSessionConfig] = None,
    ) -> LiveVoiceSession:
        """Create and start a new live voice session."""
        session = LiveVoiceSession(session_id, config)
        session.start()
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[LiveVoiceSession]:
        """Get an active session."""
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> Optional[dict]:
        """End a session and return stats."""
        session = self._sessions.pop(session_id, None)
        if session:
            session.end()
            return session.get_session_stats()
        return None

    def get_active_sessions(self) -> list[str]:
        """List active session IDs."""
        return list(self._sessions.keys())


# Singleton
_live_manager: Optional[LiveVoiceManager] = None

def get_live_voice_manager() -> LiveVoiceManager:
    global _live_manager
    if _live_manager is None:
        _live_manager = LiveVoiceManager()
    return _live_manager
