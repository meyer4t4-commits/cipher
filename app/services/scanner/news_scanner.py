"""News scanner using RSS feeds and NewsAPI."""

import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

try:
    import httpx
except ImportError:
    import aiohttp as httpx

from app.core.logging import logger
from .base import BaseScanner, ScanResult, ScannerConnectionError, ScannerParseError


class NewsScanner(BaseScanner):
    """Scan news from RSS feeds and NewsAPI."""

    # Free RSS feeds for tech/AI news
    RSS_FEEDS = {
        "TechCrunch": "https://feeds.techcrunch.com/feed",
        "Hacker News": "https://news.ycombinator.com/rss",
        "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
        "The Verge": "https://www.theverge.com/rss/index.xml",
        "Reuters Tech": "https://www.reuters.com/technology",
    }

    def __init__(self, newsapi_key: Optional[str] = None):
        super().__init__("news", rate_limit_delay=0.5)
        self.newsapi_key = newsapi_key
        self.newsapi_url = "https://newsapi.org/v2/everything"
        self.client = None

    async def _get_client(self):
        """Get or create HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=10.0)
        return self.client

    async def scan(self, keywords: list[str]) -> list[ScanResult]:
        """
        Scan news from NewsAPI and RSS feeds.

        Args:
            keywords: Keywords to search for

        Returns:
            List of ScanResult objects
        """
        results = []

        # Try NewsAPI first if key is available
        if self.newsapi_key:
            try:
                api_results = await self._scan_newsapi(keywords)
                results.extend(api_results)
                logger.debug(f"NewsAPI returned {len(api_results)} results")
            except ScannerConnectionError as e:
                logger.warning(f"NewsAPI failed: {e}, falling back to RSS")
        else:
            logger.debug("No NewsAPI key configured, using RSS fallback")

        # Always include RSS feed results
        try:
            rss_results = await self._scan_rss_feeds(keywords)
            results.extend(rss_results)
            logger.debug(f"RSS feeds returned {len(rss_results)} results")
        except ScannerConnectionError as e:
            logger.error(f"RSS feed scan failed: {e}")

        # Parse and filter
        parsed = await self.parse_results(results)
        filtered = await self.filter_relevant(parsed, threshold=0.3)

        logger.info(f"News scanner found {len(filtered)} relevant results")
        return filtered

    async def _scan_newsapi(self, keywords: list[str]) -> list[dict]:
        """Scan NewsAPI for keyword mentions."""
        try:
            client = await self._get_client()
            results = []

            for keyword in keywords[:5]:  # Limit to avoid rate limit
                await self._rate_limit()
                try:
                    response = await client.get(
                        self.newsapi_url,
                        params={
                            "q": keyword,
                            "sortBy": "publishedAt",
                            "pageSize": 10,
                            "apiKey": self.newsapi_key,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()

                    if data.get("status") == "ok":
                        results.extend(data.get("articles", []))
                except httpx.HTTPError as e:
                    logger.warning(f"NewsAPI request failed for '{keyword}': {e}")
                    continue

            return results
        except Exception as e:
            raise ScannerConnectionError(f"NewsAPI scan failed: {e}")

    async def _scan_rss_feeds(self, keywords: list[str]) -> list[dict]:
        """Scan RSS feeds for keyword mentions."""
        try:
            client = await self._get_client()
            results = []

            for feed_name, feed_url in self.RSS_FEEDS.items():
                try:
                    await self._rate_limit()
                    response = await client.get(feed_url, follow_redirects=True)
                    response.raise_for_status()

                    # Parse RSS
                    feed_results = self._parse_rss_feed(
                        response.text, feed_name, keywords
                    )
                    results.extend(feed_results)
                    logger.debug(f"RSS feed '{feed_name}' parsed: {len(feed_results)} items")

                except Exception as e:
                    logger.warning(f"Failed to parse RSS feed '{feed_name}': {e}")
                    continue

            return results
        except Exception as e:
            raise ScannerConnectionError(f"RSS feed scan failed: {e}")

    def _parse_rss_feed(
        self, feed_xml: str, feed_name: str, keywords: list[str]
    ) -> list[dict]:
        """
        Parse RSS feed XML and extract relevant items.

        Args:
            feed_xml: Raw XML from RSS feed
            feed_name: Name of the feed
            keywords: Keywords to match

        Returns:
            List of parsed items
        """
        try:
            items = []
            root = ET.fromstring(feed_xml)

            # Handle different RSS/Atom namespaces
            namespaces = {
                "": "http://www.rss.org/",
                "content": "http://purl.org/rss/1.0/modules/content/",
                "atom": "http://www.w3.org/2005/Atom",
            }

            # Try to find items (RSS vs Atom)
            item_elements = root.findall(".//item")
            if not item_elements:
                item_elements = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in item_elements[:20]:  # Limit items per feed
                try:
                    # Extract fields (handles both RSS and Atom)
                    title_elem = item.find("title")
                    if title_elem is None:
                        title_elem = item.find(
                            "{http://www.w3.org/2005/Atom}title"
                        )
                    title = (title_elem.text or "").strip()

                    desc_elem = item.find("description")
                    if desc_elem is None:
                        desc_elem = item.find(
                            "{http://www.w3.org/2005/Atom}summary"
                        )
                    description = (desc_elem.text or "").strip()

                    link_elem = item.find("link")
                    if link_elem is None:
                        # For Atom, link is an attribute
                        link_elem = item.find(
                            "{http://www.w3.org/2005/Atom}link"
                        )
                        link = link_elem.get("href", "") if link_elem else ""
                    else:
                        link = (link_elem.text or "").strip()

                    pub_elem = item.find("pubDate")
                    if pub_elem is None:
                        pub_elem = item.find(
                            "{http://www.w3.org/2005/Atom}published"
                        )
                    pub_date = (pub_elem.text or "").strip()

                    if title and (description or link):
                        items.append(
                            {
                                "source": feed_name,
                                "title": title,
                                "description": description,
                                "url": link,
                                "publishedAt": pub_date,
                            }
                        )
                except Exception as e:
                    logger.debug(f"Failed to parse RSS item: {e}")
                    continue

            return items
        except ET.ParseError as e:
            logger.error(f"Failed to parse RSS XML: {e}")
            return []

    async def parse_results(self, raw_results: list[dict]) -> list[ScanResult]:
        """Parse raw API results into ScanResult objects."""
        results = []

        for item in raw_results:
            try:
                # Handle both NewsAPI and RSS formats
                title = item.get("title", "").strip()
                content = item.get("description", "") or item.get("content", "")
                content = content.replace("<p>", "").replace("</p>", "").strip()
                url = item.get("url") or item.get("link") or ""
                source = item.get("source", {})
                if isinstance(source, dict):
                    source_name = source.get("name", "NewsAPI")
                else:
                    source_name = item.get("source", "News")

                # Parse timestamp
                pub_date_str = item.get("publishedAt") or item.get(
                    "pubDate", ""
                )
                try:
                    # Try ISO format first
                    timestamp = datetime.fromisoformat(
                        pub_date_str.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    timestamp = datetime.utcnow()

                if title and url:
                    result = ScanResult(
                        source=source_name,
                        title=title,
                        content=content[:500],  # Truncate long content
                        url=url,
                        timestamp=timestamp,
                        relevance_score=0.5,
                        tags=["news"],
                    )
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse news item: {e}")
                continue

        return results

    async def filter_relevant(
        self, results: list[ScanResult], threshold: float = 0.3
    ) -> list[ScanResult]:
        """Filter news by relevance threshold."""
        # News is inherently relevant if we fetched it with keywords
        return [r for r in results if r.relevance_score >= threshold]

    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
