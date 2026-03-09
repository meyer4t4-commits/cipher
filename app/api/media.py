"""
Media Generation API - endpoints for generating and serving images and videos.

Supports:
- POST /api/v1/media/generate-image - Generate images from text prompts
- POST /api/v1/media/generate-video - Generate videos from text prompts
- POST /api/v1/media/chain-video - Generate longer videos by chaining clips
- GET /api/v1/media/file/{filename} - Serve generated media files
- GET /api/v1/media/history - Get recent generated media with metadata
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.logging import logger

router = APIRouter(prefix="/api/v1/media", tags=["media"])

# Initialize agents with error protection — if an agent fails to init,
# the router still registers so we get a useful error instead of 404
image_agent = None
video_agent = None

try:
    from app.agents.models import AgentTask, AgentStatus
    from app.agents.skills.image_agent import ImageAgent
    from app.agents.skills.video_agent import VideoAgent
    image_agent = ImageAgent()
    video_agent = VideoAgent()
    logger.info("Media agents initialized: ImageAgent + VideoAgent")
except Exception as e:
    logger.error(f"Media agent initialization failed: {e}", exc_info=True)
    # Import AgentTask for endpoint signatures (may also fail, but try)
    try:
        from app.agents.models import AgentTask, AgentStatus
    except Exception:
        pass

# Data directories
IMAGES_DIR = Path("./data/images")
VIDEOS_DIR = Path("./data/videos")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


# ─── Request/Response Models ───────────────────────────────────────────────────


class GenerateImageRequest(BaseModel):
    """Request to generate an image."""
    prompt: str
    size: Optional[str] = "1024x1024"
    quality: Optional[str] = "standard"
    style: Optional[str] = "natural"
    model: Optional[str] = None


class GenerateVideoRequest(BaseModel):
    """Request to generate a video."""
    prompt: str
    duration: Optional[int] = 5
    aspect_ratio: Optional[str] = "16:9"
    model: Optional[str] = None


class ChainVideoRequest(BaseModel):
    """Request to generate a longer video by chaining multiple clips."""
    scenes: list[str]
    duration_per_clip: Optional[int] = 5
    transition: Optional[str] = "fade"


class MediaMetadata(BaseModel):
    """Metadata about a generated media file."""
    filename: str
    type: str  # "image" or "video"
    prompt: str
    created_at: datetime
    size_bytes: Optional[int] = None
    duration_seconds: Optional[int] = None
    params: dict[str, Any]


class GenerateImageResponse(BaseModel):
    """Response from image generation."""
    success: bool
    image_url: Optional[str] = None
    filename: Optional[str] = None
    prompt: str
    params: dict[str, Any]
    error: Optional[str] = None


class GenerateVideoResponse(BaseModel):
    """Response from video generation."""
    success: bool
    video_url: Optional[str] = None
    filename: Optional[str] = None
    prompt: str
    duration_seconds: Optional[int] = None
    params: dict[str, Any]
    error: Optional[str] = None


class MediaHistoryResponse(BaseModel):
    """Response containing media history."""
    images: list[MediaMetadata]
    videos: list[MediaMetadata]
    total_count: int


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_image(request: GenerateImageRequest) -> GenerateImageResponse:
    """
    Generate an image from a text prompt using ImageAgent.

    Args:
        request: Image generation request with prompt and optional parameters

    Returns:
        Response with image URL and metadata
    """
    try:
        if image_agent is None:
            return GenerateImageResponse(
                success=False,
                prompt=request.prompt,
                params=request.dict(),
                error="ImageAgent not initialized. Check server logs for import errors.",
            )
        logger.info(f"Generating image from prompt: {request.prompt[:100]}")

        # Create task for image agent
        task = AgentTask(
            agent_name="image_agent",
            instruction=f"Generate an image from the following prompt: {request.prompt}",
            params={
                "prompt": request.prompt,
                "size": request.size or "1024x1024",
                "quality": request.quality or "standard",
                "style": request.style or "natural",
                "model": request.model,
                "operation": "generate_image",
            },
            timeout_seconds=60,
        )

        # Validate task
        is_valid = await image_agent.validate(task)
        if not is_valid:
            return GenerateImageResponse(
                success=False,
                prompt=request.prompt,
                params=request.dict(),
                error="Image generation validation failed. Check API keys and parameters.",
            )

        # Execute task
        result = await image_agent.execute(task)

        if not result.success:
            return GenerateImageResponse(
                success=False,
                prompt=request.prompt,
                params=request.dict(),
                error=result.error or "Image generation failed",
            )

        # Extract image URL and filename from result
        output = result.output or {}
        image_url = output.get("image_url") or output.get("url")
        filename = output.get("filename") or "generated_image.png"

        return GenerateImageResponse(
            success=True,
            image_url=image_url,
            filename=filename,
            prompt=request.prompt,
            params=request.dict(),
        )

    except Exception as e:
        logger.error(f"Image generation error: {str(e)}", exc_info=True)
        return GenerateImageResponse(
            success=False,
            prompt=request.prompt,
            params=request.dict(),
            error=f"Image generation error: {str(e)}",
        )


@router.post("/generate-video", response_model=GenerateVideoResponse)
async def generate_video(request: GenerateVideoRequest) -> GenerateVideoResponse:
    """
    Generate a video from a text prompt using VideoAgent.

    Args:
        request: Video generation request with prompt and optional parameters

    Returns:
        Response with video URL and metadata
    """
    try:
        if video_agent is None:
            return GenerateVideoResponse(
                success=False,
                prompt=request.prompt,
                params=request.dict(),
                error="VideoAgent not initialized. Check server logs for import errors.",
            )
        logger.info(f"Generating video from prompt: {request.prompt[:100]}")

        # Create task for video agent
        task = AgentTask(
            agent_name="video_agent",
            instruction=f"Generate a video from the following prompt: {request.prompt}",
            params={
                "prompt": request.prompt,
                "duration": request.duration or 5,
                "aspect_ratio": request.aspect_ratio or "16:9",
                "model": request.model,
                "operation": "generate_video",
            },
            timeout_seconds=120,
        )

        # Validate task
        is_valid = await video_agent.validate(task)
        if not is_valid:
            return GenerateVideoResponse(
                success=False,
                prompt=request.prompt,
                params=request.dict(),
                error="Video generation validation failed. Check API keys and parameters.",
            )

        # Execute task
        result = await video_agent.execute(task)

        if not result.success:
            return GenerateVideoResponse(
                success=False,
                prompt=request.prompt,
                params=request.dict(),
                error=result.error or "Video generation failed",
            )

        # Extract video URL and filename from result
        output = result.output or {}
        video_url = output.get("video_url") or output.get("url")
        filename = output.get("filename") or "generated_video.mp4"
        duration = output.get("duration_seconds") or request.duration

        return GenerateVideoResponse(
            success=True,
            video_url=video_url,
            filename=filename,
            prompt=request.prompt,
            duration_seconds=duration,
            params=request.dict(),
        )

    except Exception as e:
        logger.error(f"Video generation error: {str(e)}", exc_info=True)
        return GenerateVideoResponse(
            success=False,
            prompt=request.prompt,
            params=request.dict(),
            error=f"Video generation error: {str(e)}",
        )


@router.post("/chain-video", response_model=GenerateVideoResponse)
async def chain_video(request: ChainVideoRequest) -> GenerateVideoResponse:
    """
    Generate a longer video by chaining multiple shorter clips together.

    Args:
        request: Chain video request with list of scene prompts

    Returns:
        Response with final video URL
    """
    try:
        if video_agent is None:
            return GenerateVideoResponse(
                success=False,
                prompt=" | ".join(request.scenes),
                params=request.dict(),
                error="VideoAgent not initialized. Check server logs for import errors.",
            )
        logger.info(f"Chaining video with {len(request.scenes)} scenes")

        if not request.scenes or len(request.scenes) == 0:
            raise ValueError("At least one scene prompt is required")

        # Create task for video chaining
        combined_prompt = " | ".join(request.scenes)
        task = AgentTask(
            agent_name="video_agent",
            instruction=f"Generate a chained video with the following scenes: {combined_prompt}",
            params={
                "scenes": request.scenes,
                "duration_per_clip": request.duration_per_clip or 5,
                "transition": request.transition or "fade",
                "operation": "chain_video",
            },
            timeout_seconds=180,
        )

        # Validate task
        is_valid = await video_agent.validate(task)
        if not is_valid:
            return GenerateVideoResponse(
                success=False,
                prompt=combined_prompt,
                params=request.dict(),
                error="Video chaining validation failed. Check API keys and parameters.",
            )

        # Execute task
        result = await video_agent.execute(task)

        if not result.success:
            return GenerateVideoResponse(
                success=False,
                prompt=combined_prompt,
                params=request.dict(),
                error=result.error or "Video chaining failed",
            )

        # Extract video URL and filename from result
        output = result.output or {}
        video_url = output.get("video_url") or output.get("url")
        filename = output.get("filename") or "chained_video.mp4"
        duration = output.get("duration_seconds") or (len(request.scenes) * (request.duration_per_clip or 5))

        return GenerateVideoResponse(
            success=True,
            video_url=video_url,
            filename=filename,
            prompt=combined_prompt,
            duration_seconds=duration,
            params=request.dict(),
        )

    except Exception as e:
        logger.error(f"Video chaining error: {str(e)}", exc_info=True)
        return GenerateVideoResponse(
            success=False,
            prompt=" | ".join(request.scenes),
            params=request.dict(),
            error=f"Video chaining error: {str(e)}",
        )


@router.get("/file/{filename}")
async def get_media_file(filename: str):
    """
    Serve a generated media file (image or video).

    Args:
        filename: Name of the file to serve

    Returns:
        FileResponse with the media file
    """
    try:
        # Sanitize filename to prevent path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Check images directory first
        image_path = IMAGES_DIR / filename
        if image_path.exists() and image_path.is_file():
            logger.info(f"Serving image: {filename}")
            return FileResponse(image_path, media_type="image/png")

        # Check videos directory
        video_path = VIDEOS_DIR / filename
        if video_path.exists() and video_path.is_file():
            logger.info(f"Serving video: {filename}")
            return FileResponse(video_path, media_type="video/mp4")

        # File not found
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {filename}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error serving file")


@router.get("/history", response_model=MediaHistoryResponse)
async def get_media_history(
    limit: int = 50,
    hours: int = 24,
):
    """
    Get recent generated media files (images and videos) with metadata.

    Args:
        limit: Maximum number of files to return (default 50)
        hours: Look back this many hours (default 24)

    Returns:
        MediaHistoryResponse with lists of images and videos
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        images = []
        videos = []

        # Scan images directory
        if IMAGES_DIR.exists():
            image_files = sorted(
                IMAGES_DIR.glob("*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            for file_path in image_files[:limit]:
                if file_path.is_file():
                    try:
                        stat = file_path.stat()
                        if datetime.fromtimestamp(stat.st_mtime) > cutoff_time:
                            # Extract prompt from filename or metadata if available
                            # For now, use filename as prompt placeholder
                            images.append(
                                MediaMetadata(
                                    filename=file_path.name,
                                    type="image",
                                    prompt=file_path.stem,
                                    created_at=datetime.fromtimestamp(stat.st_mtime),
                                    size_bytes=stat.st_size,
                                    params={"source": "generated"},
                                )
                            )
                    except Exception as e:
                        logger.warning(f"Error processing image {file_path.name}: {str(e)}")
                        continue

        # Scan videos directory
        if VIDEOS_DIR.exists():
            video_files = sorted(
                VIDEOS_DIR.glob("*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            for file_path in video_files[:limit]:
                if file_path.is_file():
                    try:
                        stat = file_path.stat()
                        if datetime.fromtimestamp(stat.st_mtime) > cutoff_time:
                            videos.append(
                                MediaMetadata(
                                    filename=file_path.name,
                                    type="video",
                                    prompt=file_path.stem,
                                    created_at=datetime.fromtimestamp(stat.st_mtime),
                                    size_bytes=stat.st_size,
                                    params={"source": "generated"},
                                )
                            )
                    except Exception as e:
                        logger.warning(f"Error processing video {file_path.name}: {str(e)}")
                        continue

        logger.info(f"Returning {len(images)} images and {len(videos)} videos")

        return MediaHistoryResponse(
            images=images,
            videos=videos,
            total_count=len(images) + len(videos),
        )

    except Exception as e:
        logger.error(f"Error getting media history: {str(e)}", exc_info=True)
        return MediaHistoryResponse(
            images=[],
            videos=[],
            total_count=0,
        )
