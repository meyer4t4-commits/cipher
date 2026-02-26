"""GitHub scanner for tracking tech trends and repository activity."""

import asyncio
from datetime import datetime

try:
    import httpx
except ImportError:
    import aiohttp as httpx

from app.core.logging import logger
from .base import BaseScanner, ScanResult, ScannerConnectionError, ScannerParseError


class GitHubScanner(BaseScanner):
    """Scan GitHub for trending AI/ML repositories."""

    def __init__(self):
        super().__init__("github", rate_limit_delay=2.0)
        self.client = None
        self.api_url = "https://api.github.com"

        # Key projects to monitor
        self.key_repos = [
            ("BerriAI", "litellm"),
            ("ollama", "ollama"),
            ("chroma-core", "chroma"),
            ("langchain-ai", "langchain"),
            ("anthropics", "anthropic-sdk-python"),
            ("openai", "openai-python"),
            ("vllm-project", "vllm"),
            ("THUDM", "ChatGLM3"),
        ]

        # Trending topic queries
        self.trending_queries = [
            "language:python topic:machine-learning",
            "language:python topic:large-language-model",
            "language:python topic:artificial-intelligence",
        ]

    async def _get_client(self):
        """Get or create HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=10.0,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Orchid Scanner",
                },
            )
        return self.client

    async def scan(self, keywords: list[str]) -> list[ScanResult]:
        """
        Scan GitHub for trending repositories and activity.

        Args:
            keywords: Keywords to search for

        Returns:
            List of ScanResult objects
        """
        results = []

        # Monitor key repositories
        try:
            key_repo_results = await self._scan_key_repos()
            results.extend(key_repo_results)
            logger.debug(f"Key repos scan returned {len(key_repo_results)} results")
        except ScannerConnectionError as e:
            logger.warning(f"Key repos scan failed: {e}")

        # Search for trending repos by keywords
        try:
            trending_results = await self._search_trending_repos(keywords)
            results.extend(trending_results)
            logger.debug(f"Trending search returned {len(trending_results)} results")
        except ScannerConnectionError as e:
            logger.warning(f"Trending search failed: {e}")

        # Parse and filter
        parsed = await self.parse_results(results)
        filtered = await self.filter_relevant(parsed, threshold=0.3)

        logger.info(f"GitHub scanner found {len(filtered)} relevant results")
        return filtered

    async def _scan_key_repos(self) -> list[dict]:
        """
        Monitor activity on key repositories.

        Returns:
            List of repo update dicts
        """
        try:
            client = await self._get_client()
            results = []

            for owner, repo in self.key_repos:
                try:
                    await self._rate_limit()

                    # Get repo info
                    url = f"{self.api_url}/repos/{owner}/{repo}"
                    response = await client.get(url)
                    response.raise_for_status()
                    repo_data = response.json()

                    # Get recent releases
                    releases_url = f"{self.api_url}/repos/{owner}/{repo}/releases"
                    try:
                        releases_response = await client.get(
                            releases_url, params={"per_page": 3}
                        )
                        releases_response.raise_for_status()
                        releases = releases_response.json()
                    except Exception:
                        releases = []

                    # Compile result
                    result = {
                        "owner": owner,
                        "repo": repo,
                        "full_name": repo_data.get("full_name"),
                        "description": repo_data.get("description", ""),
                        "stars": repo_data.get("stargazers_count", 0),
                        "forks": repo_data.get("forks_count", 0),
                        "language": repo_data.get("language", ""),
                        "updated_at": repo_data.get("updated_at", ""),
                        "url": repo_data.get("html_url", ""),
                        "latest_releases": releases[:2],
                    }
                    results.append(result)

                except httpx.HTTPError as e:
                    logger.debug(f"Failed to fetch GitHub repo {owner}/{repo}: {e}")
                    continue

            return results
        except Exception as e:
            raise ScannerConnectionError(f"Key repos scan failed: {e}")

    async def _search_trending_repos(self, keywords: list[str]) -> list[dict]:
        """
        Search for trending repositories by keywords.

        Args:
            keywords: Search keywords

        Returns:
            List of trending repo dicts
        """
        try:
            client = await self._get_client()
            results = []

            # Build search query with keywords
            search_terms = " ".join(keywords[:3])
            query = f"language:python {search_terms}"

            try:
                await self._rate_limit()

                url = f"{self.api_url}/search/repositories"
                response = await client.get(
                    url,
                    params={
                        "q": query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 10,
                    },
                )
                response.raise_for_status()
                data = response.json()

                for repo in data.get("items", []):
                    result = {
                        "owner": repo.get("owner", {}).get("login", ""),
                        "repo": repo.get("name", ""),
                        "full_name": repo.get("full_name", ""),
                        "description": repo.get("description", ""),
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "language": repo.get("language", ""),
                        "updated_at": repo.get("updated_at", ""),
                        "url": repo.get("html_url", ""),
                    }
                    results.append(result)

            except httpx.HTTPError as e:
                logger.debug(f"GitHub search failed: {e}")

            return results
        except Exception as e:
            raise ScannerConnectionError(f"Trending search failed: {e}")

    async def parse_results(self, raw_results: list[dict]) -> list[ScanResult]:
        """Parse raw GitHub results into ScanResult objects."""
        results = []

        for repo in raw_results:
            try:
                full_name = repo.get("full_name", "")
                description = repo.get("description", "") or "No description"
                stars = repo.get("stars", 0)
                forks = repo.get("forks", 0)
                language = repo.get("language", "")
                updated_at = repo.get("updated_at", "")
                url = repo.get("url", "")

                # Build title
                title = f"{full_name} ({stars} stars, {forks} forks)"

                # Build content with release info
                content_parts = [
                    description,
                    f"Language: {language}" if language else "",
                    f"Stars: {stars}, Forks: {forks}",
                ]

                releases = repo.get("latest_releases", [])
                if releases:
                    content_parts.append("\nRecent releases:")
                    for release in releases:
                        rel_name = release.get("name", release.get("tag_name", ""))
                        rel_date = release.get("published_at", "")
                        content_parts.append(f"- {rel_name} ({rel_date[:10]})")

                content = "\n".join(filter(None, content_parts))

                # Parse timestamp
                try:
                    timestamp = datetime.fromisoformat(
                        updated_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    timestamp = datetime.utcnow()

                if full_name and url:
                    result = ScanResult(
                        source="GitHub",
                        title=title,
                        content=content[:500],
                        url=url,
                        timestamp=timestamp,
                        relevance_score=0.65,
                        tags=["github", "repository", language.lower()],
                    )
                    results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse GitHub result: {e}")
                continue

        return results

    async def filter_relevant(
        self, results: list[ScanResult], threshold: float = 0.3
    ) -> list[ScanResult]:
        """Filter GitHub results by relevance."""
        return [r for r in results if r.relevance_score >= threshold]

    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
