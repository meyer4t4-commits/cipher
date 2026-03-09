"""
Fact Checker — Multi-tier hallucination detection for Cipher responses.

Uses a secondary LLM call to validate claims in responses, scoring confidence
and flagging unverified assertions. Runs asynchronously so it doesn't block
the main response.
"""

import os
import re
from typing import Optional

from app.core.logging import logger


# Patterns that indicate factual claims worth checking
_FACTUAL_PATTERNS = [
    re.compile(r'\$[\d,.]+[BMTbmt]?'),  # Dollar amounts
    re.compile(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?%'),  # Percentages
    re.compile(r'\b(?:in|on|since|by|from) (?:January|February|March|April|May|June|July|August|September|October|November|December|20\d{2})'),  # Dates
    re.compile(r'\b(?:founded|established|created|launched|released|announced) (?:in|on) \d{4}'),  # Historical dates
    re.compile(r'\b(?:according to|study shows|research indicates|data suggests|statistics show)'),  # Citation claims
    re.compile(r'\b\d+(?:\.\d+)? (?:million|billion|trillion|thousand)'),  # Large numbers
]

# Patterns that indicate NON-factual content (skip checking)
_CREATIVE_PATTERNS = [
    re.compile(r'\b(?:once upon a time|imagine|let\'s say|hypothetically|in theory)\b', re.I),
    re.compile(r'\b(?:I think|I believe|in my opinion|I\'d suggest|I recommend)\b', re.I),
    re.compile(r'\b(?:here\'s a|here is a|let me write|let me create|draft|poem|story|lyrics)\b', re.I),
]


def _has_factual_claims(text: str) -> bool:
    """Check if text contains patterns that look like verifiable facts."""
    for pattern in _FACTUAL_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _is_creative_content(text: str) -> bool:
    """Check if text is creative/opinion content that doesn't need fact-checking."""
    for pattern in _CREATIVE_PATTERNS:
        if pattern.search(text):
            return True
    return False


async def validate_response(
    response_text: str,
    user_query: str,
    context: str = "",
    live_data_used: bool = False,
) -> dict:
    """
    Validate a Cipher response for potential hallucinations.

    Args:
        response_text: The LLM response to validate
        user_query: What the user asked
        context: Any additional context (memory, live data)
        live_data_used: Whether live data was injected (already validated)

    Returns:
        {
            "confidence": float (0-1),
            "warnings": list[str],
            "verified": bool,
            "checked": bool  # Whether checking was actually performed
        }
    """
    # Skip checking for short responses, creative content, or already-validated data
    if len(response_text) < 50:
        return {"confidence": 0.95, "warnings": [], "verified": True, "checked": False}

    if live_data_used:
        return {"confidence": 0.95, "warnings": [], "verified": True, "checked": False}

    if _is_creative_content(response_text):
        return {"confidence": 0.9, "warnings": [], "verified": True, "checked": False}

    if not _has_factual_claims(response_text):
        return {"confidence": 0.85, "warnings": [], "verified": True, "checked": False}

    # Has factual claims — run validation
    try:
        import litellm

        # Use a fast/cheap model for validation
        validation_model = None
        if os.getenv("GROQ_API_KEY"):
            validation_model = "groq/llama-3.1-8b-instant"
        elif os.getenv("ANTHROPIC_API_KEY"):
            validation_model = "anthropic/claude-3-5-haiku-20241022"
        elif os.getenv("OPENAI_API_KEY"):
            validation_model = "openai/gpt-4o-mini"

        if not validation_model:
            logger.warning("No model available for fact-checking")
            return {"confidence": 0.7, "warnings": ["Fact-checking unavailable"], "verified": False, "checked": False}

        validation_prompt = f"""You are a fact-checker. Analyze this AI response for potential hallucinations or unverified claims.

USER QUESTION: {user_query[:500]}

AI RESPONSE: {response_text[:2000]}

Rate the response on these dimensions:
1. CONFIDENCE (0.0-1.0): How likely is this response to be factually accurate?
2. WARNINGS: List any specific claims that seem unverifiable, suspicious, or likely fabricated. If none, say "none".
3. VERDICT: "verified" if confident, "caution" if uncertain, "warning" if likely contains fabricated info.

Respond in this exact format:
CONFIDENCE: 0.X
WARNINGS: [list or "none"]
VERDICT: [verified/caution/warning]"""

        result = await litellm.acompletion(
            model=validation_model,
            messages=[{"role": "user", "content": validation_prompt}],
            max_tokens=300,
            temperature=0.1,
        )

        validation_text = result.choices[0].message.content

        # Parse the validation response
        confidence = 0.7  # default
        warnings = []
        verified = False

        # Extract confidence
        conf_match = re.search(r'CONFIDENCE:\s*([\d.]+)', validation_text)
        if conf_match:
            try:
                confidence = min(1.0, max(0.0, float(conf_match.group(1))))
            except ValueError:
                pass

        # Extract warnings
        warn_match = re.search(r'WARNINGS:\s*(.+?)(?:VERDICT:|$)', validation_text, re.DOTALL)
        if warn_match:
            warn_text = warn_match.group(1).strip()
            if warn_text.lower() != "none" and warn_text != "[]":
                # Split by newlines or dashes
                for line in warn_text.split('\n'):
                    line = line.strip().lstrip('- ').strip()
                    if line and line.lower() != "none":
                        warnings.append(line)

        # Extract verdict
        verdict_match = re.search(r'VERDICT:\s*(\w+)', validation_text)
        if verdict_match:
            verified = verdict_match.group(1).lower() == "verified"

        logger.info(f"Fact-check: confidence={confidence:.2f}, warnings={len(warnings)}, verified={verified}")

        return {
            "confidence": confidence,
            "warnings": warnings[:5],  # Max 5 warnings
            "verified": verified,
            "checked": True,
        }

    except Exception as e:
        logger.error(f"Fact-checking failed: {e}")
        return {"confidence": 0.7, "warnings": ["Fact-checking encountered an error"], "verified": False, "checked": False}
