"""
LLM Router - The intelligence routing engine of Orchid.
Uses LiteLLM to route requests to the optimal model based on task type.

This is the core innovation: one interface, many models, intelligent routing.
Claude for reasoning, Llama for speed, local models for sovereignty.
"""

import time
from typing import AsyncGenerator

import litellm
from litellm import acompletion, completion_cost

from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import ModelTier

# Configure LiteLLM
litellm.drop_params = True  # Gracefully handle unsupported params per provider
litellm.set_verbose = False


# Model routing table
MODEL_MAP: dict[ModelTier, str] = {
    ModelTier.DEFAULT: settings.default_model,
    ModelTier.REASONING: settings.reasoning_model,
    ModelTier.FAST: settings.fast_model,
    ModelTier.LOCAL: settings.local_model,
    ModelTier.CODE: settings.code_model,
}


def get_model_for_tier(tier: ModelTier) -> str:
    """Resolve a model tier to a specific model ID."""
    return MODEL_MAP.get(tier, settings.default_model)


def get_provider(model_id: str) -> str:
    """Extract provider name from model ID."""
    if "/" in model_id:
        return model_id.split("/")[0]
    if model_id.startswith("claude"):
        return "anthropic"
    if model_id.startswith("gpt"):
        return "openai"
    return "unknown"


async def chat_completion(
    messages: list[dict],
    model_tier: ModelTier = ModelTier.DEFAULT,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    system_prompt: str | None = None,
) -> dict:
    """
    Send a chat completion request through LiteLLM.
    Returns the response with metadata (model used, tokens, cost, latency).
    """
    model_id = get_model_for_tier(model_tier)

    # Prepend system prompt if provided
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    start_time = time.time()

    try:
        response = await acompletion(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        latency_ms = (time.time() - start_time) * 1000
        content = response.choices[0].message.content
        usage = response.usage

        # Calculate cost
        try:
            cost = completion_cost(completion_response=response)
        except Exception:
            cost = 0.0

        logger.info(
            f"LLM response | model={model_id} | tokens={usage.total_tokens} | "
            f"cost=${cost:.4f} | latency={latency_ms:.0f}ms"
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
        }

    except Exception as e:
        logger.error(f"LLM error on {model_id}: {e}")

        # Fallback: try fast model if reasoning model fails
        if model_tier in (ModelTier.REASONING, ModelTier.DEFAULT) and model_id != settings.fast_model:
            logger.info(f"Falling back to fast model: {settings.fast_model}")
            return await chat_completion(
                messages=messages,
                model_tier=ModelTier.FAST,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        raise


async def stream_completion(
    messages: list[dict],
    model_tier: ModelTier = ModelTier.DEFAULT,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat completion response token by token.
    Yields content chunks as they arrive.
    """
    model_id = get_model_for_tier(model_tier)

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        response = await acompletion(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    except Exception as e:
        logger.error(f"Stream error on {model_id}: {e}")
        yield f"\n[Error: {str(e)}]"


async def check_model_availability() -> list[dict]:
    """Check which models are currently accessible."""
    results = []
    test_messages = [{"role": "user", "content": "Hello"}]

    for tier, model_id in MODEL_MAP.items():
        try:
            response = await acompletion(
                model=model_id,
                messages=test_messages,
                max_tokens=5,
            )
            results.append({
                "tier": tier.value,
                "model_id": model_id,
                "provider": get_provider(model_id),
                "available": True,
            })
        except Exception as e:
            results.append({
                "tier": tier.value,
                "model_id": model_id,
                "provider": get_provider(model_id),
                "available": False,
                "error": str(e),
            })

    return results
