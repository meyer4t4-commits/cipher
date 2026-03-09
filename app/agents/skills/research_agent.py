"""
Research & Intelligence Agent - Web search, news, market research, competitor analysis.
Uses Brave Search API (preferred) with DuckDuckGo HTML scraping as fallback.
"""

import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


class ResearchAgent(BaseAgent):
    """Research, analysis, and intelligence gathering."""

    def __init__(self):
        """Initialize the research agent."""
        super().__init__(
            name="research_agent",
            description="Web search, news, research, and market intelligence",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="web_search",
                    description="Search the web for information",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="news_search",
                    description="Search for news articles",
                    category="data",
                    timeout_seconds=20,
                ),
                AgentCapability(
                    name="academic_search",
                    description="Search academic papers and research",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="competitor_analysis",
                    description="Analyze competitors and market",
                    category="data",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="market_research",
                    description="Research market trends and data",
                    category="data",
                    timeout_seconds=45,
                ),
                AgentCapability(
                    name="fact_check",
                    description="Verify facts and check sources",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="sentiment_analysis",
                    description="Analyze sentiment from text and social media",
                    category="data",
                    timeout_seconds=20,
                ),
                AgentCapability(
                    name="summarize",
                    description="Summarize research findings",
                    category="data",
                    timeout_seconds=30,
                ),
            ],
        )

    async def validate(self, task: AgentTask) -> bool:
        """Validate research task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation") or task.params.get("action", "web_search")

        # Normalize
        if operation in ("search", "web", "google"):
            operation = "web_search"

        # Ensure query parameter exists for search operations
        search_ops = ("web_search", "news_search", "academic_search", "search")
        if operation in search_ops:
            if "query" not in task.params:
                # Fallback: use the instruction as the query
                task.params["query"] = task.instruction
                logger.info(f"Task {task.task_id}: Using instruction as query fallback")

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute research operation."""
        # Support both "operation" and "action" param keys; default to web_search
        operation = task.params.get("operation") or task.params.get("action", "web_search")

        # Normalize common variations
        if operation in ("search", "web", "google"):
            operation = "web_search"
        elif operation in ("news", "news_search"):
            operation = "news_search"

        try:
            query = task.params.get("query", "")
            if operation == "web_search":
                await self.emit_progress(f"Searching the web for '{query[:50]}'...")
                return await self._web_search(task)
            elif operation == "news_search":
                await self.emit_progress(f"Searching news for '{query[:50]}'...")
                return await self._news_search(task)
            elif operation == "academic_search":
                await self.emit_progress("Searching academic papers...")
                return await self._academic_search(task)
            elif operation == "competitor_analysis":
                await self.emit_progress("Running competitor analysis...")
                return await self._competitor_analysis(task)
            elif operation == "market_research":
                await self.emit_progress("Researching market data...")
                return await self._market_research(task)
            elif operation == "fact_check":
                await self.emit_progress("Fact-checking...")
                return await self._fact_check(task)
            elif operation == "sentiment_analysis":
                await self.emit_progress("Analyzing sentiment...")
                return await self._sentiment_analysis(task)
            elif operation == "summarize":
                await self.emit_progress("Summarizing content...")
                return await self._summarize(task)
            elif operation == "update_model_registry":
                await self.emit_progress("Running model discovery + benchmarks...")
                return await self._update_model_registry(task)
            else:
                # Fallback: if we have a query, do a web search
                if "query" in task.params:
                    await self.emit_progress(f"Searching for '{query[:50]}'...")
                    return await self._web_search(task)
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Research operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _web_search(self, task: AgentTask) -> AgentResult:
        """Web search — tries Brave Search API first, falls back to DuckDuckGo."""
        query = task.params.get("query", task.instruction)
        num_results = task.params.get("num_results", 10)

        logger.info(f"[{self.name}] Searching: {query}")

        # Try Brave Search API first (if key is configured)
        brave_key = getattr(settings, "brave_search_api_key", "")
        if brave_key:
            try:
                result = await self._brave_search(query, num_results, brave_key)
                if result and result.get("num_results", 0) > 0:
                    return AgentResult(
                        task_id=task.task_id,
                        agent_name=self.name,
                        success=True,
                        output=result,
                    )
                logger.warning(f"[{self.name}] Brave returned 0 results, falling back to DDG")
            except Exception as e:
                logger.warning(f"[{self.name}] Brave search failed ({e}), falling back to DDG")

        # Fallback: DuckDuckGo HTML scraping
        return await self._ddg_search(task, query, num_results)

    async def _brave_search(self, query: str, num_results: int, api_key: str) -> dict:
        """Search via Brave Search API."""
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": min(num_results, 20)},
                headers={
                    "X-Subscription-Token": api_key,
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("web", {}).get("results", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "source": item.get("url", ""),
                    "age": item.get("age", ""),
                })

            logger.info(f"[{self.name}] Brave returned {len(results)} results for '{query}'")

            return {
                "query": query,
                "num_results": len(results),
                "results": results,
                "source": "brave_search",
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _ddg_search(self, task: AgentTask, query: str, num_results: int) -> AgentResult:
        """Fallback: DuckDuckGo HTML scraping with retry and multiple strategies."""
        import random

        # Rotate user agents to reduce rate-limiting
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
        ]

        # Strategy 1: DDG HTML scraping
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                resp = await client.get(url, headers={
                    "User-Agent": random.choice(user_agents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                })
                resp.raise_for_status()
                logger.info(f"[{self.name}] DDG response: status={resp.status_code}, length={len(resp.text)}")

                soup = BeautifulSoup(resp.text, "html.parser")
                results = []

                # Try multiple CSS selectors (DDG changes these periodically)
                result_divs = soup.select(".result")
                if not result_divs:
                    result_divs = soup.select(".web-result")
                if not result_divs:
                    result_divs = soup.select("[data-testid='result']")

                logger.info(f"[{self.name}] Found {len(result_divs)} result divs in HTML")

                for result_div in result_divs[:num_results]:
                    title_el = result_div.select_one(".result__title a, .result__a, a.result__url")
                    snippet_el = result_div.select_one(".result__snippet, .result__body")
                    url_el = result_div.select_one(".result__url, .result__extras__url")

                    title = title_el.get_text(strip=True) if title_el else ""
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    link = ""

                    if title_el and title_el.get("href"):
                        href = title_el["href"]
                        href = href.replace("&amp;", "&")
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

                    displayed_url = url_el.get_text(strip=True) if url_el else link

                    if title:
                        results.append({
                            "title": title,
                            "url": link,
                            "snippet": snippet,
                            "source": displayed_url,
                        })

                if results:
                    output = {
                        "query": query,
                        "num_results": len(results),
                        "results": results,
                        "source": "duckduckgo_html",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    logger.info(f"[{self.name}] DDG HTML found {len(results)} results for '{query}'")
                    return AgentResult(
                        task_id=task.task_id,
                        agent_name=self.name,
                        success=True,
                        output=output,
                    )

                logger.warning(f"[{self.name}] DDG HTML returned 0 results, trying DDG API")

        except Exception as e:
            logger.warning(f"[{self.name}] DDG HTML scraping failed ({e}), trying DDG API")

        # Strategy 2: DDG Instant Answer API (structured JSON, no scraping)
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_redirect": "1", "no_html": "1"},
                    headers={"User-Agent": random.choice(user_agents)},
                )
                resp.raise_for_status()
                data = resp.json()

                results = []

                # Abstract (main answer)
                if data.get("Abstract"):
                    results.append({
                        "title": data.get("Heading", query),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("Abstract", ""),
                        "source": data.get("AbstractSource", ""),
                    })

                # Related topics
                for topic in data.get("RelatedTopics", [])[:num_results - len(results)]:
                    if isinstance(topic, dict):
                        if "Topics" in topic:
                            # Nested topic group
                            for sub in topic["Topics"][:3]:
                                if sub.get("Text"):
                                    results.append({
                                        "title": sub.get("Text", "")[:100],
                                        "url": sub.get("FirstURL", ""),
                                        "snippet": sub.get("Text", ""),
                                        "source": sub.get("FirstURL", ""),
                                    })
                        elif topic.get("Text"):
                            results.append({
                                "title": topic.get("Text", "")[:100],
                                "url": topic.get("FirstURL", ""),
                                "snippet": topic.get("Text", ""),
                                "source": topic.get("FirstURL", ""),
                            })

                # Results section
                for item in data.get("Results", [])[:num_results - len(results)]:
                    if item.get("Text"):
                        results.append({
                            "title": item.get("Text", "")[:100],
                            "url": item.get("FirstURL", ""),
                            "snippet": item.get("Text", ""),
                            "source": item.get("FirstURL", ""),
                        })

                if results:
                    output = {
                        "query": query,
                        "num_results": len(results),
                        "results": results,
                        "source": "duckduckgo_api",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    logger.info(f"[{self.name}] DDG API found {len(results)} results for '{query}'")
                    return AgentResult(
                        task_id=task.task_id,
                        agent_name=self.name,
                        success=True,
                        output=output,
                    )

                logger.warning(f"[{self.name}] DDG API also returned 0 results")

        except Exception as e:
            logger.warning(f"[{self.name}] DDG API failed: {e}")

        # Strategy 3: DuckDuckGo Lite (simplest HTML, most reliable)
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}",
                    headers={
                        "User-Agent": random.choice(user_agents),
                        "Accept": "text/html",
                    },
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []

                # DDG Lite uses simple table rows with links
                for link in soup.select("a.result-link, td a[href^='http']")[:num_results]:
                    href = link.get("href", "")
                    title = link.get_text(strip=True)
                    if href and title and href.startswith("http"):
                        # Find snippet in next sibling or parent row
                        snippet = ""
                        parent_td = link.find_parent("td")
                        if parent_td:
                            next_td = parent_td.find_next_sibling("td")
                            if next_td:
                                snippet = next_td.get_text(strip=True)
                        # Also check the next row for snippet text
                        parent_tr = link.find_parent("tr")
                        if parent_tr and not snippet:
                            next_tr = parent_tr.find_next_sibling("tr")
                            if next_tr:
                                snippet_td = next_tr.find("td", class_="result-snippet")
                                if snippet_td:
                                    snippet = snippet_td.get_text(strip=True)

                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet,
                            "source": href,
                        })

                if results:
                    output = {
                        "query": query,
                        "num_results": len(results),
                        "results": results,
                        "source": "duckduckgo_lite",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    logger.info(f"[{self.name}] DDG Lite found {len(results)} results for '{query}'")
                    return AgentResult(
                        task_id=task.task_id,
                        agent_name=self.name,
                        success=True,
                        output=output,
                    )

        except Exception as e:
            logger.warning(f"[{self.name}] DDG Lite failed: {e}")

        # All strategies failed
        logger.error(f"[{self.name}] All search strategies failed for '{query}'")
        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=False,
            error=f"Web search failed: All search strategies exhausted (DDG HTML, DDG API, DDG Lite). Configure BRAVE_SEARCH_API_KEY for reliable results.",
        )

    async def _news_search(self, task: AgentTask) -> AgentResult:
        """Search for news articles — uses DuckDuckGo with 'news' appended."""
        query = task.params.get("query", task.instruction)
        # Append 'news' to bias results toward news articles
        news_query = f"{query} news"
        task.params["query"] = news_query
        return await self._web_search(task)

    async def _academic_search(self, task: AgentTask) -> AgentResult:
        """Search academic papers."""
        query = task.params.get("query", task.instruction)
        # Append academic terms to bias search results toward research papers
        academic_query = f"{query} research paper arxiv"
        task.params["query"] = academic_query
        return await self._web_search(task)

    async def _competitor_analysis(self, task: AgentTask) -> AgentResult:
        """Analyze competitors."""
        company = task.params.get("company", task.instruction)
        # Create search query focused on competitor analysis
        competitor_query = f"{company} competitor analysis market share"
        task.params["query"] = competitor_query
        return await self._web_search(task)

    async def _market_research(self, task: AgentTask) -> AgentResult:
        """Research market trends."""
        market = task.params.get("market", task.instruction)
        # Create search query focused on market research
        market_query = f"{market} market size growth trends 2025"
        task.params["query"] = market_query
        return await self._web_search(task)

    async def _fact_check(self, task: AgentTask) -> AgentResult:
        """Verify facts."""
        claim = task.params.get("claim", task.instruction)
        # Create search query focused on fact checking
        fact_check_query = f"{claim} fact check verification"
        task.params["query"] = fact_check_query
        return await self._web_search(task)

    async def _sentiment_analysis(self, task: AgentTask) -> AgentResult:
        """Analyze sentiment."""
        text = task.params.get("text", task.instruction)

        # Sentiment analysis requires NLP model integration; delegate to web search for related information
        sentiment_query = f"{text} sentiment opinion reviews"
        task.params["query"] = sentiment_query

        result = await self._web_search(task)

        # Add a note to output that this is web search results, not actual sentiment analysis
        if result.success and isinstance(result.output, dict):
            result.output["note"] = "Sentiment analysis requires NLP model integration. Returning web search results about the topic instead."

        return result

    async def _summarize(self, task: AgentTask) -> AgentResult:
        """Summarize research findings."""
        # Summarization requires context from findings; delegate to web search instead
        query = task.params.get("query") or task.params.get("topic", task.instruction)

        task.params["query"] = query
        result = await self._web_search(task)

        # Add a note to output explaining the limitation
        if result.success and isinstance(result.output, dict):
            result.output["note"] = "Summarization without additional context returns raw web search results. Pass a specific topic or query to summarize."

        return result

    async def _update_model_registry(self, task: AgentTask) -> AgentResult:
        """
        Run full model discovery + benchmarking.
        Called by the nightly cron task "model-registry-update".

        Scans X/Twitter, web search, and LiteLLM for new model releases,
        then benchmarks any new models and proposes routing updates.
        """
        try:
            from app.services.model_discovery import get_model_registry
            from app.services.self_research.model_evaluator import (
                compare_models, propose_routing_updates,
            )
            from app.services.llm_router import (
                MODEL_REGISTRY, save_model_benchmarks,
            )

            registry = get_model_registry()

            # Phase 1: Discovery from all sources
            await self.emit_progress("Phase 1: Scanning X, web, and LiteLLM for new models...")
            discovery_results = await registry.full_discovery()

            new_count = discovery_results.get("total_new", 0)
            x_signals = len(discovery_results.get("x_signals", []))
            web_signals = len(discovery_results.get("web_signals", []))

            await self.emit_progress(
                f"Discovery complete: {new_count} new models, "
                f"{x_signals} X signals, {web_signals} web signals"
            )

            # Phase 2: Benchmark if requested
            run_benchmarks = task.params.get("run_benchmarks", True)
            if run_benchmarks:
                await self.emit_progress("Phase 2: Benchmarking all models...")
                all_models = [info["model_id"] for info in MODEL_REGISTRY.values()]
                comparison = await compare_models(all_models)
                proposals = await propose_routing_updates(comparison)

                if proposals.get("model_map_overrides") or proposals.get("agent_model_overrides"):
                    reasoning = proposals.get("reasoning", [])
                    await self.emit_progress(
                        f"Found {len(reasoning)} routing improvements. Saving..."
                    )
                    save_model_benchmarks({
                        "comparison": comparison,
                        "proposals": proposals,
                        "model_map_overrides": proposals.get("model_map_overrides", {}),
                        "agent_model_overrides": proposals.get("agent_model_overrides", {}),
                    })
                else:
                    await self.emit_progress("Current routing is optimal. No changes needed.")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "discovery": discovery_results,
                    "new_models": new_count,
                    "x_signals": x_signals,
                    "web_signals": web_signals,
                    "benchmarks_run": run_benchmarks,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"Model registry update failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def verify(self, result: AgentResult) -> bool:
        """Verify research result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        # Research results should have some content
        if not result.output:
            logger.warning(f"Result {result.task_id}: Empty output")
            return False

        # Should have timestamp
        if "timestamp" not in result.output and "research_date" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing timestamp")
            return False

        return True
