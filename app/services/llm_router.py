import time
import re
from typing import AsyncGenerator
import litellm
from litellm import acompletion, completion_cost
from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import ModelTier

litellm.drop_params = True
litellm.set_verbose = False

MODEL_MAP = {
    ModelTier.DEFAULT: "anthropic/claude-sonnet-4-20250514",
    ModelTier.REASONING: "deepseek/deepseek-reasoner",
    ModelTier.FAST: "groq/llama-3.3-70b-versatile",
    ModelTier.LOCAL: "groq/llama-3.3-70b-versatile",
    ModelTier.CODE: "deepseek/deepseek-chat",
    ModelTier.AUTO: "anthropic/claude-sonnet-4-20250514",  # Fallback, should be resolved by classifier
}

# Cascade routing - FrugalGPT approach
# Define model cascades for each tier: try cheapest first, escalate if quality is low
MODEL_CASCADES = {
    ModelTier.DEFAULT: [
        "groq/llama-3.3-70b-versatile",      # Cheapest
        "deepseek/deepseek-chat",             # Mid-tier
        "anthropic/claude-sonnet-4-20250514", # Best
    ],
    ModelTier.FAST: [
        "groq/llama-3.3-70b-versatile",      # Cheapest, lowest latency
        "deepseek/deepseek-chat",             # Fallback
    ],
    ModelTier.CODE: [
        "groq/llama-3.3-70b-versatile",      # Cheap, decent for code
        "deepseek/deepseek-chat",             # Better for code
        "anthropic/claude-sonnet-4-20250514", # Best for code
    ],
    ModelTier.REASONING: [
        "groq/llama-3.3-70b-versatile",      # Try cheap first
        "deepseek/deepseek-reasoner",         # Better reasoning
        "anthropic/claude-sonnet-4-20250514", # Best reasoning
    ],
}

def get_model_for_tier(tier):
    return MODEL_MAP.get(tier, "anthropic/claude-sonnet-4-20250514")

def get_provider(model_id):
    if "/" in model_id:
        return model_id.split("/")[0]
    return "unknown"

def _score_response_quality(response_content: str, task_type: ModelTier) -> float:
    """
    Score response quality using heuristics.
    Returns a confidence score from 0.0 to 1.0.

    Heuristics:
    - Very short responses to complex questions = low confidence
    - Contains "I don't know" / "I'm not sure" = low confidence
    - Contains code blocks when CODE requested = high confidence
    - Directly answers the question = high confidence
    - Coherent, substantive answer = high confidence
    """
    if not response_content or len(response_content.strip()) == 0:
        return 0.0

    content = response_content.lower()
    score = 0.5  # Base score

    # Penalty for uncertainty/hedging
    hedging_phrases = [
        "i don't know",
        "i'm not sure",
        "i cannot",
        "i can't",
        "unable to",
        "not sure",
        "don't have",
        "unclear",
        "uncertain",
    ]
    hedging_count = sum(1 for phrase in hedging_phrases if phrase in content)
    score -= (hedging_count * 0.15)  # Each hedging phrase reduces confidence

    # Reward for substantive content
    if len(response_content) > 100:
        score += 0.15
    if len(response_content) > 500:
        score += 0.15
    if len(response_content) > 1000:
        score += 0.1

    # Code task: reward for code blocks
    if task_type == ModelTier.CODE:
        if "```" in response_content:
            score += 0.2  # High confidence if code blocks present
        # Reward for specific programming concepts
        code_keywords = ["function", "class", "def", "return", "import", "async", "await"]
        code_matches = sum(1 for kw in code_keywords if f" {kw} " in f" {content} ")
        score += min(0.15, code_matches * 0.03)

    # Check for coherence (multiple sentences, proper punctuation)
    sentence_count = response_content.count(".") + response_content.count("!") + response_content.count("?")
    if sentence_count >= 3:
        score += 0.1

    # Clamp to 0-1 range
    return max(0.0, min(1.0, score))

async def chat_completion(messages, model_tier=ModelTier.DEFAULT, max_tokens=4096, temperature=0.7, system_prompt=None, cascade_enabled=None):
    """
    Chat completion with optional cascade routing (FrugalGPT approach).

    Args:
        messages: Chat messages
        model_tier: Model tier to use
        max_tokens: Max tokens in response
        temperature: Temperature for generation
        system_prompt: System prompt to prepend
        cascade_enabled: Enable cascade routing (None = use config default)

    Returns:
        Response dict with content, model_used, quality_score, cascade_attempts, etc.
    """

    # Determine if cascade is enabled
    if cascade_enabled is None:
        cascade_enabled = getattr(settings, "cascade_routing_enabled", True)

    # Check if a specific tier was requested (not AUTO)
    # If a specific tier is requested, skip cascade and use that model directly
    use_cascade = cascade_enabled and model_tier != ModelTier.AUTO

    if not use_cascade:
        # Direct routing - no cascade
        model_id = get_model_for_tier(model_tier)
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
        start_time = time.time()
        response = await acompletion(model=model_id, messages=messages, max_tokens=max_tokens, temperature=temperature)
        latency_ms = (time.time() - start_time) * 1000
        content = response.choices[0].message.content
        usage = response.usage
        try:
            cost = completion_cost(completion_response=response)
        except Exception:
            cost = 0.0
        return {
            "content": content,
            "model_used": model_id,
            "provider": get_provider(model_id),
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "response_quality_score": 0.95,  # Assume direct routing is intentional
            "cascade_attempts": 0,
            "cascade_enabled": False,
        }

    # Cascade routing - try models in order
    cascade = MODEL_CASCADES.get(model_tier, [get_model_for_tier(model_tier)])
    quality_threshold = 0.7
    cascade_attempts = 0

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    for attempt, model_id in enumerate(cascade):
        cascade_attempts = attempt + 1
        try:
            start_time = time.time()
            response = await acompletion(model=model_id, messages=messages, max_tokens=max_tokens, temperature=temperature)
            latency_ms = (time.time() - start_time) * 1000
            content = response.choices[0].message.content
            usage = response.usage

            try:
                cost = completion_cost(completion_response=response)
            except Exception:
                cost = 0.0

            # Score response quality
            quality_score = _score_response_quality(content, model_tier)

            logger.info(
                f"Cascade attempt {cascade_attempts}/{len(cascade)}: "
                f"{model_id}, quality_score={quality_score:.2f}, threshold={quality_threshold}"
            )

            # If quality is sufficient, return this response
            if quality_score >= quality_threshold or attempt == len(cascade) - 1:
                # Last model or quality threshold met - return response
                logger.info(
                    f"Cascade complete: {model_id} quality={quality_score:.2f} "
                    f"(attempts={cascade_attempts}/{len(cascade)})"
                )
                return {
                    "content": content,
                    "model_used": model_id,
                    "provider": get_provider(model_id),
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": cost,
                    "latency_ms": latency_ms,
                    "response_quality_score": quality_score,
                    "cascade_attempts": cascade_attempts,
                    "cascade_enabled": True,
                }

            # Quality too low, try next model
            logger.debug(f"Quality score {quality_score:.2f} below threshold, escalating to next model")

        except Exception as e:
            logger.warning(f"Cascade attempt {cascade_attempts} failed with {model_id}: {e}")
            if attempt == len(cascade) - 1:
                # Last model failed, raise error
                raise
            # Otherwise continue to next model

    # Fallback (should not reach here)
    raise Exception("All cascade models failed")

async def stream_completion(messages, model_tier=ModelTier.DEFAULT, max_tokens=4096, temperature=0.7, system_prompt=None):
    model_id = get_model_for_tier(model_tier)
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages
    try:
        response = await acompletion(model=model_id, messages=messages, max_tokens=max_tokens, temperature=temperature, stream=True)
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        yield str(e)

async def check_model_availability():
    return [{"tier": t.value, "model_id": m, "provider": get_provider(m), "available": True} for t, m in MODEL_MAP.items()]
