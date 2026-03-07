"""
Video Generation Agent - Text-to-video and image-to-video via multiple providers.

PRIMARY: Replicate API (access to Runway Gen-4, Kling 2.6, Hailuo, Wan, open-source)
FALLBACK: fal.ai (Veo 2, LTX Video, Minimax)

KEY FEATURE: Video chaining — generates sequential clips and stitches them with ffmpeg
to produce videos longer than any single provider's limit. This is how Cipher bypasses
the 5-15 second cap that limits Grok/Sora/etc.

NO MOCK DATA. All real API calls.
"""

import asyncio
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


# ─── Provider configs ────────────────────────────────────────────────────────

# Replicate models (best-first ordering)
REPLICATE_MODELS = {
    "runway-gen4": {
        "version": "runwayml/gen4-turbo",
        "max_seconds": 10,
        "supports_text_to_video": True,
        "supports_image_to_video": True,
    },
    "kling-2.6": {
        "version": "kwaivgi/kling-v2.6",
        "max_seconds": 10,
        "supports_text_to_video": True,
        "supports_image_to_video": True,
    },
    "hailuo": {
        "version": "minimax/hailuo-ai-video-01-live",
        "max_seconds": 6,
        "supports_text_to_video": True,
        "supports_image_to_video": True,
    },
    "wan-2.1": {
        "version": "wan-ai/wan2.1-t2v-14b",
        "max_seconds": 5,
        "supports_text_to_video": True,
        "supports_image_to_video": False,
    },
}

# fal.ai models (fallback)
FAL_MODELS = {
    "veo2": {
        "model_id": "fal-ai/veo2",
        "max_seconds": 5,
        "supports_text_to_video": True,
        "supports_image_to_video": True,
    },
    "ltx-video": {
        "model_id": "fal-ai/ltx-video-v2",
        "max_seconds": 6,
        "supports_text_to_video": True,
        "supports_image_to_video": True,
    },
    "minimax": {
        "model_id": "fal-ai/minimax-video",
        "max_seconds": 6,
        "supports_text_to_video": True,
        "supports_image_to_video": True,
    },
}


class VideoAgent(BaseAgent):
    """
    Generate videos using AI models — real API calls only.

    Supports:
    - Text-to-video generation
    - Image-to-video animation
    - Video chaining (stitch multiple clips for longer videos)
    - Multiple providers with automatic fallback
    """

    def __init__(self, output_dir: str = "./data/videos"):
        """Initialize the video agent."""
        super().__init__(
            name="video_agent",
            description="AI video generation — text-to-video, image-to-video, and video chaining for unlimited length",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="generate_video",
                    description="Generate a video from a text prompt",
                    category="creative",
                    timeout_seconds=300,
                ),
                AgentCapability(
                    name="image_to_video",
                    description="Animate an image into a video",
                    category="creative",
                    timeout_seconds=300,
                ),
                AgentCapability(
                    name="chain_video",
                    description="Generate a longer video by chaining multiple clips together",
                    category="creative",
                    timeout_seconds=600,
                ),
                AgentCapability(
                    name="list_models",
                    description="List available video generation models and their capabilities",
                    category="data",
                    timeout_seconds=5,
                ),
            ],
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def validate(self, task: AgentTask) -> bool:
        """Validate video generation task."""
        if not await super().validate(task):
            return False

        replicate_key = getattr(settings, "replicate_api_key", "")
        fal_key = getattr(settings, "fal_api_key", "")

        if not replicate_key and not fal_key:
            logger.error("No video generation API key configured (need REPLICATE_API_TOKEN or FAL_KEY)")
            return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute video generation operation."""
        operation = task.params.get("operation") or task.params.get("action", "generate_video")

        # Normalize operation names
        if operation in ("generate", "create", "text_to_video", "t2v", "video"):
            operation = "generate_video"
        elif operation in ("animate", "img2vid", "i2v", "image_to_video"):
            operation = "image_to_video"
        elif operation in ("chain", "long_video", "stitch", "extend"):
            operation = "chain_video"
        elif operation in ("models", "list"):
            operation = "list_models"

        try:
            if operation == "generate_video":
                return await self._generate_video(task)
            elif operation == "image_to_video":
                return await self._image_to_video(task)
            elif operation == "chain_video":
                return await self._chain_video(task)
            elif operation == "list_models":
                return await self._list_models(task)
            else:
                if "prompt" in task.params or task.instruction:
                    return await self._generate_video(task)
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown video operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Video operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    # ─── Core generation methods ─────────────────────────────────────────

    async def _generate_video(self, task: AgentTask) -> AgentResult:
        """Generate video from text prompt. Tries Replicate first, then fal.ai."""
        prompt = task.params.get("prompt", task.instruction)
        model_preference = task.params.get("model")
        duration = task.params.get("duration", 5)
        aspect_ratio = task.params.get("aspect_ratio", "16:9")
        resolution = task.params.get("resolution", "720p")

        logger.info(f"[video_agent] Generating video: '{prompt[:80]}...' ({duration}s, {aspect_ratio})")

        # Try Replicate first
        replicate_key = getattr(settings, "replicate_api_key", "")
        if replicate_key:
            result = await self._replicate_generate(
                prompt=prompt,
                model_name=model_preference,
                duration=duration,
                aspect_ratio=aspect_ratio,
                api_key=replicate_key,
            )
            if result:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=result,
                )

        # Fallback to fal.ai
        fal_key = getattr(settings, "fal_api_key", "")
        if fal_key:
            result = await self._fal_generate(
                prompt=prompt,
                model_name=model_preference,
                duration=duration,
                aspect_ratio=aspect_ratio,
                api_key=fal_key,
            )
            if result:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=result,
                )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=False,
            error="All video generation providers failed. Check API keys and try again.",
        )

    async def _image_to_video(self, task: AgentTask) -> AgentResult:
        """Animate an image into a video."""
        prompt = task.params.get("prompt", task.instruction)
        image_path = task.params.get("image_path") or task.params.get("image_url", "")
        duration = task.params.get("duration", 5)
        aspect_ratio = task.params.get("aspect_ratio", "16:9")

        if not image_path:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="image_path or image_url required for image-to-video",
            )

        # If it's a local file, we need to handle it differently per provider
        image_url = image_path
        if os.path.exists(image_path):
            # For Replicate, we need a URL — upload to a temporary host or use base64
            # For now, require a URL
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Local file paths not yet supported for image-to-video. Provide an image_url instead.",
            )

        replicate_key = getattr(settings, "replicate_api_key", "")
        if replicate_key:
            result = await self._replicate_img2vid(
                prompt=prompt,
                image_url=image_url,
                duration=duration,
                aspect_ratio=aspect_ratio,
                api_key=replicate_key,
            )
            if result:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=result,
                )

        fal_key = getattr(settings, "fal_api_key", "")
        if fal_key:
            result = await self._fal_img2vid(
                prompt=prompt,
                image_url=image_url,
                duration=duration,
                api_key=fal_key,
            )
            if result:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=result,
                )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=False,
            error="Image-to-video failed on all providers.",
        )

    async def _chain_video(self, task: AgentTask) -> AgentResult:
        """
        THE SECRET WEAPON — chain multiple clips into one longer video.

        How it works:
        1. Takes a list of scene prompts (or splits a long prompt into scenes)
        2. Generates each scene as a separate clip
        3. Stitches them together with ffmpeg
        4. Returns one continuous video that breaks provider length limits

        This is how Cipher generates 30s, 60s, even multi-minute videos
        while competitors are capped at 5-15 seconds per clip.
        """
        scenes = task.params.get("scenes", [])
        prompt = task.params.get("prompt", task.instruction)
        duration_per_clip = task.params.get("duration_per_clip", 5)
        aspect_ratio = task.params.get("aspect_ratio", "16:9")
        transition = task.params.get("transition", "crossfade")
        transition_duration = task.params.get("transition_duration", 0.5)

        # If no scenes provided, try to split the prompt into scenes
        if not scenes and prompt:
            scenes = self._split_into_scenes(prompt)

        if not scenes:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Provide 'scenes' (list of prompts) or a detailed prompt to auto-split into scenes.",
            )

        logger.info(f"[video_agent] Chaining {len(scenes)} scenes ({duration_per_clip}s each)")

        # Generate each scene clip
        clip_paths = []
        clip_results = []
        errors = []

        for i, scene_prompt in enumerate(scenes):
            logger.info(f"[video_agent] Generating scene {i+1}/{len(scenes)}: '{scene_prompt[:60]}...'")

            # Create a sub-task for each scene
            scene_task = AgentTask(
                task_id=f"{task.task_id}_scene_{i}",
                agent_name=self.name,
                instruction=scene_prompt,
                params={
                    "prompt": scene_prompt,
                    "duration": duration_per_clip,
                    "aspect_ratio": aspect_ratio,
                },
            )

            result = await self._generate_video(scene_task)

            if result.success and result.output:
                saved_path = result.output.get("saved_path", "")
                if saved_path and os.path.exists(saved_path):
                    clip_paths.append(saved_path)
                    clip_results.append({
                        "scene": i + 1,
                        "prompt": scene_prompt[:100],
                        "path": saved_path,
                        "provider": result.output.get("provider", "unknown"),
                    })
                else:
                    errors.append(f"Scene {i+1}: generated but no local file saved")
            else:
                errors.append(f"Scene {i+1}: {result.error}")

        if not clip_paths:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"No clips generated successfully. Errors: {'; '.join(errors)}",
            )

        # Stitch clips together with ffmpeg
        if len(clip_paths) > 1:
            final_path = await self._stitch_clips(
                clip_paths,
                transition=transition,
                transition_duration=transition_duration,
            )
        else:
            final_path = clip_paths[0]

        if not final_path or not os.path.exists(final_path):
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Failed to stitch clips together. Check ffmpeg installation.",
            )

        total_duration = len(clip_paths) * duration_per_clip
        file_size = os.path.getsize(final_path)

        output = {
            "operation": "chain_video",
            "scenes_requested": len(scenes),
            "scenes_generated": len(clip_paths),
            "total_duration_seconds": total_duration,
            "transition": transition,
            "saved_path": str(final_path),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "individual_clips": clip_results,
            "errors": errors if errors else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"[video_agent] Chain complete: {len(clip_paths)} clips → "
            f"{total_duration}s video at {final_path}"
        )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _list_models(self, task: AgentTask) -> AgentResult:
        """List available video generation models."""
        models = []

        replicate_key = getattr(settings, "replicate_api_key", "")
        fal_key = getattr(settings, "fal_api_key", "")

        if replicate_key:
            for name, info in REPLICATE_MODELS.items():
                models.append({
                    "name": name,
                    "provider": "replicate",
                    "model_id": info["version"],
                    "max_seconds": info["max_seconds"],
                    "text_to_video": info["supports_text_to_video"],
                    "image_to_video": info["supports_image_to_video"],
                    "available": True,
                })

        if fal_key:
            for name, info in FAL_MODELS.items():
                models.append({
                    "name": name,
                    "provider": "fal.ai",
                    "model_id": info["model_id"],
                    "max_seconds": info["max_seconds"],
                    "text_to_video": info["supports_text_to_video"],
                    "image_to_video": info["supports_image_to_video"],
                    "available": True,
                })

        if not models:
            models.append({
                "message": "No video providers configured. Set REPLICATE_API_TOKEN or FAL_KEY in .env",
                "available": False,
            })

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output={
                "models": models,
                "count": len(models),
                "chain_video_supported": True,
                "max_chain_length": "unlimited",
            },
        )

    # ─── Replicate provider ──────────────────────────────────────────────

    async def _replicate_generate(
        self,
        prompt: str,
        model_name: Optional[str],
        duration: int,
        aspect_ratio: str,
        api_key: str,
    ) -> Optional[dict]:
        """Generate video via Replicate API."""
        # Pick model
        if model_name and model_name in REPLICATE_MODELS:
            model_info = REPLICATE_MODELS[model_name]
        else:
            # Default: try kling first (best quality/cost ratio)
            model_name = "kling-2.6"
            model_info = REPLICATE_MODELS[model_name]

        model_version = model_info["version"]

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                # Create prediction
                resp = await client.post(
                    "https://api.replicate.com/v1/predictions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_version,
                        "input": {
                            "prompt": prompt,
                            "duration": min(duration, model_info["max_seconds"]),
                            "aspect_ratio": aspect_ratio,
                        },
                    },
                )

                if resp.status_code not in (200, 201):
                    logger.warning(f"Replicate create failed ({resp.status_code}): {resp.text[:200]}")
                    return None

                prediction = resp.json()
                prediction_id = prediction.get("id")

                if not prediction_id:
                    logger.warning("Replicate returned no prediction ID")
                    return None

                # Poll for completion
                video_url = await self._replicate_poll(client, prediction_id, api_key)

                if not video_url:
                    return None

                # Download video
                saved_path = await self._download_video(client, video_url, f"replicate_{model_name}")

                return {
                    "provider": f"replicate/{model_name}",
                    "model": model_version,
                    "prompt": prompt,
                    "duration_seconds": min(duration, model_info["max_seconds"]),
                    "aspect_ratio": aspect_ratio,
                    "video_url": video_url,
                    "saved_path": str(saved_path) if saved_path else None,
                    "prediction_id": prediction_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.warning(f"Replicate generation failed: {e}")
            return None

    async def _replicate_img2vid(
        self,
        prompt: str,
        image_url: str,
        duration: int,
        aspect_ratio: str,
        api_key: str,
    ) -> Optional[dict]:
        """Image-to-video via Replicate."""
        model_name = "kling-2.6"
        model_info = REPLICATE_MODELS[model_name]

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                resp = await client.post(
                    "https://api.replicate.com/v1/predictions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_info["version"],
                        "input": {
                            "prompt": prompt,
                            "image": image_url,
                            "duration": min(duration, model_info["max_seconds"]),
                            "aspect_ratio": aspect_ratio,
                        },
                    },
                )

                if resp.status_code not in (200, 201):
                    logger.warning(f"Replicate img2vid failed: {resp.status_code}")
                    return None

                prediction = resp.json()
                prediction_id = prediction.get("id")

                video_url = await self._replicate_poll(client, prediction_id, api_key)
                if not video_url:
                    return None

                saved_path = await self._download_video(client, video_url, f"replicate_i2v_{model_name}")

                return {
                    "provider": f"replicate/{model_name}",
                    "operation": "image_to_video",
                    "prompt": prompt,
                    "source_image": image_url,
                    "video_url": video_url,
                    "saved_path": str(saved_path) if saved_path else None,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.warning(f"Replicate img2vid failed: {e}")
            return None

    async def _replicate_poll(
        self, client: httpx.AsyncClient, prediction_id: str, api_key: str, max_wait: int = 300
    ) -> Optional[str]:
        """Poll Replicate prediction until complete. Returns video URL or None."""
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        headers = {"Authorization": f"Bearer {api_key}"}

        start = time.time()
        while time.time() - start < max_wait:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None

            data = resp.json()
            status = data.get("status")

            if status == "succeeded":
                output = data.get("output")
                # Output can be a string URL or a list
                if isinstance(output, str):
                    return output
                elif isinstance(output, list) and output:
                    return output[0]
                elif isinstance(output, dict):
                    return output.get("url") or output.get("video")
                return None

            elif status in ("failed", "canceled"):
                error = data.get("error", "Unknown error")
                logger.warning(f"Replicate prediction {prediction_id} {status}: {error}")
                return None

            # Still processing — wait and poll again
            await asyncio.sleep(5)

        logger.warning(f"Replicate prediction {prediction_id} timed out after {max_wait}s")
        return None

    # ─── fal.ai provider ─────────────────────────────────────────────────

    async def _fal_generate(
        self,
        prompt: str,
        model_name: Optional[str],
        duration: int,
        aspect_ratio: str,
        api_key: str,
    ) -> Optional[dict]:
        """Generate video via fal.ai API."""
        if model_name and model_name in FAL_MODELS:
            model_info = FAL_MODELS[model_name]
        else:
            model_name = "minimax"
            model_info = FAL_MODELS[model_name]

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                # Submit request
                resp = await client.post(
                    f"https://queue.fal.run/{model_info['model_id']}",
                    headers={
                        "Authorization": f"Key {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "prompt": prompt,
                        "duration": min(duration, model_info["max_seconds"]),
                        "aspect_ratio": aspect_ratio,
                    },
                )

                if resp.status_code not in (200, 201, 202):
                    logger.warning(f"fal.ai submit failed ({resp.status_code}): {resp.text[:200]}")
                    return None

                data = resp.json()
                request_id = data.get("request_id")

                if not request_id:
                    # Synchronous response — video URL directly in response
                    video_url = data.get("video", {}).get("url") or data.get("url")
                    if video_url:
                        saved_path = await self._download_video(
                            client, video_url, f"fal_{model_name}"
                        )
                        return {
                            "provider": f"fal.ai/{model_name}",
                            "model": model_info["model_id"],
                            "prompt": prompt,
                            "video_url": video_url,
                            "saved_path": str(saved_path) if saved_path else None,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    return None

                # Poll for completion
                video_url = await self._fal_poll(client, model_info["model_id"], request_id, api_key)
                if not video_url:
                    return None

                saved_path = await self._download_video(client, video_url, f"fal_{model_name}")

                return {
                    "provider": f"fal.ai/{model_name}",
                    "model": model_info["model_id"],
                    "prompt": prompt,
                    "duration_seconds": min(duration, model_info["max_seconds"]),
                    "video_url": video_url,
                    "saved_path": str(saved_path) if saved_path else None,
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.warning(f"fal.ai generation failed: {e}")
            return None

    async def _fal_img2vid(
        self,
        prompt: str,
        image_url: str,
        duration: int,
        api_key: str,
    ) -> Optional[dict]:
        """Image-to-video via fal.ai."""
        model_name = "minimax"
        model_info = FAL_MODELS[model_name]

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                resp = await client.post(
                    f"https://queue.fal.run/{model_info['model_id']}",
                    headers={
                        "Authorization": f"Key {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "prompt": prompt,
                        "image_url": image_url,
                        "duration": min(duration, model_info["max_seconds"]),
                    },
                )

                if resp.status_code not in (200, 201, 202):
                    return None

                data = resp.json()
                request_id = data.get("request_id")

                if request_id:
                    video_url = await self._fal_poll(client, model_info["model_id"], request_id, api_key)
                else:
                    video_url = data.get("video", {}).get("url") or data.get("url")

                if not video_url:
                    return None

                saved_path = await self._download_video(client, video_url, f"fal_i2v_{model_name}")

                return {
                    "provider": f"fal.ai/{model_name}",
                    "operation": "image_to_video",
                    "prompt": prompt,
                    "source_image": image_url,
                    "video_url": video_url,
                    "saved_path": str(saved_path) if saved_path else None,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.warning(f"fal.ai img2vid failed: {e}")
            return None

    async def _fal_poll(
        self, client: httpx.AsyncClient, model_id: str, request_id: str, api_key: str, max_wait: int = 300
    ) -> Optional[str]:
        """Poll fal.ai request until complete."""
        url = f"https://queue.fal.run/{model_id}/requests/{request_id}/status"
        headers = {"Authorization": f"Key {api_key}"}

        start = time.time()
        while time.time() - start < max_wait:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                await asyncio.sleep(5)
                continue

            data = resp.json()
            status = data.get("status")

            if status == "COMPLETED":
                # Fetch result
                result_resp = await client.get(
                    f"https://queue.fal.run/{model_id}/requests/{request_id}",
                    headers=headers,
                )
                if result_resp.status_code == 200:
                    result_data = result_resp.json()
                    return (
                        result_data.get("video", {}).get("url")
                        or result_data.get("url")
                    )
                return None

            elif status in ("FAILED", "CANCELLED"):
                logger.warning(f"fal.ai request {request_id} {status}")
                return None

            await asyncio.sleep(5)

        return None

    # ─── Video stitching (ffmpeg) ─────────────────────────────────────────

    async def _stitch_clips(
        self,
        clip_paths: list[str],
        transition: str = "crossfade",
        transition_duration: float = 0.5,
    ) -> Optional[str]:
        """
        Stitch multiple video clips into one continuous video using ffmpeg.
        Supports crossfade transitions between clips.
        """
        if not clip_paths:
            return None

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"chained_{timestamp}.mp4"

        # Create concat file for ffmpeg
        concat_file = self.output_dir / f"concat_{timestamp}.txt"

        if transition == "none" or len(clip_paths) == 1:
            # Simple concatenation
            with open(concat_file, "w") as f:
                for path in clip_paths:
                    f.write(f"file '{path}'\n")

            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path),
            ]
        else:
            # Crossfade between clips — requires re-encoding
            # Build complex filter for crossfade transitions
            inputs = []
            for path in clip_paths:
                inputs.extend(["-i", path])

            # Build filter complex for crossfade
            filter_parts = []
            n = len(clip_paths)

            if n == 2:
                filter_parts.append(
                    f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:offset=auto[outv]"
                )
                map_video = "[outv]"
            else:
                # Chain crossfades for 3+ clips
                prev = "0:v"
                for i in range(1, n):
                    out_label = f"v{i}" if i < n - 1 else "outv"
                    filter_parts.append(
                        f"[{prev}][{i}:v]xfade=transition=fade:duration={transition_duration}:offset=auto[{out_label}]"
                    )
                    prev = out_label
                map_video = "[outv]"

            filter_complex = ";".join(filter_parts)

            cmd = ["ffmpeg", "-y"] + inputs + [
                "-filter_complex", filter_complex,
                "-map", map_video,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                str(output_path),
            ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

            # Clean up concat file
            if concat_file.exists():
                concat_file.unlink()

            if process.returncode != 0:
                logger.error(f"ffmpeg stitch failed: {stderr.decode()[:500]}")
                # Fallback: simple concat without transitions
                if transition != "none":
                    return await self._stitch_clips(clip_paths, transition="none")
                return None

            logger.info(f"[video_agent] Stitched {len(clip_paths)} clips → {output_path}")
            return str(output_path)

        except asyncio.TimeoutError:
            logger.error("ffmpeg stitch timed out")
            return None
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install with: brew install ffmpeg (macOS) or apt install ffmpeg")
            return None

    # ─── Helpers ──────────────────────────────────────────────────────────

    async def _download_video(
        self, client: httpx.AsyncClient, url: str, prefix: str
    ) -> Optional[Path]:
        """Download video from URL and save locally."""
        try:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            ext = "mp4"
            content_type = resp.headers.get("content-type", "")
            if "webm" in content_type:
                ext = "webm"

            filename = f"{prefix}_{timestamp}.{ext}"
            filepath = self.output_dir / filename
            filepath.write_bytes(resp.content)

            logger.info(f"[video_agent] Saved video: {filepath} ({len(resp.content)} bytes)")
            return filepath

        except Exception as e:
            logger.warning(f"Failed to download video: {e}")
            return None

    def _split_into_scenes(self, prompt: str) -> list[str]:
        """
        Split a narrative prompt into individual scene prompts.
        Handles natural language scene descriptions.
        """
        # Split on common scene delimiters
        import re

        # Try numbered scenes: "1. ...", "Scene 1: ..."
        numbered = re.split(r'\d+[\.\)]\s*|[Ss]cene\s+\d+[:\s]*', prompt)
        numbered = [s.strip() for s in numbered if s.strip() and len(s.strip()) > 10]
        if len(numbered) >= 2:
            return numbered

        # Try sentence-based splitting for long prompts
        sentences = re.split(r'[\.!]\s+', prompt)
        sentences = [s.strip() + "." for s in sentences if s.strip() and len(s.strip()) > 15]

        if len(sentences) >= 3:
            # Group into scenes of 1-2 sentences each
            scenes = []
            for i in range(0, len(sentences), 2):
                scene = " ".join(sentences[i:i+2])
                scenes.append(scene)
            return scenes

        # Can't split — return as single scene
        return [prompt]

    async def verify(self, result: AgentResult) -> bool:
        """Verify video generation result."""
        if not isinstance(result.output, dict):
            return False

        # Should have a video URL or saved path
        has_video = (
            result.output.get("video_url")
            or result.output.get("saved_path")
            or result.output.get("individual_clips")
        )

        if not has_video:
            logger.warning(f"Result {result.task_id}: No video output")
            return False

        return True
