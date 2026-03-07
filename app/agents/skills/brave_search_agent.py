"""
Brave Search Agent - Web and news search using Brave Search API.
Falls back to DuckDuckGo scraping if BRAVE_SEARCH_API_KEY is not configured.
"""

import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class BraveSearchAgent(BaseAgent):
    """Brave Search API agent for web and news search with DuckDuckGo fallback."""

    def __init__(self):
        """Initialize the Brave Search agent."""
        # Get API key from settings, gracefully handle if not present
        try:
            from app.core.config import settings
            self.api_key = getattr(settings, 'brave_search_api_key', '')
        except Exception:
            self.api_key = ''

        super().__init__(
            name="brave_search_agent",
            description="Web and news search using Brave Search API with DuckDuckGo fallback",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="web_search",
                    description="Search the web for information using Brave Search",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="news_search",
                    description="Search for news articles using Brave Search",
                    category="data",
                    timeout_seconds=20,
                ),
            ],
        )

    async def validate(self, task: AgentTask) -> bool:
        """Validate Brave Search task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation") or task.params.get("action", "web_search")

        # Normalize operation names
        if operation in ("search", "web", "brave"):
            operation = "web_search"

        # Ensure query parameter exists for search operations
        search_ops = ("web_search", "news_search", "search")
        if operation in search_ops:
            if "query" not in task.params:
                # Fallback: use the instruction as the query
                task.params["query"] = task.instruction
                logger.info(f"Task {task.task_id}: Using instruction as query fallback")

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute Brave Search operation."""
        # Support both "operation" and "action" param keys; default to web_search
        operation = task.params.get("operation") or task.params.get("action", "web_search")

        # Normalize common variations
        if operation in ("search", "web", "brave"):
            operation = "web_search"
        elif operation in ("news", "news_search"):
            operation = "news_search"

        try:
            if operation == "web_search":
                return await self._web_search(task)
            elif operation == "news_search":
                return await self._news_search(task)
            else:
                # Fallback: if we have a query, do a web search
                if "query" in task.params:
                    return await self._web_search(task)
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Brave Search operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _web_search(self, task: AgentTask) -> AgentResult:
        """Perform web search via Brave Search API or DuckDuckGo fallback."""
        query = task.params.get("query", task.instruction)
        num_results = task.params.get("num_results", 10)
        country = task.params.get("country")
        search_lang = task.params.get("search_lang")
        freshness = task.params.get("freshness")  # e.g., "pd" for past day

        logger.info(f"[{self.name}] Searching: {query}")

        # Try Brave Search API first if key is available
        if self.api_key:
            result = await self._brave_web_search(
                task, query, num_results, country, search_lang, freshness
            )
            if result.success:
                return result
            # Log fallback
            logger.warning(
                f"[{self.name}] Brave Search failed, falling back to DuckDuckGo"
            )

        # Fallback to DuckDuckGo
        return await self._duckduckgo_web_search(task, query, num_results)

    async def _brave_web_search(
        self,
        task: AgentTask,
        query: str,
        num_results: int,
        country: Optional[str],
        search_lang: Optional[str],
        freshness: Optional[str],
    ) -> AgentResult:
        """Perform web search via Brave Search API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = "https://api.search.brave.com/res/v1/web/search"
                headers = {
                    "X-Subscription-Token": self.api_key,
                    "Accept": "application/json",
                }
                params = {
                    "q": query,
                    "count": min(num_results, 20),  # Brave limits to 20 per request
                }

                # Add optional parameters if provided
                if country:
                    params["country"] = country
                if search_lang:
                    params["search_lang"] = search_lang
                if freshness:
                    params["freshness"] = freshness

                logger.info(f"[{self.name}] Calling Brave Search API with params: {params}")

                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()

                data = resp.json()
                logger.info(
                    f"[{self.name}] Brave API response status: {resp.status_code}"
                )

                results = []
                if "web" in data and "results" in data["web"]:
                    for result in data["web"]["results"][:num_results]:
                        results.append({
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "snippet": result.get("description", ""),
                            "source": result.get("url", ""),
                            "age": result.get("age"),  # May include age info
                        })

                output = {
                    "query": query,
                    "num_results": len(results),
                    "results": results,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "brave_search",
                }

                logger.info(
                    f"[{self.name}] Found {len(results)} results for '{query}' via Brave"
                )

                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=output,
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning(
                    f"[{self.name}] Brave Search API authentication failed (401)"
                )
            elif e.response.status_code == 429:
                logger.warning(f"[{self.name}] Brave Search API rate limited (429)")
            else:
                logger.error(f"[{self.name}] Brave Search API error: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Brave Search API error: {e}",
            )
        except Exception as e:
            logger.error(f"[{self.name}] Brave Search API request failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Brave Search API request failed: {str(e)}",
            )

    async def _duckduckgo_web_search(
        self, task: AgentTask, query: str, num_results: int
    ) -> AgentResult:
        """Perform web search via DuckDuckGo HTML scraping (fallback)."""
        logger.info(f"[{self.name}] Using DuckDuckGo fallback for: {query}")

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                # Use DuckDuckGo HTML (no API key needed)
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    },
                )
                resp.raise_for_status()
                logger.info(
                    f"[{self.name}] DDG response: status={resp.status_code}, "
                    f"length={len(resp.text)}"
                )

                soup = BeautifulSoup(resp.text, "html.parser")
                results = []

                result_divs = soup.select(".result")
                logger.info(
                    f"[{self.name}] Found {len(result_divs)} result divs in HTML"
                )

                # DuckDuckGo HTML results are in .result divs
                for result_div in result_divs[:num_results]:
                    title_el = result_div.select_one(".result__title a, .result__a")
                    snippet_el = result_div.select_one(".result__snippet")
                    url_el = result_div.select_one(".result__url")

                    title = title_el.get_text(strip=True) if title_el else ""
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    link = ""

                    if title_el and title_el.get("href"):
                        href = title_el["href"]
                        # Decode any HTML entities first
                        href = href.replace("&amp;", "&")
                        # DuckDuckGo wraps URLs in redirect; extract real URL
                        url_match = re.search(r"uddg=([^&]+)", href)
                        if url_match:
                            from urllib.parse import unquote
                            link = unquote(url_match.group(1))
                        elif href.startswith("http"):
                            link = href
                        elif href.startswith("//"):
                            link = "https:" + href
                        else:
                            link = href

                    if url_el:
                        displayed_url = url_el.get_text(strip=True)
                    else:
                        displayed_url = link

                    if title:
                        results.append({
                            "title": title,
                            "url": link,
                            "snippet": snippet,
                            "source": displayed_url,
                        })

                output = {
                    "query": query,
                    "num_results": len(results),
                    "results": results,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "duckduckgo_fallback",
                }

                logger.info(
                    f"[{self.name}] Found {len(results)} results for '{query}' via DDG"
                )

                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=output,
                )

        except Exception as e:
            logger.error(f"[{self.name}] Web search failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Web search failed: {str(e)}",
            )

    async def _news_search(self, task: AgentTask) -> AgentResult:
        """Search for news articles via Brave News API or DuckDuckGo fallback."""
        query = task.params.get("query", task.instruction)
        num_results = task.params.get("num_results", 10)
        country = task.params.get("country")
        search_lang = task.params.get("search_lang")

        logger.info(f"[{self.name}] Searching news: {query}")

        # Try Brave News API first if key is available
        if self.api_key:
            result = await self._brave_news_search(
                task, query, num_results, country, search_lang
            )
            if result.success:
                return result
            # Log fallback
            logger.warning(
                f"[{self.name}] Brave News Search failed, falling back to DuckDuckGo"
            )

        # Fallback to DuckDuckGo with news bias
        news_query = f"{query} news"
        task.params["query"] = news_query
        return await self._duckduckgo_web_search(task, news_query, num_results)

    async def _brave_news_search(
        self,
        task: AgentTask,
        query: str,
        num_results: int,
        country: Optional[str],
        search_lang: Optional[str],
    ) -> AgentResult:
        """Perform news search via Brave News API."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                url = "https://api.search.brave.com/res/v1/news/search"
                headers = {
                    "X-Subscription-Token": self.api_key,
                    "Accept": "application/json",
                }
                params = {
                    "q": query,
                    "count": min(num_results, 20),  # Brave limits to 20 per request
                }

                # Add optional parameters if provided
                if country:
                    params["country"] = country
                if search_lang:
                    params["search_lang"] = search_lang

                logger.info(
                    f"[{self.name}] Calling Brave News API with params: {params}"
                )

                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()

                data = resp.json()
                logger.info(
                    f"[{self.name}] Brave News API response status: {resp.status_code}"
                )

                results = []
                if "news" in data and "results" in data["news"]:
                    for result in data["news"]["results"][:num_results]:
                        results.append({
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "snippet": result.get("description", ""),
                            "source": result.get("url", ""),
                            "age": result.get("age"),
                        })

                output = {
                    "query": query,
                    "num_results": len(results),
                    "results": results,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "brave_news_search",
                }

                logger.info(
                    f"[{self.name}] Found {len(results)} news results for '{query}' "
                    f"via Brave"
                )

                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=output,
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning(
                    f"[{self.name}] Brave News API authentication failed (401)"
                )
            elif e.response.status_code == 429:
                logger.warning(f"[{self.name}] Brave News API rate limited (429)")
            else:
                logger.error(f"[{self.name}] Brave News API error: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Brave News API error: {e}",
            )
        except Exception as e:
            logger.error(f"[{self.name}] Brave News API request failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Brave News API request failed: {str(e)}",
            )

    async def verify(self, result: AgentResult) -> bool:
        """Verify Brave Search result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        # Search results should have some content
        if not result.output:
            logger.warning(f"Result {result.task_id}: Empty output")
            return False

        # Should have timestamp
        if "timestamp" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing timestamp")
            return False

        # Should have results array (even if empty, it's still valid)
        if "results" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing results array")
            return False

        # Check that results is a list
        if not isinstance(result.output["results"], list):
            logger.warning(
                f"Result {result.task_id}: results is not a list, "
                f"got {type(result.output['results'])}"
            )
            return False

        # Verify each result has expected fields
        for i, res in enumerate(result.output["results"]):
            if not isinstance(res, dict):
                logger.warning(
                    f"Result {result.task_id}: result[{i}] is not a dict"
                )
                return False
            if "title" not in res or "url" not in res:
                logger.warning(
                    f"Result {result.task_id}: result[{i}] missing title or url"
                )
                return False

        return True
