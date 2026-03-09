"""
Intelligent message classifier for auto-routing to optimal model tier.

PHILOSOPHY: Default to the BEST model (DEFAULT tier = Claude Sonnet).
Only route to FAST tier for truly trivial queries where speed matters more than depth.
Only route to CODE/REASONING for queries that specifically need those capabilities.

The old classifier sent most messages to FAST (Llama) because:
- Short messages (<30 chars) → FAST
- Simple question patterns → FAST
- Any "what/when/where" question → FAST

The NEW classifier defaults to DEFAULT (Claude) for anything that isn't
obviously trivial, because quality matters more than saving a few cents.
"""

import re
from typing import Tuple
from app.models.schemas import ModelTier


# ═══════════════════════════════════════════════════════════════════════════════
# TIER KEYWORDS
# ═══════════════════════════════════════════════════════════════════════════════

# Keywords that STRONGLY indicate code tasks
CODE_KEYWORDS = {
    "write", "build", "debug", "fix", "function", "class", "api", "script",
    "code", "implement", "deploy", "docker", "git", "sql", "python", "javascript",
    "html", "css", "regex", "error", "traceback", "bug", "compile", "endpoint",
    "database", "query", "migrate", "refactor", "test", "unit test", "pytest",
    "json", "xml", "rest", "graphql", "webhook", "microservice", "lambda",
    "kubernetes", "terraform", "yaml", "toml", "requirement", "dependency",
    "framework", "library", "package", "module", "import", "export", "async",
    "await", "promise", "callback", "middleware", "cache", "queue", "stream",
    "pagination", "authentication", "authorization", "encryption", "hash",
    "validate", "serialize", "deserialize", "schema", "type", "interface",
    "swift", "swiftui", "fastapi", "react", "typescript", "rust", "golang",
    "nginx", "dockerfile", "cicd", "pipeline", "server", "backend", "frontend",
}

# Keywords that indicate deep reasoning/analysis tasks
REASONING_KEYWORDS = {
    "analyze", "compare", "evaluate", "pros", "cons", "trade-off", "tradeoff",
    "strategy", "should i", "which is better", "explain why", "break down",
    "assess", "investigate", "research", "implications", "long-term",
    "architecture", "design decision", "pattern", "approach", "methodology",
    "theory", "concept", "principle", "hypothesis", "critical thinking",
    "contradict", "validate", "verify", "argue", "debate", "perspective",
    "considering", "alternative", "scenario", "outcome", "consequence",
    "impact", "risk", "opportunity", "prioritize", "weigh", "decision",
    "recommendation", "insight", "interpretation", "deep dive",
    "financial model", "valuation", "due diligence", "legal", "contract",
    "negotiate", "business plan", "market analysis", "competitor analysis",
}

# ONLY truly trivial queries get FAST tier — one-liners with no real depth needed
TRIVIAL_PATTERNS = [
    r"^(hi|hey|hello|sup|yo|gm|good morning|good night|thanks|thank you|ok|okay|cool|nice|got it|bet|word)\s*[!.?]*$",
    r"^what time is it\??$",
    r"^what('s| is) the date\??$",
    r"^\d+\s*[\+\-\*\/]\s*\d+\s*=?\s*$",  # Simple math like "5 + 3"
    r"^(yes|no|yep|nope|sure|nah)\s*[!.?]*$",
]

# Very short threshold — only TRULY short messages go to FAST
TRIVIAL_MESSAGE_THRESHOLD = 15  # characters (was 30 — way too aggressive)


class MessageClassifier:
    """
    Classifies user messages to determine optimal model tier.
    Quality-first: defaults to DEFAULT (Claude) unless there's a strong signal
    for CODE, REASONING, or the message is genuinely trivial (FAST).
    """

    @staticmethod
    def classify(message: str) -> Tuple[ModelTier, float]:
        """
        Classify a message to the optimal ModelTier.

        Returns:
            Tuple of (ModelTier, confidence_score 0.0-1.0)
        """
        if not message or not isinstance(message, str):
            return ModelTier.DEFAULT, 0.5

        normalized = message.lower().strip()

        # ── Trivial messages → FAST (but ONLY truly trivial) ──
        if len(normalized) < TRIVIAL_MESSAGE_THRESHOLD:
            if MessageClassifier._is_trivial(normalized):
                return ModelTier.FAST, 0.90
            # Short but not trivial (e.g. "fix this bug") → DEFAULT
            # Fall through to keyword analysis

        # Check if it matches trivial patterns explicitly
        if MessageClassifier._is_trivial(normalized):
            return ModelTier.FAST, 0.85

        # ── Tokenize for keyword matching ──
        words = MessageClassifier._tokenize(normalized)
        word_set = set(words)
        # Also check 2-grams for multi-word keywords
        bigrams = set()
        for i in range(len(words) - 1):
            bigrams.add(f"{words[i]} {words[i+1]}")
        all_tokens = word_set | bigrams

        # ── Check CODE tier ──
        code_matches = len(all_tokens & CODE_KEYWORDS)
        code_confidence = min(code_matches / 2.5, 1.0)

        # Strong code signals: code blocks, file paths, error traces
        if "```" in message or re.search(r'\b\w+\.\w{2,4}\b', message):  # file extensions
            code_confidence = max(code_confidence, 0.7)
        if re.search(r'(traceback|error|exception|stack trace)', normalized):
            code_confidence = max(code_confidence, 0.8)

        # ── Check REASONING tier ──
        reasoning_matches = len(all_tokens & REASONING_KEYWORDS)
        reasoning_confidence = min(reasoning_matches / 2.0, 1.0)

        # Strong reasoning signals: long complex messages, "should I", comparisons
        if len(message) > 200 and reasoning_matches >= 2:
            reasoning_confidence = max(reasoning_confidence, 0.8)
        if re.search(r'(should i|which is better|pros and cons|compare)', normalized):
            reasoning_confidence = max(reasoning_confidence, 0.75)

        # ── Decision: highest confidence wins, but DEFAULT is the baseline ──
        # DEFAULT baseline is 0.6 — CODE/REASONING must beat this to override
        scores = {
            ModelTier.CODE: code_confidence,
            ModelTier.REASONING: reasoning_confidence,
            ModelTier.DEFAULT: 0.6,  # Strong baseline — Claude is the default brain
        }

        best_tier = max(scores, key=scores.get)
        confidence = scores[best_tier]

        # If no strong specialist signal, default to Claude
        if confidence < 0.5:
            return ModelTier.DEFAULT, 0.7

        return best_tier, min(confidence, 0.99)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text into words for keyword matching."""
        # Remove code blocks and URLs
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'`[^`]*`', '', text)
        text = re.sub(r'https?://\S+', '', text)
        tokens = re.split(r'[\s\-_.,;:!?\(\)\[\]{}\"\']+', text)
        return [t for t in tokens if t and not t.isdigit()]

    @staticmethod
    def _is_trivial(text: str) -> bool:
        """Check if text is a genuinely trivial message (greeting, yes/no, etc.)."""
        for pattern in TRIVIAL_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def get_classification_details(message: str) -> dict:
        """Return detailed classification info for debugging."""
        tier, confidence = MessageClassifier.classify(message)

        normalized = message.lower().strip()
        words = MessageClassifier._tokenize(normalized)
        word_set = set(words)

        code_matches = word_set & CODE_KEYWORDS
        reasoning_matches = word_set & REASONING_KEYWORDS

        return {
            "tier": tier.value,
            "confidence": round(confidence, 3),
            "message_length": len(message),
            "code_keywords_found": list(code_matches)[:5],
            "reasoning_keywords_found": list(reasoning_matches)[:5],
            "is_trivial": MessageClassifier._is_trivial(normalized),
            "would_use_model": None,  # Filled in by caller if needed
        }


# Public API
def auto_classify(message: str) -> Tuple[ModelTier, float]:
    """
    Auto-classify a message to the optimal model tier.

    Quality-first: defaults to DEFAULT (Claude Sonnet) unless there's a
    strong signal for CODE, REASONING, or the message is genuinely trivial.

    Examples:
        auto_classify("hi")                    → (FAST, 0.90)
        auto_classify("what's the weather?")   → (DEFAULT, 0.70)
        auto_classify("write a Python script") → (CODE, 0.80)
        auto_classify("compare React vs Vue")  → (REASONING, 0.75)
    """
    return MessageClassifier.classify(message)
