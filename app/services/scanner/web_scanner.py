"""Web intelligence scanner using Google Trends and Reddit."""

import asyncio
from datetime import datetime

try:
    import httpx
except ImportError:
    import aiohttp as httpx

from app.core.logging import logger
from .base import BaseScanner, ScanResult, ScannerConnectionError, ScannerParseError


class WebScanner(BaseScanner):
    """Scan web intelligence from Trends and Reddit."""

    REDDIT_SUBREDDITS = [
        "artificial",
        "LocalLLaMA",
        "machinelearning",
        "LanguageModels",
        "ChatGPT",
    ]

    def __init__(self):
        super().__init__("web", rate_limit_delay=2.0)
        self.client = None
        self.trends_url = "https://trends.google.com/trends/api/explore"

    async def _get_client(self):
        """Get or create HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=10.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
        return self.client

    async def scan(self, keywords: list[str]) -> list[ScanResult]:
        """
        Scan web for trending intelligence.

        Args:
            keywords: Keywords to monitor

        Returns:
            List of ScanResult objects
        """
        results = []

        # Scan Reddit for discussions
        try:
            reddit_results = await self._scan_reddit(keywords)
            results.extend(reddit_results)
            logger.debug(f"Reddit scan returned {len(reddit_results)} results")
        except ScannerConnectionError as e:
            logger.warning(f"Reddit scan failed: {e}")

        # Parse and filter
        parsed = await self.parse_results(results)
        filtered = await self.filter_relevant(parsed, threshold=0.3)

        logger.info(f"Web scanner found {len(filtered)} relevant results")
        return filtered

    async def _scan_reddit(self, keywords: list[str]) -> list[dict]:
        """
        Scan Reddit for keyword discussions.

        Args:
            keywords: Keywords to search for

        Returns:
            List of Reddit posts
        """
        try:
            client = await self._get_client()
            results = []

            for subreddit in self.REDDIT_SUBREDDITS:
                try:
                    await self._rate_limit()
                    url = f"https://reddit.com/r/{subreddit}/.json"
                    response = await client.get(url)
                    response.raise_for_status()

                    data = response.json()
                    posts = data.get("data", {}).get("children", [])

                    for post_data in posts[:15]:  # Limit posts
                        post = post_data.get("data", {})
                        title = post.get("title", "").strip()
                        content = post.get("selftext", "").strip()
                        url = f"https://reddit.com{post.get('permalink', '')}"
                        created = post.get("created_utc", 0)

                        # Check relevance to keywords
                        text = f"{title} {content}".lower()
                        relevant = any(
                            kw.lower() in text for kw in keywords
                        )

                        if relevant and title:
                            results.append(
                                {
                                    "source": f"Reddit r/{subreddit}",
                                    "title": title,
                                    "content": content[:500],
                                    "url": url,
                                    "created_utc": created,
                                    "subreddit": subreddit,
                                }
                            )
                except Exception as e:
                    logger.debug(
                        f"Failed to scan Reddit r/{subreddit}: {e}"
                    )
                    continue

            return results
        except Exception as e:
            raise ScannerConnectionError(f"Reddit scan failed: {e}")

    async def parse_results(self, raw_results: list[dict]) -> list[ScanResult]:
        """Parse raw Reddit results into ScanResult objects."""
        results = []

        for item in raw_results:
            try:
                title = item.get("title", "").strip()
                content = item.get("content", "").strip()
                url = item.get("url", "")
                source = item.get("source", "Reddit")
                created = item.get("created_utc", 0)

                # Convert Unix timestamp to datetime
                try:
                    timestamp = datetime.utcfromtimestamp(created)
                except (ValueError, OSError):
                    timestamp = datetime.utcnow()

                if title and url:
                    result = ScanResult(
                        source=source,
                        title=title,
                        content=content[:500],
                        url=url,
                        timestamp=timestamp,
                        relevance_score=0.6,
                        tags=["reddit", "discussion"],
                    )
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse Reddit result: {e}")
                continue

        return results

    async def filter_relevant(
        self, results: list[ScanResult], threshold: float = 0.3
    ) -> list[ScanResult]:
        """Filter web results by relevance."""
        # Keep results that are already filtered during scan
        return [r for r in results if r.relevance_score >= threshold]

    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
