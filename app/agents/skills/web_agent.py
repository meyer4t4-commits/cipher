"""
Web Browsing Agent - HTTP requests, web scraping, and API interaction.
"""

import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class WebAgent(BaseAgent):
    """Make HTTP requests, scrape web content, and interact with APIs."""

    def __init__(self, timeout_seconds: int = 30):
        """Initialize the web agent."""
        super().__init__(
            name="web_agent",
            description="HTTP requests, web scraping, and API interaction",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="http_request",
                    description="Make HTTP requests (GET, POST, PUT, DELETE)",
                    category="data",
                    timeout_seconds=timeout_seconds,
                ),
                AgentCapability(
                    name="scrape_html",
                    description="Scrape and parse HTML content",
                    category="data",
                    timeout_seconds=timeout_seconds,
                ),
                AgentCapability(
                    name="api_json",
                    description="Interact with JSON APIs",
                    category="data",
                    timeout_seconds=timeout_seconds,
                ),
                AgentCapability(
                    name="form_submit",
                    description="Parse forms and simulate submission",
                    category="data",
                    timeout_seconds=timeout_seconds,
                ),
            ],
        )
        self.timeout = timeout_seconds
        self.rate_limits: dict[str, int] = {}  # Domain -> request count
        self._session = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP client session."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
        return self._session

    def _is_safe_url(self, url: str) -> bool:
        """Validate URL is safe to request."""
        try:
            parsed = urlparse(url)

            # Whitelist schemes
            if parsed.scheme not in ("http", "https"):
                return False

            # Check for localhost
            if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
                return False

            # Basic URL validation
            if not parsed.hostname:
                return False

            return True
        except Exception:
            return False

    async def validate(self, task: AgentTask) -> bool:
        """Validate the web task."""
        if not await super().validate(task):
            return False

        # Check for method parameter
        method = task.params.get("method", "GET").upper()
        if method not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"):
            logger.warning(f"Task {task.task_id}: Invalid HTTP method {method}")
            return False

        # Check for URL
        if "url" not in task.params:
            logger.warning(f"Task {task.task_id}: Missing 'url' parameter")
            return False

        url = task.params["url"]
        if not self._is_safe_url(url):
            logger.warning(f"Task {task.task_id}: Unsafe URL {url}")
            return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a web request."""
        try:
            session = await self._get_session()

            url = task.params["url"]
            method = task.params.get("method", "GET").upper()
            headers = task.params.get("headers", {})
            data = task.params.get("data")
            json_body = task.params.get("json")
            params = task.params.get("params")

            logger.debug(f"[{self.name}] {method} {url}")

            # Make request
            response = await session.request(
                method,
                url,
                headers=headers,
                data=data,
                json=json_body,
                params=params,
                follow_redirects=True,
            )

            # Parse response
            content_type = response.headers.get("content-type", "")
            status_code = response.status_code

            output = {
                "url": str(response.url),
                "status_code": status_code,
                "headers": dict(response.headers),
            }

            if "application/json" in content_type:
                try:
                    output["data"] = response.json()
                except json.JSONDecodeError:
                    output["text"] = response.text[:1000]
            else:
                output["text"] = response.text[:2000]

            success = 200 <= status_code < 300

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=success,
                output=output,
                error=None if success else f"HTTP {status_code}",
            )

        except Exception as e:
            logger.error(f"[{self.name}] Request failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def scrape_html(self, url: str, selector: Optional[str] = None) -> dict[str, Any]:
        """
        Scrape HTML content from a URL.

        Args:
            url: URL to scrape
            selector: CSS selector to extract specific elements

        Returns:
            Dict with scraped data
        """
        try:
            session = await self._get_session()
            response = await session.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)

            result = {
                "url": url,
                "title": soup.title.string if soup.title else None,
                "text": text[:2000],
                "links": [],
            }

            # Extract links
            for link in soup.find_all("a", href=True):
                result["links"].append({
                    "text": link.get_text(strip=True),
                    "href": link["href"],
                })

            # Extract by selector if provided
            if selector:
                elements = soup.select(selector)
                result["selected_elements"] = [str(el) for el in elements[:10]]

            return result

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            return {"error": str(e)}

    async def verify(self, result: AgentResult) -> bool:
        """Verify web request result."""
        if not result.success:
            # Check if we have HTTP error details
            if isinstance(result.output, dict):
                return "status_code" in result.output
            return False

        # Verify we have response structure
        if not isinstance(result.output, dict):
            return False

        # Check required fields
        required_fields = ["status_code", "url"]
        for field in required_fields:
            if field not in result.output:
                logger.warning(f"Result {result.task_id}: Missing '{field}'")
                return False

        # Verify status code
        status_code = result.output.get("status_code")
        if not isinstance(status_code, int):
            return False

        if not (200 <= status_code < 300):
            logger.warning(f"Result {result.task_id}: Status {status_code} but success=True")
            return False

        # Verify we got some content
        has_content = "data" in result.output or "text" in result.output
        if not has_content:
            logger.warning(f"Result {result.task_id}: No response content")
            return False

        return True


class WebAgentFactory:
    """Factory for creating web agents with different configurations."""

    @staticmethod
    def create_scraper() -> WebAgent:
        """Create a web agent optimized for scraping."""
        agent = WebAgent(timeout_seconds=60)
        agent.description = "Web scraper agent with 60s timeout"
        return agent

    @staticmethod
    def create_api_client() -> WebAgent:
        """Create a web agent optimized for API calls."""
        agent = WebAgent(timeout_seconds=15)
        agent.description = "API client agent with 15s timeout"
        return agent
