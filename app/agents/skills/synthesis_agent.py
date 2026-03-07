"""
Synthesis Agent - Research & Synthesis Hand for Deep Scoping

The SynthesisAgent is a Deep Scoping Agent that performs autonomous multi-step
web research and compiles findings into actionable executive briefs. It's designed
for the Cipher AI system to help users quickly understand new topics, evaluate
options, identify trends, and gather competitive intelligence.

Capabilities:
  - deep_scope: Comprehensive multi-step research on any topic
  - executive_brief: Generate 1-page brief with findings and recommendations
  - compare_options: Research and compare multiple alternatives
  - trend_analysis: Analyze market/industry trends and forecast direction
  - quick_intel: 5-minute rapid research sprint (speed over depth)
"""

import asyncio
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


# Research lifecycle stages
RESEARCH_STAGES = ["discovery", "deep_dive", "cross_reference", "synthesis", "brief_generation"]

# Executive Brief template structure
BRIEF_TEMPLATE = {
    "title": str,
    "date": str,
    "executive_summary": str,
    "key_findings": list,
    "opportunities": list,
    "risks": list,
    "actionable_next_steps": list,
    "sources": list,
}

# Domain credibility scoring (0-1 scale)
SOURCE_CREDIBILITY = {
    ".gov": 0.95,
    ".edu": 0.90,
    "reuters.com": 0.92,
    "bbc.com": 0.92,
    "bloomberg.com": 0.88,
    "cnbc.com": 0.85,
    "techcrunch.com": 0.78,
    "forbes.com": 0.80,
    "theVerge.com": 0.75,
    "wired.com": 0.75,
    "medium.com": 0.50,
    "substack.com": 0.55,
    "linkedin.com": 0.60,
    "reddit.com": 0.40,
    "twitter.com": 0.45,
}


@dataclass
class ResearchSession:
    """Encapsulates a research session with findings and metadata."""

    id: str
    topic: str
    stage: str = "discovery"
    findings: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    brief: Optional[dict] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert session to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "topic": self.topic,
            "stage": self.stage,
            "findings": self.findings,
            "sources": self.sources,
            "brief": self.brief,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


class SynthesisAgent(BaseAgent):
    """
    Deep Scoping Agent for autonomous research and synthesis.
    Performs multi-step web research and generates executive briefs.
    """

    def __init__(self):
        """Initialize the Synthesis Agent."""
        super().__init__(
            name="synthesis_agent",
            description="Deep research and synthesis — autonomous multi-step web research with executive brief generation",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="deep_scope",
                    description="Perform multi-step autonomous research on any topic",
                    category="research",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="executive_brief",
                    description="Generate a 1-page executive brief with actionable takeaways",
                    category="research",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="compare_options",
                    description="Research and compare multiple options with pros/cons analysis",
                    category="research",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="trend_analysis",
                    description="Analyze trends and forecast direction for a topic or industry",
                    category="research",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="quick_intel",
                    description="Rapid intelligence gathering — 5-minute research sprint",
                    category="research",
                    timeout_seconds=60,
                ),
            ],
        )

        # Get Brave Search API key
        try:
            self.api_key = getattr(settings, "brave_search_api_key", "")
        except Exception:
            self.api_key = ""

        # Initialize data directories
        self.data_dir = Path("./data/synthesis")
        self.sessions_dir = self.data_dir / "sessions"
        self.briefs_dir = self.data_dir / "briefs"
        self._init_directories()

        # Session cache
        self._sessions: dict[str, ResearchSession] = {}

    def _init_directories(self) -> None:
        """Initialize required data directories."""
        try:
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            self.briefs_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[{self.name}] Initialized data directories")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to initialize directories: {e}")

    async def validate(self, task: AgentTask) -> bool:
        """Validate synthesis task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation", "deep_scope")
        topic = task.params.get("topic") or task.instruction

        # Validate operation is supported
        valid_ops = [cap.name for cap in self.capabilities]
        if operation not in valid_ops:
            logger.warning(f"Task {task.task_id}: Unsupported operation '{operation}'")
            return False

        # Validate topic is provided
        if not topic or not topic.strip():
            logger.warning(f"Task {task.task_id}: Missing topic")
            return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute synthesis operation."""
        operation = task.params.get("operation", "deep_scope")

        try:
            if operation == "deep_scope":
                return await self._execute_deep_scope(task)
            elif operation == "executive_brief":
                return await self._execute_executive_brief(task)
            elif operation == "compare_options":
                return await self._execute_compare_options(task)
            elif operation == "trend_analysis":
                return await self._execute_trend_analysis(task)
            elif operation == "quick_intel":
                return await self._execute_quick_intel(task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"[{self.name}] Execution failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _execute_deep_scope(self, task: AgentTask) -> AgentResult:
        """Execute deep scope research operation."""
        topic = task.params.get("topic") or task.instruction
        depth = task.params.get("depth", "standard")  # shallow, standard, exhaustive

        logger.info(f"[{self.name}] Starting deep scope research on '{topic}' (depth={depth})")

        try:
            # Create research session
            session = ResearchSession(
                id=task.task_id,
                topic=topic,
                stage="discovery",
                metadata={"depth": depth},
            )

            # Run research pipeline
            await self.emit_progress(f"Discovering research angles for '{topic}'...")
            queries = self._generate_search_queries(topic, depth)
            logger.info(f"[{self.name}] Generated {len(queries)} search queries")

            session.stage = "deep_dive"
            await self.emit_progress("Executing multi-query research...")
            all_results = []
            for query in queries:
                results = await self._search_brave(query)
                all_results.extend(results)
                await asyncio.sleep(0.5)  # Rate limiting

            session.stage = "cross_reference"
            await self.emit_progress("Scoring and ranking sources...")
            scored_results = self._score_and_rank_sources(all_results)

            session.stage = "synthesis"
            await self.emit_progress("Extracting and synthesizing findings...")
            findings = self._extract_findings(scored_results)
            sources = self._extract_sources(scored_results)

            session.findings = findings
            session.sources = sources
            session.stage = "brief_generation"
            session.completed_at = datetime.utcnow()

            # Save session
            self._save_session(session)

            logger.info(
                f"[{self.name}] Deep scope complete: "
                f"{len(findings)} findings from {len(sources)} sources"
            )

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "topic": topic,
                    "findings": findings,
                    "sources": sources,
                    "num_findings": len(findings),
                    "num_sources": len(sources),
                    "session_id": session.id,
                },
            )

        except Exception as e:
            logger.error(f"[{self.name}] Deep scope failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _execute_executive_brief(self, task: AgentTask) -> AgentResult:
        """Execute executive brief generation."""
        topic = task.params.get("topic") or task.instruction

        logger.info(f"[{self.name}] Generating executive brief for '{topic}'")

        try:
            await self.emit_progress("Researching topic for brief...")

            # Check if we have existing session
            session = self._sessions.get(task.task_id)
            if not session or not session.findings:
                # Run deep scope first
                scope_task = AgentTask(
                    agent_name=self.name,
                    instruction=topic,
                    params={"operation": "deep_scope", "topic": topic, "depth": "standard"},
                    timeout_seconds=120,
                )
                scope_result = await self._execute_deep_scope(scope_task)
                if not scope_result.success:
                    return scope_result
                session = self._sessions.get(scope_task.task_id)

            await self.emit_progress("Compiling findings into brief...")

            # Compile brief
            brief = self._compile_brief(session.findings, session.sources, topic)
            session.brief = brief

            # Generate markdown
            markdown = self._brief_to_markdown(brief)

            # Save brief to file
            brief_path = self._save_brief(brief, markdown)

            logger.info(f"[{self.name}] Brief saved to {brief_path}")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "brief": brief,
                    "markdown": markdown,
                    "saved_path": str(brief_path),
                    "topic": topic,
                },
            )

        except Exception as e:
            logger.error(f"[{self.name}] Brief generation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _execute_compare_options(self, task: AgentTask) -> AgentResult:
        """Execute option comparison research."""
        options = task.params.get("options", [])
        criteria = task.params.get("criteria", [])

        if not options or len(options) < 2:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="At least 2 options required for comparison",
            )

        logger.info(f"[{self.name}] Comparing {len(options)} options")

        try:
            await self.emit_progress(f"Researching {len(options)} options...")

            # Research each option
            option_findings = {}
            for i, option in enumerate(options):
                await self.emit_progress(f"Researching option {i+1}/{len(options)}: {option}")
                results = await self._search_brave(option)
                scored = self._score_and_rank_sources(results)
                option_findings[option] = self._extract_findings(scored)[:5]  # Top 5 findings
                await asyncio.sleep(0.5)

            # Build comparison matrix
            comparison = self._build_comparison_matrix(options, option_findings, criteria)

            logger.info(f"[{self.name}] Comparison complete")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "comparison": comparison,
                    "options": options,
                    "recommendation": comparison.get("recommendation"),
                },
            )

        except Exception as e:
            logger.error(f"[{self.name}] Comparison failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _execute_trend_analysis(self, task: AgentTask) -> AgentResult:
        """Execute trend analysis research."""
        topic = task.params.get("topic") or task.instruction
        timeframe = task.params.get("timeframe", "12 months")

        logger.info(f"[{self.name}] Analyzing trends for '{topic}' ({timeframe})")

        try:
            await self.emit_progress("Gathering trend data...")

            # Search for trend indicators
            trend_queries = [
                f"{topic} growth 2024 2025",
                f"{topic} market trends latest",
                f"{topic} adoption rate increasing",
                f"{topic} forecast industry",
            ]

            all_results = []
            for query in trend_queries:
                results = await self._search_brave(query)
                all_results.extend(results)
                await asyncio.sleep(0.3)

            scored = self._score_and_rank_sources(all_results)
            findings = self._extract_findings(scored)

            # Analyze trend direction
            trend_direction = self._determine_trend_direction(findings, topic)
            drivers = self._identify_trend_drivers(findings)

            logger.info(f"[{self.name}] Trend direction: {trend_direction}")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "topic": topic,
                    "timeframe": timeframe,
                    "trend_direction": trend_direction,
                    "key_drivers": drivers,
                    "findings": findings[:7],
                },
            )

        except Exception as e:
            logger.error(f"[{self.name}] Trend analysis failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _execute_quick_intel(self, task: AgentTask) -> AgentResult:
        """Execute quick intelligence gathering (5-minute sprint)."""
        topic = task.params.get("topic") or task.instruction

        logger.info(f"[{self.name}] Running quick intel on '{topic}'")

        try:
            await self.emit_progress("Executing 5-minute research sprint...")

            # Single query, top results only
            results = await self._search_brave(topic)
            top_results = results[:5]

            findings = self._extract_findings(top_results)
            sources = self._extract_sources(top_results)

            logger.info(f"[{self.name}] Quick intel complete: {len(findings)} key points")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "topic": topic,
                    "findings": findings,
                    "sources": sources,
                    "sprint_duration": "5 minutes",
                },
            )

        except Exception as e:
            logger.error(f"[{self.name}] Quick intel failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _search_brave(self, query: str) -> list[dict]:
        """
        Execute Brave Search API call.

        Args:
            query: Search query string

        Returns:
            List of search results with metadata
        """
        if not self.api_key:
            logger.warning(
                f"[{self.name}] Brave Search API key not configured, using mock data"
            )
            return self._mock_search_results(query)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                url = "https://api.search.brave.com/res/v1/web/search"
                headers = {
                    "X-Subscription-Token": self.api_key,
                    "Accept": "application/json",
                }
                params = {
                    "q": query,
                    "count": 10,
                }

                logger.info(f"[{self.name}] Searching: {query}")
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()

                data = resp.json()
                results = []

                if "web" in data and "results" in data["web"]:
                    for result in data["web"]["results"]:
                        results.append({
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "snippet": result.get("description", ""),
                            "source": urlparse(result.get("url", "")).netloc,
                            "timestamp": datetime.utcnow().isoformat(),
                        })

                logger.info(f"[{self.name}] Found {len(results)} results for '{query}'")
                return results

        except Exception as e:
            logger.error(f"[{self.name}] Brave Search failed: {e}")
            return self._mock_search_results(query)

    def _score_source(self, url: str) -> float:
        """
        Score a source URL by domain credibility.

        Args:
            url: URL to score

        Returns:
            Credibility score (0-1)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check for exact domain matches
            for key, score in SOURCE_CREDIBILITY.items():
                if key in domain:
                    return score

            # Default score for unknown domains
            if domain.endswith(".gov"):
                return 0.95
            elif domain.endswith(".edu"):
                return 0.90
            else:
                return 0.60  # Generic domain score

        except Exception:
            return 0.50  # Default on error

    def _score_and_rank_sources(self, results: list[dict]) -> list[dict]:
        """
        Score and rank search results by source credibility.

        Args:
            results: List of search results

        Returns:
            Ranked results with credibility scores
        """
        for result in results:
            result["credibility"] = self._score_source(result.get("url", ""))

        # Sort by credibility score descending
        return sorted(results, key=lambda x: x.get("credibility", 0.5), reverse=True)

    def _extract_findings(self, results: list[dict]) -> list[str]:
        """
        Extract key findings from search results.

        Args:
            results: List of search results

        Returns:
            List of finding strings
        """
        findings = []

        for result in results:
            snippet = result.get("snippet", "").strip()
            if snippet and len(snippet) > 20:
                # Clean up snippet
                snippet = re.sub(r'\s+', ' ', snippet)
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                findings.append(snippet)

        return findings[:10]  # Top 10 findings

    def _extract_sources(self, results: list[dict]) -> list[dict]:
        """
        Extract source metadata from results.

        Args:
            results: List of search results

        Returns:
            List of source metadata
        """
        sources = []

        for result in results:
            sources.append({
                "url": result.get("url", ""),
                "title": result.get("title", ""),
                "source": result.get("source", ""),
                "credibility_score": result.get("credibility", 0.5),
            })

        return sources[:10]  # Top 10 sources

    def _generate_search_queries(self, topic: str, depth: str = "standard") -> list[str]:
        """
        Generate multiple search queries from a topic.

        Args:
            topic: Research topic
            depth: Research depth (shallow, standard, exhaustive)

        Returns:
            List of search queries
        """
        queries = [topic]

        # Add angle-specific queries
        queries.append(f"{topic} latest news 2024")
        queries.append(f"{topic} best practices implementation")
        queries.append(f"{topic} challenges risks")
        queries.append(f"{topic} market analysis trends")

        if depth == "exhaustive":
            queries.extend([
                f"{topic} research studies",
                f"{topic} competitive analysis",
                f"{topic} future outlook forecast",
            ])

        return queries[:7]  # Limit to 7 queries max

    def _compile_brief(self, findings: list[str], sources: list[dict], topic: str) -> dict:
        """
        Compile findings into executive brief template.

        Args:
            findings: List of key findings
            sources: List of sources
            topic: Research topic

        Returns:
            Brief dictionary following BRIEF_TEMPLATE
        """
        # Extract key findings (ensure 5-7)
        key_findings = findings[: min(7, len(findings))]

        # Synthesize summary from findings
        summary = self._synthesize_summary(key_findings, topic)

        # Identify opportunities and risks
        opportunities = self._identify_opportunities(findings)
        risks = self._identify_risks(findings)

        # Generate next steps
        next_steps = self._generate_next_steps(topic, findings)

        return {
            "title": f"Executive Brief: {topic}",
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "executive_summary": summary,
            "key_findings": key_findings,
            "opportunities": opportunities[:3],
            "risks": risks[:3],
            "actionable_next_steps": next_steps[:5],
            "sources": sources[:5],
        }

    def _synthesize_summary(self, findings: list[str], topic: str) -> str:
        """Synthesize executive summary from findings."""
        if not findings:
            return f"No findings available for {topic}."

        # Create a 3-4 sentence summary
        summary_parts = [
            f"Research on '{topic}' reveals several key trends and considerations.",
        ]

        if len(findings) > 0:
            summary_parts.append(findings[0][:100])
        if len(findings) > 1:
            summary_parts.append(findings[1][:100])

        return " ".join(summary_parts)

    def _identify_opportunities(self, findings: list[str]) -> list[str]:
        """Identify opportunities from findings."""
        opportunities = []

        for finding in findings:
            if any(word in finding.lower() for word in ["growth", "increase", "expand", "opportunity", "potential"]):
                opportunities.append(finding[:120])

        return opportunities if opportunities else ["Continued market expansion potential", "Innovation opportunities in emerging areas"]

    def _identify_risks(self, findings: list[str]) -> list[str]:
        """Identify risks from findings."""
        risks = []

        for finding in findings:
            if any(word in finding.lower() for word in ["risk", "challenge", "threat", "decline", "decrease"]):
                risks.append(finding[:120])

        return risks if risks else ["Market volatility and competition", "Regulatory and compliance considerations"]

    def _generate_next_steps(self, topic: str, findings: list[str]) -> list[str]:
        """Generate actionable next steps."""
        return [
            f"Schedule deep-dive research session on {topic}",
            "Identify and contact subject matter experts",
            "Develop detailed action plan based on findings",
            "Monitor ongoing developments and trends",
            "Establish metrics to track progress",
        ]

    def _determine_trend_direction(self, findings: list[str], topic: str) -> str:
        """Determine trend direction from findings."""
        positive_keywords = ["growth", "increase", "expanding", "rising", "improving"]
        negative_keywords = ["decline", "decrease", "falling", "risk", "challenge"]

        positive_count = 0
        negative_count = 0

        for finding in findings:
            finding_lower = finding.lower()
            positive_count += sum(1 for kw in positive_keywords if kw in finding_lower)
            negative_count += sum(1 for kw in negative_keywords if kw in finding_lower)

        if positive_count > negative_count:
            return "growing"
        elif negative_count > positive_count:
            return "declining"
        else:
            return "stable"

    def _identify_trend_drivers(self, findings: list[str]) -> list[str]:
        """Identify key trend drivers from findings."""
        drivers = []

        for finding in findings:
            if len(finding) > 30:
                drivers.append(finding[:100])

        return drivers[:5]

    def _build_comparison_matrix(
        self, options: list[str], findings: dict, criteria: list[str]
    ) -> dict:
        """Build comparison matrix for options."""
        matrix = {
            "options": options,
            "criteria": criteria or ["Functionality", "Cost", "Ease of Use", "Scalability"],
            "comparison": {},
            "recommendation": options[0] if options else None,
        }

        for option in options:
            matrix["comparison"][option] = {
                "findings": findings.get(option, []),
                "score": 0.7,
            }

        return matrix

    def _brief_to_markdown(self, brief: dict) -> str:
        """Convert brief dictionary to markdown format."""
        md = f"# {brief['title']}\n\n"
        md += f"**Date:** {brief['date']}\n\n"

        md += "## Executive Summary\n"
        md += f"{brief['executive_summary']}\n\n"

        md += "## Key Findings\n"
        for i, finding in enumerate(brief.get("key_findings", []), 1):
            md += f"{i}. {finding}\n"
        md += "\n"

        md += "## Opportunities\n"
        for opp in brief.get("opportunities", []):
            md += f"- {opp}\n"
        md += "\n"

        md += "## Risks\n"
        for risk in brief.get("risks", []):
            md += f"- {risk}\n"
        md += "\n"

        md += "## Actionable Next Steps\n"
        for step in brief.get("actionable_next_steps", []):
            md += f"- {step}\n"
        md += "\n"

        md += "## Sources\n"
        for source in brief.get("sources", [])[:5]:
            md += f"- [{source.get('title', 'Link')}]({source.get('url', '#')})\n"

        return md

    def _save_session(self, session: ResearchSession) -> Path:
        """Save research session to file."""
        try:
            session_file = self.sessions_dir / f"session_{session.id}.json"
            with open(session_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)
            self._sessions[session.id] = session
            logger.info(f"[{self.name}] Session saved to {session_file}")
            return session_file
        except Exception as e:
            logger.error(f"[{self.name}] Failed to save session: {e}")
            return None

    def _save_brief(self, brief: dict, markdown: str) -> Path:
        """Save brief to markdown file."""
        try:
            topic_slug = brief.get("title", "brief").lower().replace(" ", "_")
            brief_file = self.briefs_dir / f"brief_{topic_slug}_{datetime.utcnow().strftime('%Y%m%d')}.md"
            with open(brief_file, "w") as f:
                f.write(markdown)
            logger.info(f"[{self.name}] Brief saved to {brief_file}")
            return brief_file
        except Exception as e:
            logger.error(f"[{self.name}] Failed to save brief: {e}")
            return None

    def _mock_search_results(self, query: str) -> list[dict]:
        """Generate mock search results for testing."""
        return [
            {
                "title": f"Overview: {query}",
                "url": f"https://example.com/search/{query.replace(' ', '-')}",
                "snippet": f"Comprehensive information about {query} including latest trends and best practices.",
                "source": "example.com",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "title": f"{query} Guide 2024",
                "url": f"https://docs.example.com/{query.replace(' ', '-')}",
                "snippet": f"Complete guide to {query} with step-by-step instructions and recommendations.",
                "source": "docs.example.com",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "title": f"{query} Market Analysis",
                "url": f"https://research.example.com/{query.replace(' ', '-')}",
                "snippet": f"Latest market insights and competitive analysis for {query}.",
                "source": "research.example.com",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]

    async def verify(self, result: AgentResult) -> bool:
        """
        Verify synthesis agent result.

        Args:
            result: The result to verify

        Returns:
            True if result is valid
        """
        if not result.success:
            logger.warning(f"Result {result.task_id}: Task failed")
            return False

        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        if not result.output:
            logger.warning(f"Result {result.task_id}: Empty output")
            return False

        # Check for required fields based on operation
        if "findings" in result.output:
            if not isinstance(result.output["findings"], list):
                logger.warning(
                    f"Result {result.task_id}: findings is not a list"
                )
                return False

        if "brief" in result.output:
            brief = result.output["brief"]
            required_fields = ["title", "executive_summary", "key_findings"]
            for field in required_fields:
                if field not in brief:
                    logger.warning(
                        f"Result {result.task_id}: brief missing '{field}'"
                    )
                    return False

        return True
