"""
Universal Browser Automation Service — Cipher's Eyes & Hands on the Web

Playwright-based browser that acts as a real human. Logs into sites,
maintains sessions, scrapes data, fills forms, clicks buttons, extracts
content. This is how Cipher interacts with ANY website without paid APIs.

Use cases:
  - Scrape X/Twitter without the $200/month API
  - Use ElevenLabs voice library through the browser
  - Fill forms, submit applications, monitor dashboards
  - Screenshot pages for visual analysis
  - Extract structured data from any site

Session cookies persist between runs in data/browser_sessions/.
"""

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from app.core.logging import logger

# Browser state
_browser = None
_browser_context = None
_page_cache: dict[str, Any] = {}  # tab_id -> page

SESSIONS_DIR = Path("data/browser_sessions")
SCREENSHOTS_DIR = Path("data/browser_screenshots")


async def _ensure_browser():
    """Launch browser if not running. Reuses existing instance."""
    global _browser, _browser_context

    if _browser and _browser.is_connected():
        return _browser_context

    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()

        # Launch with stealth settings
        _browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        # Create context with realistic fingerprint
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        storage_path = SESSIONS_DIR / "default_state.json"

        context_opts = {
            "viewport": {"width": 1440, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "color_scheme": "dark",
            "java_script_enabled": True,
        }

        # Load saved session if exists
        if storage_path.exists():
            context_opts["storage_state"] = str(storage_path)
            logger.info("Browser: loaded saved session state")

        _browser_context = await _browser.new_context(**context_opts)

        # Stealth: override navigator.webdriver
        await _browser_context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)

        logger.info("Browser: launched stealth Chromium")
        return _browser_context

    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        raise RuntimeError("Playwright not installed")
    except Exception as e:
        logger.error(f"Browser launch failed: {e}")
        raise


async def _get_page(tab_id: str = "main") -> Any:
    """Get or create a page/tab."""
    ctx = await _ensure_browser()

    if tab_id in _page_cache:
        page = _page_cache[tab_id]
        if not page.is_closed():
            return page

    page = await ctx.new_page()
    _page_cache[tab_id] = page

    # Block heavy resources for speed (images optional)
    await page.route("**/*.{woff,woff2,ttf,otf}", lambda route: route.abort())

    return page


async def save_session(name: str = "default"):
    """Save browser cookies/state to disk for persistence."""
    if not _browser_context:
        return {"error": "No browser session active"}

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{name}_state.json"

    try:
        state = await _browser_context.storage_state()
        Path(path).write_text(json.dumps(state, indent=2))
        logger.info(f"Browser: saved session '{name}'")
        return {"success": True, "path": str(path)}
    except Exception as e:
        return {"error": str(e)}


async def close_browser():
    """Gracefully close browser and save state."""
    global _browser, _browser_context, _page_cache

    if _browser_context:
        await save_session("default")
        await _browser_context.close()
    if _browser:
        await _browser.close()

    _browser = None
    _browser_context = None
    _page_cache.clear()
    logger.info("Browser: closed")


# ===================================================================
# Core Browser Actions — These are what the LLM calls via tool_calling
# ===================================================================


async def browser_navigate(url: str, tab_id: str = "main", wait_until: str = "domcontentloaded") -> dict:
    """Navigate to a URL and return page info."""
    page = await _get_page(tab_id)

    try:
        resp = await page.goto(url, wait_until=wait_until, timeout=30000)
        await page.wait_for_timeout(1000)  # Let JS settle

        title = await page.title()
        current_url = page.url

        return {
            "success": True,
            "url": current_url,
            "title": title,
            "status": resp.status if resp else None,
        }
    except Exception as e:
        return {"error": str(e), "url": url}


async def browser_extract_text(tab_id: str = "main", selector: str = "body", max_chars: int = 15000) -> dict:
    """Extract text content from the current page or a specific element."""
    page = await _get_page(tab_id)

    try:
        if selector == "body":
            # Smart extraction: try article/main first, fall back to body
            for sel in ["article", "main", "[role='main']", "body"]:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        if len(text.strip()) > 100:
                            text = text.strip()[:max_chars]
                            return {"success": True, "text": text, "selector": sel, "chars": len(text)}
                except Exception:
                    continue

        # Specific selector
        el = await page.query_selector(selector)
        if not el:
            return {"error": f"Element not found: {selector}"}

        text = await el.inner_text()
        text = text.strip()[:max_chars]
        return {"success": True, "text": text, "selector": selector, "chars": len(text)}

    except Exception as e:
        return {"error": str(e)}


async def browser_extract_elements(
    tab_id: str = "main",
    selector: str = "a",
    attributes: list[str] = None,
    max_results: int = 50,
) -> dict:
    """Extract structured data from multiple elements matching a selector.

    Great for: tweet lists, search results, product listings, form fields, links.
    """
    page = await _get_page(tab_id)
    if attributes is None:
        attributes = ["href", "src", "text", "class", "data-testid", "aria-label"]

    try:
        elements = await page.query_selector_all(selector)
        results = []

        for el in elements[:max_results]:
            item = {}
            for attr in attributes:
                if attr == "text":
                    try:
                        item["text"] = (await el.inner_text()).strip()[:500]
                    except Exception:
                        item["text"] = ""
                elif attr == "html":
                    try:
                        item["html"] = (await el.inner_html())[:1000]
                    except Exception:
                        item["html"] = ""
                else:
                    val = await el.get_attribute(attr)
                    if val:
                        item[attr] = val

            if item:
                results.append(item)

        return {
            "success": True,
            "selector": selector,
            "count": len(results),
            "elements": results,
        }
    except Exception as e:
        return {"error": str(e)}


async def browser_click(
    tab_id: str = "main",
    selector: str = None,
    text: str = None,
    wait_after: int = 1000,
) -> dict:
    """Click an element by selector or by visible text."""
    page = await _get_page(tab_id)

    try:
        if text:
            # Click by visible text (more human-like)
            await page.get_by_text(text, exact=False).first.click(timeout=10000)
        elif selector:
            await page.click(selector, timeout=10000)
        else:
            return {"error": "Provide either 'selector' or 'text' to click"}

        await page.wait_for_timeout(wait_after)

        return {
            "success": True,
            "clicked": text or selector,
            "url": page.url,
            "title": await page.title(),
        }
    except Exception as e:
        return {"error": str(e), "target": text or selector}


async def browser_type(
    tab_id: str = "main",
    selector: str = None,
    text: str = "",
    press_enter: bool = False,
    clear_first: bool = True,
    human_delay: int = 50,
) -> dict:
    """Type text into an input field with human-like delays."""
    page = await _get_page(tab_id)

    try:
        if selector:
            el = await page.query_selector(selector)
            if not el:
                return {"error": f"Input not found: {selector}"}

            if clear_first:
                await el.click(click_count=3)  # Select all
                await page.keyboard.press("Backspace")

            await el.type(text, delay=human_delay)
        else:
            # Type into whatever is focused
            await page.keyboard.type(text, delay=human_delay)

        if press_enter:
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(1500)

        return {"success": True, "typed": text[:100], "pressed_enter": press_enter}
    except Exception as e:
        return {"error": str(e)}


async def browser_scroll(
    tab_id: str = "main",
    direction: str = "down",
    amount: int = 3,
    selector: str = None,
) -> dict:
    """Scroll the page or a specific element."""
    page = await _get_page(tab_id)

    try:
        pixels = amount * 400
        delta = pixels if direction == "down" else -pixels

        if selector:
            el = await page.query_selector(selector)
            if el:
                await el.evaluate(f"el => el.scrollTop += {delta}")
        else:
            await page.evaluate(f"window.scrollBy(0, {delta})")

        await page.wait_for_timeout(800)

        return {
            "success": True,
            "direction": direction,
            "pixels": abs(delta),
            "url": page.url,
        }
    except Exception as e:
        return {"error": str(e)}


async def browser_screenshot(tab_id: str = "main", full_page: bool = False, name: str = None) -> dict:
    """Take a screenshot. Returns the file path."""
    page = await _get_page(tab_id)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    filename = name or f"screenshot_{int(time.time())}"
    path = SCREENSHOTS_DIR / f"{filename}.png"

    try:
        await page.screenshot(path=str(path), full_page=full_page)
        return {
            "success": True,
            "path": str(path),
            "url": page.url,
            "title": await page.title(),
        }
    except Exception as e:
        return {"error": str(e)}


async def browser_wait_for(tab_id: str = "main", selector: str = None, text: str = None, timeout: int = 10000) -> dict:
    """Wait for an element or text to appear on the page."""
    page = await _get_page(tab_id)

    try:
        if selector:
            await page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "found": selector}
        elif text:
            await page.get_by_text(text).first.wait_for(timeout=timeout)
            return {"success": True, "found": text}
        else:
            return {"error": "Provide 'selector' or 'text' to wait for"}
    except Exception as e:
        return {"error": f"Timeout waiting for: {selector or text}"}


async def browser_evaluate(tab_id: str = "main", script: str = "") -> dict:
    """Execute JavaScript on the page and return the result."""
    page = await _get_page(tab_id)

    try:
        result = await page.evaluate(script)
        return {"success": True, "result": result}
    except Exception as e:
        return {"error": str(e)}


async def browser_get_page_info(tab_id: str = "main") -> dict:
    """Get current page URL, title, and basic stats."""
    page = await _get_page(tab_id)

    try:
        return {
            "url": page.url,
            "title": await page.title(),
            "viewport": page.viewport_size,
        }
    except Exception as e:
        return {"error": str(e)}


# ===================================================================
# High-Level Compound Actions — Multi-step browser workflows
# ===================================================================


async def browser_login(
    url: str,
    username_selector: str,
    username: str,
    password_selector: str,
    password: str,
    submit_selector: str = None,
    submit_text: str = None,
    session_name: str = "default",
    tab_id: str = "main",
) -> dict:
    """Log into a website and save the session."""
    page = await _get_page(tab_id)

    try:
        # Navigate
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        # Fill username
        await page.fill(username_selector, username)
        await page.wait_for_timeout(500)

        # Fill password
        await page.fill(password_selector, password)
        await page.wait_for_timeout(500)

        # Submit
        if submit_selector:
            await page.click(submit_selector)
        elif submit_text:
            await page.get_by_text(submit_text, exact=False).first.click()
        else:
            await page.keyboard.press("Enter")

        # Wait for navigation
        await page.wait_for_timeout(5000)

        # Save session
        await save_session(session_name)

        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "session_saved": session_name,
        }
    except Exception as e:
        return {"error": str(e), "url": url}


async def scrape_x_feed(
    query: str = None,
    account: str = None,
    max_tweets: int = 20,
    tab_id: str = "x_scanner",
) -> dict:
    """
    Scrape X/Twitter feed or search results via browser.
    No API key needed — uses logged-in session.

    Args:
        query: Search query (e.g., "sovereign AI")
        account: Account to scrape (e.g., "AnthropicAI")
        max_tweets: Maximum tweets to collect
    """
    page = await _get_page(tab_id)

    try:
        if query:
            url = f"https://x.com/search?q={query}&src=typed_query&f=live"
        elif account:
            url = f"https://x.com/{account.lstrip('@')}"
        else:
            url = "https://x.com/home"

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Check if we need to log in
        current_url = page.url
        if "login" in current_url.lower() or "flow" in current_url.lower():
            return {
                "error": "Not logged in to X. Use browser_login first with your X credentials.",
                "hint": "Call browser_login with url='https://x.com/login', username_selector='input[autocomplete=\"username\"]', password_selector='input[type=\"password\"]'"
            }

        tweets = []
        scroll_attempts = 0
        max_scrolls = max_tweets // 4 + 2  # Rough estimate: ~4 tweets per scroll

        while len(tweets) < max_tweets and scroll_attempts < max_scrolls:
            # Extract tweet articles
            tweet_elements = await page.query_selector_all('article[data-testid="tweet"]')

            for el in tweet_elements:
                try:
                    text_el = await el.query_selector('[data-testid="tweetText"]')
                    text = await text_el.inner_text() if text_el else ""

                    user_el = await el.query_selector('[data-testid="User-Name"]')
                    user = await user_el.inner_text() if user_el else ""

                    time_el = await el.query_selector("time")
                    timestamp = await time_el.get_attribute("datetime") if time_el else ""

                    # Engagement metrics
                    metrics = {}
                    for metric_name in ["reply", "retweet", "like"]:
                        metric_el = await el.query_selector(f'[data-testid="{metric_name}"]')
                        if metric_el:
                            metric_text = await metric_el.inner_text()
                            metrics[metric_name] = metric_text.strip()

                    # Link to tweet
                    link_els = await el.query_selector_all('a[href*="/status/"]')
                    tweet_url = ""
                    for link_el in link_els:
                        href = await link_el.get_attribute("href")
                        if href and "/status/" in href:
                            tweet_url = f"https://x.com{href}" if href.startswith("/") else href
                            break

                    tweet_data = {
                        "text": text.strip()[:500],
                        "user": user.strip().split("\n")[0] if user else "",
                        "timestamp": timestamp,
                        "url": tweet_url,
                        "metrics": metrics,
                    }

                    # Deduplicate by text
                    if tweet_data["text"] and not any(t["text"] == tweet_data["text"] for t in tweets):
                        tweets.append(tweet_data)

                except Exception:
                    continue

            # Scroll for more
            await page.evaluate("window.scrollBy(0, 1200)")
            await page.wait_for_timeout(2000)
            scroll_attempts += 1

        return {
            "success": True,
            "source": query or account or "home",
            "count": len(tweets),
            "tweets": tweets[:max_tweets],
        }
    except Exception as e:
        return {"error": str(e)}


async def scrape_page_structured(
    url: str,
    item_selector: str,
    fields: dict[str, str],
    max_items: int = 50,
    tab_id: str = "main",
) -> dict:
    """
    Universal structured scraper. Navigate to a URL and extract
    repeated items with named fields.

    Example: scrape ElevenLabs voice library
        url = "https://elevenlabs.io/voice-library"
        item_selector = "[data-voice-card]"  # or whatever wraps each voice
        fields = {
            "name": ".voice-name",
            "description": ".voice-description",
            "play_button": "button[aria-label*='play']",
        }
    """
    page = await _get_page(tab_id)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        items = []
        elements = await page.query_selector_all(item_selector)

        for el in elements[:max_items]:
            item = {}
            for field_name, field_selector in fields.items():
                try:
                    child = await el.query_selector(field_selector)
                    if child:
                        item[field_name] = (await child.inner_text()).strip()[:300]
                except Exception:
                    item[field_name] = None
            if any(item.values()):
                items.append(item)

        return {
            "success": True,
            "url": url,
            "item_selector": item_selector,
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        return {"error": str(e), "url": url}


# ===================================================================
# ElevenLabs Browser Workflows — Voice Library & Cloning
# ===================================================================


async def elevenlabs_login(tab_id: str = "elevenlabs") -> dict:
    """
    Log into ElevenLabs using saved credentials from .env.
    Supports both Google OAuth and email/password login.
    Set ELEVENLABS_LOGIN_METHOD=google in .env for Google sign-in.
    """
    import os
    email = os.getenv("ELEVENLABS_LOGIN_EMAIL", "")
    password = os.getenv("ELEVENLABS_LOGIN_PASSWORD", "")
    login_method = os.getenv("ELEVENLABS_LOGIN_METHOD", "google").lower()

    if not email or not password:
        return {
            "error": "ElevenLabs credentials not set. Add ELEVENLABS_LOGIN_EMAIL and ELEVENLABS_LOGIN_PASSWORD to .env"
        }

    page = await _get_page(tab_id)

    try:
        await page.goto("https://elevenlabs.io/sign-in", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Check if already logged in (redirected to app)
        if "/app" in page.url or "/speech-synthesis" in page.url or "/voice-library" in page.url:
            await save_session("elevenlabs")
            return {"success": True, "message": "Already logged in", "url": page.url}

        if login_method == "google":
            # ── Google OAuth Flow ──
            # Click "Continue with Google" button on ElevenLabs
            google_clicked = False
            for btn_text in ["Continue with Google", "Sign in with Google", "Google"]:
                try:
                    await page.get_by_text(btn_text, exact=False).first.click(timeout=5000)
                    google_clicked = True
                    break
                except Exception:
                    continue

            if not google_clicked:
                # Try finding Google button by icon/class
                try:
                    google_btn = await page.query_selector(
                        'button[data-provider="google"], '
                        '[class*="google" i], '
                        'a[href*="accounts.google.com"], '
                        'button:has(svg), '
                        '[aria-label*="Google" i]'
                    )
                    if google_btn:
                        await google_btn.click()
                        google_clicked = True
                except Exception:
                    pass

            if not google_clicked:
                return {"error": "Could not find Google sign-in button on ElevenLabs"}

            # Wait for Google sign-in page
            await page.wait_for_timeout(3000)

            # Google OAuth page — enter email
            try:
                # Wait for Google's email input
                await page.wait_for_selector('input[type="email"]', timeout=10000)
                await page.fill('input[type="email"]', email)
                await page.wait_for_timeout(500)

                # Click "Next"
                try:
                    await page.get_by_text("Next", exact=False).first.click(timeout=5000)
                except Exception:
                    await page.keyboard.press("Enter")

                await page.wait_for_timeout(3000)

                # Google password page
                await page.wait_for_selector('input[type="password"]', timeout=10000)
                # Google needs a brief pause before typing (it validates email first)
                await page.wait_for_timeout(1000)
                await page.fill('input[type="password"]', password)
                await page.wait_for_timeout(500)

                # Click "Next"
                try:
                    await page.get_by_text("Next", exact=False).first.click(timeout=5000)
                except Exception:
                    await page.keyboard.press("Enter")

                # Wait for redirect back to ElevenLabs
                await page.wait_for_timeout(8000)

                # Handle "Allow" consent screen if it appears
                try:
                    allow_btn = await page.query_selector('button:has-text("Allow"), button:has-text("Continue"), #submit_approve_access')
                    if allow_btn:
                        await allow_btn.click()
                        await page.wait_for_timeout(5000)
                except Exception:
                    pass

            except Exception as e:
                return {
                    "error": f"Google OAuth flow failed: {e}",
                    "url": page.url,
                    "hint": "Google may require manual 2FA or CAPTCHA on first login. Try logging in once manually via the browser."
                }

        else:
            # ── Email/Password Flow ──
            email_input = await page.query_selector('input[type="email"], input[name="email"], input[placeholder*="email" i]')
            if email_input:
                await email_input.fill(email)
                await page.wait_for_timeout(500)
            else:
                try:
                    await page.get_by_text("Continue with email", exact=False).first.click(timeout=5000)
                    await page.wait_for_timeout(2000)
                    email_input = await page.query_selector('input[type="email"], input[name="email"]')
                    if email_input:
                        await email_input.fill(email)
                        await page.wait_for_timeout(500)
                except Exception:
                    pass

            password_input = await page.query_selector('input[type="password"]')
            if password_input:
                await password_input.fill(password)
                await page.wait_for_timeout(500)

            try:
                submit = await page.query_selector('button[type="submit"]')
                if submit:
                    await submit.click()
                else:
                    await page.get_by_text("Sign in", exact=False).first.click(timeout=5000)
            except Exception:
                await page.keyboard.press("Enter")

            await page.wait_for_timeout(5000)

        # Verify login succeeded
        current_url = page.url
        if any(x in current_url for x in ["/app", "/speech-synthesis", "/voice-library", "/voice-lab"]):
            await save_session("elevenlabs")
            return {"success": True, "url": current_url, "title": await page.title(), "method": login_method}
        elif "elevenlabs.io" in current_url and "sign-in" not in current_url:
            await save_session("elevenlabs")
            return {"success": True, "url": current_url, "title": await page.title(), "method": login_method}
        else:
            return {
                "error": "Login may have failed — check credentials or complete 2FA manually",
                "url": current_url,
                "method": login_method,
            }

    except Exception as e:
        return {"error": str(e)}


async def x_login(tab_id: str = "x_scanner") -> dict:
    """Log into X/Twitter using saved credentials from .env."""
    import os
    username = os.getenv("X_LOGIN_USERNAME", "")
    password = os.getenv("X_LOGIN_PASSWORD", "")

    if not username or not password:
        return {"error": "X credentials not set. Add X_LOGIN_USERNAME and X_LOGIN_PASSWORD to .env"}

    page = await _get_page(tab_id)

    try:
        await page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Check if already logged in
        if "/home" in page.url:
            await save_session("x")
            return {"success": True, "message": "Already logged in", "url": page.url}

        # Step 1: Enter username
        username_input = await page.query_selector('input[autocomplete="username"], input[name="text"]')
        if username_input:
            await username_input.fill(username)
            await page.wait_for_timeout(500)

        # Click Next
        try:
            await page.get_by_text("Next", exact=True).first.click(timeout=5000)
        except Exception:
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(3000)

        # Step 2: Handle possible "unusual activity" verification (email/phone)
        verify_input = await page.query_selector('input[data-testid="ocfEnterTextTextInput"]')
        if verify_input:
            # X sometimes asks for email or phone to verify
            email = os.getenv("ELEVENLABS_LOGIN_EMAIL", "")  # Same email
            await verify_input.fill(email)
            await page.wait_for_timeout(500)
            try:
                await page.get_by_text("Next", exact=True).first.click(timeout=5000)
            except Exception:
                await page.keyboard.press("Enter")
            await page.wait_for_timeout(3000)

        # Step 3: Enter password
        password_input = await page.query_selector('input[type="password"], input[name="password"]')
        if password_input:
            await password_input.fill(password)
            await page.wait_for_timeout(500)

        # Click Log in
        try:
            await page.get_by_text("Log in", exact=True).first.click(timeout=5000)
        except Exception:
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(5000)

        # Verify
        if "/home" in page.url or "x.com" in page.url and "login" not in page.url:
            await save_session("x")
            return {"success": True, "url": page.url, "title": await page.title()}
        else:
            return {"error": "X login may have failed — check credentials or complete 2FA", "url": page.url}

    except Exception as e:
        return {"error": str(e)}


async def elevenlabs_list_voices(
    category: str = "my_voices",
    max_voices: int = 50,
    tab_id: str = "elevenlabs",
) -> dict:
    """
    Browse ElevenLabs voice library.

    Categories:
        my_voices: Your personal voices (default)
        library: Public voice library
        cloned: Your cloned voices
    """
    page = await _get_page(tab_id)

    try:
        url_map = {
            "my_voices": "https://elevenlabs.io/app/voice-lab",
            "library": "https://elevenlabs.io/app/voice-library",
            "cloned": "https://elevenlabs.io/app/voice-lab",
        }

        target_url = url_map.get(category, url_map["my_voices"])
        current_url = page.url

        # Navigate if not already there
        if target_url not in current_url:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

        # Check if logged in
        if "sign-in" in page.url.lower() or "login" in page.url.lower():
            return {"error": "Not logged in to ElevenLabs. Use elevenlabs_login first."}

        voices = []

        # ElevenLabs voice cards — try multiple selectors (UI changes)
        voice_selectors = [
            '[data-testid*="voice"]',
            '[class*="voice-card"]',
            '[class*="VoiceCard"]',
            'div[role="button"][class*="voice"]',
            'tr[class*="voice"]',      # Table layout
            'div[class*="card"]',       # Generic cards
        ]

        elements = []
        for sel in voice_selectors:
            elements = await page.query_selector_all(sel)
            if len(elements) > 0:
                break

        if not elements:
            # Fallback: extract all visible text content as structured data
            text = await page.evaluate("""
                () => {
                    const items = [];
                    // Look for any repeated card-like structure
                    document.querySelectorAll('[class*="voice"], [class*="Voice"], [data-voice], .card').forEach(el => {
                        const text = el.innerText.trim();
                        if (text.length > 5 && text.length < 500) {
                            items.push(text);
                        }
                    });
                    return items.slice(0, 50);
                }
            """)
            if text:
                return {
                    "success": True,
                    "category": category,
                    "count": len(text),
                    "voices": [{"raw_text": t} for t in text],
                    "note": "Extracted raw text — UI selectors may need updating",
                }

            # Last resort: take screenshot + extract page text
            return {
                "success": True,
                "category": category,
                "count": 0,
                "voices": [],
                "page_text": (await browser_extract_text(tab_id=tab_id))["text"][:5000] if True else "",
                "note": "No voice cards found. Page text included for analysis.",
            }

        # Parse voice cards
        for el in elements[:max_voices]:
            try:
                voice = {}
                # Get all text content
                text = await el.inner_text()
                voice["raw_text"] = text.strip()[:300]

                # Try to extract name (usually first line or specific element)
                name_el = await el.query_selector('h3, h4, [class*="name"], [class*="Name"], strong, b')
                if name_el:
                    voice["name"] = (await name_el.inner_text()).strip()

                # Try to extract description
                desc_el = await el.query_selector('p, [class*="desc"], [class*="Desc"], span:not(:first-child)')
                if desc_el:
                    voice["description"] = (await desc_el.inner_text()).strip()[:200]

                # Try to get voice ID from data attributes or links
                voice_id = await el.get_attribute("data-voice-id")
                if not voice_id:
                    link = await el.query_selector("a[href*='voice']")
                    if link:
                        href = await link.get_attribute("href")
                        if href:
                            voice["link"] = href

                if voice_id:
                    voice["voice_id"] = voice_id

                # Labels/tags
                labels = await el.query_selector_all('[class*="tag"], [class*="Tag"], [class*="label"], [class*="Label"], [class*="badge"]')
                if labels:
                    voice["tags"] = []
                    for label in labels[:5]:
                        tag_text = await label.inner_text()
                        if tag_text.strip():
                            voice["tags"].append(tag_text.strip())

                if voice.get("name") or voice.get("raw_text"):
                    voices.append(voice)
            except Exception:
                continue

        return {
            "success": True,
            "category": category,
            "count": len(voices),
            "voices": voices,
            "url": page.url,
        }
    except Exception as e:
        return {"error": str(e)}


async def elevenlabs_clone_voice(
    voice_name: str,
    description: str = "",
    audio_file_paths: list[str] = None,
    tab_id: str = "elevenlabs",
) -> dict:
    """
    Clone a voice on ElevenLabs using the browser.
    Navigate to Voice Lab, click "Add Voice", upload audio samples, and create the clone.

    Args:
        voice_name: Name for the cloned voice
        description: Voice description
        audio_file_paths: List of paths to audio files for cloning
    """
    page = await _get_page(tab_id)

    try:
        # Navigate to Voice Lab
        await page.goto("https://elevenlabs.io/app/voice-lab", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        if "sign-in" in page.url.lower():
            return {"error": "Not logged in to ElevenLabs. Use elevenlabs_login first."}

        # Click "Add Voice" or "Create" button
        add_clicked = False
        for btn_text in ["Add Voice", "Create Voice", "Add Generative", "Instant Voice Cloning", "Clone"]:
            try:
                await page.get_by_text(btn_text, exact=False).first.click(timeout=3000)
                add_clicked = True
                await page.wait_for_timeout(2000)
                break
            except Exception:
                continue

        if not add_clicked:
            # Try clicking a plus/add button
            try:
                add_btn = await page.query_selector('button[aria-label*="add" i], button[aria-label*="create" i], [data-testid*="add"]')
                if add_btn:
                    await add_btn.click()
                    add_clicked = True
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

        if not add_clicked:
            return {
                "error": "Could not find 'Add Voice' button. UI may have changed.",
                "url": page.url,
                "suggestion": "Navigate manually and use browser(action='screenshot') to inspect the page"
            }

        # Look for Instant Voice Cloning option
        for option_text in ["Instant Voice Cloning", "Clone a voice", "Upload audio"]:
            try:
                await page.get_by_text(option_text, exact=False).first.click(timeout=3000)
                await page.wait_for_timeout(2000)
                break
            except Exception:
                continue

        # Fill in the voice name
        name_input = await page.query_selector('input[placeholder*="name" i], input[name="name"], input[aria-label*="name" i]')
        if name_input:
            await name_input.fill(voice_name)
            await page.wait_for_timeout(500)

        # Fill description if field exists
        if description:
            desc_input = await page.query_selector('textarea, input[placeholder*="desc" i], input[name="description"]')
            if desc_input:
                await desc_input.fill(description)
                await page.wait_for_timeout(500)

        # Upload audio files
        if audio_file_paths:
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(audio_file_paths)
                await page.wait_for_timeout(3000)
                logger.info(f"Uploaded {len(audio_file_paths)} audio files for voice cloning")
            else:
                return {
                    "partial": True,
                    "message": f"Voice name '{voice_name}' entered, but couldn't find file upload. Drag-drop may be needed.",
                    "url": page.url,
                }

        # Accept terms if checkbox present
        try:
            terms_checkbox = await page.query_selector('input[type="checkbox"]')
            if terms_checkbox:
                await terms_checkbox.click()
                await page.wait_for_timeout(500)
        except Exception:
            pass

        # Click create/clone button
        for submit_text in ["Clone Voice", "Create Voice", "Add Voice", "Generate", "Submit"]:
            try:
                await page.get_by_text(submit_text, exact=False).first.click(timeout=3000)
                await page.wait_for_timeout(5000)
                break
            except Exception:
                continue

        await save_session("elevenlabs")

        return {
            "success": True,
            "voice_name": voice_name,
            "url": page.url,
            "title": await page.title(),
            "message": f"Voice '{voice_name}' clone initiated. Check ElevenLabs dashboard for status.",
        }
    except Exception as e:
        return {"error": str(e)}


async def elevenlabs_get_usage(tab_id: str = "elevenlabs") -> dict:
    """Check ElevenLabs character/token usage and quota."""
    page = await _get_page(tab_id)

    try:
        # Navigate to subscription/usage page
        await page.goto("https://elevenlabs.io/app/subscription", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        if "sign-in" in page.url.lower():
            return {"error": "Not logged in to ElevenLabs. Use elevenlabs_login first."}

        # Extract usage info from the page
        text = await browser_extract_text(tab_id=tab_id)
        page_text = text.get("text", "")

        # Try to find specific usage elements
        usage_data = {}
        usage_selectors = [
            '[class*="usage"]', '[class*="Usage"]',
            '[class*="quota"]', '[class*="Quota"]',
            '[class*="characters"]', '[class*="Characters"]',
            '[class*="plan"]', '[class*="Plan"]',
        ]

        for sel in usage_selectors:
            els = await page.query_selector_all(sel)
            for el in els[:5]:
                try:
                    el_text = await el.inner_text()
                    if el_text.strip():
                        usage_data[sel] = el_text.strip()[:200]
                except Exception:
                    continue

        return {
            "success": True,
            "url": page.url,
            "usage": usage_data if usage_data else None,
            "page_text": page_text[:3000],
            "note": "Usage data extracted. Check page_text for character counts.",
        }
    except Exception as e:
        return {"error": str(e)}


# ===================================================================
# Master dispatch — called by tool_calling.py
# ===================================================================


async def execute_browser_action(action: str, params: dict) -> str:
    """
    Single entry point for all browser actions. Called from tool_calling.py.

    Actions:
        navigate, extract_text, extract_elements, click, type, scroll,
        screenshot, wait_for, evaluate, get_page_info, login, save_session,
        scrape_x, scrape_structured, close
    """
    action_map = {
        "navigate": browser_navigate,
        "extract_text": browser_extract_text,
        "extract_elements": browser_extract_elements,
        "click": browser_click,
        "type": browser_type,
        "scroll": browser_scroll,
        "screenshot": browser_screenshot,
        "wait_for": browser_wait_for,
        "evaluate": browser_evaluate,
        "get_page_info": browser_get_page_info,
        "login": browser_login,
        "save_session": lambda **kw: save_session(kw.get("name", "default")),
        "scrape_x": scrape_x_feed,
        "scrape_structured": scrape_page_structured,
        "x_login": lambda **kw: x_login(kw.get("tab_id", "x_scanner")),
        "elevenlabs_login": lambda **kw: elevenlabs_login(kw.get("tab_id", "elevenlabs")),
        "elevenlabs_list_voices": elevenlabs_list_voices,
        "elevenlabs_clone_voice": elevenlabs_clone_voice,
        "elevenlabs_get_usage": lambda **kw: elevenlabs_get_usage(kw.get("tab_id", "elevenlabs")),
        "close": lambda **kw: close_browser(),
    }

    handler = action_map.get(action)
    if not handler:
        return json.dumps({"error": f"Unknown browser action: {action}", "available": list(action_map.keys())})

    try:
        result = await handler(**params)
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error(f"Browser action failed: {action}: {e}")
        return json.dumps({"error": str(e), "action": action})
