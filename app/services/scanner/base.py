"""Base scanner class for all intelligence sources."""

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.core.logging import logger


class ScanResult:
    """Standardized scan result format."""

    def __init__(
        self,
        source: str,
        title: str,
        content: str,
        url: str,
        timestamp: Optional[datetime] = None,
        relevance_score: float = 0.5,
        tags: Optional[list[str]] = None,
    ):
        self.source = source
        self.title = title
        self.content = content
        self.url = url
        self.timestamp = timestamp or datetime.utcnow()
        self.relevance_score = min(1.0, max(0.0, relevance_score))  # clamp 0-1
        self.tags = tags or []

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "source": self.source,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "timestamp": self.timestamp.isoformat(),
            "relevance_score": self.relevance_score,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return f"ScanResult(source={self.source}, score={self.relevance_score:.2f}, title={self.title[:50]})"


class BaseScanner(ABC):
    """Abstract base class for all scanners."""

    def __init__(self, name: str, rate_limit_delay: float = 1.0):
        """
        Initialize scanner.

        Args:
            name: Scanner name (e.g., 'news', 'twitter')
            rate_limit_delay: Minimum seconds between API calls
        """
        self.name = name
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time: float = 0
        self._session = None

    @abstractmethod
    async def scan(self, keywords: list[str]) -> list[ScanResult]:
        """
        Scan for intelligence based on keywords.

        Args:
            keywords: List of keywords to search for

        Returns:
            List of ScanResult objects
        """
        pass

    @abstractmethod
    async def parse_results(self, raw_results: list[dict]) -> list[ScanResult]:
        """
        Parse raw API/feed results into standardized format.

        Args:
            raw_results: Raw results from API/feed

        Returns:
            List of ScanResult objects
        """
        pass

    @abstractmethod
    async def filter_relevant(
        self, results: list[ScanResult], threshold: float = 0.3
    ) -> list[ScanResult]:
        """
        Filter results by relevance threshold.

        Args:
            results: Results to filter
            threshold: Minimum relevance score (0-1)

        Returns:
            Filtered results above threshold
        """
        pass

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _calculate_relevance(
        self, text: str, keywords: list[str], base_score: float = 0.5
    ) -> float:
        """
        Calculate relevance score based on keyword matches.

        Args:
            text: Text to score
            keywords: Keywords to match
            base_score: Base relevance score

        Returns:
            Relevance score (0-1)
        """
        if not keywords:
            return base_score

        text_lower = text.lower()
        matched_keywords = sum(1 for kw in keywords if kw.lower() in text_lower)
        keyword_score = min(1.0, matched_keywords / len(keywords))

        # Weighted combination: base score + keyword boost
        combined = (base_score * 0.3) + (keyword_score * 0.7)
        return min(1.0, combined)

    async def close(self) -> None:
        """Cleanup resources."""
        if self._session:
            await self._session.aclose()

    async def __aenter__(self):
        """Context manager support."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        await self.close()


class ScannerError(Exception):
    """Base exception for scanner errors."""

    pass


class ScannerConnectionError(ScannerError):
    """Raised when scanner cannot connect to source."""

    pass


class ScannerParseError(ScannerError):
    """Raised when scanner cannot parse results."""

    pass
