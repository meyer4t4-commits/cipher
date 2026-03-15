"""
Headless Browser Agent — Full web browsing capabilities for Cipher.

This is Cipher's eyes on the internet. While web_agent does raw HTTP,
this agent renders pages like a real browser — JavaScript execution,
dynamic content loading, screenshots, and structured data extraction.

Use cases:
- Competitor website analysis (see what customers actually see)
- Screenshot competitor storefronts
- Extract product data from JS-rendered pages
- Scrape pricing, reviews, and layouts
- Fill forms and interact with web apps
- Monitor competitor changes over time

Architecture:
- Wraps app/services/headless_browser.py (Playwright/Chromium)
- Falls back to httpx+BeautifulSoup if Playwright isn't installed
- Memory-conscious: browser auto-shuts after 2 min idle
"""

import json
import time
from typing import Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class HeadlessBrowserAgent(BaseAgent):
    """Full headless browser agent — Cipher's eyes on the web."""

    def __init__(self):
        super().__init__(
            name="headless_browser_agent",
            description="Headless browser — visits pages, takes screenshots, extracts rendered content, scrapes products",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="visit",
                    description="Visit a URL and extract rendered text, links, and metadata",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="screenshot",
                    description="Take a full screenshot of a web page (returns base64 PNG)",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=45,
                ),
                AgentCapability(
                    name="extract",
                    description="Extract structured data using CSS selectors",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="scrape_products",
                    description="Scrape product listings from e-commerce pages",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="execute_js",
                    description="Visit a URL and run custom JavaScript",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=45,
                ),
                AgentCapability(
                    name="competitor_scan",
                    description="Full competitor analysis — screenshot + products + metadata + SEO",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="status",
                    description="Get browser status (running/idle/memory)",
                    category="data",
                    requires_approval=False,
                    timeout_seconds=5,
                ),
            ],
        )

    async def validate(self, task: AgentTask) -> bool:
        operation = task.params.get("operation", "")
        valid = {cap.name for cap in self.capabilities}
        if operation not in valid:
            logger.warning(f"[headless_browser] Unknown operation '{operation}'")
            return False
        if operation not in ("status",) and not task.params.get("url"):
            # Most operations need a URL
            if operation not in ("status",):
                url_in_instruction = "http" in (task.instruction or "").lower()
                if not url_in_instruction:
                    logger.warning(f"[headless_browser] Missing url parameter")
                    return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        operation = task.params.get("operation", "")
        url = task.params.get("url", "")

        # Extract URL from instruction if not in params
        if not url and task.instruction:
            import re
            url_match = re.search(r'https?://\S+', task.instruction)
            if url_match:
                url = url_match.group()

        try:
            from app.services.headless_browser import (
                visit_page, take_screenshot, extract_structured_data,
                execute_js, scrape_product_pages, get_status
            )

            if operation == "status":
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=get_status(),
                )

            if operation == "visit":
                result = await visit_page(
                    url=url,
                    extract_text=task.params.get("extract_text", True),
                    extract_links=task.params.get("extract_links", True),
                    take_screenshot=task.params.get("screenshot", False),
                    scroll_to_bottom=task.params.get("scroll", False),
                    wait_selector=task.params.get("wait_selector"),
                )

            elif operation == "screenshot":
                result = await take_screenshot(
                    url=url,
                    full_page=task.params.get("full_page", False),
                    viewport_width=task.params.get("viewport_width", 1280),
                    viewport_height=task.params.get("viewport_height", 900),
                )

            elif operation == "extract":
                selectors = task.params.get("selectors", {})
                if not selectors:
                    return AgentResult(
                        task_id=task.task_id,
                        agent_name=self.name,
                        success=False,
                        error="'selectors' dict required for extract operation",
                    )
                result = await extract_structured_data(url=url, selectors=selectors)

            elif operation == "scrape_products":
                result = await scrape_product_pages(
                    url=url,
                    product_selector=task.params.get("product_selector", ".product, .product-card, [data-product]"),
                )

            elif operation == "execute_js":
                script = task.params.get("script", "")
                if not script:
                    return AgentResult(
                        task_id=task.task_id,
                        agent_name=self.name,
                        success=False,
                        error="'script' parameter required for execute_js",
                    )
                result = await execute_js(url=url, script=script)

            elif operation == "competitor_scan":
                # Full competitor analysis — combines multiple operations
                await self.emit_progress(f"Scanning competitor: {url}")
                output = await self._competitor_scan(url, task)
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=True,
                    output=output,
                )

            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )

            # Convert BrowserResult to AgentResult
            output = result.to_dict()
            if result.text:
                output["text_preview"] = result.text[:2000]
            if result.links:
                output["links_sample"] = result.links[:20]
            if result.screenshot_b64:
                output["screenshot_b64"] = result.screenshot_b64[:100] + "..."
                output["screenshot_full_length"] = len(result.screenshot_b64)

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=result.success,
                output=output,
                error=result.error if not result.success else None,
            )

        except Exception as e:
            logger.error(f"[headless_browser] Operation '{operation}' failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def verify(self, result: AgentResult) -> bool:
        if not result.success:
            return False
        if result.output is None:
            return False
        return True

    async def _competitor_scan(self, url: str, task: AgentTask) -> dict:
        """Full competitor scan: visit + screenshot + products + SEO analysis."""
        from app.services.headless_browser import visit_page, take_screenshot, scrape_product_pages

        scan = {
            "url": url,
            "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sections": {},
        }

        # 1. Visit and extract content
        await self.emit_progress("Extracting page content...")
        visit_result = await visit_page(
            url=url,
            extract_text=True,
            extract_links=True,
            scroll_to_bottom=True,
        )
        if visit_result.success:
            scan["title"] = visit_result.title
            scan["sections"]["content"] = {
                "text_length": len(visit_result.text),
                "text_preview": visit_result.text[:3000],
                "links_count": len(visit_result.links),
                "metadata": visit_result.metadata,
            }

        # 2. Screenshot
        await self.emit_progress("Taking screenshot...")
        ss_result = await take_screenshot(url=url)
        if ss_result.success:
            scan["sections"]["screenshot"] = {
                "has_screenshot": True,
                "screenshot_b64_length": len(ss_result.screenshot_b64),
            }
            scan["screenshot_b64"] = ss_result.screenshot_b64

        # 3. Scrape products
        await self.emit_progress("Scraping products...")
        products_result = await scrape_product_pages(url=url)
        if products_result.success:
            scan["sections"]["products"] = products_result.metadata

        # 4. LLM analysis of competitor
        await self.emit_progress("Analyzing competitor strategy...")
        try:
            from app.services.llm_router import chat_completion
            from app.models.schemas import ModelTier

            analysis_prompt = f"""Analyze this competitor website data and provide strategic insights.

URL: {url}
Title: {scan.get('title', 'N/A')}
Content preview: {visit_result.text[:2000] if visit_result.success else 'N/A'}
Products found: {json.dumps(products_result.metadata.get('products', [])[:5], indent=2) if products_result.success else 'None'}
Page metadata: {json.dumps(visit_result.metadata, indent=2) if visit_result.success else 'N/A'}

Provide a JSON analysis:
{{
    "brand_positioning": "how they position themselves",
    "strengths": ["top 3 strengths"],
    "weaknesses": ["top 3 weaknesses"],
    "pricing_strategy": "what their pricing tells us",
    "design_quality": "1-10 rating with brief note",
    "seo_quality": "1-10 rating with key observations",
    "conversion_elements": ["CTAs, trust badges, urgency elements found"],
    "key_differentiators": ["what makes them unique"],
    "opportunities_for_tallowroots": ["how TallowRoots can do better"]
}}"""

            response = await chat_completion(
                messages=[{"role": "user", "content": analysis_prompt}],
                model_tier=ModelTier.DEFAULT,
                temperature=0.3,
                max_tokens=1500,
            )

            content = response.get("content", "")
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                scan["sections"]["analysis"] = json.loads(content[start_idx:end_idx])
            else:
                scan["sections"]["analysis"] = {"raw": content[:1000]}

        except Exception as e:
            scan["sections"]["analysis"] = {"error": str(e)}

        return scan
