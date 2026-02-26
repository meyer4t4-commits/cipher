"""Scanner API endpoints for intelligence retrieval and configuration."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import logger
from app.services.scanner.orchestrator import get_orchestrator

router = APIRouter(tags=["scanner"])


# Pydantic models for API
class ScannerStatus(BaseModel):
    """Scanner status response."""

    running: bool
    last_full_scan: Optional[str]
    scan_count: int
    error_count: int
    last_scan_times: dict[str, str]
    enabled_sources: list[str]
    memory_stats: dict


class ScannerConfig(BaseModel):
    """Scanner configuration."""

    keywords: dict[str, list[str]]
    sources_enabled: dict[str, bool]
    scan_intervals: dict[str, int]
    relevance_threshold: float
    max_results_per_scan: int


class BriefingResponse(BaseModel):
    """Briefing response."""

    content: str
    generated_at: str


@router.get("/scanner/status", response_model=ScannerStatus)
async def get_scanner_status() -> ScannerStatus:
    """
    Get current scanner status.

    Returns:
        Scanner status including last run time, scan count, errors, enabled sources
    """
    try:
        orchestrator = await get_orchestrator()
        status = await orchestrator.get_status()
        return ScannerStatus(**status)
    except Exception as e:
        logger.error(f"Error getting scanner status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scanner/briefing")
async def get_latest_briefing() -> BriefingResponse:
    """
    Get the latest intelligence briefing.

    Returns:
        Latest briefing in markdown format
    """
    try:
        orchestrator = await get_orchestrator()
        content = await orchestrator.get_briefing()
        return BriefingResponse(
            content=content,
            generated_at=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Error getting briefing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scanner/briefing/{date}")
async def get_briefing_by_date(date: str) -> BriefingResponse:
    """
    Get intelligence briefing for a specific date.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        Briefing for the specified date
    """
    try:
        # Validate date format
        datetime.strptime(date, "%Y-%m-%d")

        orchestrator = await get_orchestrator()
        content = await orchestrator.get_briefing(date)
        return BriefingResponse(
            content=content,
            generated_at=datetime.utcnow().isoformat(),
        )
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Date must be in YYYY-MM-DD format"
        )
    except Exception as e:
        logger.error(f"Error getting briefing for {date}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scanner/scan-now")
async def trigger_scan() -> dict:
    """
    Trigger an immediate full scan.

    Returns:
        Status of the scan
    """
    try:
        orchestrator = await get_orchestrator()
        await orchestrator.run_full_scan()
        logger.info("Manual scan triggered")

        status = await orchestrator.get_status()
        return {
            "status": "completed",
            "scan_count": status["scan_count"],
            "last_full_scan": status["last_full_scan"],
        }
    except Exception as e:
        logger.error(f"Error triggering scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scanner/briefing-now")
async def generate_briefing_now() -> BriefingResponse:
    """
    Generate a briefing immediately.

    Returns:
        Generated briefing
    """
    try:
        orchestrator = await get_orchestrator()
        content = await orchestrator.generate_briefing()
        logger.info("Manual briefing generated")

        return BriefingResponse(
            content=content,
            generated_at=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Error generating briefing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scanner/config", response_model=ScannerConfig)
async def get_scanner_config() -> ScannerConfig:
    """
    Get current scanner configuration.

    Returns:
        Scanner configuration including keywords, intervals, and thresholds
    """
    try:
        orchestrator = await get_orchestrator()
        config_dict = orchestrator._config_to_dict()
        return ScannerConfig(**config_dict)
    except Exception as e:
        logger.error(f"Error getting scanner config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scanner/config", response_model=ScannerConfig)
async def update_scanner_config(config: ScannerConfig) -> ScannerConfig:
    """
    Update scanner configuration.

    Args:
        config: New configuration

    Returns:
        Updated configuration
    """
    try:
        orchestrator = await get_orchestrator()
        config_dict = config.dict()
        updated = await orchestrator.update_config(config_dict)
        logger.info("Scanner configuration updated")

        return ScannerConfig(**updated)
    except Exception as e:
        logger.error(f"Error updating scanner config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scanner/keywords")
async def add_keyword(
    keyword: str = Query(..., description="Keyword to add"),
    category: str = Query(
        "technology", description="Category for the keyword"
    ),
) -> dict:
    """
    Add a keyword to track.

    Args:
        keyword: Keyword to add
        category: Category (technology, brand, industry, competitors)

    Returns:
        Updated keywords
    """
    try:
        orchestrator = await get_orchestrator()
        if category not in orchestrator.config.keywords:
            orchestrator.config.keywords[category] = []

        if keyword not in orchestrator.config.keywords[category]:
            orchestrator.config.keywords[category].append(keyword)
            logger.info(f"Added keyword '{keyword}' to category '{category}'")

        return {"keywords": orchestrator.config.keywords}
    except Exception as e:
        logger.error(f"Error adding keyword: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scanner/keywords")
async def remove_keyword(
    keyword: str = Query(..., description="Keyword to remove"),
    category: str = Query(
        "technology", description="Category containing the keyword"
    ),
) -> dict:
    """
    Remove a keyword from tracking.

    Args:
        keyword: Keyword to remove
        category: Category containing the keyword

    Returns:
        Updated keywords
    """
    try:
        orchestrator = await get_orchestrator()
        if category in orchestrator.config.keywords:
            orchestrator.config.keywords[category] = [
                kw for kw in orchestrator.config.keywords[category]
                if kw != keyword
            ]
            logger.info(
                f"Removed keyword '{keyword}' from category '{category}'"
            )

        return {"keywords": orchestrator.config.keywords}
    except Exception as e:
        logger.error(f"Error removing keyword: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scanner/health")
async def scanner_health() -> dict:
    """
    Check scanner health.

    Returns:
        Health status
    """
    try:
        orchestrator = await get_orchestrator()
        status = await orchestrator.get_status()

        # Consider healthy if running and scanned within last 3 hours
        is_healthy = orchestrator.running
        if status["last_full_scan"]:
            last_scan = datetime.fromisoformat(status["last_full_scan"])
            hours_ago = (datetime.utcnow() - last_scan).total_seconds() / 3600
            is_healthy = is_healthy and hours_ago < 3

        return {
            "healthy": is_healthy,
            "running": status["running"],
            "last_scan": status["last_full_scan"],
            "errors": status["error_count"],
        }
    except Exception as e:
        logger.error(f"Error checking scanner health: {e}")
        return {"healthy": False, "error": str(e)}
