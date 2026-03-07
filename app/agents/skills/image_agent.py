"""
Image Generation Agent - Generate images using OpenAI DALL-E or Stability AI.
Supports text-to-image generation, style variations, and image editing.
"""

import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


class ImageAgent(BaseAgent):
    """Generate and manipulate images using AI models."""

    def __init__(self, output_dir: str = "./data/images"):
        """Initialize the image agent."""
        super().__init__(
            name="image_agent",
            description="AI image generation with DALL-E 3 and Stability AI",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="generate_image",
                    description="Generate an image from a text prompt",
                    category="creative",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="edit_image",
                    description="Edit or modify an existing image with a prompt",
                    category="creative",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="variation",
                    description="Create variations of an existing image",
                    category="creative",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="describe_image",
                    description="Describe what should be generated (prompt engineering helper)",
                    category="creative",
                    timeout_seconds=10,
                ),
            ],
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def validate(self, task: AgentTask) -> bool:
        """Validate image generation task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation") or task.params.get("action", "generate_image")

        # Normalize
        if operation in ("generate", "create", "draw", "make", "image"):
            operation = "generate_image"
        elif operation in ("edit", "modify", "change"):
            operation = "edit_image"
        elif operation in ("vary", "variation", "variations"):
            operation = "variation"

        # Check we have either OpenAI or Stability key
        openai_key = getattr(settings, "openai_api_key", "")
        stability_key = getattr(settings, "stability_api_key", "")

        if not openai_key and not stability_key:
            logger.error("No image generation API key configured (need OPENAI_API_KEY or STABILITY_API_KEY)")
            return False

        # Generate needs a prompt
        if operation == "generate_image":
            if "prompt" not in task.params:
                task.params["prompt"] = task.instruction
                logger.info(f"Task {task.task_id}: Using instruction as image prompt")

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute image generation operation."""
        operation = task.params.get("operation") or task.params.get("action", "generate_image")

        # Normalize
        if operation in ("generate", "create", "draw", "make", "image"):
            operation = "generate_image"
        elif operation in ("edit", "modify", "change"):
            operation = "edit_image"
        elif operation in ("vary", "variation", "variations"):
            operation = "variation"

        try:
            if operation == "generate_image":
                await self.emit_progress("Generating image with DALL-E...")
                return await self._generate_image(task)
            elif operation == "edit_image":
                await self.emit_progress("Editing image with DALL-E...")
                return await self._edit_image(task)
            elif operation == "variation":
                await self.emit_progress("Creating image variation...")
                return await self._create_variation(task)
            elif operation == "describe_image":
                await self.emit_progress("Analyzing image...")
                return await self._describe_prompt(task)
            else:
                # Default: treat as generation if we have a prompt
                if "prompt" in task.params or task.instruction:
                    await self.emit_progress("Generating image with DALL-E...")
                    return await self._generate_image(task)
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown image operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Image operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _generate_image(self, task: AgentTask) -> AgentResult:
        """Generate an image from a text prompt."""
        prompt = task.params.get("prompt", task.instruction)
        size = task.params.get("size", "1024x1024")
        quality = task.params.get("quality", "standard")  # "standard" or "hd"
        style = task.params.get("style", "vivid")  # "vivid" or "natural"
        model = task.params.get("model", "dall-e-3")
        n = task.params.get("n", 1)

        logger.info(f"[{self.name}] Generating image: '{prompt[:80]}...' ({size}, {quality})")

        # Try OpenAI DALL-E first
        openai_key = getattr(settings, "openai_api_key", "")
        if openai_key:
            try:
                result = await self._dalle_generate(prompt, size, quality, style, model, n, openai_key)
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=result,
                )
            except Exception as e:
                logger.warning(f"[{self.name}] DALL-E failed ({e}), trying Stability AI")

        # Fallback: Stability AI
        stability_key = getattr(settings, "stability_api_key", "")
        if stability_key:
            try:
                result = await self._stability_generate(prompt, size, stability_key)
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=result,
                )
            except Exception as e:
                logger.error(f"[{self.name}] Stability AI also failed: {e}")
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"All image generation providers failed. DALL-E and Stability AI errors. Last: {str(e)}",
                )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=False,
            error="No image generation API key configured. Set OPENAI_API_KEY or STABILITY_API_KEY in .env",
        )

    async def _dalle_generate(
        self,
        prompt: str,
        size: str,
        quality: str,
        style: str,
        model: str,
        n: int,
        api_key: str,
    ) -> dict:
        """Generate image via OpenAI DALL-E API."""
        # Validate size for DALL-E 3
        valid_sizes_3 = ["1024x1024", "1792x1024", "1024x1792"]
        valid_sizes_2 = ["256x256", "512x512", "1024x1024"]

        if model == "dall-e-3":
            if size not in valid_sizes_3:
                size = "1024x1024"
            n = 1  # DALL-E 3 only supports n=1
        else:
            if size not in valid_sizes_2:
                size = "1024x1024"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "prompt": prompt,
                    "n": n,
                    "size": size,
                    "quality": quality,
                    "style": style,
                    "response_format": "url",  # Get URL (can also do b64_json)
                },
            )
            resp.raise_for_status()
            data = resp.json()

            images = []
            for i, img_data in enumerate(data.get("data", [])):
                image_url = img_data.get("url", "")
                revised_prompt = img_data.get("revised_prompt", prompt)

                images.append({
                    "url": image_url,
                    "revised_prompt": revised_prompt,
                    "index": i,
                })

            logger.info(f"[{self.name}] DALL-E generated {len(images)} image(s)")

            # Optionally download and save locally
            saved_paths = []
            for i, img in enumerate(images):
                if img["url"]:
                    try:
                        img_resp = await client.get(img["url"])
                        img_resp.raise_for_status()

                        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                        filename = f"dalle_{timestamp}_{i}.png"
                        filepath = self.output_dir / filename

                        filepath.write_bytes(img_resp.content)
                        saved_paths.append(str(filepath))
                        logger.info(f"[{self.name}] Saved image to {filepath}")
                    except Exception as e:
                        logger.warning(f"[{self.name}] Failed to save image locally: {e}")

            return {
                "provider": "openai_dalle",
                "model": model,
                "prompt": prompt,
                "revised_prompt": images[0].get("revised_prompt", prompt) if images else prompt,
                "size": size,
                "quality": quality,
                "style": style,
                "num_images": len(images),
                "images": images,
                "saved_paths": saved_paths,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _stability_generate(self, prompt: str, size: str, api_key: str) -> dict:
        """Generate image via Stability AI API."""
        # Parse size
        try:
            width, height = map(int, size.split("x"))
        except ValueError:
            width, height = 1024, 1024

        # Stability AI size constraints (must be multiples of 64, 512-2048)
        width = max(512, min(2048, (width // 64) * 64))
        height = max(512, min(2048, (height // 64) * 64))

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "text_prompts": [{"text": prompt, "weight": 1.0}],
                    "cfg_scale": 7,
                    "width": width,
                    "height": height,
                    "samples": 1,
                    "steps": 30,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            images = []
            saved_paths = []

            for i, artifact in enumerate(data.get("artifacts", [])):
                if artifact.get("finishReason") == "SUCCESS":
                    b64_data = artifact.get("base64", "")

                    # Save to file
                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    filename = f"stability_{timestamp}_{i}.png"
                    filepath = self.output_dir / filename

                    img_bytes = base64.b64decode(b64_data)
                    filepath.write_bytes(img_bytes)
                    saved_paths.append(str(filepath))

                    images.append({
                        "saved_path": str(filepath),
                        "index": i,
                        "finish_reason": artifact.get("finishReason"),
                    })

                    logger.info(f"[{self.name}] Saved Stability image to {filepath}")

            return {
                "provider": "stability_ai",
                "model": "stable-diffusion-xl-1024-v1-0",
                "prompt": prompt,
                "size": f"{width}x{height}",
                "num_images": len(images),
                "images": images,
                "saved_paths": saved_paths,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _edit_image(self, task: AgentTask) -> AgentResult:
        """Edit an existing image using DALL-E 2 or Stability AI."""
        prompt = task.params.get("prompt", task.instruction)
        image_path = task.params.get("image_path", "")
        mask_path = task.params.get("mask_path", "")

        if not image_path:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="image_path parameter required for edit operation",
            )

        if not Path(image_path).exists():
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Image file not found: {image_path}",
            )

        openai_key = getattr(settings, "openai_api_key", "")
        if not openai_key:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Image editing requires OPENAI_API_KEY (uses DALL-E 2 edit endpoint)",
            )

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                files = {
                    "image": ("image.png", open(image_path, "rb"), "image/png"),
                    "prompt": (None, prompt),
                    "n": (None, "1"),
                    "size": (None, "1024x1024"),
                    "response_format": (None, "url"),
                }

                if mask_path and Path(mask_path).exists():
                    files["mask"] = ("mask.png", open(mask_path, "rb"), "image/png")

                resp = await client.post(
                    "https://api.openai.com/v1/images/edits",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    files=files,
                )
                resp.raise_for_status()
                data = resp.json()

                images = []
                saved_paths = []

                for i, img_data in enumerate(data.get("data", [])):
                    image_url = img_data.get("url", "")
                    images.append({"url": image_url, "index": i})

                    if image_url:
                        try:
                            img_resp = await client.get(image_url)
                            img_resp.raise_for_status()
                            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                            filename = f"dalle_edit_{timestamp}_{i}.png"
                            filepath = self.output_dir / filename
                            filepath.write_bytes(img_resp.content)
                            saved_paths.append(str(filepath))
                        except Exception:
                            pass

                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output={
                        "provider": "openai_dalle_edit",
                        "prompt": prompt,
                        "original_image": image_path,
                        "num_images": len(images),
                        "images": images,
                        "saved_paths": saved_paths,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"[{self.name}] Image edit failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Image edit failed: {str(e)}",
            )

    async def _create_variation(self, task: AgentTask) -> AgentResult:
        """Create variations of an existing image."""
        image_path = task.params.get("image_path", "")

        if not image_path or not Path(image_path).exists():
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Valid image_path required for variation operation",
            )

        openai_key = getattr(settings, "openai_api_key", "")
        if not openai_key:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Image variations require OPENAI_API_KEY",
            )

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/images/variations",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    files={
                        "image": ("image.png", open(image_path, "rb"), "image/png"),
                        "n": (None, str(task.params.get("n", 2))),
                        "size": (None, "1024x1024"),
                        "response_format": (None, "url"),
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                images = []
                saved_paths = []

                for i, img_data in enumerate(data.get("data", [])):
                    image_url = img_data.get("url", "")
                    images.append({"url": image_url, "index": i})

                    if image_url:
                        try:
                            img_resp = await client.get(image_url)
                            img_resp.raise_for_status()
                            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                            filename = f"dalle_var_{timestamp}_{i}.png"
                            filepath = self.output_dir / filename
                            filepath.write_bytes(img_resp.content)
                            saved_paths.append(str(filepath))
                        except Exception:
                            pass

                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output={
                        "provider": "openai_dalle_variation",
                        "original_image": image_path,
                        "num_images": len(images),
                        "images": images,
                        "saved_paths": saved_paths,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"[{self.name}] Image variation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Image variation failed: {str(e)}",
            )

    async def _describe_prompt(self, task: AgentTask) -> AgentResult:
        """Help engineer a better image prompt based on user description."""
        description = task.params.get("description", task.instruction)

        # Build an enhanced prompt suggestion
        enhanced = self._enhance_prompt(description)

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output={
                "original_description": description,
                "enhanced_prompt": enhanced,
                "tips": [
                    "Be specific about style (photorealistic, oil painting, digital art, etc.)",
                    "Include lighting details (golden hour, studio lighting, dramatic shadows)",
                    "Mention camera angle (close-up, aerial view, eye-level)",
                    "Specify mood/atmosphere (serene, chaotic, mysterious)",
                    "Add technical details (8K, ultra-detailed, cinematic)",
                ],
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def _enhance_prompt(self, description: str) -> str:
        """Enhance a basic description into a better image prompt."""
        # Simple prompt enhancement — adds detail hints if they're missing
        desc_lower = description.lower()
        additions = []

        if not any(word in desc_lower for word in ["style", "painting", "photo", "digital", "art", "illustration"]):
            additions.append("high quality digital art")

        if not any(word in desc_lower for word in ["lighting", "light", "shadow", "bright", "dark"]):
            additions.append("dramatic lighting")

        if not any(word in desc_lower for word in ["detail", "4k", "8k", "hd", "ultra"]):
            additions.append("highly detailed")

        if additions:
            return f"{description}, {', '.join(additions)}"
        return description

    async def verify(self, result: AgentResult) -> bool:
        """Verify image generation result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        if not result.output:
            logger.warning(f"Result {result.task_id}: Empty output")
            return False

        # Check for timestamp
        if "timestamp" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing timestamp")
            return False

        # For generation results, verify we got image data
        if "images" in result.output:
            if not result.output["images"]:
                logger.warning(f"Result {result.task_id}: No images in output")
                return False

        return True
