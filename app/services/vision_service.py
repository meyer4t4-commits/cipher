"""
Vision Service — Image analysis using LiteLLM's multimodal support.

Supports Claude 3.5 Sonnet vision and GPT-4V through LiteLLM's unified API.
Handles base64 image encoding, validation, and batch analysis.
"""

import base64
import os
from typing import Optional

from app.core.logging import logger


# Supported image formats and max size
SUPPORTED_FORMATS = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB


def validate_image(image_b64: str) -> tuple[bool, str]:
    """Validate a base64-encoded image. Returns (valid, error_message)."""
    try:
        data = base64.b64decode(image_b64)
        if len(data) > MAX_IMAGE_SIZE_BYTES:
            return False, f"Image too large ({len(data) / 1024 / 1024:.1f}MB, max 5MB)"
        if len(data) < 100:
            return False, "Image data too small — likely corrupt"
        return True, ""
    except Exception as e:
        return False, f"Invalid base64 image data: {e}"


def detect_mime_type(image_b64: str) -> str:
    """Detect image MIME type from base64 data."""
    try:
        data = base64.b64decode(image_b64[:32])
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif data[:2] == b'\xff\xd8':
            return "image/jpeg"
        elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return "image/webp"
        elif data[:4] == b'GIF8':
            return "image/gif"
    except Exception:
        pass
    return "image/jpeg"  # Default assumption


async def analyze_image(image_b64: str, prompt: Optional[str] = None) -> str:
    """
    Analyze a single image using a vision-capable LLM.

    Args:
        image_b64: Base64-encoded image data
        prompt: Optional user prompt for targeted analysis

    Returns:
        Analysis text from the vision model
    """
    try:
        import litellm

        # Validate
        valid, error = validate_image(image_b64)
        if not valid:
            return f"[Image validation failed: {error}]"

        mime_type = detect_mime_type(image_b64)
        analysis_prompt = prompt or "Describe this image in detail. What do you see?"

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": analysis_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}"
                    }
                }
            ]
        }]

        # Try Claude first (best vision), fall back to GPT-4V
        model = None
        for candidate in [
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-3-5-sonnet-20241022",
            "openai/gpt-4o",
            "openai/gpt-4-turbo",
        ]:
            # Check if the provider's API key is available
            provider = candidate.split("/")[0]
            if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
                model = candidate
                break
            elif provider == "openai" and os.getenv("OPENAI_API_KEY"):
                model = candidate
                break

        if not model:
            return "[Vision analysis unavailable — no vision-capable API key configured]"

        logger.info(f"Vision analysis using {model}")
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        return f"[Vision analysis error: {str(e)[:200]}]"


async def analyze_images(images: list[str], prompt: Optional[str] = None) -> str:
    """
    Analyze multiple images, returning combined analysis.

    Args:
        images: List of base64-encoded image strings
        prompt: Optional user prompt

    Returns:
        Combined analysis text
    """
    if not images:
        return ""

    if len(images) == 1:
        return await analyze_image(images[0], prompt)

    # For multiple images, build a single multimodal message
    try:
        import litellm

        content_blocks = [
            {"type": "text", "text": prompt or f"Analyze these {len(images)} images in detail."}
        ]

        for i, img_b64 in enumerate(images[:5]):  # Max 5 images
            valid, error = validate_image(img_b64)
            if not valid:
                content_blocks.append({"type": "text", "text": f"[Image {i + 1} skipped: {error}]"})
                continue

            mime_type = detect_mime_type(img_b64)
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
            })

        messages = [{"role": "user", "content": content_blocks}]

        model = None
        for candidate in [
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-3-5-sonnet-20241022",
            "openai/gpt-4o",
        ]:
            provider = candidate.split("/")[0]
            if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
                model = candidate
                break
            elif provider == "openai" and os.getenv("OPENAI_API_KEY"):
                model = candidate
                break

        if not model:
            return "[Vision analysis unavailable — no vision-capable API key configured]"

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            max_tokens=2048,
            temperature=0.3,
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Multi-image analysis failed: {e}")
        return f"[Vision analysis error: {str(e)[:200]}]"


def build_vision_messages(user_text: str, images: list[str]) -> list[dict]:
    """
    Build multimodal message content blocks for LiteLLM.
    Used by the orchestrator to pass images directly to the LLM.

    Returns content list suitable for the 'content' field of a message.
    """
    content = [{"type": "text", "text": user_text}]

    for img_b64 in images[:5]:
        valid, _ = validate_image(img_b64)
        if not valid:
            continue
        mime_type = detect_mime_type(img_b64)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
        })

    return content
