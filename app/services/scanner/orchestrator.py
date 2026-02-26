"""Scanner Orchestrator - coordinates all intelligence scanners."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from app.services import memory

from .base import BaseScanner, ScanResult
from .config import ScannerConfig, get_config, get_all_keywords
from .news_scanner import NewsScanner
from .web_scanner import WebScanner
from .x_scanner import XScanner
from .github_scanner import GitHubScanner
from .model_scanner import ModelScanner


class ScannerOrchestrator:
    """Orchestrates all scanners and manages intelligence flow."""

    def __init__(self):
        """Initialize scanner orchestrator."""
        self.config = get_config()
        self.scanners: dict[str, BaseScanner] = {}
        self.last_scan_times: dict[str, datetime] = {}
        self.current_results: list[ScanResult] = []
        self.running = False

        # Initialize scanners based on config
        self._init_scanners()

        # Data directory for briefings
        self.data_dir = Path(settings.data_dir)
        self.briefing_dir = self.data_dir / "briefings"
        self.briefing_dir.mkdir(parents=True, exist_ok=True)

        # Status tracking
        self.last_full_scan: Optional[datetime] = None
        self.scan_count = 0
        self.error_count = 0

    def _init_scanners(self) -> None:
        """Initialize scanner instances based on config."""
        if self.config.sources_enabled.get("news", True):
            self.scanners["news"] = NewsScanner(self.config.newsapi_key)
            logger.info("Initialized NewsScanner")

        if self.config.sources_enabled.get("web", True):
            self.scanners["web"] = WebScanner()
            logger.info("Initialized WebScanner")

        if self.config.sources_enabled.get("twitter", True):
            self.scanners["twitter"] = XScanner(self.config.x_bearer_token)
            logger.info("Initialized XScanner")

        if self.config.sources_enabled.get("github", True):
            self.scanners["github"] = GitHubScanner()
            logger.info("Initialized GitHubScanner")

        # Initialize model scanner (new)
        if self.config.sources_enabled.get("models", True):
            self.scanners["models"] = ModelScanner()
            logger.info("Initialized ModelScanner")

    async def start(self) -> None:
        """Start continuous scanning."""
        if self.running:
            logger.warning("Scanner orchestrator already running")
            return

        self.running = True
        logger.info("Scanner orchestrator starting")

        try:
            # Run initial scan
            await self.run_full_scan()

            # Schedule periodic scans
            while self.running:
                await asyncio.sleep(60)  # Check every minute
                await self._check_and_scan()

        except asyncio.CancelledError:
            logger.info("Scanner orchestrator cancelled")
            self.running = False
        except Exception as e:
            logger.error(f"Scanner orchestrator error: {e}")
            self.running = False
        finally:
            await self.shutdown()

    async def _check_and_scan(self) -> None:
        """
        Check if any scanners need to run based on their per-source intervals.
        Each scanner has its own interval configured in scan_intervals.
        """
        keywords = get_all_keywords()

        for scanner_name, scanner in self.scanners.items():
            try:
                # Get interval for this specific source (with fallback to 60 min)
                interval_minutes = self.config.scan_intervals.get(scanner_name, 60)
                last_run = self.last_scan_times.get(scanner_name)

                # Calculate if enough time has passed for this source
                should_run = last_run is None or (
                    datetime.utcnow() - last_run
                ).total_seconds() >= interval_minutes * 60

                if should_run:
                    logger.debug(
                        f"Running {scanner_name} scanner (interval: {interval_minutes}min)"
                    )
                    results = await scanner.scan(keywords)

                    # Store results
                    await self._store_results(results)
                    self.last_scan_times[scanner_name] = datetime.utcnow()

                    logger.debug(
                        f"{scanner_name} scan complete. "
                        f"Next run in {interval_minutes}min"
                    )

            except Exception as e:
                logger.error(f"Error running {scanner_name} scanner: {e}")
                self.error_count += 1

    async def run_full_scan(self) -> None:
        """Run all enabled scanners immediately."""
        logger.info("Running full intelligence scan")
        keywords = get_all_keywords()

        results = []
        for scanner_name, scanner in self.scanners.items():
            try:
                logger.debug(f"Scanning {scanner_name}...")
                scan_results = await scanner.scan(keywords)
                results.extend(scan_results)
                self.last_scan_times[scanner_name] = datetime.utcnow()
            except Exception as e:
                logger.error(f"Error in {scanner_name}: {e}")
                self.error_count += 1

        # Store and deduplicate results
        await self._store_results(results)
        self.last_full_scan = datetime.utcnow()
        self.scan_count += 1

        logger.info(
            f"Full scan complete: {len(results)} total results collected"
        )

    async def _store_results(self, results: list[ScanResult]) -> None:
        """
        Store scan results in Cipher's memory.

        Args:
            results: Scan results to store
        """
        # Deduplicate by URL
        stored_urls = set(r.get("metadata", {}).get("url", "")
                         for r in memory.recall_memories("", 1000, "intelligence"))

        for result in results:
            if result.url not in stored_urls:
                # Store in memory service
                metadata = {
                    "source": result.source,
                    "url": result.url,
                    "relevance_score": result.relevance_score,
                    "tags": result.tags,
                    "timestamp": result.timestamp.isoformat(),
                }

                content = f"{result.title}\n\n{result.content}"
                memory.store_memory(
                    content=content,
                    metadata=metadata,
                    collection_name="intelligence",
                    memory_id=f"{result.source}_{result.timestamp.timestamp()}",
                )

                stored_urls.add(result.url)

        # Maintain max results limit
        all_memories = memory.recall_memories(
            "", 1000, "intelligence"
        )
        if len(all_memories) > self.config.max_stored_results:
            # Remove oldest entries
            sorted_memories = sorted(
                all_memories,
                key=lambda m: m.get("metadata", {}).get("timestamp", ""),
                reverse=True,
            )
            for old_memory in sorted_memories[self.config.max_stored_results :]:
                memory.delete_memory(old_memory["id"], "intelligence")

    async def get_status(self) -> dict:
        """Get scanner status."""
        return {
            "running": self.running,
            "last_full_scan": self.last_full_scan.isoformat()
            if self.last_full_scan
            else None,
            "scan_count": self.scan_count,
            "error_count": self.error_count,
            "last_scan_times": {
                name: t.isoformat() for name, t in self.last_scan_times.items()
            },
            "enabled_sources": [
                name for name, enabled in self.config.sources_enabled.items()
                if enabled
            ],
            "memory_stats": memory.get_memory_stats("intelligence"),
        }

    async def get_briefing(self, date: Optional[str] = None) -> str:
        """
        Get intelligence briefing.

        Args:
            date: Specific date (YYYY-MM-DD) or None for latest

        Returns:
            Markdown-formatted briefing
        """
        if date:
            briefing_file = self.briefing_dir / f"{date}.md"
            if briefing_file.exists():
                return briefing_file.read_text()
            return f"No briefing found for {date}"

        # Get latest briefing
        briefing_files = sorted(self.briefing_dir.glob("*.md"))
        if briefing_files:
            return briefing_files[-1].read_text()

        return "No briefings generated yet"

    async def generate_briefing(self) -> str:
        """
        Generate daily intelligence briefing.

        Returns:
            Markdown-formatted briefing
        """
        logger.info("Generating intelligence briefing")

        # Get recent memories
        memories = memory.recall_memories(
            "", self.config.briefing_max_items, "intelligence"
        )

        # Group by source
        by_source = {}
        for mem in memories:
            source = mem.get("metadata", {}).get("source", "Unknown")
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(mem)

        # Generate markdown
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        briefing = f"""# Intelligence Briefing
**Date:** {date_str}
**Generated:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}

---

"""

        for source, items in sorted(by_source.items()):
            briefing += f"\n## {source}\n\n"
            for item in items[:5]:  # Max 5 per source
                title = item.get("content", "").split("\n")[0][:100]
                url = item.get("metadata", {}).get("url", "")
                score = item.get("metadata", {}).get("relevance_score", 0)

                if url:
                    briefing += f"- [{title}]({url}) *(relevance: {score:.2f})*\n"
                else:
                    briefing += f"- {title} *(relevance: {score:.2f})*\n"

        # Save briefing
        briefing_file = self.briefing_dir / f"{date_str}.md"
        briefing_file.write_text(briefing)
        logger.info(f"Briefing saved to {briefing_file}")

        return briefing

    async def update_config(self, config_updates: dict) -> dict:
        """
        Update scanner configuration.

        Args:
            config_updates: Configuration updates

        Returns:
            Updated configuration
        """
        if "keywords" in config_updates:
            self.config.keywords = config_updates["keywords"]

        if "sources_enabled" in config_updates:
            self.config.sources_enabled = config_updates["sources_enabled"]

        if "scan_intervals" in config_updates:
            self.config.scan_intervals = config_updates["scan_intervals"]

        if "relevance_threshold" in config_updates:
            self.config.relevance_threshold = config_updates[
                "relevance_threshold"
            ]

        if "max_results_per_scan" in config_updates:
            self.config.max_results_per_scan = config_updates[
                "max_results_per_scan"
            ]

        logger.info("Scanner config updated")
        return self._config_to_dict()

    def _config_to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "keywords": self.config.keywords,
            "sources_enabled": self.config.sources_enabled,
            "scan_intervals": self.config.scan_intervals,
            "relevance_threshold": self.config.relevance_threshold,
            "max_results_per_scan": self.config.max_results_per_scan,
        }

    async def shutdown(self) -> None:
        """Shutdown scanner and cleanup resources."""
        logger.info("Shutting down scanner orchestrator")
        self.running = False

        for scanner in self.scanners.values():
            try:
                await scanner.close()
            except Exception as e:
                logger.error(f"Error closing scanner: {e}")


# Global orchestrator instance
_orchestrator: Optional[ScannerOrchestrator] = None


async def get_orchestrator() -> ScannerOrchestrator:
    """Get or create global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ScannerOrchestrator()
    return _orchestrator


async def start_scanner() -> None:
    """Start the scanner background task."""
    orchestrator = await get_orchestrator()
    if not orchestrator.running:
        # Run in background
        asyncio.create_task(orchestrator.start())
        logger.info("Scanner background task started")


async def stop_scanner() -> None:
    """Stop the scanner background task."""
    global _orchestrator
    if _orchestrator and _orchestrator.running:
        _orchestrator.running = False
        await _orchestrator.shutdown()
        logger.info("Scanner background task stopped")
