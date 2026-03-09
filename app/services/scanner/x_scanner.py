"""
X/Twitter scanner for intelligence gathering.

Strategy: Browser-first (free, no API), API as fallback.
The browser_service acts as a real logged-in user scraping X.
"""

import asyncio
from datetime import datetime
from typing import Optional

try:
    import httpx
except ImportError:
    import aiohttp as httpx

from app.core.logging import logger
from .base import BaseScanner, ScanResult, ScannerConnectionError, ScannerParseError


class XScanner(BaseScanner):
    """Scan X/Twitter for intelligence — browser-first, API fallback."""

    def __init__(self, bearer_token: Optional[str] = None):
        super().__init__("twitter", rate_limit_delay=1.0)
        self.bearer_token = bearer_token
        self.client = None
        self.v2_api_url = "https://api.twitter.com/2"

        # Accounts and topics to monitor
        self.monitor_accounts = [
            "markmeyeragi",   # Your account
            "OpenAI",
            "AnthropicAI",
            "GoogleDeepMind",
            "xaborai",        # xAI / Grok
            "MistralAI",
            "ollaborai",      # Ollama
        ]

        self.monitor_topics = [
            "sovereign AI",
            "local AI",
            "open source LLM",
            "AI safety",
            "AI agents",
            "OpenClaw",
        ]

    async def scan(self, keywords: list[str]) -> list[ScanResult]:
        """
        Scan X/Twitter — tries browser first (free), falls back to API.

        Args:
            keywords: Keywords to search for

        Returns:
            List of ScanResult objects
        """
        results = []

        # ---- Strategy 1: Browser scraping (free, no API needed) ----
        try:
            browser_results = await self._scan_browser(keywords)
            results.extend(browser_results)
            logger.info(f"X browser scan returned {len(browser_results)} results")
        except Exception as e:
            logger.warning(f"X browser scan failed: {e}, trying API fallback")

        # ---- Strategy 2: Twitter API v2 (if we have a bearer token and browser failed) ----
        if not results and self.bearer_token:
            try:
                api_results = await self._scan_twitter_api(keywords)
                results.extend(api_results)
                logger.info(f"X API scan returned {len(api_results)} results")
            except ScannerConnectionError as e:
                logger.warning(f"X API scan also failed: {e}")

        # Parse and filter
        parsed = await self.parse_results(results)
        filtered = await self.filter_relevant(parsed, threshold=0.3)

        logger.info(f"X scanner total: {len(filtered)} relevant results")
        return filtered

    async def _scan_browser(self, keywords: list[str]) -> list[dict]:
        """
        Scrape X/Twitter via Playwright browser automation.
        Uses saved login session — no API key required.
        """
        from app.services.browser_service import scrape_x_feed

        results = []

        # Search each keyword
        for keyword in keywords[:5]:
            try:
                await self._rate_limit()
                data = await scrape_x_feed(query=keyword, max_tweets=10)

                if data.get("error"):
                    logger.warning(f"Browser X scrape for '{keyword}': {data['error']}")
                    # If not logged in, bail out entirely
                    if "Not logged in" in str(data.get("error", "")):
                        raise RuntimeError("Not logged in to X — browser scan unavailable")
                    continue

                tweets = data.get("tweets", [])
                for tweet in tweets:
                    results.append({
                        "author": tweet.get("user", "unknown"),
                        "text": tweet.get("text", ""),
                        "url": tweet.get("url", ""),
                        "created_at": tweet.get("timestamp", ""),
                        "metrics": tweet.get("metrics", {}),
                        "source": "browser",
                    })

            except RuntimeError:
                raise  # Propagate login errors
            except Exception as e:
                logger.debug(f"Browser scrape failed for '{keyword}': {e}")
                continue

        # Also monitor specific accounts
        for account in self.monitor_accounts[:3]:
            try:
                await self._rate_limit()
                data = await scrape_x_feed(account=account, max_tweets=5)

                if data.get("error"):
                    continue

                tweets = data.get("tweets", [])
                for tweet in tweets:
                    results.append({
                        "author": tweet.get("user", account),
                        "text": tweet.get("text", ""),
                        "url": tweet.get("url", ""),
                        "created_at": tweet.get("timestamp", ""),
                        "metrics": tweet.get("metrics", {}),
                        "source": "browser",
                    })
            except Exception as e:
                logger.debug(f"Browser account scrape failed for '{account}': {e}")
                continue

        return results

    async def _get_client(self):
        """Get or create HTTP client."""
        if self.client is None:
            headers = {}
            if self.bearer_token:
                headers["Authorization"] = f"Bearer {self.bearer_token}"
            self.client = httpx.AsyncClient(
                timeout=10.0,
                headers=headers | {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
        return self.client

    async def _scan_twitter_api(self, keywords: list[str]) -> list[dict]:
        """Fallback: Scan Twitter API v2 for keyword mentions."""
        try:
            if not self.bearer_token:
                return []

            client = await self._get_client()
            results = []

            for keyword in keywords[:3]:
                await self._rate_limit()
                try:
                    search_url = f"{self.v2_api_url}/tweets/search/recent"
                    response = await client.get(
                        search_url,
                        params={
                            "query": keyword,
                            "max_results": 10,
                            "tweet.fields": "created_at,public_metrics",
                            "expansions": "author_id",
                            "user.fields": "username,verified",
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    tweets = data.get("data", [])
                    results.extend(tweets)
                except httpx.HTTPError as e:
                    logger.warning(f"Twitter API request failed for '{keyword}': {e}")
                    continue

            return results
        except Exception as e:
            raise ScannerConnectionError(f"Twitter API scan failed: {e}")

    async def parse_results(self, raw_results: list[dict]) -> list[ScanResult]:
        """Parse raw results into ScanResult objects."""
        results = []

        for item in raw_results:
            try:
                # Determine format
                source_type = item.get("source", "api")

                if source_type == "browser":
                    author = item.get("author", "unknown")
                    text = item.get("text", "").strip()
                    title = f"@{author}: {text[:80]}"
                    created_at = item.get("created_at", "")
                    url = item.get("url", "")
                elif "author_id" in item or "public_metrics" in item:
                    # Twitter API v2
                    text = item.get("text", "").strip()
                    title = text[:100]
                    created_at = item.get("created_at", "")
                    author = item.get("author_id", "unknown")
                    url = ""
                else:
                    author = item.get("author", "unknown")
                    text = item.get("text", "")
                    title = f"@{author}: {text[:80]}"
                    created_at = item.get("created_at", "")
                    url = item.get("url", "")

                # Parse timestamp
                try:
                    timestamp = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    timestamp = datetime.utcnow()

                if title and text:
                    result = ScanResult(
                        source=f"X (@{author})",
                        title=title,
                        content=text[:300],
                        url=url,
                        timestamp=timestamp,
                        relevance_score=0.7,
                        tags=["twitter", "social"],
                    )
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse tweet: {e}")
                continue

        return results

    async def filter_relevant(
        self, results: list[ScanResult], threshold: float = 0.3
    ) -> list[ScanResult]:
        """Filter Twitter results by relevance."""
        return [r for r in results if r.relevance_score >= threshold]

    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
