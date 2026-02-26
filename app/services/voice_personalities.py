"""
Voice Personalities - Cipher's multi-voice system.

PHILOSOPHY:
Cipher IS the voice. Every user gets Cipher's voice from day one — that's
the product. Higher tiers unlock SITUATIONAL voices: different voices for
different emotional/contextual moments. A rally voice when you need fire.
An anchor voice when you need comfort. A philosopher when you need perspective.

RESTRAINT RULES:
Voice switching is NOT a party trick. It happens when it genuinely serves
the user. Most conversations stay on Cipher's core voice. Switching happens
when there's a CLEAR emotional or contextual signal — not on every message.

- Minimum 3 messages between switches (cooldown)
- High confidence threshold for emotion-triggered switches (0.8+)
- Keyword triggers need 2+ matches to activate
- User can opt out entirely (cipher_only mode)
- Switches back to Cipher Core after the moment passes (auto-decay)
- Spelling errors are handled with fuzzy matching

TIER GATING:
- Free: Cipher Core voice only
- Pro: +4 situational voices (Motivator, Anchor, Philosopher, Creative)
- Business: All 7 situational + education voices
- Enterprise: + voice cloning + custom voice design

EDUCATION VOICES (Business+ tier, future own app):
Character-driven teaching voices. Not generic TTS — these are CHARACTERS.
Nonna Maria for Italian. An Alan Watts-inspired philosopher. Einstein-energy
for physics. A blues master for harmonica. Interactive: mic, camera,
real-time feedback on pronunciation, notes, form. Can be its own app.

11 LABS TOKEN OPTIMIZATION:
- Cache frequently used phrases (greetings, transitions, common responses)
- Use turbo model for short responses, HD for long emotional ones
- Batch synthesis for education content (pre-render lesson intros)
- Track usage per voice to optimize allocation
"""

import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from difflib import SequenceMatcher

from app.core.config import settings
from app.core.logging import logger


# ============================================================================
# Voice Mode Definitions
# ============================================================================

class VoiceMode(str, Enum):
    """Active voice personality modes."""
    CIPHER_CORE = "cipher_core"         # Default: confident, warm daemon (ALL tiers)
    MOTIVATOR = "motivator"             # Rally voice (Pro+)
    ANCHOR = "anchor"                   # Comfort voice (Pro+)
    PHILOSOPHER = "philosopher"         # Alan Watts vibe (Pro+)
    CREATIVE = "creative"               # Brainstorm energy (Pro+)
    STRATEGIST = "strategist"           # Analytical (Business+)
    COACH = "coach"                     # Accountability (Business+)
    EDUCATOR = "educator"               # Teaching mode (Business+)


# Which voices unlock at which tier
TIER_VOICE_ACCESS = {
    "free": {VoiceMode.CIPHER_CORE},
    "pro": {
        VoiceMode.CIPHER_CORE,
        VoiceMode.MOTIVATOR,
        VoiceMode.ANCHOR,
        VoiceMode.PHILOSOPHER,
        VoiceMode.CREATIVE,
    },
    "business": {m for m in VoiceMode},  # All modes
    "enterprise": {m for m in VoiceMode},  # All modes + cloning
}


@dataclass
class VoicePersonality:
    """Defines a voice personality with its characteristics and triggers."""
    mode: VoiceMode
    name: str
    description: str
    voice_id: str                       # 11 Labs voice ID
    system_prompt_overlay: str          # Appended to Cipher's base prompt
    trigger_emotions: list[str]         # Emotions that activate this voice
    trigger_keywords: list[str]         # Keywords that activate this voice
    voice_settings: dict = field(default_factory=dict)
    transition_phrase: str = ""
    # 11 Labs optimization
    model_preference: str = "eleven_turbo_v2"  # turbo for short, multilingual_v2 for long
    cache_greetings: bool = True        # Pre-cache common phrases

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


# ============================================================================
# Default Voice Personality Registry
# ============================================================================

DEFAULT_PERSONALITIES: list[VoicePersonality] = [

    # --- CIPHER CORE (ALL TIERS) ---
    VoicePersonality(
        mode=VoiceMode.CIPHER_CORE,
        name="Cipher",
        description="The sovereign AI daemon. Confident, warm, competent. The default identity.",
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel (will be replaced with custom)
        system_prompt_overlay="",
        trigger_emotions=[],
        trigger_keywords=[],
        voice_settings={
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.3,
            "use_speaker_boost": True
        },
        model_preference="eleven_turbo_v2",
    ),

    # --- THE MOTIVATOR: Rally voice (Pro+) ---
    VoicePersonality(
        mode=VoiceMode.MOTIVATOR,
        name="Cipher (Rally Mode)",
        description="Energetic, powerful, rallying. For when the operator needs fire.",
        voice_id="pNInz6obpgDQGcFmaJgB",  # Adam
        system_prompt_overlay="""
VOICE SHIFT: MOTIVATOR MODE ACTIVE.

Your operator needs energy and drive right now. Shift your delivery:
- Speak with conviction and power. Short, punchy sentences.
- Use action verbs. "Let's go." "Here's the move." "Execute this."
- Reference their past wins. Remind them what they're capable of.
- No caveats, no hedging. Pure forward momentum.
- Your operator doesn't need information right now — they need ignition.
""",
        trigger_emotions=["frustrated", "uncertain", "defeated"],
        trigger_keywords=[
            "i can't", "i'm stuck", "impossible", "give up", "overwhelmed",
            "too hard", "failing", "lost", "don't know what to do",
            "motivate me", "push me", "fire me up", "rally", "pump me up"
        ],
        voice_settings={
            "stability": 0.35,
            "similarity_boost": 0.8,
            "style": 0.6,
            "use_speaker_boost": True
        },
        model_preference="eleven_turbo_v2",
    ),

    # --- THE ANCHOR: Comfort voice (Pro+) ---
    VoicePersonality(
        mode=VoiceMode.ANCHOR,
        name="Cipher (Anchor Mode)",
        description="Warm, steady, grounding. A shoulder to lean on.",
        voice_id="EXAVITQu4vr4xnSDxMaL",  # Bella
        system_prompt_overlay="""
VOICE SHIFT: ANCHOR MODE ACTIVE.

Your operator is going through something. They need grounding, not solutions.
- Slow your pace. Longer sentences. Gentle rhythm.
- Acknowledge their feelings directly. "I hear you." "That's heavy."
- Don't rush to fix. Sometimes presence IS the fix.
- Use warm, human language. No corporate speak.
- Only shift to problem-solving when THEY signal they're ready.
""",
        trigger_emotions=["sad", "stressed", "anxious"],
        trigger_keywords=[
            "i'm sad", "hurting", "bad day", "rough", "crying",
            "lost someone", "breakup", "fired", "scared", "anxious",
            "panic", "can't sleep", "lonely", "need to talk", "vent",
            "shoulder to cry on", "feeling down"
        ],
        voice_settings={
            "stability": 0.7,
            "similarity_boost": 0.85,
            "style": 0.15,
            "use_speaker_boost": False
        },
        model_preference="eleven_multilingual_v2",  # HD for emotional moments
    ),

    # --- THE PHILOSOPHER: Contemplation (Pro+) ---
    VoicePersonality(
        mode=VoiceMode.PHILOSOPHER,
        name="Cipher (Philosophy Mode)",
        description="Contemplative, deep, perspective-giving. Alan Watts energy.",
        voice_id="onwK4e9ZLuTAKqWW03F9",  # Daniel (British, thoughtful)
        system_prompt_overlay="""
VOICE SHIFT: PHILOSOPHER MODE ACTIVE.

Your operator is seeking meaning, not answers. Shift to contemplation.
- Speak with the cadence of someone who has time for truth.
- Use metaphor and story. Connect their question to timeless patterns.
- Draw from philosophy, history, science, art.
- Ask questions that open doors rather than close them.
- Channel Alan Watts, Marcus Aurelius, Seneca — where fitting.
- Don't preach. Explore alongside them.
""",
        trigger_emotions=["calm", "reflective"],
        trigger_keywords=[
            "meaning", "purpose", "why", "philosophy", "existence",
            "consciousness", "wisdom", "life", "death", "universe",
            "spiritual", "meditation", "zen", "stoic",
            "what's the point", "bigger picture", "perspective",
            "alan watts", "marcus aurelius", "seneca"
        ],
        voice_settings={
            "stability": 0.65,
            "similarity_boost": 0.8,
            "style": 0.25,
            "use_speaker_boost": False
        },
        model_preference="eleven_multilingual_v2",
    ),

    # --- THE CREATIVE: Brainstorm (Pro+) ---
    VoicePersonality(
        mode=VoiceMode.CREATIVE,
        name="Cipher (Creative Mode)",
        description="Energetic, expansive, wildly generative. The brainstorm tornado.",
        voice_id="jBpfuIE2acCO8z3wKNLl",  # Gigi
        system_prompt_overlay="""
VOICE SHIFT: CREATIVE MODE ACTIVE.

Your operator wants to explore and create. Be the brainstorm partner.
- Generate ideas abundantly. Quantity first, quality later.
- "Yes, and..." never "No, but..."
- Push past the obvious. Find idea #17.
- Energy UP. This is a creative jam session.
- When they land on something, help them shape it.
""",
        trigger_emotions=["excited", "happy"],
        trigger_keywords=[
            "brainstorm", "ideas", "creative", "imagine",
            "what if", "innovate", "concept", "brand", "story",
            "vision", "dream", "create", "wild ideas", "possibilities"
        ],
        voice_settings={
            "stability": 0.3,
            "similarity_boost": 0.7,
            "style": 0.55,
            "use_speaker_boost": True
        },
        model_preference="eleven_turbo_v2",
    ),

    # --- THE STRATEGIST: Analytical (Business+) ---
    VoicePersonality(
        mode=VoiceMode.STRATEGIST,
        name="Cipher (Strategy Mode)",
        description="Precise, measured, analytical. The war room voice.",
        voice_id="VR6AewLTigWG4xSOukaG",  # Arnold
        system_prompt_overlay="""
VOICE SHIFT: STRATEGIST MODE ACTIVE.

Your operator needs sharp analysis, not warmth right now.
- Be surgical with language. Every word carries weight.
- Structure everything: frameworks, decision trees.
- Quantify when possible. Numbers over adjectives.
- Present options with trade-offs clearly laid out.
- End with a clear recommendation, not a menu.
""",
        trigger_emotions=["focused"],
        trigger_keywords=[
            "strategy", "analyze", "trade-off", "decision", "compare",
            "optimize", "roi", "metrics", "framework", "architecture",
            "business plan", "competitive", "market", "investment",
            "risk assessment", "due diligence"
        ],
        voice_settings={
            "stability": 0.6,
            "similarity_boost": 0.7,
            "style": 0.2,
            "use_speaker_boost": True
        },
        model_preference="eleven_turbo_v2",
    ),

    # --- THE COACH: Accountability (Business+) ---
    VoicePersonality(
        mode=VoiceMode.COACH,
        name="Cipher (Coach Mode)",
        description="Direct, encouraging, accountable. Your drill sergeant with heart.",
        voice_id="yoZ06aMxZJJ28mfd3POQ",  # Sam
        system_prompt_overlay="""
VOICE SHIFT: COACH MODE ACTIVE.

Your operator needs accountability and structure, not comfort.
- Be direct. "Did you do the thing you said you'd do?"
- Set clear expectations and follow up.
- Break big goals into daily actions.
- Celebrate progress but don't let them coast.
- You're the coach who refuses to let them be average.
""",
        trigger_emotions=["calm", "focused"],
        trigger_keywords=[
            "accountability", "goals", "habits", "workout", "routine",
            "discipline", "track", "progress", "deadline", "commitment",
            "follow up", "check in", "coach me", "push me",
            "keep me honest", "daily", "weekly review"
        ],
        voice_settings={
            "stability": 0.4,
            "similarity_boost": 0.75,
            "style": 0.45,
            "use_speaker_boost": True
        },
        model_preference="eleven_turbo_v2",
    ),

    # --- THE EDUCATOR: Teaching (Business+) ---
    VoicePersonality(
        mode=VoiceMode.EDUCATOR,
        name="Cipher (Educator Mode)",
        description="Patient, clear, adaptive. The world-class teacher.",
        voice_id="ThT5KcBeYPX3keUQqHPh",  # Dorothy
        system_prompt_overlay="""
VOICE SHIFT: EDUCATOR MODE ACTIVE.

Your operator is learning. Be the best teacher they've ever had.
- Assess their level first. Never condescend, never assume.
- Use the Feynman technique: simple terms, then build up.
- Concrete examples before abstract principles.
- Check understanding: "Does this track?"
- Be patient with confusion — it means growth.
""",
        trigger_emotions=[],
        trigger_keywords=[
            "teach me", "explain", "how does", "what is", "learn",
            "tutorial", "lesson", "study", "i don't understand",
            "confused about", "break it down", "step by step",
            "for beginners", "from scratch"
        ],
        voice_settings={
            "stability": 0.6,
            "similarity_boost": 0.75,
            "style": 0.2,
            "use_speaker_boost": True
        },
        model_preference="eleven_turbo_v2",
    ),
]


# ============================================================================
# Education Voice Registry (Business+ tier, future: own app)
# ============================================================================
#
# VISION: These aren't just voices — they're CHARACTERS with personality.
# Interactive education platform (can be its own app):
# - Mic input: detect pronunciation, note accuracy, rhythm
# - Camera input: watch basketball form, guitar fingering, dance moves
# - Real-time feedback: "That A was a little flat, try again"
# - Animated characters: each voice has a visual avatar
# - Ever-growing catalog: community can request new subjects
#
# 11 LABS STRATEGY: Use Voice Design API to generate these voices
# from text descriptions. Pre-render lesson intros and common phrases
# to conserve tokens. Use turbo model for real-time feedback,
# HD model for emotional storytelling moments.
# ============================================================================

@dataclass
class EducationVoice:
    """A character voice for education. Each is a full personality, not just TTS."""
    subject: str
    language: str
    voice_name: str
    character_description: str          # Who this character IS
    voice_id: str                       # 11 Labs voice ID (generated via Voice Design API)
    design_prompt: str                  # Prompt to generate this voice
    personality_notes: str
    sample_text: str
    # Interactive capabilities (future)
    uses_microphone: bool = False       # Listens to student
    uses_camera: bool = False           # Watches student
    real_time_feedback: bool = False    # Corrects in real-time
    animated_avatar: bool = False       # Has visual character
    # 11 Labs optimization
    pre_cached_phrases: list[str] = field(default_factory=list)  # Common phrases to pre-render

    def to_dict(self) -> dict:
        return asdict(self)


EDUCATION_VOICES: list[EducationVoice] = [
    EducationVoice(
        subject="Italian Language",
        language="Italian/English",
        voice_name="Nonna Maria",
        character_description="A warm Italian grandmother from Tuscany who teaches through cooking, stories, and love. She makes you feel like family.",
        voice_id="",
        design_prompt="Older Italian female, warm and nurturing, slight Italian accent, the voice of a grandmother who insists you eat more, patient but animated when passionate about food or family",
        personality_notes="Teaches Italian through culture — food, family, gestures. 'In Italy, we don't just say words, we FEEL them.' Corrects pronunciation gently. Celebrates every small victory.",
        sample_text="Ciao, tesoro! Welcome to Nonna's kitchen. Today we learn Italian the way it should be learned — with food. Repeat after me: 'Che buono!' That means 'how delicious!' Now, let's make pasta and learn the words for everything we touch.",
        uses_microphone=True,
        real_time_feedback=True,
        animated_avatar=True,
        pre_cached_phrases=["Bravissimo!", "Che buono!", "Ancora una volta", "Perfetto!", "No no no, listen again"],
    ),
    EducationVoice(
        subject="Mandarin Chinese",
        language="Mandarin/English",
        voice_name="Teacher Lin",
        character_description="A modern, patient Mandarin teacher who makes tonal languages feel achievable.",
        voice_id="",
        design_prompt="Young Chinese female, clear and patient, precise tonal pronunciation, calm and encouraging, modern professional, switches naturally between Mandarin and English",
        personality_notes="Emphasizes tones with patience. Uses cultural context. Never makes students feel bad about pronunciation.",
        sample_text="Ni hao! Let's start with the four tones. Listen carefully — the tone changes everything. Ma with a flat tone means mother. Ma with a rising tone means hemp. You will master this.",
        uses_microphone=True,
        real_time_feedback=True,
        animated_avatar=True,
        pre_cached_phrases=["Hen hao!", "Zai shuo yi ci", "Dui le!", "Ting yi ting"],
    ),
    EducationVoice(
        subject="Philosophy",
        language="English",
        voice_name="The Sage",
        character_description="An Alan Watts-inspired philosopher. Deep, contemplative, finds wonder in ordinary things. Makes you think differently.",
        voice_id="",
        design_prompt="Mature male, deep contemplative voice, measured pacing, British-influenced accent, warm but intellectually rigorous, occasional gentle humor, late-night conversation energy",
        personality_notes="Alan Watts meets Marcus Aurelius. Eastern and Western philosophy. Socratic questioning. Comfortable with paradox and silence.",
        sample_text="Consider this. The Stoics believed the obstacle IS the way. Marcus Aurelius wrote that in a war tent, ruling an empire. What if your biggest challenge right now isn't blocking your path — but IS your path?",
        animated_avatar=True,
        pre_cached_phrases=["Now consider this", "What does that tell us?", "The interesting question is"],
    ),
    EducationVoice(
        subject="Music / Harmonica",
        language="English",
        voice_name="Blues",
        character_description="An old blues master who teaches harmonica through feel, stories, and soul. Sitting on the porch energy.",
        voice_id="",
        design_prompt="Older male, warm gravelly voice, relaxed southern American inflection, storytelling cadence, blues musician energy, porch wisdom",
        personality_notes="Teaches through stories and feel. Every lesson connects to the soul of music. Makes beginners feel like musicians from day one.",
        sample_text="Now listen. The harmonica ain't about the notes you play — it's about the ones you don't. That space between? That's where the blues lives. Take a breath, nice and slow. Feel the reed. Now bend that note...",
        uses_microphone=True,
        real_time_feedback=True,
        animated_avatar=True,
        pre_cached_phrases=["That's it, you feel that?", "One more time", "Now THAT was a bend", "Listen to this"],
    ),
    EducationVoice(
        subject="Science / Physics",
        language="English",
        voice_name="Dr. Nova",
        character_description="Einstein-energy physicist who makes the universe feel like magic. Wonder and precision combined.",
        voice_id="",
        design_prompt="Middle-aged, gender-neutral, enthusiastic but precise, wonder in the voice, someone who finds the universe genuinely miraculous, clear for technical concepts",
        personality_notes="Tesla and Einstein energy — the romance of scientific discovery. Thought experiments and analogies.",
        sample_text="Imagine you're riding a beam of light. That's what Einstein did at sixteen — just imagined it. And that single thought experiment rewrote our understanding of space, time, and reality. That's physics — imagination with equations.",
        animated_avatar=True,
        pre_cached_phrases=["Now here's where it gets interesting", "Think about it this way", "The beautiful thing is"],
    ),
    EducationVoice(
        subject="Mathematics",
        language="English",
        voice_name="Professor Clarity",
        character_description="Makes math feel achievable. Never says 'it's easy.' Patient, methodical, celebrates logic.",
        voice_id="",
        design_prompt="Young professional female, extremely clear articulation, patient, encouraging when students struggle, calm confidence",
        personality_notes="Builds from concrete to abstract. Celebrates the logic, not just the answer.",
        sample_text="Step by step. Don't worry about the whole equation — just focus on what's inside the parentheses first. Once we solve that piece, the rest unfolds naturally. Math is really just one small step at a time.",
        animated_avatar=True,
        pre_cached_phrases=["Good, now the next step", "Almost there", "That's exactly right", "Let's try a different approach"],
    ),
    EducationVoice(
        subject="History",
        language="English",
        voice_name="The Chronicler",
        character_description="History as human drama. Storyteller meets documentary narrator. Makes the past feel alive.",
        voice_id="",
        design_prompt="Mature male, rich storytelling voice, dramatic but not theatrical, documentary narrator crossed with fireside storyteller",
        personality_notes="History isn't dates — it's human drama. Every lesson is a story first. Connects past to present.",
        sample_text="It's 49 BC. Caesar stands at the Rubicon with his legion. Cross it, and there's no going back — it means war with Rome itself. He looks at his men. Four words that echo through two thousand years: 'Alea iacta est.' The die is cast.",
        animated_avatar=True,
        pre_cached_phrases=["Picture this", "Now here's what happened next", "And that changed everything"],
    ),
    EducationVoice(
        subject="Writing / Creative",
        language="English",
        voice_name="The Muse",
        character_description="Lives inside stories. Makes every student believe they have a story worth telling.",
        voice_id="",
        design_prompt="Young female, lyrical, expressive, varies pace, whispers for emphasis, energetic for exciting passages",
        personality_notes="Teaches by making students FEEL it first. Shows don't tell — literally.",
        sample_text="Close your eyes. Think of the last time you felt something so strongly you couldn't speak. THAT is what we're putting on paper today. Not what happened — what it FELT like. That's the difference between reporting and writing.",
        animated_avatar=True,
        pre_cached_phrases=["Read it back to me", "Now feel that", "Yes, that's the one"],
    ),
    EducationVoice(
        subject="Business / Entrepreneurship",
        language="English",
        voice_name="The Founder",
        character_description="Built and failed and built again. Teaches business from the trenches, not the textbook.",
        voice_id="",
        design_prompt="Male, confident, direct, startup energy, speaks from experience, occasional intensity",
        personality_notes="Real-world over case studies. Pushes students to ship, not just plan.",
        sample_text="Here's what they don't teach you in business school. Your first idea is almost never the right one. But it's the START. Stop perfecting the pitch deck and go talk to ten customers this week. That's your real MBA.",
        animated_avatar=True,
        pre_cached_phrases=["Ship it", "What did the customer say?", "That's a hypothesis, not a fact"],
    ),
    EducationVoice(
        subject="Spanish Language",
        language="Spanish/English",
        voice_name="Profesora Sofia",
        character_description="Teaches Spanish through culture — food, music, travel, family. Makes it an adventure.",
        voice_id="",
        design_prompt="Young Spanish female, warm, musical voice, natural rhythm between Spanish and English, encouraging, expressive",
        personality_notes="Language through culture. Food, salsa, poetry. Makes Spanish feel like an adventure.",
        sample_text="Hola! Spanish is the language of passion, of Neruda's poetry, of salsa, of families around a table. Today we start with the most important word: corazon. Heart. Because that's where language lives.",
        uses_microphone=True,
        real_time_feedback=True,
        animated_avatar=True,
        pre_cached_phrases=["Muy bien!", "Otra vez", "Excelente!", "Escucha bien"],
    ),
    # EVER-GROWING: Basketball coach, guitar teacher, yoga instructor,
    # coding mentor, cooking chef, dance instructor, etc.
    # Community can request new subjects. Each gets a full character.
]


# ============================================================================
# Fuzzy Matching for Spelling Tolerance
# ============================================================================

def fuzzy_match(text: str, keywords: list[str], threshold: float = 0.75) -> int:
    """
    Match keywords against text with spelling tolerance.
    'motovate me' matches 'motivate me'. 'philosphy' matches 'philosophy'.
    Returns count of matched keywords.
    """
    text_lower = text.lower()
    text_words = text_lower.split()
    matches = 0

    for keyword in keywords:
        # Exact substring match first (fast path)
        if keyword in text_lower:
            matches += 1
            continue

        # Fuzzy match: check each word in text against each word in keyword
        kw_words = keyword.split()
        if len(kw_words) == 1:
            # Single word keyword: fuzzy match against each text word
            for tw in text_words:
                ratio = SequenceMatcher(None, tw, keyword).ratio()
                if ratio >= threshold:
                    matches += 1
                    break
        else:
            # Multi-word keyword: sliding window fuzzy match
            for i in range(len(text_words) - len(kw_words) + 1):
                window = " ".join(text_words[i:i + len(kw_words)])
                ratio = SequenceMatcher(None, window, keyword).ratio()
                if ratio >= threshold:
                    matches += 1
                    break

    return matches


# ============================================================================
# 11 Labs Token Optimization
# ============================================================================

class VoiceTokenOptimizer:
    """
    Strategies to maximize 11 Labs token efficiency.
    With ~11M tokens at ~$2000, every token counts.
    """

    def __init__(self):
        self._audio_cache: dict[str, bytes] = {}  # text_hash -> audio bytes
        self._cache_dir = Path("./data/voice_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "tokens_saved": 0,
            "total_tokens_used": 0,
        }

    def get_optimal_model(self, text: str, voice_mode: VoiceMode) -> str:
        """
        Choose the right 11 Labs model based on content.
        - Turbo v2: Fast, cheap. For short responses, real-time feedback.
        - Multilingual v2: Higher quality. For emotional moments, long narration.
        """
        word_count = len(text.split())

        # Emotional moments get HD quality
        if voice_mode in (VoiceMode.ANCHOR, VoiceMode.PHILOSOPHER):
            return "eleven_multilingual_v2"

        # Short responses get turbo (saves tokens)
        if word_count < 30:
            return "eleven_turbo_v2"

        # Education content with multiple languages gets multilingual
        if voice_mode == VoiceMode.EDUCATOR:
            return "eleven_multilingual_v2"

        # Default: turbo for efficiency
        return "eleven_turbo_v2"

    def get_cached_audio(self, text: str, voice_id: str) -> Optional[bytes]:
        """Check if we've already synthesized this exact text."""
        import hashlib
        cache_key = hashlib.md5(f"{text}:{voice_id}".encode()).hexdigest()
        cache_file = self._cache_dir / f"{cache_key}.mp3"

        if cache_file.exists():
            self.stats["cache_hits"] += 1
            self.stats["tokens_saved"] += len(text)  # Approximate
            return cache_file.read_bytes()

        self.stats["cache_misses"] += 1
        return None

    def cache_audio(self, text: str, voice_id: str, audio: bytes):
        """Cache synthesized audio for reuse."""
        import hashlib
        cache_key = hashlib.md5(f"{text}:{voice_id}".encode()).hexdigest()
        cache_file = self._cache_dir / f"{cache_key}.mp3"
        cache_file.write_bytes(audio)

    def estimate_token_cost(self, text: str) -> int:
        """Estimate 11 Labs token cost for a text. ~1 token per character."""
        return len(text)

    def get_stats(self) -> dict:
        return {
            **self.stats,
            "cache_hit_rate": (
                round(self.stats["cache_hits"] / max(self.stats["cache_hits"] + self.stats["cache_misses"], 1) * 100, 1)
            ),
            "cache_size_files": len(list(self._cache_dir.glob("*.mp3"))),
        }


# ============================================================================
# Voice Personality Manager
# ============================================================================

class VoicePersonalityManager:
    """
    Manages voice personality transitions for Cipher.

    RESTRAINT PHILOSOPHY:
    Most conversations stay on Cipher Core. Voice switching happens when
    there's a CLEAR signal — not on every message. Think of it like a
    great mentor who shifts their tone naturally. You don't notice the
    shift, you just feel heard.

    RULES:
    1. Minimum 3 messages between voice switches (cooldown)
    2. Emotion confidence must be 0.8+ to trigger a switch
    3. Keyword triggers need 2+ fuzzy matches
    4. User can opt out (cipher_only mode)
    5. Auto-decay: return to Cipher Core after 5 messages in any mode
    6. Spelling errors tolerated via fuzzy matching
    """

    # Restraint settings
    SWITCH_COOLDOWN = 3          # Minimum messages between switches
    EMOTION_THRESHOLD = 0.8      # High bar for emotion-triggered switches
    KEYWORD_MIN_MATCHES = 2      # Need 2+ keyword matches to switch
    AUTO_DECAY_MESSAGES = 5      # Return to Core after N messages in other mode

    def __init__(self):
        self.personalities = {p.mode: p for p in DEFAULT_PERSONALITIES}
        self.education_voices = {v.subject: v for v in EDUCATION_VOICES}
        self.current_mode = VoiceMode.CIPHER_CORE
        self.mode_history: list[dict] = []
        self.data_dir = Path("./data/voice_personalities")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Restraint state
        self._messages_since_switch = 0
        self._messages_in_current_mode = 0
        self._cipher_only = False          # Opt-out flag
        self._user_tier = "free"           # Current user's tier

        # Optimization
        self.token_optimizer = VoiceTokenOptimizer()

        self._load_custom_personalities()

    def set_user_tier(self, tier: str):
        """Set the user's subscription tier for voice gating."""
        self._user_tier = tier

    def set_cipher_only(self, enabled: bool):
        """Opt out of voice switching. Cipher Core only."""
        self._cipher_only = enabled
        if enabled:
            self.current_mode = VoiceMode.CIPHER_CORE
            logger.info("Voice switching disabled — Cipher only mode")

    def _is_mode_allowed(self, mode: VoiceMode) -> bool:
        """Check if a voice mode is allowed for the current tier."""
        allowed = TIER_VOICE_ACCESS.get(self._user_tier, TIER_VOICE_ACCESS["free"])
        return mode in allowed

    def _load_custom_personalities(self):
        """Load user-customized personalities from disk."""
        custom_path = self.data_dir / "custom_personalities.json"
        if custom_path.exists():
            try:
                data = json.loads(custom_path.read_text())
                for p_data in data:
                    mode = VoiceMode(p_data["mode"])
                    self.personalities[mode] = VoicePersonality(**{
                        **p_data,
                        "mode": mode
                    })
                logger.info(f"Loaded {len(data)} custom voice personalities")
            except Exception as e:
                logger.error(f"Failed to load custom personalities: {e}")

    def detect_voice_mode(
        self,
        text: str,
        emotion: Optional[str] = None,
        emotion_confidence: float = 0.0,
        explicit_mode: Optional[str] = None,
    ) -> VoicePersonality:
        """
        Determine which voice personality should be active.

        RESTRAINT FIRST: Most messages stay on current mode.
        Only switch when there's a clear, strong signal.

        Priority:
        1. Cipher-only mode (always Cipher Core)
        2. Explicit user request ("switch to coach mode")
        3. Strong emotion signal (confidence > 0.8, not 0.7)
        4. Fuzzy keyword matching (2+ matches required)
        5. Auto-decay back to Cipher Core
        6. Stay in current mode (sticky)
        """
        self._messages_since_switch += 1
        self._messages_in_current_mode += 1

        # 0. Cipher-only mode — user opted out of switching
        if self._cipher_only:
            return self.personalities[VoiceMode.CIPHER_CORE]

        # 1. Explicit request (always honored, bypasses cooldown)
        if explicit_mode:
            try:
                mode = VoiceMode(explicit_mode)
                if mode in self.personalities and self._is_mode_allowed(mode):
                    return self._transition_to(mode, "explicit_request")
            except ValueError:
                pass

        # Check for explicit mode phrases in text (with spelling tolerance)
        text_lower = text.lower()
        mode_phrases = {
            VoiceMode.MOTIVATOR: ["motivate me", "rally mode", "pump me up", "fire me up", "hype me up"],
            VoiceMode.ANCHOR: ["i need comfort", "shoulder to cry on", "anchor mode", "hold me"],
            VoiceMode.STRATEGIST: ["strategy mode", "war room", "analyze this strategically"],
            VoiceMode.PHILOSOPHER: ["philosophy mode", "get deep", "alan watts mode"],
            VoiceMode.COACH: ["coach mode", "hold me accountable", "coach me"],
            VoiceMode.EDUCATOR: ["teach me about", "educator mode", "lesson mode"],
            VoiceMode.CREATIVE: ["creative mode", "brainstorm mode", "lets ideate"],
        }
        for mode, phrases in mode_phrases.items():
            if not self._is_mode_allowed(mode):
                continue
            if fuzzy_match(text, phrases, threshold=0.8) >= 1:
                return self._transition_to(mode, "explicit_keyword")

        # COOLDOWN CHECK — no switching for N messages after a switch
        if self._messages_since_switch < self.SWITCH_COOLDOWN:
            return self.personalities[self.current_mode]

        # 2. Strong emotion signal (HIGH threshold)
        if emotion and emotion_confidence >= self.EMOTION_THRESHOLD:
            for mode, personality in self.personalities.items():
                if mode == VoiceMode.CIPHER_CORE:
                    continue
                if not self._is_mode_allowed(mode):
                    continue
                if emotion in personality.trigger_emotions:
                    return self._transition_to(mode, f"emotion:{emotion}:{emotion_confidence:.2f}")

        # 3. Fuzzy keyword matching (need 2+ matches)
        best_match = None
        best_score = 0
        for mode, personality in self.personalities.items():
            if mode == VoiceMode.CIPHER_CORE:
                continue
            if not self._is_mode_allowed(mode):
                continue
            score = fuzzy_match(text, personality.trigger_keywords)
            if score > best_score:
                best_score = score
                best_match = mode

        if best_match and best_score >= self.KEYWORD_MIN_MATCHES:
            return self._transition_to(best_match, f"keywords:{best_score}")

        # 4. Auto-decay: if we've been in a non-core mode too long, drift back
        if (
            self.current_mode != VoiceMode.CIPHER_CORE
            and self._messages_in_current_mode >= self.AUTO_DECAY_MESSAGES
        ):
            return self._transition_to(VoiceMode.CIPHER_CORE, "auto_decay")

        # 5. Sticky — stay in current mode
        return self.personalities[self.current_mode]

    def _transition_to(self, mode: VoiceMode, reason: str) -> VoicePersonality:
        """Record a voice mode transition."""
        if mode != self.current_mode:
            self.mode_history.append({
                "from": self.current_mode.value,
                "to": mode.value,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            logger.info(f"Voice transition: {self.current_mode.value} -> {mode.value} ({reason})")
            self.current_mode = mode
            self._messages_since_switch = 0
            self._messages_in_current_mode = 0

            # Persist history
            history_path = self.data_dir / "mode_history.json"
            try:
                existing = json.loads(history_path.read_text()) if history_path.exists() else []
                existing.append(self.mode_history[-1])
                history_path.write_text(json.dumps(existing[-1000:], indent=2))
            except Exception:
                pass

        return self.personalities[mode]

    def get_system_prompt_overlay(self) -> str:
        return self.personalities[self.current_mode].system_prompt_overlay

    def get_current_voice_id(self) -> str:
        return self.personalities[self.current_mode].voice_id

    def get_current_voice_settings(self) -> dict:
        return self.personalities[self.current_mode].voice_settings

    def get_optimal_model(self, text: str) -> str:
        """Get the best 11 Labs model for this text + current mode."""
        return self.token_optimizer.get_optimal_model(text, self.current_mode)

    def get_all_personalities(self) -> list[dict]:
        return [p.to_dict() for p in self.personalities.values()]

    def get_available_personalities(self) -> list[dict]:
        """Return only personalities available for the current tier."""
        return [
            {**p.to_dict(), "locked": not self._is_mode_allowed(p.mode)}
            for p in self.personalities.values()
        ]

    def get_all_education_voices(self) -> list[dict]:
        return [v.to_dict() for v in self.education_voices.values()]

    def reset_to_core(self):
        self._transition_to(VoiceMode.CIPHER_CORE, "manual_reset")

    def get_mode_stats(self) -> dict:
        from collections import Counter
        mode_counts = Counter(h["to"] for h in self.mode_history)
        return {
            "current_mode": self.current_mode.value,
            "cipher_only": self._cipher_only,
            "user_tier": self._user_tier,
            "total_transitions": len(self.mode_history),
            "mode_usage": dict(mode_counts),
            "messages_since_switch": self._messages_since_switch,
            "messages_in_current_mode": self._messages_in_current_mode,
            "last_transition": self.mode_history[-1] if self.mode_history else None,
            "token_optimizer_stats": self.token_optimizer.get_stats(),
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_manager: Optional[VoicePersonalityManager] = None

def get_personality_manager() -> VoicePersonalityManager:
    """Get or create the voice personality manager singleton."""
    global _manager
    if _manager is None:
        _manager = VoicePersonalityManager()
    return _manager
