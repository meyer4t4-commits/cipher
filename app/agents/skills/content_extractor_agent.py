"""
Content Extractor Agent v1.0.0 — Extract and transcribe content from YouTube, X/Twitter, articles.

Truly agentic: auto-detects URL type, extracts content via APIs/scraping,
transcribes videos, and returns structured data for Cipher to analyze.

Capabilities:
1. extract_youtube — Get transcript + metadata from YouTube videos
2. extract_tweet — Extract tweet/thread text, media, metadata from X/Twitter
3. extract_article — Extract clean article text from any web URL
4. transcribe_video — Download + transcribe any video to text
5. auto_extract — Auto-detect URL type and extract accordingly
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class ContentExtractorAgent(BaseAgent):
    """Extract and transcribe content from YouTube, X/Twitter, web articles, and videos."""

    def __init__(self):
        super().__init__(
            name="content_extractor_agent",
            description=(
                "Content extraction and transcription — YouTube video transcripts, "
                "X/Twitter posts and threads, web article text, video transcription. "
                "Auto-detects URL type and extracts structured content."
            ),
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="extract_youtube",
                    description="Extract transcript and metadata from YouTube videos",
                    category="data",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="extract_tweet",
                    description="Extract text, media, and metadata from X/Twitter posts and threads",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="extract_article",
                    description="Extract clean text, title, author from any web article/blog",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="transcribe_video",
                    description="Download and transcribe any video URL to text with timestamps",
                    category="data",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="auto_extract",
                    description="Auto-detect URL type and extract content accordingly",
                    category="data",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="deep_extract",
                    description=(
                        "Deep extraction: extract content from a URL, find all embedded links, "
                        "follow them, and extract their content too. Returns the original content "
                        "plus all linked article content. Use this for tweets/posts that contain "
                        "links to articles, blog posts, or other content."
                    ),
                    category="data",
                    timeout_seconds=120,
                ),
            ],
        )

        # Temp dir for downloads (Railway-safe)
        self._tmp_dir = Path("/tmp/cipher_content_extractor")
        try:
            self._tmp_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self._tmp_dir = Path("/tmp")

        logger.info("ContentExtractorAgent v1.0.0 initialized")

    def requires_approval_for(self, instruction: str) -> bool:
        return False  # Read-only extraction doesn't need approval

    async def validate(self, task: AgentTask) -> bool:
        if not await super().validate(task):
            return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Route to the correct extraction method based on operation or URL."""
        operation = task.params.get("operation", "auto_extract")
        url = task.params.get("url", "")

        # Try to extract URL from instruction if not in params
        if not url:
            url = self._extract_url_from_text(task.instruction)

        logger.info(f"[CONTENT EXTRACTOR] operation={operation}, url={url}")

        if not url and operation == "auto_extract":
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output={},
                error="No URL found in the request. Please provide a YouTube, X/Twitter, or article URL.",
            )

        # Auto-detect URL type if operation is auto_extract
        if operation == "auto_extract":
            url_type = self._detect_url_type(url)
            logger.info(f"[CONTENT EXTRACTOR] Auto-detected URL type: {url_type}")
            if url_type == "youtube":
                operation = "extract_youtube"
            elif url_type == "twitter":
                operation = "extract_tweet"
            else:
                operation = "extract_article"

        try:
            if operation == "extract_youtube":
                return await self._extract_youtube(url, task)
            elif operation == "extract_tweet":
                return await self._extract_tweet(url, task)
            elif operation == "extract_article":
                return await self._extract_article(url, task)
            elif operation == "deep_extract":
                return await self._deep_extract(url, task)
            elif operation == "transcribe_video":
                return await self._transcribe_video(url, task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    output={},
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"[CONTENT EXTRACTOR] Error: {type(e).__name__}: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output={},
                error=f"Extraction failed: {type(e).__name__}: {str(e)}",
            )

    async def verify(self, result: AgentResult) -> bool:
        """Verify extraction produced valid content."""
        if not result.success:
            return False
        if not isinstance(result.output, dict):
            return False
        # Must have some content
        content = result.output.get("content", "")
        if not content or len(str(content)) < 10:
            result.error = "Extraction produced empty or too-short content"
            result.success = False
            return False
        return True

    # ── URL Detection ───────────────────────────────────────────────

    def _extract_url_from_text(self, text: str) -> str:
        """Extract the first URL from a text string."""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        match = re.search(url_pattern, text)
        return match.group(0).rstrip(".,;:!?)") if match else ""

    def _detect_url_type(self, url: str) -> str:
        """Detect if URL is YouTube, Twitter/X, or generic article."""
        parsed = urlparse(url.lower())
        domain = parsed.netloc.replace("www.", "")

        if any(d in domain for d in ["youtube.com", "youtu.be", "m.youtube.com"]):
            return "youtube"
        elif any(d in domain for d in ["twitter.com", "x.com", "mobile.twitter.com"]):
            return "twitter"
        elif any(d in domain for d in ["tiktok.com", "vimeo.com", "dailymotion.com"]):
            return "video"
        else:
            return "article"

    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from various URL formats."""
        parsed = urlparse(url)
        if "youtu.be" in parsed.netloc:
            return parsed.path.lstrip("/").split("/")[0]
        if "youtube.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            return qs.get("v", [None])[0]
        return None

    # ── YouTube Extraction ──────────────────────────────────────────

    async def _extract_youtube(self, url: str, task: AgentTask) -> AgentResult:
        """Extract transcript and metadata from a YouTube video."""
        video_id = self._extract_youtube_id(url)
        if not video_id:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output={},
                error=f"Could not extract YouTube video ID from: {url}",
            )

        await self.emit_progress(f"Extracting YouTube video {video_id}...")

        # Try youtube-transcript-api first (fastest, no download needed)
        transcript_text = ""
        transcript_segments = []
        metadata = {}

        # Method 1: youtube-transcript-api
        try:
            transcript_result = await self.run_bash(
                f'python3 -c "'
                f"from youtube_transcript_api import YouTubeTranscriptApi;"
                f"t = YouTubeTranscriptApi.get_transcript('{video_id}');"
                f"import json; print(json.dumps(t))"
                f'"',
                timeout=30,
            )
            if transcript_result.get("success") and transcript_result.get("stdout"):
                segments = json.loads(transcript_result["stdout"])
                transcript_segments = segments
                transcript_text = " ".join(seg.get("text", "") for seg in segments)
                logger.info(f"[YOUTUBE] Got transcript via youtube-transcript-api: {len(segments)} segments")
        except Exception as e:
            logger.warning(f"[YOUTUBE] youtube-transcript-api failed: {e}")

        # Method 2: yt-dlp for metadata + subtitles fallback
        if not transcript_text:
            try:
                ytdlp_result = await self.run_bash(
                    f"yt-dlp --write-auto-sub --sub-lang en --skip-download "
                    f"--print-json --no-warnings 'https://www.youtube.com/watch?v={video_id}' 2>/dev/null",
                    timeout=45,
                )
                if ytdlp_result.get("success") and ytdlp_result.get("stdout"):
                    yt_data = json.loads(ytdlp_result["stdout"])
                    metadata = {
                        "title": yt_data.get("title", ""),
                        "channel": yt_data.get("channel", yt_data.get("uploader", "")),
                        "duration_seconds": yt_data.get("duration", 0),
                        "view_count": yt_data.get("view_count", 0),
                        "upload_date": yt_data.get("upload_date", ""),
                        "description": (yt_data.get("description", "") or "")[:1000],
                        "thumbnail": yt_data.get("thumbnail", ""),
                        "like_count": yt_data.get("like_count", 0),
                        "tags": (yt_data.get("tags", []) or [])[:20],
                    }
                    # Check for auto-generated subtitles in the data
                    if yt_data.get("subtitles") or yt_data.get("automatic_captions"):
                        subs = yt_data.get("subtitles", {}) or yt_data.get("automatic_captions", {})
                        if "en" in subs:
                            for sub_format in subs["en"]:
                                if sub_format.get("ext") == "json3":
                                    sub_url = sub_format.get("url", "")
                                    if sub_url:
                                        async with httpx.AsyncClient(timeout=15) as client:
                                            resp = await client.get(sub_url)
                                            if resp.status_code == 200:
                                                sub_data = resp.json()
                                                events = sub_data.get("events", [])
                                                parts = []
                                                for evt in events:
                                                    segs = evt.get("segs", [])
                                                    for seg in segs:
                                                        text = seg.get("utf8", "").strip()
                                                        if text and text != "\n":
                                                            parts.append(text)
                                                transcript_text = " ".join(parts)
                                                logger.info(f"[YOUTUBE] Got transcript via yt-dlp auto-captions")
                                                break
            except Exception as e:
                logger.warning(f"[YOUTUBE] yt-dlp metadata failed: {e}")

        # Method 3: If we still don't have metadata, try yt-dlp just for info
        if not metadata.get("title"):
            try:
                info_result = await self.run_bash(
                    f"yt-dlp --print title --print channel --print duration "
                    f"--no-warnings 'https://www.youtube.com/watch?v={video_id}' 2>/dev/null",
                    timeout=20,
                )
                if info_result.get("success") and info_result.get("stdout"):
                    lines = info_result["stdout"].strip().split("\n")
                    metadata["title"] = lines[0] if len(lines) > 0 else ""
                    metadata["channel"] = lines[1] if len(lines) > 1 else ""
                    metadata["duration_seconds"] = int(lines[2]) if len(lines) > 2 and lines[2].isdigit() else 0
            except Exception:
                pass

        # Method 4: Last resort — get page HTML and parse
        if not transcript_text and not metadata.get("title"):
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(
                        f"https://www.youtube.com/watch?v={video_id}",
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    if resp.status_code == 200:
                        html = resp.text
                        title_match = re.search(r'<title>(.*?)</title>', html)
                        if title_match:
                            metadata["title"] = title_match.group(1).replace(" - YouTube", "").strip()
            except Exception:
                pass

        if not transcript_text and not metadata.get("title"):
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output={},
                error=(
                    f"Could not extract transcript or metadata for video {video_id}. "
                    "The video may be private, age-restricted, or have no captions available."
                ),
            )

        output = {
            "content": transcript_text or "(No transcript available — metadata only)",
            "source_url": url,
            "source_type": "youtube",
            "video_id": video_id,
            "metadata": metadata,
            "transcript_segments": transcript_segments[:100] if transcript_segments else [],
            "word_count": len(transcript_text.split()) if transcript_text else 0,
            "extracted_at": datetime.utcnow().isoformat(),
            "extraction_method": "youtube-transcript-api" if transcript_segments else "yt-dlp",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    # ── Twitter/X Extraction ────────────────────────────────────────

    async def _extract_tweet(self, url: str, task: AgentTask) -> AgentResult:
        """Extract tweet content, media references, and metadata from X/Twitter."""
        await self.emit_progress("Extracting tweet content...")

        # Normalize URL: twitter.com → x.com (or vice versa for API compatibility)
        clean_url = url.replace("twitter.com", "x.com").replace("mobile.x.com", "x.com")

        # Extract tweet ID from URL
        tweet_id = None
        match = re.search(r'/status/(\d+)', clean_url)
        if match:
            tweet_id = match.group(1)

        # Method 1: Use nitter or alternative frontend to scrape (no API key needed)
        tweet_text = ""
        tweet_metadata = {}

        # Try yt-dlp which can also extract tweets
        try:
            result = await self.run_bash(
                f"yt-dlp --print description --print title --no-warnings '{url}' 2>/dev/null",
                timeout=20,
            )
            if result.get("success") and result.get("stdout"):
                lines = result["stdout"].strip()
                if lines:
                    tweet_text = lines
                    logger.info(f"[TWITTER] Got tweet text via yt-dlp")
        except Exception as e:
            logger.warning(f"[TWITTER] yt-dlp tweet extraction failed: {e}")

        # Method 2: Direct HTTP scraping with multiple approaches
        if not tweet_text:
            # Try various public endpoints/embeds
            for scrape_url in [
                f"https://publish.twitter.com/oembed?url={url}",
                f"https://publish.twitter.com/oembed?url={clean_url}",
            ]:
                try:
                    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                        resp = await client.get(scrape_url)
                        if resp.status_code == 200:
                            data = resp.json()
                            tweet_text = data.get("html", "")
                            tweet_metadata["author_name"] = data.get("author_name", "")
                            tweet_metadata["author_url"] = data.get("author_url", "")
                            # Clean HTML from oembed
                            tweet_text = re.sub(r'<[^>]+>', ' ', tweet_text).strip()
                            tweet_text = re.sub(r'\s+', ' ', tweet_text)
                            logger.info(f"[TWITTER] Got tweet via oembed API")
                            break
                except Exception as e:
                    logger.warning(f"[TWITTER] oembed failed for {scrape_url}: {e}")

        # Method 3: Try syndication API (public, no auth)
        if not tweet_text and tweet_id:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"https://syndication.twitter.com/srv/timeline-profile/screen-name/tweet",
                        params={"id": tweet_id},
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    if resp.status_code == 200:
                        # Parse response for tweet text
                        html = resp.text
                        text_match = re.search(r'data-text="([^"]*)"', html)
                        if text_match:
                            tweet_text = text_match.group(1)
            except Exception:
                pass

        # Method 4: Use nitter instances
        if not tweet_text and tweet_id:
            nitter_instances = [
                "nitter.net", "nitter.privacydev.net",
                "nitter.poast.org", "nitter.woodland.cafe",
            ]
            for instance in nitter_instances:
                try:
                    nitter_url = url.replace("x.com", instance).replace("twitter.com", instance)
                    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                        resp = await client.get(nitter_url, headers={"User-Agent": "Mozilla/5.0"})
                        if resp.status_code == 200:
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(resp.text, "html.parser")
                            tweet_content = soup.find("div", class_="tweet-content")
                            if tweet_content:
                                tweet_text = tweet_content.get_text(strip=True)
                                # Get author
                                author = soup.find("a", class_="fullname")
                                if author:
                                    tweet_metadata["author_name"] = author.get_text(strip=True)
                                logger.info(f"[TWITTER] Got tweet via nitter ({instance})")
                                break
                except Exception:
                    continue

        if not tweet_text:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output={},
                error=(
                    "Could not extract tweet content. X/Twitter has restricted API access. "
                    "Try pasting the tweet text directly, or I can try alternative methods."
                ),
            )

        # Extract all URLs from the tweet text so downstream can follow them
        embedded_urls = re.findall(r'https?://\S+', tweet_text)
        # Clean trailing punctuation from URLs
        embedded_urls = [u.rstrip('.,;:!?)"\'>') for u in embedded_urls]
        # Filter out twitter/x.com self-references
        embedded_urls = [
            u for u in embedded_urls
            if not any(d in u.lower() for d in ["twitter.com", "x.com", "t.co/"])
        ]

        output = {
            "content": tweet_text,
            "source_url": url,
            "source_type": "twitter",
            "tweet_id": tweet_id,
            "metadata": tweet_metadata,
            "embedded_urls": embedded_urls,
            "word_count": len(tweet_text.split()),
            "extracted_at": datetime.utcnow().isoformat(),
            "extraction_method": "oembed" if tweet_metadata.get("author_name") else "scrape",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    # ── Deep Extraction (follow links) ─────────────────────────────

    async def _deep_extract(self, url: str, task: AgentTask) -> AgentResult:
        """
        Deep extraction: extract content from a URL, find embedded links,
        follow each one, and return all content combined.

        This is the key capability for tweets that link to articles.
        Flow: extract tweet → find URLs → extract each article → combine.
        """
        await self.emit_progress(f"Deep extracting from {url}...")

        # Step 1: Extract the source content
        url_type = self._detect_url_type(url)
        if url_type == "youtube":
            source_result = await self._extract_youtube(url, task)
        elif url_type == "twitter":
            source_result = await self._extract_tweet(url, task)
        else:
            source_result = await self._extract_article(url, task)

        if not source_result.success:
            return source_result

        source_output = source_result.output if isinstance(source_result.output, dict) else {}
        source_content = source_output.get("content", "")

        # Step 2: Find all embedded URLs (from output + raw text scan)
        embedded_urls = source_output.get("embedded_urls", [])

        # Also scan the content text for any URLs we might have missed
        content_urls = re.findall(r'https?://\S+', source_content)
        content_urls = [u.rstrip('.,;:!?)"\'>') for u in content_urls]

        # Combine and deduplicate, filter out self-references
        all_urls = list(dict.fromkeys(embedded_urls + content_urls))  # preserve order, dedupe
        all_urls = [
            u for u in all_urls
            if not any(d in u.lower() for d in ["twitter.com", "x.com"])
            and u != url  # Don't re-extract the source
        ]

        # Step 3: Follow each URL and extract content
        linked_content = []
        for i, link_url in enumerate(all_urls[:5]):  # Max 5 links to stay within timeout
            await self.emit_progress(f"Following link {i+1}/{min(len(all_urls), 5)}: {link_url[:60]}...")
            try:
                # Resolve t.co and other redirects first
                resolved_url = await self._resolve_redirects(link_url)
                link_type = self._detect_url_type(resolved_url)

                if link_type == "youtube":
                    link_result = await self._extract_youtube(resolved_url, task)
                else:
                    link_result = await self._extract_article(resolved_url, task)

                if link_result.success:
                    link_output = link_result.output if isinstance(link_result.output, dict) else {}
                    linked_content.append({
                        "url": resolved_url,
                        "original_url": link_url,
                        "type": link_type,
                        "title": link_output.get("metadata", {}).get("title", ""),
                        "content": link_output.get("content", "")[:10000],  # Cap per article
                        "word_count": link_output.get("word_count", 0),
                    })
                else:
                    linked_content.append({
                        "url": resolved_url,
                        "original_url": link_url,
                        "type": link_type,
                        "error": link_result.error or "Extraction failed",
                    })
            except Exception as e:
                linked_content.append({
                    "url": link_url,
                    "original_url": link_url,
                    "error": f"{type(e).__name__}: {str(e)[:200]}",
                })

        # Step 4: Combine everything
        combined_output = {
            "source": source_output,
            "linked_content": linked_content,
            "total_links_found": len(all_urls),
            "total_links_followed": len(linked_content),
            "source_type": url_type,
            "deep_extract": True,
            "content": source_content,  # Keep top-level content for compatibility
            "word_count": (
                source_output.get("word_count", 0)
                + sum(lc.get("word_count", 0) for lc in linked_content)
            ),
            "extracted_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=combined_output,
        )

    async def _resolve_redirects(self, url: str) -> str:
        """Follow redirects (especially t.co shortlinks) to get the final URL."""
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.head(url, headers={"User-Agent": "Mozilla/5.0"})
                return str(resp.url)
        except Exception:
            return url  # Return original if redirect fails

    # ── Article Extraction ──────────────────────────────────────────

    async def _extract_article(self, url: str, task: AgentTask) -> AgentResult:
        """Extract clean article text from any web URL."""
        await self.emit_progress(f"Extracting article from {urlparse(url).netloc}...")

        article_text = ""
        article_metadata = {}

        # Method 1: Try newspaper3k first (best for articles)
        try:
            extract_script = f"""
import json
try:
    from newspaper import Article
    a = Article('{url}')
    a.download()
    a.parse()
    result = {{
        "title": a.title or "",
        "text": a.text or "",
        "authors": a.authors or [],
        "publish_date": str(a.publish_date) if a.publish_date else "",
        "top_image": a.top_image or "",
        "meta_description": a.meta_description or "",
    }}
    print(json.dumps(result))
except ImportError:
    print(json.dumps({{"error": "newspaper3k not installed"}}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
"""
            result = await self.run_bash(
                f"python3 -c {json.dumps(extract_script)}",
                timeout=30,
            )
            if result.get("success") and result.get("stdout"):
                data = json.loads(result["stdout"])
                if not data.get("error") and data.get("text"):
                    article_text = data["text"]
                    article_metadata = {
                        "title": data.get("title", ""),
                        "authors": data.get("authors", []),
                        "publish_date": data.get("publish_date", ""),
                        "image": data.get("top_image", ""),
                        "description": data.get("meta_description", ""),
                    }
                    logger.info(f"[ARTICLE] Extracted via newspaper3k: {len(article_text)} chars")
        except Exception as e:
            logger.warning(f"[ARTICLE] newspaper3k failed: {e}")

        # Method 2: Direct HTTP + BeautifulSoup
        if not article_text:
            try:
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    })
                    if resp.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(resp.text, "html.parser")

                        # Get title
                        title_tag = soup.find("title")
                        article_metadata["title"] = title_tag.get_text(strip=True) if title_tag else ""

                        # Get meta description
                        meta_desc = soup.find("meta", attrs={"name": "description"})
                        if meta_desc:
                            article_metadata["description"] = meta_desc.get("content", "")

                        # Get author
                        author_meta = soup.find("meta", attrs={"name": "author"})
                        if author_meta:
                            article_metadata["authors"] = [author_meta.get("content", "")]

                        # Remove non-content elements
                        for tag in soup(["script", "style", "nav", "header", "footer",
                                        "aside", "form", "button", "iframe", "noscript"]):
                            tag.decompose()

                        # Try article tag first
                        article_tag = soup.find("article")
                        if article_tag:
                            article_text = article_tag.get_text(separator="\n", strip=True)
                        else:
                            # Try main content area
                            main = soup.find("main") or soup.find("div", {"role": "main"})
                            if main:
                                article_text = main.get_text(separator="\n", strip=True)
                            else:
                                # Fallback: get all paragraph text
                                paragraphs = soup.find_all("p")
                                article_text = "\n\n".join(
                                    p.get_text(strip=True) for p in paragraphs
                                    if len(p.get_text(strip=True)) > 30
                                )

                        # Clean up whitespace
                        article_text = re.sub(r'\n{3,}', '\n\n', article_text)
                        logger.info(f"[ARTICLE] Extracted via BeautifulSoup: {len(article_text)} chars")
            except Exception as e:
                logger.warning(f"[ARTICLE] BS4 extraction failed: {e}")

        if not article_text:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output={},
                error=f"Could not extract content from {url}. The page may require JavaScript or authentication.",
            )

        # Trim very long articles
        if len(article_text) > 15000:
            article_text = article_text[:15000] + "\n\n[... article truncated at 15,000 characters ...]"

        output = {
            "content": article_text,
            "source_url": url,
            "source_type": "article",
            "metadata": article_metadata,
            "word_count": len(article_text.split()),
            "extracted_at": datetime.utcnow().isoformat(),
            "extraction_method": "newspaper3k" if article_metadata.get("authors") else "beautifulsoup",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    # ── Video Transcription ─────────────────────────────────────────

    async def _transcribe_video(self, url: str, task: AgentTask) -> AgentResult:
        """Download a video and transcribe it using available tools."""
        await self.emit_progress("Downloading video for transcription...")

        # If it's a YouTube URL, try transcript API first
        if self._detect_url_type(url) == "youtube":
            yt_result = await self._extract_youtube(url, task)
            if yt_result.success and yt_result.output.get("content", "").strip():
                return yt_result

        # Download video audio with yt-dlp
        audio_path = str(self._tmp_dir / f"audio_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.mp3")

        try:
            dl_result = await self.run_bash(
                f"yt-dlp -x --audio-format mp3 --audio-quality 5 "
                f"-o '{audio_path}' --no-warnings '{url}' 2>&1",
                timeout=90,
            )
            if not dl_result.get("success"):
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    output={},
                    error=f"Failed to download video audio: {dl_result.get('stderr', 'unknown error')}",
                )

            await self.emit_progress("Transcribing audio...")

            # Try whisper (local or API)
            transcript = ""

            # Method 1: faster-whisper (local)
            try:
                whisper_result = await self.run_bash(
                    f'python3 -c "'
                    f"from faster_whisper import WhisperModel;"
                    f"model = WhisperModel('tiny', device='cpu');"
                    f"segments, _ = model.transcribe('{audio_path}');"
                    f"print(' '.join(seg.text for seg in segments))"
                    f'"',
                    timeout=120,
                )
                if whisper_result.get("success") and whisper_result.get("stdout"):
                    transcript = whisper_result["stdout"].strip()
                    logger.info(f"[TRANSCRIBE] Got transcript via faster-whisper")
            except Exception:
                pass

            # Method 2: OpenAI Whisper API
            if not transcript:
                openai_key = os.getenv("OPENAI_API_KEY", "")
                if openai_key:
                    try:
                        whisper_script = f"""
import json
from openai import OpenAI
client = OpenAI()
with open("{audio_path}", "rb") as f:
    result = client.audio.transcriptions.create(model="whisper-1", file=f)
print(result.text)
"""
                        api_result = await self.run_bash(
                            f"python3 -c {json.dumps(whisper_script)}",
                            timeout=60,
                        )
                        if api_result.get("success") and api_result.get("stdout"):
                            transcript = api_result["stdout"].strip()
                            logger.info(f"[TRANSCRIBE] Got transcript via OpenAI Whisper API")
                    except Exception as e:
                        logger.warning(f"[TRANSCRIBE] OpenAI Whisper API failed: {e}")

            # Clean up audio file
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass

            if not transcript:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    output={},
                    error="Could not transcribe video. Neither local Whisper nor OpenAI API available.",
                )

            output = {
                "content": transcript,
                "source_url": url,
                "source_type": "video_transcription",
                "metadata": {},
                "word_count": len(transcript.split()),
                "extracted_at": datetime.utcnow().isoformat(),
                "extraction_method": "whisper",
            }

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output=output,
            )

        except Exception as e:
            # Clean up on error
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass
            raise
