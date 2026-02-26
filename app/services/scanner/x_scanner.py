"""X/Twitter scanner for intelligence gathering."""

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
    """Scan X/Twitter for intelligence."""

    def __init__(self, bearer_token: Optional[str] = None):
        super().__init__("twitter", rate_limit_delay=1.0)
        self.bearer_token = bearer_token
        self.client = None
        self.v2_api_url = "https://api.twitter.com/2"

        # Accounts and topics to monitor
        self.monitor_accounts = [
            "markmeyeragi",  # Your account
            "OpenAI",
            "AnthropicAI",
            "GoogleDeepMind",
        ]

        self.monitor_topics = [
            "sovereign AI",
            "local AI",
            "open source LLM",
            "AI safety",
        ]

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

    async def scan(self, keywords: list[str]) -> list[ScanResult]:
        """
        Scan X/Twitter for mentions and discussions.

        Args:
            keywords: Keywords to search for

        Returns:
            List of ScanResult objects
        """
        results = []

        # Try official API first
        if self.bearer_token:
            try:
                api_results = await self._scan_twitter_api(keywords)
                results.extend(api_results)
                logger.debug(f"Twitter API returned {len(api_results)} results")
            except ScannerConnectionError as e:
                logger.warning(f"Twitter API failed: {e}, falling back to Nitter")
        else:
            logger.debug("No Twitter bearer token, using Nitter fallback")

        # Always try Nitter as fallback
        try:
            nitter_results = await self._scan_nitter(keywords)
            results.extend(nitter_results)
            logger.debug(f"Nitter returned {len(nitter_results)} results")
        except ScannerConnectionError as e:
            logger.warning(f"Nitter scan failed: {e}")

        # Parse and filter
        parsed = await self.parse_results(results)
        filtered = await self.filter_relevant(parsed, threshold=0.3)

        logger.info(f"X scanner found {len(filtered)} relevant results")
        return filtered

    async def _scan_twitter_api(self, keywords: list[str]) -> list[dict]:
        """
        Scan Twitter API v2 for keyword mentions.

        Args:
            keywords: Keywords to search for

        Returns:
            List of tweets
        """
        try:
            if not self.bearer_token:
                return []

            client = await self._get_client()
            results = []

            # Search for each keyword
            for keyword in keywords[:3]:  # Limit to avoid rate limit
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

    async def _scan_nitter(self, keywords: list[str]) -> list[dict]:
        """
        Scan Nitter (privacy-friendly Twitter frontend) for keyword mentions.

        Args:
            keywords: Keywords to search for

        Returns:
            List of tweets (as dicts)
        """
        try:
            client = await self._get_client()
            results = []

            # Nitter RSS search endpoint
            nitter_instances = [
                "https://nitter.net",
                "https://nitter.1d4.us",
                "https://nitter.cz",
            ]

            for keyword in keywords[:5]:
                for nitter_url in nitter_instances:
                    try:
                        await self._rate_limit()

                        # Nitter search RSS feed
                        search_rss_url = f"{nitter_url}/search/rss"
                        response = await client.get(
                            search_rss_url,
                            params={"q": keyword},
                            follow_redirects=True,
                        )
                        response.raise_for_status()

                        # Parse tweets from RSS feed
                        tweets = self._parse_nitter_rss(
                            response.text, keyword
                        )
                        results.extend(tweets)
                        logger.debug(
                            f"Nitter ({nitter_url}) search '{keyword}': {len(tweets)} results"
                        )
                        break  # Success with this instance
                    except Exception as e:
                        logger.debug(
                            f"Nitter search failed ({nitter_url}, '{keyword}'): {e}"
                        )
                        continue

            return results
        except Exception as e:
            raise ScannerConnectionError(f"Nitter scan failed: {e}")

    def _parse_nitter_rss(self, rss_xml: str, keyword: str) -> list[dict]:
        """
        Parse Nitter RSS feed for tweets.

        Args:
            rss_xml: Raw XML from Nitter RSS
            keyword: Search keyword (for context)

        Returns:
            List of tweet dicts
        """
        import xml.etree.ElementTree as ET

        tweets = []
        try:
            root = ET.fromstring(rss_xml)

            # Find all items in RSS feed
            items = root.findall(".//item")

            for item in items[:10]:
                try:
                    title_elem = item.find("title")
                    desc_elem = item.find("description")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")

                    title = (title_elem.text or "").strip() if title_elem else ""
                    description = (desc_elem.text or "").strip() if desc_elem else ""
                    link = (link_elem.text or "").strip() if link_elem else ""
                    pub_date = (pub_elem.text or "").strip() if pub_elem else ""

                    # Extract author from title (usually "Author: tweet text")
                    if ":" in title:
                        author, tweet_text = title.split(":", 1)
                        author = author.strip()
                    else:
                        author = "unknown"
                        tweet_text = title

                    if tweet_text or link:
                        tweets.append(
                            {
                                "author": author,
                                "text": tweet_text,
                                "description": description,
                                "url": link,
                                "created_at": pub_date,
                            }
                        )
                except Exception as e:
                    logger.debug(f"Failed to parse Nitter RSS item: {e}")
                    continue

            return tweets
        except ET.ParseError as e:
            logger.debug(f"Failed to parse Nitter RSS: {e}")
            return []

    async def parse_results(self, raw_results: list[dict]) -> list[ScanResult]:
        """Parse raw Twitter/Nitter results into ScanResult objects."""
        results = []

        for item in raw_results:
            try:
                # Handle both Twitter API v2 and Nitter formats
                if "author_id" in item or "public_metrics" in item:
                    # Twitter API v2 format
                    text = item.get("text", "").strip()
                    title = text[:100]
                    created_at = item.get("created_at", "")
                    author = item.get("author_id", "unknown")
                else:
                    # Nitter format
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
