"""
Cipher Headless Browser Service — Full web browsing for agents.

Gives Cipher the same power as a human sitting at a browser:
- Visit any URL and get the fully rendered DOM (JS-rendered content)
- Take screenshots of pages
- Extract structured data from rendered pages
- Fill forms and click buttons
- Scroll and interact with dynamic content

Architecture:
- Playwright (Chromium) for full browser capabilities
- Lazy initialization — browser only launches when needed
- Auto-shutdown after configurable idle time to save RAM
- Fallback to httpx + BeautifulSoup for simple pages
- Memory-conscious: single process, GPU disabled, minimal Chromium

Memory budget: ~150-200MB when browser is active, 0 when idle.
"""

import asyncio
import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.logging import logger

# Browser state
_browser = None
_context = None
_last_used = 0
_lock = asyncio.Lock()
_IDLE_TIMEOUT = 120  # Shut down browser after 2 min idle


class BrowserResult:
    """Result from a browser operation."""

    def __init__(
        self,
        success: bool = False,
        url: str = "",
        title: str = "",
        text: str = "",
        html: str = "",
        screenshot_b64: str = "",
        links: list[dict] = None,
        metadata: dict = None,
        error: str = "",
        execution_time_ms: float = 0,
    ):
        self.success = success
        self.url = url
        self.title = title
        self.text = text
        self.html = html
        self.screenshot_b64 = screenshot_b64
        self.links = links or []
        self.metadata = metadata or {}
        self.error = error
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> dict:
        d = {
            "success": self.success,
            "url": self.url,
            "title": self.title,
            "text_length": len(self.text),
            "html_length": len(self.html),
            "has_screenshot": bool(self.screenshot_b64),
            "links_count": len(self.links),
            "metadata": self.metadata,
            "execution_time_ms": self.execution_time_ms,
        }
        if self.error:
            d["error"] = self.error
        return d


async def _ensure_browser():
    """Lazy-initialize Playwright browser. Returns (browser, context)."""
    global _browser, _context, _last_used

    if _browser and _context:
        _last_used = time.time()
        return _browser, _context

    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--no-zygote",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--mute-audio",
                "--no-first-run",
                "--disable-features=TranslateUI",
                "--disable-background-timer-throttling",
            ],
        )
        _context = await _browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            java_script_enabled=True,
            bypass_csp=True,
        )
        _last_used = time.time()

        # Start idle monitor
        asyncio.create_task(_idle_shutdown_monitor())

        logger.info("[HeadlessBrowser] Chromium launched successfully")
        return _browser, _context

    except ImportError:
        logger.error("[HeadlessBrowser] Playwright not installed — run: pip install playwright && playwright install chromium")
        raise RuntimeError("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    except Exception as e:
        logger.error(f"[HeadlessBrowser] Failed to launch: {e}")
        raise


async def _idle_shutdown_monitor():
    """Auto-shutdown browser after idle timeout to free RAM."""
    global _browser, _context, _last_used
    while _browser:
        await asyncio.sleep(30)
        if _browser and (time.time() - _last_used) > _IDLE_TIMEOUT:
            logger.info("[HeadlessBrowser] Idle timeout — shutting down to free RAM")
            await shutdown()
            break


async def shutdown():
    """Gracefully shut down the browser."""
    global _browser, _context
    try:
        if _context:
            await _context.close()
        if _browser:
            await _browser.close()
    except Exception as e:
        logger.warning(f"[HeadlessBrowser] Shutdown error: {e}")
    finally:
        _context = None
        _browser = None
        logger.info("[HeadlessBrowser] Shut down — RAM freed")


def is_running() -> bool:
    """Check if the browser is currently active."""
    return _browser is not None


# ── Public API ──────────────────────────────────────────────────


async def visit_page(
    url: str,
    wait_for: str = "networkidle",
    timeout: int = 30000,
    extract_text: bool = True,
    extract_links: bool = True,
    take_screenshot: bool = False,
    scroll_to_bottom: bool = False,
    wait_selector: Optional[str] = None,
) -> BrowserResult:
    """
    Visit a URL with full browser rendering and extract content.

    Args:
        url: URL to visit
        wait_for: Wait strategy - "networkidle", "load", "domcontentloaded"
        timeout: Timeout in milliseconds
        extract_text: Extract visible text content
        extract_links: Extract all links from the page
        take_screenshot: Capture a screenshot (base64 PNG)
        scroll_to_bottom: Scroll to bottom to trigger lazy-loaded content
        wait_selector: Wait for a specific CSS selector before extracting
    """
    start = time.time()

    async with _lock:
        try:
            browser, context = await _ensure_browser()
            page = await context.new_page()

            try:
                # Navigate
                await page.goto(url, wait_until=wait_for, timeout=timeout)

                # Wait for specific element if requested
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=5000)
                    except Exception:
                        pass

                # Scroll to bottom for lazy-loaded content
                if scroll_to_bottom:
                    await _scroll_page(page)

                # Extract data
                title = await page.title()
                current_url = page.url

                text = ""
                if extract_text:
                    text = await page.evaluate("""
                        () => {
                            // Remove scripts, styles, hidden elements
                            const remove = document.querySelectorAll('script, style, noscript, iframe, [hidden], [aria-hidden="true"]');
                            remove.forEach(el => el.remove());
                            return document.body ? document.body.innerText : '';
                        }
                    """)

                html = ""
                try:
                    html = await page.content()
                except Exception:
                    pass

                links = []
                if extract_links:
                    links = await page.evaluate("""
                        () => {
                            return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                                text: a.innerText.trim().substring(0, 100),
                                href: a.href,
                                rel: a.rel || ''
                            })).filter(l => l.href && !l.href.startsWith('javascript:'));
                        }
                    """)

                screenshot_b64 = ""
                if take_screenshot:
                    screenshot_bytes = await page.screenshot(full_page=False, type="png")
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                # Extract metadata
                metadata = await page.evaluate("""
                    () => {
                        const getMeta = (name) => {
                            const el = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
                            return el ? el.content : '';
                        };
                        return {
                            description: getMeta('description'),
                            og_title: getMeta('og:title'),
                            og_description: getMeta('og:description'),
                            og_image: getMeta('og:image'),
                            canonical: (document.querySelector('link[rel="canonical"]') || {}).href || '',
                            h1: Array.from(document.querySelectorAll('h1')).map(h => h.innerText.trim()).filter(Boolean),
                            h2: Array.from(document.querySelectorAll('h2')).map(h => h.innerText.trim()).filter(Boolean),
                            images_count: document.querySelectorAll('img').length,
                            forms_count: document.querySelectorAll('form').length,
                            buttons_count: document.querySelectorAll('button, input[type="submit"]').length,
                        };
                    }
                """)

                exec_ms = (time.time() - start) * 1000

                return BrowserResult(
                    success=True,
                    url=current_url,
                    title=title,
                    text=text[:50000],  # Cap at 50K chars
                    html=html[:100000],  # Cap at 100K chars
                    screenshot_b64=screenshot_b64,
                    links=links[:200],  # Cap at 200 links
                    metadata=metadata,
                    execution_time_ms=exec_ms,
                )

            finally:
                await page.close()

        except RuntimeError as e:
            # Playwright not installed — fall back to httpx
            if "not installed" in str(e):
                return await _fallback_fetch(url, start)
            raise
        except Exception as e:
            exec_ms = (time.time() - start) * 1000
            logger.error(f"[HeadlessBrowser] visit_page failed: {e}")
            return BrowserResult(
                success=False,
                url=url,
                error=str(e),
                execution_time_ms=exec_ms,
            )


async def take_screenshot(
    url: str,
    full_page: bool = False,
    viewport_width: int = 1280,
    viewport_height: int = 900,
) -> BrowserResult:
    """Take a screenshot of a URL. Returns base64 PNG."""
    start = time.time()

    async with _lock:
        try:
            browser, context = await _ensure_browser()
            page = await context.new_page()

            try:
                await page.set_viewport_size({"width": viewport_width, "height": viewport_height})
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Small delay for animations to settle
                await asyncio.sleep(1)

                screenshot_bytes = await page.screenshot(full_page=full_page, type="png")
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                exec_ms = (time.time() - start) * 1000
                return BrowserResult(
                    success=True,
                    url=page.url,
                    title=await page.title(),
                    screenshot_b64=screenshot_b64,
                    execution_time_ms=exec_ms,
                )
            finally:
                await page.close()

        except Exception as e:
            exec_ms = (time.time() - start) * 1000
            return BrowserResult(success=False, url=url, error=str(e), execution_time_ms=exec_ms)


async def extract_structured_data(
    url: str,
    selectors: dict[str, str],
) -> BrowserResult:
    """
    Extract structured data using CSS selectors.

    Args:
        url: URL to visit
        selectors: Dict mapping field names to CSS selectors
            e.g. {"title": "h1", "price": ".product-price", "description": ".product-desc"}

    Returns:
        BrowserResult with metadata containing extracted fields
    """
    start = time.time()

    async with _lock:
        try:
            browser, context = await _ensure_browser()
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                extracted = {}
                for field_name, selector in selectors.items():
                    try:
                        elements = await page.query_selector_all(selector)
                        values = []
                        for el in elements[:10]:  # Max 10 per selector
                            text = await el.inner_text()
                            values.append(text.strip())
                        extracted[field_name] = values if len(values) > 1 else (values[0] if values else "")
                    except Exception:
                        extracted[field_name] = ""

                exec_ms = (time.time() - start) * 1000
                return BrowserResult(
                    success=True,
                    url=page.url,
                    title=await page.title(),
                    metadata={"extracted": extracted, "selectors_used": selectors},
                    execution_time_ms=exec_ms,
                )
            finally:
                await page.close()

        except Exception as e:
            exec_ms = (time.time() - start) * 1000
            return BrowserResult(success=False, url=url, error=str(e), execution_time_ms=exec_ms)


async def execute_js(url: str, script: str) -> BrowserResult:
    """Visit a URL and execute custom JavaScript, returning the result."""
    start = time.time()

    async with _lock:
        try:
            browser, context = await _ensure_browser()
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                result = await page.evaluate(script)

                exec_ms = (time.time() - start) * 1000
                return BrowserResult(
                    success=True,
                    url=page.url,
                    title=await page.title(),
                    metadata={"js_result": result},
                    execution_time_ms=exec_ms,
                )
            finally:
                await page.close()

        except Exception as e:
            exec_ms = (time.time() - start) * 1000
            return BrowserResult(success=False, url=url, error=str(e), execution_time_ms=exec_ms)


async def scrape_product_pages(
    url: str,
    product_selector: str = ".product, .product-card, [data-product]",
) -> BrowserResult:
    """
    Scrape product information from an e-commerce page.
    Specialized for competitor analysis.
    """
    start = time.time()

    async with _lock:
        try:
            browser, context = await _ensure_browser()
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Scroll to load lazy products
                await _scroll_page(page)

                products = await page.evaluate(f"""
                    () => {{
                        const cards = document.querySelectorAll('{product_selector}');
                        if (cards.length > 0) {{
                            return Array.from(cards).slice(0, 50).map(card => ({{
                                name: (card.querySelector('h2, h3, h4, .product-title, .product-name') || {{}}).innerText || '',
                                price: (card.querySelector('.price, .product-price, [data-price]') || {{}}).innerText || '',
                                image: (card.querySelector('img') || {{}}).src || '',
                                link: (card.querySelector('a') || {{}}).href || '',
                                description: (card.querySelector('.description, .product-description, p') || {{}}).innerText || '',
                            }}));
                        }}
                        // Fallback: try to find any product-like content
                        return Array.from(document.querySelectorAll('h2, h3')).slice(0, 20).map(h => ({{
                            name: h.innerText.trim(),
                            price: '',
                            image: '',
                            link: (h.closest('a') || {{}}).href || '',
                            description: '',
                        }}));
                    }}
                """)

                # Also get page-level data
                page_data = await page.evaluate("""
                    () => ({
                        title: document.title,
                        description: (document.querySelector('meta[name="description"]') || {}).content || '',
                        canonical: (document.querySelector('link[rel="canonical"]') || {}).href || '',
                        total_images: document.querySelectorAll('img').length,
                        total_links: document.querySelectorAll('a').length,
                        has_cart: !!document.querySelector('[class*="cart"], [id*="cart"], .add-to-cart'),
                        has_search: !!document.querySelector('[type="search"], .search, #search'),
                        has_reviews: !!document.querySelector('[class*="review"], [class*="rating"], .stars'),
                    })
                """)

                exec_ms = (time.time() - start) * 1000
                return BrowserResult(
                    success=True,
                    url=page.url,
                    title=await page.title(),
                    metadata={
                        "products": products,
                        "products_count": len(products),
                        "page_data": page_data,
                    },
                    execution_time_ms=exec_ms,
                )
            finally:
                await page.close()

        except Exception as e:
            exec_ms = (time.time() - start) * 1000
            return BrowserResult(success=False, url=url, error=str(e), execution_time_ms=exec_ms)


# ── Helpers ──────────────────────────────────────────────────────


async def _scroll_page(page, max_scrolls: int = 5):
    """Scroll page to bottom to trigger lazy-loaded content."""
    for i in range(max_scrolls):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(0.5)
    # Scroll back to top
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(0.3)


async def _fallback_fetch(url: str, start_time: float) -> BrowserResult:
    """Fallback to httpx + BeautifulSoup when Playwright isn't available."""
    logger.info(f"[HeadlessBrowser] Using httpx fallback for {url}")
    try:
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts and styles
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string if soup.title else ""

        links = []
        for a in soup.find_all("a", href=True)[:200]:
            links.append({
                "text": a.get_text(strip=True)[:100],
                "href": a["href"],
                "rel": a.get("rel", ""),
            })

        # Metadata
        def get_meta(name):
            tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
            return tag["content"] if tag and tag.get("content") else ""

        metadata = {
            "description": get_meta("description"),
            "og_title": get_meta("og:title"),
            "og_description": get_meta("og:description"),
            "og_image": get_meta("og:image"),
            "h1": [h.get_text(strip=True) for h in soup.find_all("h1")][:5],
            "h2": [h.get_text(strip=True) for h in soup.find_all("h2")][:10],
            "images_count": len(soup.find_all("img")),
            "fallback_mode": True,
        }

        exec_ms = (time.time() - start_time) * 1000
        return BrowserResult(
            success=True,
            url=str(resp.url),
            title=title,
            text=text[:50000],
            html=resp.text[:100000],
            links=links,
            metadata=metadata,
            execution_time_ms=exec_ms,
        )

    except Exception as e:
        exec_ms = (time.time() - start_time) * 1000
        return BrowserResult(
            success=False,
            url=url,
            error=f"Fallback fetch failed: {e}",
            execution_time_ms=exec_ms,
        )


def get_status() -> dict:
    """Get current browser status."""
    return {
        "running": is_running(),
        "idle_timeout_seconds": _IDLE_TIMEOUT,
        "last_used": datetime.fromtimestamp(_last_used).isoformat() if _last_used else None,
        "idle_seconds": int(time.time() - _last_used) if _last_used else None,
    }
