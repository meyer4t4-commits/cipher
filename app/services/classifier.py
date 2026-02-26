"""
Intelligent message classifier for auto-routing to optimal model tier.
Analyzes message content and returns the best ModelTier with confidence score.
"""

import re
from typing import Tuple
from app.models.schemas import ModelTier

# Keywords for CODE tier routing
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
}

# Keywords for REASONING tier routing
REASONING_KEYWORDS = {
    "analyze", "compare", "evaluate", "pros", "cons", "trade-off", "tradeoff",
    "strategy", "should i", "which is better", "explain why", "break down",
    "assess", "investigate", "research", "implications", "long-term",
    "architecture", "design decision", "pattern", "approach", "methodology",
    "framework", "model", "theory", "concept", "principle", "hypothesis",
    "problem-solve", "problem solve", "critical thinking", "reason", "logic",
    "contradict", "validate", "verify", "argue", "debate", "perspective",
    "considering", "alternative", "option", "scenario", "outcome", "consequence",
    "impact", "risk", "opportunity", "prioritize", "weigh", "decision",
    "recommendation", "insight", "understanding", "interpretation", "analysis",
}

# Keywords for simple/quick responses (FAST tier)
SIMPLE_KEYWORDS = {
    "what is", "when did", "how many", "who is", "define", "what time",
    "yes", "no", "simple", "quick", "brief", "short", "tldr", "summary",
    "translate", "summarize", "quote", "definition", "fact", "list",
    "what's", "what are", "how do", "where is", "why did", "difference",
}

# Patterns for short messages
SHORT_MESSAGE_THRESHOLD = 30  # characters

# Patterns for queries (simple yes/no or fact retrieval)
SIMPLE_PATTERNS = [
    r"^(what|when|where|who|which|how|why)\s",  # Question start
    r"(is|are)\s[a-z]+\?$",  # Simple statement questions
    r"^(translate|define|summarize|list)\s",  # Single-word commands
    r"^\d+\s*[\+\-\*\/]\s*\d+",  # Simple math
]


class MessageClassifier:
    """
    Classifies user messages to determine optimal model tier.
    Uses keyword matching and pattern analysis for fast, accurate routing.
    """

    @staticmethod
    def classify(message: str) -> Tuple[ModelTier, float]:
        """
        Classify a message to the optimal ModelTier.

        Args:
            message: The user's message to classify

        Returns:
            Tuple of (ModelTier, confidence_score)
            confidence_score ranges from 0.0 to 1.0
        """
        if not message or not isinstance(message, str):
            return ModelTier.DEFAULT, 0.5

        # Normalize message for keyword matching
        normalized = message.lower().strip()

        # Check message length first (very short messages -> FAST)
        if len(normalized) < SHORT_MESSAGE_THRESHOLD:
            return ModelTier.FAST, 0.85

        # Check for simple patterns (facts, definitions, simple queries)
        if MessageClassifier._matches_simple_pattern(normalized):
            return ModelTier.FAST, 0.80

        # Tokenize for keyword matching
        words = MessageClassifier._tokenize(normalized)
        word_set = set(words)

        # Check CODE tier keywords
        code_matches = len(word_set & CODE_KEYWORDS)
        code_confidence = min(code_matches / 3.0, 1.0)  # Normalize to 0-1

        # Check REASONING tier keywords
        reasoning_matches = len(word_set & REASONING_KEYWORDS)
        reasoning_confidence = min(reasoning_matches / 3.0, 1.0)

        # Check SIMPLE tier keywords
        simple_matches = len(word_set & SIMPLE_KEYWORDS)
        simple_confidence = min(simple_matches / 2.0, 1.0)

        # Determine best tier by confidence
        scores = {
            ModelTier.CODE: code_confidence,
            ModelTier.REASONING: reasoning_confidence,
            ModelTier.FAST: simple_confidence,
            ModelTier.DEFAULT: 0.5,  # Default baseline
        }

        best_tier = max(scores, key=scores.get)
        confidence = scores[best_tier]

        # If no strong signal, default to DEFAULT tier
        if confidence < 0.3:
            return ModelTier.DEFAULT, 0.6

        return best_tier, min(confidence, 0.99)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """
        Tokenize text into words for keyword matching.
        Removes punctuation and splits on whitespace and hyphens.
        """
        # Remove code blocks and URLs to avoid noise
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'`[^`]*`', '', text)
        text = re.sub(r'https?://\S+', '', text)

        # Split on whitespace, hyphens, and common punctuation
        tokens = re.split(r'[\s\-_.,;:!?\(\)\[\]{}\"\']+', text)

        # Filter empty tokens and keep only non-numeric tokens
        return [t for t in tokens if t and not t.isdigit()]

    @staticmethod
    def _matches_simple_pattern(text: str) -> bool:
        """Check if text matches patterns for simple/quick responses."""
        for pattern in SIMPLE_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def get_classification_details(message: str) -> dict:
        """
        Return detailed classification info for debugging/monitoring.
        Useful for understanding why a tier was selected.
        """
        tier, confidence = MessageClassifier.classify(message)

        normalized = message.lower().strip()
        words = MessageClassifier._tokenize(normalized)
        word_set = set(words)

        code_matches = word_set & CODE_KEYWORDS
        reasoning_matches = word_set & REASONING_KEYWORDS
        simple_matches = word_set & SIMPLE_KEYWORDS

        return {
            "tier": tier.value,
            "confidence": round(confidence, 3),
            "message_length": len(message),
            "code_keywords_found": list(code_matches)[:5],  # Top 5
            "reasoning_keywords_found": list(reasoning_matches)[:5],
            "simple_keywords_found": list(simple_matches)[:5],
            "is_short_message": len(normalized) < SHORT_MESSAGE_THRESHOLD,
            "matches_simple_pattern": MessageClassifier._matches_simple_pattern(normalized),
        }


# Public API - single function for simplicity
def auto_classify(message: str) -> Tuple[ModelTier, float]:
    """
    Auto-classify a message to the optimal model tier.

    Args:
        message: The user's message

    Returns:
        Tuple of (ModelTier, confidence_score)

    Example:
        tier, confidence = auto_classify("Write me a Python function to sort a list")
        # Returns (ModelTier.CODE, 0.95)
    """
    return MessageClassifier.classify(message)
