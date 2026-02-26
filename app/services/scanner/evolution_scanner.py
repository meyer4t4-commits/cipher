"""Evolution scanner - comprehensive AI/tech landscape monitoring system.

This scanner monitors:
- LLM providers (Anthropic, OpenAI, Google, etc.)
- Voice/Audio AI
- Image/Video AI
- Research papers and trends
- News and media coverage
- Community discussions
- Developer tools and packages
- Hardware and infrastructure
- Educational AI resources

Schedule:
- Daily full scan: 6 AM
- Weekly recap: Sunday 8 PM
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from difflib import SequenceMatcher

import aiohttp
from app.core.logging import logger
from .base import BaseScanner, ScanResult, ScannerConnectionError, ScannerParseError


class ImplementationDifficulty(str, Enum):
    """Difficulty levels for feature implementation."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EPIC = "epic"


class CompetitiveUrgency(str, Enum):
    """Urgency levels for competitive features."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceCategory(str, Enum):
    """Source categories for monitoring."""
    LLM_PROVIDERS = "llm_providers"
    VOICE_AI = "voice_ai"
    IMAGE_VIDEO_AI = "image_video_ai"
    RESEARCH = "research"
    NEWS = "news"
    COMMUNITY = "community"
    DEVELOPER_TOOLS = "developer_tools"
    HARDWARE = "hardware"
    EDUCATION_AI = "education_ai"


class SourceType(str, Enum):
    """Type of scanning needed for source."""
    RSS = "rss"
    API = "api"
    SCRAPE = "scrape"
    GITHUB = "github"
    REDDIT = "reddit"
    ARXIV = "arxiv"


@dataclass
class MonitoredSource:
    """A source to monitor for AI evolution."""
    name: str
    url: str
    category: SourceCategory
    source_type: SourceType
    scan_interval_minutes: int = 60
    enabled: bool = True
    last_scan: Optional[datetime] = None
    last_scan_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "name": self.name,
            "url": self.url,
            "category": self.category.value,
            "source_type": self.source_type.value,
            "scan_interval_minutes": self.scan_interval_minutes,
            "enabled": self.enabled,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "last_scan_count": self.last_scan_count,
        }


@dataclass
class FeatureProposal:
    """Represents a detected competitor feature for potential implementation."""

    id: str
    source: str  # e.g., "Claude", "ChatGPT", "Gemini"
    feature_name: str
    description: str
    relevance_score: float  # 0-1, based on alignment with Cipher
    implementation_difficulty: ImplementationDifficulty
    affected_components: list[str]  # e.g., ["llm_router", "voice", "memory"]
    competitive_urgency: CompetitiveUrgency
    detected_at: datetime
    url: str = ""
    original_description: str = ""
    notes: str = ""
    approved: bool = False
    rejected: bool = False
    decision_date: Optional[datetime] = None
    category: Optional[SourceCategory] = None

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "id": self.id,
            "source": self.source,
            "feature_name": self.feature_name,
            "description": self.description,
            "relevance_score": self.relevance_score,
            "implementation_difficulty": self.implementation_difficulty.value,
            "affected_components": self.affected_components,
            "competitive_urgency": self.competitive_urgency.value,
            "detected_at": self.detected_at.isoformat(),
            "url": self.url,
            "original_description": self.original_description,
            "notes": self.notes,
            "approved": self.approved,
            "rejected": self.rejected,
            "decision_date": self.decision_date.isoformat() if self.decision_date else None,
            "category": self.category.value if self.category else None,
        }


class EvolutionScanner(BaseScanner):
    """
    Comprehensive AI evolution scanner monitoring 100+ sources worldwide.

    Tracks AI/tech evolution across:
    - 20+ LLM providers and model releases
    - Voice, image, video AI innovations
    - Academic research and papers
    - News and media coverage
    - Community discussions and forums
    - Developer tools and packages
    - Hardware and infrastructure
    """

    # Comprehensive monitoring sources
    MONITORED_SOURCES = [
        # LLM Providers - APIs/Blogs
        MonitoredSource("Anthropic Blog", "https://www.anthropic.com/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 60),
        MonitoredSource("Anthropic Docs", "https://docs.anthropic.com", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),
        MonitoredSource("OpenAI Blog", "https://openai.com/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 60),
        MonitoredSource("OpenAI Changelog", "https://platform.openai.com/docs/changelog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),
        MonitoredSource("Google DeepMind Blog", "https://deepmind.google/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 60),
        MonitoredSource("Google AI Blog", "https://blog.google/technology/ai", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 60),
        MonitoredSource("Perplexity Blog", "https://perplexity.ai/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),
        MonitoredSource("Meta AI Blog", "https://ai.meta.com/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 60),
        MonitoredSource("Apple ML", "https://machinelearning.apple.com", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),
        MonitoredSource("Microsoft AI Blog", "https://blogs.microsoft.com/ai", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 60),
        MonitoredSource("xAI Blog", "https://x.ai/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),
        MonitoredSource("Mistral AI", "https://mistral.ai/news", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),
        MonitoredSource("Cohere Blog", "https://cohere.com/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),
        MonitoredSource("Databricks Blog", "https://databricks.com/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 60),
        MonitoredSource("Together AI Blog", "https://together.ai/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),
        MonitoredSource("Groq Blog", "https://groq.com/blog", SourceCategory.LLM_PROVIDERS, SourceType.SCRAPE, 120),

        # Voice/Audio AI
        MonitoredSource("11 Labs Blog", "https://elevenlabs.io/blog", SourceCategory.VOICE_AI, SourceType.SCRAPE, 120),
        MonitoredSource("PlayHT Blog", "https://playht.com/blog", SourceCategory.VOICE_AI, SourceType.SCRAPE, 120),
        MonitoredSource("Amazon Polly Updates", "https://aws.amazon.com/blogs/machine-learning", SourceCategory.VOICE_AI, SourceType.SCRAPE, 120),
        MonitoredSource("OpenAI Whisper", "https://github.com/openai/whisper/releases", SourceCategory.VOICE_AI, SourceType.GITHUB, 240),
        MonitoredSource("Fish Speech", "https://github.com/fishaudio/fish-speech", SourceCategory.VOICE_AI, SourceType.GITHUB, 240),

        # Image/Video AI
        MonitoredSource("Runway ML Blog", "https://runwayml.com/blog", SourceCategory.IMAGE_VIDEO_AI, SourceType.SCRAPE, 120),
        MonitoredSource("Stability AI Blog", "https://stability.ai/blog", SourceCategory.IMAGE_VIDEO_AI, SourceType.SCRAPE, 120),
        MonitoredSource("Midjourney Updates", "https://www.midjourney.com/updates", SourceCategory.IMAGE_VIDEO_AI, SourceType.SCRAPE, 120),

        # Research
        MonitoredSource("ArXiv CS.AI", "https://arxiv.org/list/cs.AI/recent", SourceCategory.RESEARCH, SourceType.ARXIV, 240),
        MonitoredSource("ArXiv CS.CL", "https://arxiv.org/list/cs.CL/recent", SourceCategory.RESEARCH, SourceType.ARXIV, 240),
        MonitoredSource("ArXiv CS.LG", "https://arxiv.org/list/cs.LG/recent", SourceCategory.RESEARCH, SourceType.ARXIV, 240),
        MonitoredSource("Papers With Code", "https://paperswithcode.com/trending", SourceCategory.RESEARCH, SourceType.SCRAPE, 240),
        MonitoredSource("Semantic Scholar AI", "https://www.semanticscholar.org", SourceCategory.RESEARCH, SourceType.API, 240),

        # News & Media
        MonitoredSource("TechCrunch AI", "https://techcrunch.com/tag/artificial-intelligence/feed", SourceCategory.NEWS, SourceType.RSS, 30),
        MonitoredSource("The Verge AI", "https://www.theverge.com/ai", SourceCategory.NEWS, SourceType.SCRAPE, 30),
        MonitoredSource("Ars Technica AI", "https://arstechnica.com/ai", SourceCategory.NEWS, SourceType.SCRAPE, 30),
        MonitoredSource("VentureBeat AI", "https://venturebeat.com/ai", SourceCategory.NEWS, SourceType.SCRAPE, 30),
        MonitoredSource("Product Hunt AI", "https://www.producthunt.com/feed.xml", SourceCategory.NEWS, SourceType.RSS, 60),

        # Community
        MonitoredSource("Hacker News", "https://news.ycombinator.com", SourceCategory.COMMUNITY, SourceType.API, 30),
        MonitoredSource("r/MachineLearning", "https://reddit.com/r/MachineLearning", SourceCategory.COMMUNITY, SourceType.REDDIT, 60),
        MonitoredSource("r/LocalLLaMA", "https://reddit.com/r/LocalLLaMA", SourceCategory.COMMUNITY, SourceType.REDDIT, 60),
        MonitoredSource("r/artificial", "https://reddit.com/r/artificial", SourceCategory.COMMUNITY, SourceType.REDDIT, 60),
        MonitoredSource("r/ChatGPT", "https://reddit.com/r/ChatGPT", SourceCategory.COMMUNITY, SourceType.REDDIT, 60),

        # Developer Tools
        MonitoredSource("HuggingFace Blog", "https://huggingface.co/blog", SourceCategory.DEVELOPER_TOOLS, SourceType.SCRAPE, 120),
        MonitoredSource("GitHub Trending Python", "https://github.com/trending/python", SourceCategory.DEVELOPER_TOOLS, SourceType.GITHUB, 60),
        MonitoredSource("PyPI AI Packages", "https://pypi.org/project", SourceCategory.DEVELOPER_TOOLS, SourceType.API, 120),
        MonitoredSource("npm AI Packages", "https://www.npmjs.com/search", SourceCategory.DEVELOPER_TOOLS, SourceType.API, 120),
        MonitoredSource("VS Code AI Extensions", "https://marketplace.visualstudio.com", SourceCategory.DEVELOPER_TOOLS, SourceType.SCRAPE, 240),
        MonitoredSource("Chrome AI Extensions", "https://chromewebstore.google.com", SourceCategory.DEVELOPER_TOOLS, SourceType.SCRAPE, 240),

        # Hardware & Infrastructure
        MonitoredSource("Nvidia Deep Learning", "https://blogs.nvidia.com/blog/category/deep-learning", SourceCategory.HARDWARE, SourceType.SCRAPE, 120),
        MonitoredSource("AWS ML Blog", "https://aws.amazon.com/blogs/machine-learning", SourceCategory.HARDWARE, SourceType.SCRAPE, 120),
        MonitoredSource("Google Cloud AI", "https://cloud.google.com/blog", SourceCategory.HARDWARE, SourceType.SCRAPE, 120),

        # Education
        MonitoredSource("Andrej Karpathy", "https://karpathy.ai", SourceCategory.EDUCATION_AI, SourceType.SCRAPE, 240),
    ]

    # Keywords indicating feature announcements
    FEATURE_INDICATORS = [
        "launch", "announce", "introducing", "release", "new feature", "new model",
        "now available", "available today", "ship", "shipped", "available",
        "support for", "added support", "now supports", "beta", "experimental",
        "open source", "open-source", "released", "unveiled", "debut",
    ]

    # Component mapping to Cipher systems
    COMPONENT_KEYWORDS = {
        "llm_router": ["model", "routing", "provider", "integration", "inference", "api", "endpoint"],
        "voice": ["voice", "audio", "speech", "tts", "text-to-speech", "talking", "vocal", "speak", "whisper"],
        "memory": ["memory", "context", "recall", "storage", "persistence", "knowledge", "rag"],
        "orchestrator": ["workflow", "orchestration", "pipeline", "coordination", "execution", "scheduling"],
        "scanner": ["intelligence", "monitoring", "tracking", "detection", "analysis", "intelligence"],
        "ios_app": ["mobile", "iOS", "app", "interface", "UI", "native", "frontend"],
        "api": ["API", "endpoint", "integration", "webhook", "stream", "protocol"],
    }

    def __init__(self, data_dir: str = "/data/evolution"):
        super().__init__("evolution", rate_limit_delay=0.5)  # 2 requests/sec max
        self.client: Optional[aiohttp.ClientSession] = None
        self.proposals: list[FeatureProposal] = []
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        (self.data_dir / "scans").mkdir(exist_ok=True)
        (self.data_dir / "proposals").mkdir(exist_ok=True)
        (self.data_dir / "sources").mkdir(exist_ok=True)

        # Load or initialize sources
        self.sources = self._load_sources()
        self._seen_urls: set[str] = set()  # For deduplication

    async def _get_client(self) -> aiohttp.ClientSession:
        """Get or create HTTP client."""
        if self.client is None:
            self.client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15.0),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; EvolutionScanner/1.0)",
                },
            )
        return self.client

    def _load_sources(self) -> list[MonitoredSource]:
        """Load sources from file or return defaults."""
        sources_file = self.data_dir / "sources" / "sources.json"
        if sources_file.exists():
            try:
                with open(sources_file, 'r') as f:
                    sources_data = json.load(f)
                    return [MonitoredSource(**s) for s in sources_data]
            except Exception as e:
                logger.warning(f"Failed to load sources: {e}, using defaults")
        return self.MONITORED_SOURCES

    async def save_sources(self) -> None:
        """Save current sources to file."""
        sources_file = self.data_dir / "sources" / "sources.json"
        sources_data = [s.to_dict() for s in self.sources]
        with open(sources_file, 'w') as f:
            json.dump(sources_data, f, indent=2)
        logger.info(f"Saved {len(self.sources)} monitored sources")

    async def scan(self, keywords: Optional[list[str]] = None, full_scan: bool = True) -> list[ScanResult]:
        """
        Comprehensive scan of AI evolution sources.

        Args:
            keywords: Optional keywords to prioritize (unused for evolution scanner)
            full_scan: If True, scan all enabled sources; if False, only stale sources

        Returns:
            List of ScanResult objects summarizing found features
        """
        results = []
        logger.info(f"Starting evolution scan (full={full_scan}) with {len(self.sources)} sources")

        # Scan each source in parallel
        scan_tasks = []
        for source in self.sources:
            if not source.enabled:
                continue

            # Check if source needs scanning
            if not full_scan and source.last_scan:
                minutes_since_scan = (datetime.utcnow() - source.last_scan).total_seconds() / 60
                if minutes_since_scan < source.scan_interval_minutes:
                    continue

            # Create scan task
            if source.source_type == SourceType.RSS:
                scan_tasks.append(self._scan_rss_source(source))
            elif source.source_type == SourceType.GITHUB:
                scan_tasks.append(self._scan_github_source(source))
            elif source.source_type == SourceType.REDDIT:
                scan_tasks.append(self._scan_reddit_source(source))
            elif source.source_type == SourceType.ARXIV:
                scan_tasks.append(self._scan_arxiv_source(source))
            elif source.source_type == SourceType.API:
                scan_tasks.append(self._scan_api_source(source))
            else:  # SCRAPE
                scan_tasks.append(self._scan_webpage_source(source))

        # Execute all scans concurrently
        if scan_tasks:
            scan_results = await asyncio.gather(*scan_tasks, return_exceptions=True)
            for result in scan_results:
                if isinstance(result, list):
                    results.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Scan task failed: {result}")

        # Deduplicate and parse
        results = self._deduplicate_results(results)
        parsed = await self.parse_results(results)
        filtered = await self.filter_relevant(parsed, threshold=0.35)

        logger.info(f"Evolution scan complete: {len(results)} raw -> {len(parsed)} parsed -> {len(filtered)} relevant")

        # Save scan results
        await self._save_scan_results(filtered)

        return filtered

    async def _scan_webpage_source(self, source: MonitoredSource) -> list[dict]:
        """Scan a webpage source for announcements."""
        results = []
        try:
            await self._rate_limit()
            client = await self._get_client()
            async with client.get(source.url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch {source.name}: {response.status}")
                    return results

                html = await response.text()
                results = self._extract_announcements_from_html(html, source)
                source.last_scan = datetime.utcnow()
                source.last_scan_count = len(results)

        except Exception as e:
            logger.warning(f"Error scanning {source.name}: {e}")

        return results

    async def _scan_rss_source(self, source: MonitoredSource) -> list[dict]:
        """Scan an RSS feed source."""
        results = []
        try:
            await self._rate_limit()
            client = await self._get_client()
            async with client.get(source.url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return results

                xml_content = await response.text()
                items = self._parse_rss_feed(xml_content)

                for item in items[:15]:  # Limit items per feed
                    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
                    if any(ind in text for ind in self.FEATURE_INDICATORS) or \
                       any(kw in text for kw in ["ai", "model", "feature", "launch", "release"]):
                        results.append({
                            "source": source.name,
                            "title": item.get("title", ""),
                            "content": item.get("description", "")[:500],
                            "url": item.get("link", source.url),
                            "pub_date": item.get("pub_date", ""),
                            "category": source.category.value,
                        })

                source.last_scan = datetime.utcnow()
                source.last_scan_count = len(results)

        except Exception as e:
            logger.warning(f"Error scanning RSS {source.name}: {e}")

        return results

    async def _scan_github_source(self, source: MonitoredSource) -> list[dict]:
        """Scan GitHub releases."""
        results = []
        try:
            await self._rate_limit()
            client = await self._get_client()

            # Parse GitHub URL to get owner/repo
            match = re.search(r'github\.com/([^/]+)/([^/]+)', source.url)
            if not match:
                return results

            owner, repo = match.groups()
            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

            async with client.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return results

                releases = await response.json()

                for release in releases[:10]:  # Last 10 releases
                    if release.get('prerelease'):  # Skip pre-releases
                        continue

                    results.append({
                        "source": source.name,
                        "title": f"Release: {release.get('tag_name', '')}",
                        "content": (release.get('body', '') or "")[:500],
                        "url": release.get('html_url', source.url),
                        "pub_date": release.get('published_at', ""),
                        "category": source.category.value,
                    })

                source.last_scan = datetime.utcnow()
                source.last_scan_count = len(results)

        except Exception as e:
            logger.warning(f"Error scanning GitHub {source.name}: {e}")

        return results

    async def _scan_reddit_source(self, source: MonitoredSource) -> list[dict]:
        """Scan Reddit subreddit."""
        results = []
        try:
            await self._rate_limit()
            client = await self._get_client()

            # Reddit JSON API
            json_url = source.url.rstrip('/') + '/.json'

            async with client.get(json_url, timeout=aiohttp.ClientTimeout(total=10), headers={
                "User-Agent": "EvolutionScanner/1.0"
            }) as response:
                if response.status != 200:
                    return results

                data = await response.json()
                posts = data.get('data', {}).get('children', [])

                for post in posts[:30]:  # Last 30 posts
                    post_data = post.get('data', {})
                    title = post_data.get('title', '')
                    content = post_data.get('selftext', '')

                    # Filter by keywords
                    text = f"{title} {content}".lower()
                    if any(kw in text for kw in ["ai", "llm", "model", "release", "launch", "feature"]):
                        results.append({
                            "source": source.name,
                            "title": title,
                            "content": content[:500],
                            "url": f"https://reddit.com{post_data.get('permalink', '')}",
                            "pub_date": datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat(),
                            "category": source.category.value,
                        })

                source.last_scan = datetime.utcnow()
                source.last_scan_count = len(results)

        except Exception as e:
            logger.warning(f"Error scanning Reddit {source.name}: {e}")

        return results

    async def _scan_arxiv_source(self, source: MonitoredSource) -> list[dict]:
        """Scan ArXiv for recent papers."""
        results = []
        try:
            await self._rate_limit()
            client = await self._get_client()

            # ArXiv API
            api_url = "http://export.arxiv.org/api/query"
            category = source.url.split('/')[-1]  # cs.AI, cs.CL, etc.

            params = {
                "search_query": f"cat:{category}",
                "start": 0,
                "max_results": 20,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }

            async with client.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return results

                xml_content = await response.text()

                # Simple XML parsing for ArXiv feed
                entries = re.findall(r'<entry>(.*?)</entry>', xml_content, re.DOTALL)
                for entry in entries[:15]:
                    title_match = re.search(r'<title>(.*?)</title>', entry)
                    summary_match = re.search(r'<summary>(.*?)</summary>', entry)
                    id_match = re.search(r'<id>(.*?)</id>', entry)

                    if title_match and summary_match:
                        results.append({
                            "source": source.name,
                            "title": title_match.group(1).strip(),
                            "content": summary_match.group(1).strip()[:500],
                            "url": id_match.group(1).replace('http://', 'https://') if id_match else source.url,
                            "pub_date": "",
                            "category": source.category.value,
                        })

                source.last_scan = datetime.utcnow()
                source.last_scan_count = len(results)

        except Exception as e:
            logger.warning(f"Error scanning ArXiv {source.name}: {e}")

        return results

    async def _scan_api_source(self, source: MonitoredSource) -> list[dict]:
        """Scan API-based sources (Hacker News, Semantic Scholar, etc.)."""
        results = []
        try:
            await self._rate_limit()
            client = await self._get_client()

            if "news.ycombinator.com" in source.url.lower():
                # Hacker News Firebase API
                hn_url = "https://hacker-news.firebaseio.com/v0/topstories.json"

                async with client.get(hn_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        return results

                    story_ids = await response.json()

                    for story_id in story_ids[:30]:
                        story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"

                        async with client.get(story_url, timeout=aiohttp.ClientTimeout(total=10)) as story_response:
                            if story_response.status != 200:
                                continue

                            story = await story_response.json()
                            title = story.get('title', '')
                            text = f"{title} {story.get('text', '')}".lower()

                            if any(kw in text for kw in ["ai", "llm", "model", "release", "launch", "feature"]):
                                results.append({
                                    "source": source.name,
                                    "title": title,
                                    "content": story.get('text', '')[:500],
                                    "url": story.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                                    "pub_date": datetime.fromtimestamp(story.get('time', 0)).isoformat(),
                                    "category": source.category.value,
                                })

                source.last_scan = datetime.utcnow()
                source.last_scan_count = len(results)

        except Exception as e:
            logger.warning(f"Error scanning API {source.name}: {e}")

        return results

    def _extract_announcements_from_html(self, html: str, source: MonitoredSource) -> list[dict]:
        """Extract feature announcements from HTML."""
        announcements = []
        try:
            # Extract links and titles
            link_pattern = r'<a[^>]+href=(["\'])([^"\']+)\1[^>]*>([^<]+)</a>'
            heading_pattern = r'<h[1-6][^>]*>([^<]+)</h[1-6]>'

            # Extract headings
            for heading in re.finditer(heading_pattern, html):
                text = heading.group(1).strip()
                if any(ind in text.lower() for ind in self.FEATURE_INDICATORS):
                    announcements.append({
                        "source": source.name,
                        "title": text[:200],
                        "content": text[:300],
                        "url": source.url,
                        "category": source.category.value,
                    })

            # Extract links with relevant anchor text
            for link in re.finditer(link_pattern, html):
                text = link.group(3).strip()
                if any(ind in text.lower() for ind in self.FEATURE_INDICATORS):
                    announcements.append({
                        "source": source.name,
                        "title": text[:200],
                        "content": text,
                        "url": link.group(2),
                        "category": source.category.value,
                    })

        except Exception as e:
            logger.debug(f"Error extracting from HTML: {e}")

        return announcements

    def _parse_rss_feed(self, xml_content: str) -> list[dict]:
        """Parse RSS/Atom feed XML."""
        items = []
        try:
            # Simple regex-based parsing (more resilient than XML parsing)
            item_pattern = r'<item>(.*?)</item>|<entry>(.*?)</entry>'
            title_pattern = r'<title[^>]*>(.*?)</title>'
            desc_pattern = r'<description>(.*?)</description>|<summary[^>]*>(.*?)</summary>'
            link_pattern = r'<link[^>]*>(?:<!\[CDATA\[(.*?)\]\]>|(.*?))</link>|<link[^>]*href=(["\'])([^"\']+)\3'
            date_pattern = r'<(pubDate|updated|published)[^>]*>(.*?)</\1>'

            for match in re.finditer(item_pattern, xml_content, re.DOTALL):
                item_content = match.group(1) or match.group(2)

                title_match = re.search(title_pattern, item_content)
                title = title_match.group(1) if title_match else ''

                if not title:
                    continue

                desc_match = re.search(desc_pattern, item_content, re.DOTALL)
                description = (desc_match.group(1) or desc_match.group(2)) if desc_match else ''

                link_match = re.search(link_pattern, item_content)
                link = (link_match.group(1) or link_match.group(2) or link_match.group(4)) if link_match else ''

                date_match = re.search(date_pattern, item_content)
                pub_date = date_match.group(2) if date_match else ''

                items.append({
                    "title": re.sub(r'<[^>]+>', '', title).strip(),
                    "description": re.sub(r'<[^>]+>', '', description).strip(),
                    "link": link.strip(),
                    "pub_date": pub_date.strip(),
                })

        except Exception as e:
            logger.warning(f"Error parsing RSS feed: {e}")

        return items

    def _deduplicate_results(self, results: list[dict]) -> list[dict]:
        """Remove duplicate results based on URL and title similarity."""
        unique_results = []
        seen_hashes = set()

        for result in results:
            url = result.get('url', '')
            title = result.get('title', '')

            # Create a hash of URL (preferred dedup key)
            if url:
                url_hash = hashlib.md5(url.encode()).hexdigest()
                if url_hash in seen_hashes:
                    continue
                seen_hashes.add(url_hash)

            # Check for title similarity
            if title:
                is_similar = False
                for seen_result in unique_results:
                    if self._title_similarity(title, seen_result.get('title', '')) > 0.85:
                        is_similar = True
                        break

                if is_similar:
                    continue

            unique_results.append(result)

        return unique_results

    @staticmethod
    def _title_similarity(title1: str, title2: str) -> float:
        """Calculate similarity between two titles (0-1)."""
        return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()

    async def parse_results(self, raw_results: list[dict]) -> list[ScanResult]:
        """Parse raw results into ScanResult objects."""
        results = []

        for item in raw_results:
            try:
                title = item.get("title", "").strip()
                content = item.get("content", "").strip()
                url = item.get("url", "")
                source = item.get("source", "Unknown")
                category = item.get("category", "")

                if title:
                    # Calculate relevance based on keywords
                    text = f"{title} {content}".lower()
                    relevance = self._calculate_feature_relevance(text)

                    result = ScanResult(
                        source=source,
                        title=title,
                        content=content,
                        url=url,
                        timestamp=datetime.utcnow(),
                        relevance_score=relevance,
                        tags=["evolution", "feature", category] if category else ["evolution", "feature"],
                    )
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse result: {e}")
                continue

        return results

    def _calculate_feature_relevance(self, text: str) -> float:
        """Calculate relevance of a feature based on keywords."""
        base_score = 0.25

        # Boost score for feature indicators
        feature_matches = sum(
            1 for indicator in self.FEATURE_INDICATORS
            if indicator in text
        )
        feature_boost = min(0.35, feature_matches * 0.08)

        # Boost for AI/ML keywords
        ai_keywords = ["ai", "model", "llm", "neural", "learning", "intelligence", "training", "inference"]
        ai_matches = sum(1 for kw in ai_keywords if kw in text)
        ai_boost = min(0.4, ai_matches * 0.12)

        # Boost for specific domains
        domain_keywords = ["voice", "audio", "vision", "image", "video", "reasoning", "memory"]
        domain_matches = sum(1 for kw in domain_keywords if kw in text)
        domain_boost = min(0.2, domain_matches * 0.08)

        combined = base_score + feature_boost + ai_boost + domain_boost
        return min(1.0, combined)

    async def filter_relevant(
        self, results: list[ScanResult], threshold: float = 0.35
    ) -> list[ScanResult]:
        """Filter results by relevance threshold."""
        return [r for r in results if r.relevance_score >= threshold]

    def propose_features(self, scan_results: list[ScanResult]) -> list[FeatureProposal]:
        """
        Convert scan results into feature proposals.

        Args:
            scan_results: Results from scanning competitor sources

        Returns:
            List of FeatureProposal objects
        """
        proposals = []

        for i, result in enumerate(scan_results):
            try:
                # Generate proposal ID
                proposal_id = f"FP-{datetime.utcnow().strftime('%Y%m%d%H%M')}-{i:03d}"

                # Extract feature information
                feature_name = self._extract_feature_name(result.title)
                affected_components = self._map_components(result.content)
                difficulty = self._estimate_difficulty(result.content)
                urgency = self._assess_urgency(result.source, result.relevance_score)

                # Extract category from tags
                category = None
                for tag in result.tags:
                    try:
                        category = SourceCategory(tag)
                        break
                    except ValueError:
                        pass

                proposal = FeatureProposal(
                    id=proposal_id,
                    source=result.source,
                    feature_name=feature_name,
                    description=result.content[:300],
                    relevance_score=result.relevance_score,
                    implementation_difficulty=difficulty,
                    affected_components=affected_components,
                    competitive_urgency=urgency,
                    detected_at=result.timestamp,
                    url=result.url,
                    original_description=result.content,
                    category=category,
                )

                proposals.append(proposal)

            except Exception as e:
                logger.debug(f"Failed to propose feature from result: {e}")
                continue

        self.proposals = proposals
        return proposals

    def _extract_feature_name(self, title: str) -> str:
        """Extract a clean feature name from title."""
        title = title.strip()
        # Remove leading articles
        title = re.sub(r'^(the|a|an)\s+', '', title, flags=re.IGNORECASE)
        # Remove common prefixes
        title = re.sub(r'^(new|now|introducing|announcing|released?)\s+', '', title, flags=re.IGNORECASE)
        # Remove trailing punctuation
        title = re.sub(r'[!?:.]*$', '', title)
        return title[:100]

    def _map_components(self, description: str) -> list[str]:
        """Map content to affected Cipher components."""
        components = []
        description_lower = description.lower()

        for component, keywords in self.COMPONENT_KEYWORDS.items():
            if any(kw in description_lower for kw in keywords):
                components.append(component)

        # Default to scanner if no specific components found
        if not components:
            components = ["scanner"]

        return components

    def _estimate_difficulty(self, description: str) -> ImplementationDifficulty:
        """Estimate implementation difficulty."""
        description_lower = description.lower()

        # Epic indicators
        epic_indicators = [
            "architecture", "redesign", "rewrite", "platform",
            "infrastructure", "system-wide", "major", "overhaul"
        ]
        if any(ind in description_lower for ind in epic_indicators):
            return ImplementationDifficulty.EPIC

        # Hard indicators
        hard_indicators = [
            "complex", "difficult", "integration", "multiple", "cross",
            "distributed", "scaling", "performance"
        ]
        if any(ind in description_lower for ind in hard_indicators):
            return ImplementationDifficulty.HARD

        # Medium indicators
        medium_indicators = [
            "feature", "capability", "add", "improve", "enhance",
            "update", "modification", "support", "api"
        ]
        if any(ind in description_lower for ind in medium_indicators):
            return ImplementationDifficulty.MEDIUM

        # Default to easy
        return ImplementationDifficulty.EASY

    def _assess_urgency(
        self, source: str, relevance: float
    ) -> CompetitiveUrgency:
        """Assess competitive urgency based on source and relevance."""
        # Major competitors
        major_competitors = [
            "Claude", "Anthropic", "ChatGPT", "OpenAI", "Gemini", "Google",
            "Meta AI", "Llama", "Microsoft", "Copilot"
        ]

        # Check if source is a major competitor
        is_major = any(comp.lower() in source.lower() for comp in major_competitors)

        if is_major:
            if relevance > 0.8:
                return CompetitiveUrgency.CRITICAL
            elif relevance > 0.6:
                return CompetitiveUrgency.HIGH
            elif relevance > 0.4:
                return CompetitiveUrgency.MEDIUM
        else:
            if relevance > 0.8:
                return CompetitiveUrgency.HIGH
            elif relevance > 0.6:
                return CompetitiveUrgency.MEDIUM
            elif relevance > 0.4:
                return CompetitiveUrgency.LOW

        return CompetitiveUrgency.LOW

    async def _save_scan_results(self, results: list[ScanResult]) -> None:
        """Save scan results to file."""
        try:
            scan_file = self.data_dir / "scans" / f"scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            results_data = [r.to_dict() for r in results]

            with open(scan_file, 'w') as f:
                json.dump(results_data, f, indent=2)

            logger.info(f"Saved {len(results)} scan results to {scan_file}")
        except Exception as e:
            logger.error(f"Failed to save scan results: {e}")

    async def close(self) -> None:
        """Cleanup HTTP client and save sources."""
        await self.save_sources()
        if self.client:
            await self.client.aclose()
            self.client = None

    async def __aenter__(self):
        """Context manager support."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        await self.close()
