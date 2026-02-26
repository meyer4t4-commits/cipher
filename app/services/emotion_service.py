"""
Emotion Service - Audio emotion analysis and detection.
Analyzes audio for emotional cues and generates adaptation prompts for Cipher.

Supports both librosa-based analysis (if installed) and fallback heuristics.
Uses pitch, tempo, energy, and pause patterns to infer emotional state.
"""

import json
import struct
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict

from app.core.config import settings
from app.core.logging import logger

# Try to import librosa for advanced audio analysis
try:
    import librosa
    import numpy as np
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.warning("librosa not installed - emotion detection will use basic heuristics")


@dataclass
class AudioFeatures:
    """Raw audio features extracted from audio data."""

    pitch_mean: float  # Hz
    pitch_std: float  # Hz
    energy_mean: float  # dB
    energy_std: float  # dB
    speaking_rate: float  # words per minute estimate
    pause_count: int
    pause_duration_total: float  # seconds
    zero_crossing_rate: float
    mfcc_mean: list[float]
    vocal_tremor: float  # 0-1


@dataclass
class EmotionProfile:
    """Detected emotional profile from audio."""

    primary_emotion: str  # calm, excited, stressed, sad, focused, frustrated, happy, uncertain
    confidence: float  # 0-1
    secondary_emotions: list[tuple[str, float]]  # [(emotion, confidence), ...]
    arousal: float  # -1 (calm) to 1 (excited)
    valence: float  # -1 (sad) to 1 (happy)
    dominance: float  # -1 (uncertain) to 1 (confident)
    audio_features: AudioFeatures
    timestamp: datetime


EMOTION_MAP = {
    "calm": {"arousal": -0.7, "valence": 0.3, "dominance": 0.0},
    "excited": {"arousal": 0.9, "valence": 0.8, "dominance": 0.5},
    "stressed": {"arousal": 0.7, "valence": -0.4, "dominance": -0.3},
    "sad": {"arousal": -0.6, "valence": -0.8, "dominance": -0.5},
    "focused": {"arousal": 0.2, "valence": 0.2, "dominance": 0.7},
    "frustrated": {"arousal": 0.6, "valence": -0.5, "dominance": 0.3},
    "happy": {"arousal": 0.6, "valence": 0.9, "dominance": 0.4},
    "uncertain": {"arousal": 0.3, "valence": 0.0, "dominance": -0.7},
}


class EmotionService:
    """Audio emotion analysis and detection."""

    def __init__(self):
        """Initialize emotion service."""
        self.librosa_available = LIBROSA_AVAILABLE
        self.emotion_history_dir = Path(settings.data_dir) / "emotions"
        self.emotion_history_dir.mkdir(parents=True, exist_ok=True)

    async def analyze_audio(self, audio_data: bytes, user_id: str = "default") -> EmotionProfile:
        """
        Analyze audio for emotional cues.

        Args:
            audio_data: Audio file bytes (mp3 or wav)
            user_id: User ID for emotion history tracking

        Returns:
            EmotionProfile with detected emotions and features

        Raises:
            ValueError: If audio data is invalid
        """
        if not audio_data:
            raise ValueError("Audio data cannot be empty")

        logger.info(f"Analyzing audio: {len(audio_data)} bytes for user {user_id}")

        try:
            if self.librosa_available:
                emotion_profile = await self._analyze_with_librosa(audio_data)
            else:
                emotion_profile = await self._analyze_with_heuristics(audio_data)

            # Store emotion history
            await self._store_emotion_history(user_id, emotion_profile)

            return emotion_profile

        except Exception as e:
            logger.error(f"Emotion analysis failed: {e}")
            # Return neutral profile on error
            return self._create_neutral_profile()

    async def _analyze_with_librosa(self, audio_data: bytes) -> EmotionProfile:
        """
        Analyze audio using librosa (advanced analysis).

        Args:
            audio_data: Audio file bytes

        Returns:
            EmotionProfile with detailed features
        """
        import io

        # Try to load audio with librosa
        try:
            y, sr = librosa.load(io.BytesIO(audio_data), sr=22050)
        except Exception as e:
            logger.warning(f"Failed to load audio with librosa: {e}, using fallback")
            return await self._analyze_with_heuristics(audio_data)

        # Extract features
        features = self._extract_librosa_features(y, sr)

        # Infer emotion from features
        emotion = self._infer_emotion_from_features(features)

        logger.info(f"Audio analysis complete: {emotion.primary_emotion}")

        return emotion

    def _extract_librosa_features(self, y: "np.ndarray", sr: int) -> AudioFeatures:
        """Extract audio features using librosa."""
        # Pitch analysis using piptrack
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        # Get mean pitch
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_values.append(pitch)

        pitch_mean = float(np.mean(pitch_values)) if pitch_values else 120.0
        pitch_std = float(np.std(pitch_values)) if pitch_values else 20.0

        # Energy/loudness
        energy = np.sqrt(np.mean(y**2))
        energy_db = 20 * np.log10(max(energy, 1e-10))
        energy_mean = float(energy_db)
        energy_std = float(np.std(librosa.feature.melspectrogram(y=y, sr=sr)))

        # Speaking rate estimation (zero crossing rate as proxy)
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        zero_crossing_rate = float(np.mean(zcr))

        # Speaking rate estimate (very rough)
        speaking_rate = zero_crossing_rate * 200  # Arbitrary scaling

        # Pause detection (quiet sections)
        threshold = np.mean(np.abs(y)) * 0.2
        pause_frames = np.abs(y) < threshold
        pause_count = int(np.sum(np.diff(pause_frames.astype(int)) == 1))
        pause_duration = float(np.sum(pause_frames) / sr)

        # MFCC for voice characteristics
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = [float(m) for m in np.mean(mfcc, axis=1)]

        # Vocal tremor (variation in amplitude)
        frame_energy = librosa.feature.rms(y=y)[0]
        tremor = float(np.std(frame_energy) / np.mean(frame_energy)) if np.mean(frame_energy) > 0 else 0.0

        return AudioFeatures(
            pitch_mean=pitch_mean,
            pitch_std=pitch_std,
            energy_mean=energy_mean,
            energy_std=energy_std,
            speaking_rate=speaking_rate,
            pause_count=pause_count,
            pause_duration_total=pause_duration,
            zero_crossing_rate=zero_crossing_rate,
            mfcc_mean=mfcc_mean[:5],  # First 5 MFCCs
            vocal_tremor=min(tremor, 1.0),
        )

    async def _analyze_with_heuristics(self, audio_data: bytes) -> EmotionProfile:
        """
        Analyze audio using basic heuristics (fallback when librosa unavailable).

        Args:
            audio_data: Audio file bytes

        Returns:
            EmotionProfile with basic features
        """
        # Extract basic features from raw audio
        features = self._extract_basic_features(audio_data)

        # Infer emotion from features
        emotion = self._infer_emotion_from_features(features)

        logger.info(f"Basic audio analysis complete: {emotion.primary_emotion}")

        return emotion

    def _extract_basic_features(self, audio_data: bytes) -> AudioFeatures:
        """Extract basic audio features from raw audio bytes."""
        try:
            # Very basic analysis - count amplitude changes
            # This assumes 16-bit PCM audio
            samples = []
            try:
                # Try to extract PCM samples
                for i in range(0, min(len(audio_data) - 1, 10000), 2):
                    sample = struct.unpack("<h", audio_data[i : i + 2])[0]
                    samples.append(sample)
            except Exception:
                # If extraction fails, use byte data
                samples = list(audio_data[:5000])

            if not samples:
                return self._create_default_features()

            samples_arr = [float(s) for s in samples]
            max_val = max(abs(s) for s in samples_arr) if samples_arr else 1.0
            normalized = [s / max(max_val, 1.0) for s in samples_arr]

            # Estimate energy
            energy_mean = float(sum(abs(s) for s in normalized) / len(normalized))
            energy_std = float(
                (sum((abs(s) - energy_mean) ** 2 for s in normalized) / len(normalized)) ** 0.5
            )

            # Estimate zero crossing rate
            zero_crossings = sum(1 for i in range(len(normalized) - 1) if normalized[i] * normalized[i + 1] < 0)
            zcr = zero_crossings / len(normalized)

            # Estimate pitch (very crude - based on zero crossing)
            pitch_mean = zcr * 500  # Arbitrary scaling
            pitch_std = 30.0

            # Estimate pause count
            silence_frames = sum(1 for s in normalized if abs(s) < energy_mean * 0.3)
            pause_count = int(silence_frames / len(normalized) * 10)
            pause_duration = float(silence_frames / len(normalized))

            return AudioFeatures(
                pitch_mean=pitch_mean,
                pitch_std=pitch_std,
                energy_mean=energy_mean * 100,
                energy_std=energy_std * 100,
                speaking_rate=zcr * 150,
                pause_count=max(pause_count, 0),
                pause_duration_total=pause_duration,
                zero_crossing_rate=zcr,
                mfcc_mean=[0.0] * 5,
                vocal_tremor=energy_std,
            )

        except Exception as e:
            logger.warning(f"Failed to extract audio features: {e}")
            return self._create_default_features()

    def _create_default_features(self) -> AudioFeatures:
        """Create default audio features."""
        return AudioFeatures(
            pitch_mean=120.0,
            pitch_std=20.0,
            energy_mean=0.0,
            energy_std=0.0,
            speaking_rate=150.0,
            pause_count=3,
            pause_duration_total=0.5,
            zero_crossing_rate=0.1,
            mfcc_mean=[0.0] * 5,
            vocal_tremor=0.1,
        )

    def _infer_emotion_from_features(self, features: AudioFeatures) -> EmotionProfile:
        """
        Infer emotion from extracted audio features.

        Args:
            features: AudioFeatures object

        Returns:
            EmotionProfile with inferred emotions
        """
        scores = {}

        # Arousal dimension: high energy + high speaking rate + high pitch variation
        arousal = 0.0
        arousal += min(abs(features.energy_mean) / 50, 1.0) * 0.4
        arousal += min(features.speaking_rate / 200, 1.0) * 0.3
        arousal += min(features.pitch_std / 100, 1.0) * 0.3
        arousal = max(-1.0, min(1.0, arousal - 0.5))  # Normalize to -1..1

        # Valence dimension: energy and tremor
        valence = 0.0
        valence += min(abs(features.energy_mean) / 100, 1.0) * 0.5
        if features.vocal_tremor > 0.5:
            valence -= 0.3  # Tremor suggests stress/sadness
        else:
            valence += 0.2
        valence = max(-1.0, min(1.0, valence - 0.5))

        # Dominance/confidence: pitch consistency + speaking rate
        dominance = 0.0
        dominance -= min(features.pitch_std / 200, 1.0) * 0.4  # High variation = uncertain
        dominance += min(features.speaking_rate / 200, 1.0) * 0.6
        dominance = max(-1.0, min(1.0, dominance))

        # Map to emotion categories
        # Calm: low arousal, positive valence
        if arousal < -0.3 and valence > -0.2:
            scores["calm"] = 0.85
            scores["focused"] = 0.4

        # Excited: high arousal, positive valence
        elif arousal > 0.5 and valence > 0.3:
            scores["excited"] = 0.9
            scores["happy"] = 0.6

        # Stressed: high arousal, negative valence
        elif arousal > 0.3 and valence < -0.3:
            scores["stressed"] = 0.85
            scores["frustrated"] = 0.5

        # Sad: low arousal, negative valence
        elif arousal < 0.0 and valence < -0.5:
            scores["sad"] = 0.85
            scores["uncertain"] = 0.3

        # Focused: moderate arousal, high dominance
        elif 0.0 < arousal < 0.5 and dominance > 0.3:
            scores["focused"] = 0.8
            scores["calm"] = 0.3

        # Frustrated: moderate-high arousal, negative valence, low dominance
        elif 0.3 < arousal < 0.7 and valence < -0.1 and dominance < 0.3:
            scores["frustrated"] = 0.8
            scores["stressed"] = 0.4

        # Uncertain: low dominance
        elif dominance < -0.4:
            scores["uncertain"] = 0.8
            scores["calm"] = 0.3

        # Happy: high valence
        elif valence > 0.6:
            scores["happy"] = 0.85
            scores["excited"] = 0.4

        # Default
        if not scores:
            scores["calm"] = 0.5
            scores["focused"] = 0.3

        # Sort by confidence
        sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_emotion = sorted_emotions[0][0]
        primary_confidence = sorted_emotions[0][1]
        secondary = sorted_emotions[1:4]  # Next 3

        return EmotionProfile(
            primary_emotion=primary_emotion,
            confidence=primary_confidence,
            secondary_emotions=secondary,
            arousal=arousal,
            valence=valence,
            dominance=dominance,
            audio_features=features,
            timestamp=datetime.now(timezone.utc),
        )

    def _create_neutral_profile(self) -> EmotionProfile:
        """Create a neutral emotion profile (for errors)."""
        features = self._create_default_features()
        return EmotionProfile(
            primary_emotion="calm",
            confidence=0.5,
            secondary_emotions=[("focused", 0.3)],
            arousal=0.0,
            valence=0.0,
            dominance=0.0,
            audio_features=features,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_adaptation_prompt(self, emotion_profile: EmotionProfile) -> str:
        """
        Generate a system prompt addition based on emotional profile.

        This prompt is meant to be appended to Cipher's system prompt to guide
        response generation based on the detected emotional state.

        Args:
            emotion_profile: EmotionProfile from audio analysis

        Returns:
            String to be appended to system prompt
        """
        emotion = emotion_profile.primary_emotion
        confidence = emotion_profile.confidence

        # Confidence threshold
        if confidence < 0.4:
            return "The user's emotional state is unclear. Respond with clear, neutral professionalism while being open to their needs."

        # Emotion-specific adaptations
        adaptations = {
            "calm": "The user sounds calm and composed. Maintain professional clarity with measured detail. Avoid unnecessary urgency.",
            "excited": "The user sounds energized and enthusiastic. Match their energy with crisp, impactful responses. Capitalize on their momentum.",
            "stressed": "The user sounds stressed or under pressure. Respond with extra clarity and conciseness. Cut to the core issue. Acknowledge the weight, then focus on solutions.",
            "sad": "The user sounds down or discouraged. Lead with warmth and empathy before pivoting to constructive action. Avoid toxic positivity.",
            "focused": "The user sounds intensely focused. Deliver substance and detail. They're ready for depth. No small talk.",
            "frustrated": "The user sounds frustrated. Validate the frustration briefly, then pivot decisively to solutions. Be problem-focused, not commiserative.",
            "happy": "The user sounds genuinely pleased. You can afford more personality and light humor. Sustain their positive momentum.",
            "uncertain": "The user sounds uncertain or hesitant. Provide clear, confident guidance with explicit next steps. Reduce ambiguity.",
        }

        base_prompt = adaptations.get(emotion, "Respond appropriately to the user's needs.")

        if len(emotion_profile.secondary_emotions) > 0:
            secondary_emotion, secondary_conf = emotion_profile.secondary_emotions[0]
            if secondary_conf > 0.4:
                secondary_prompt = adaptations.get(secondary_emotion, "")
                if secondary_prompt:
                    base_prompt += f" The user may also be {secondary_emotion}."

        return base_prompt

    async def _store_emotion_history(self, user_id: str, emotion_profile: EmotionProfile) -> None:
        """
        Store emotion history for longitudinal tracking.

        Args:
            user_id: User identifier
            emotion_profile: EmotionProfile to store
        """
        try:
            user_emotion_dir = self.emotion_history_dir / user_id
            user_emotion_dir.mkdir(parents=True, exist_ok=True)

            # Store as JSON
            timestamp = emotion_profile.timestamp.isoformat()
            filename = f"{timestamp.replace(':', '-')}.json"

            data = {
                "timestamp": timestamp,
                "primary_emotion": emotion_profile.primary_emotion,
                "confidence": emotion_profile.confidence,
                "secondary_emotions": emotion_profile.secondary_emotions,
                "arousal": emotion_profile.arousal,
                "valence": emotion_profile.valence,
                "dominance": emotion_profile.dominance,
                "audio_features": asdict(emotion_profile.audio_features),
            }

            filepath = user_emotion_dir / filename
            filepath.write_text(json.dumps(data, indent=2))
            logger.debug(f"Stored emotion history: {filepath}")

        except Exception as e:
            logger.warning(f"Failed to store emotion history: {e}")

    async def get_emotion_history(self, user_id: str, limit: int = 100) -> list[dict]:
        """
        Get emotion history for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of records to return

        Returns:
            List of emotion profiles (most recent first)
        """
        try:
            user_emotion_dir = self.emotion_history_dir / user_id
            if not user_emotion_dir.exists():
                return []

            files = sorted(user_emotion_dir.glob("*.json"), reverse=True)[:limit]
            history = []

            for filepath in files:
                try:
                    data = json.loads(filepath.read_text())
                    history.append(data)
                except Exception as e:
                    logger.warning(f"Failed to read emotion file {filepath}: {e}")

            return history

        except Exception as e:
            logger.warning(f"Failed to get emotion history: {e}")
            return []


# Singleton instance
_emotion_service: Optional[EmotionService] = None


async def get_emotion_service() -> EmotionService:
    """Get or create the emotion service singleton."""
    global _emotion_service
    if _emotion_service is None:
        _emotion_service = EmotionService()
    return _emotion_service
