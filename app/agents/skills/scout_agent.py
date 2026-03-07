"""
Scout Agent — High-velocity lead discovery for the Global Expansion Pulse.

Finds companies that are high-revenue but "automation-poor" — meaning they
have outdated tech stacks, manual processes, weak online presence, or gaps
where Cipher's agent ecosystem could be plugged in.

Uses Brave Search API to scan industries, company databases, and public
signals to build a weekly pipeline of 5-10 qualified targets.

Capabilities:
1. scan_industry — Scan a specific industry/niche for automation-poor targets
2. scan_company — Deep-scan a specific company for automation gaps
3. build_target_list — Generate a ranked shortlist of targets from scan results
4. score_lead — Score a single lead on automation-readiness (0-100)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class ScoutAgent(BaseAgent):
    """Discover high-value, automation-poor companies for Elysian Protocol outreach."""

    def __init__(self):
        super().__init__(
            name="scout_agent",
            description="High-velocity lead discovery — finds automation-poor companies ripe for Cipher integration",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="scan_industry",
                    description="Scan an industry for companies with weak automation/tech infrastructure",
                    category="research",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="scan_company",
                    description="Deep-scan a specific company for automation gaps and integration opportunities",
                    category="research",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="build_target_list",
                    description="Generate a ranked shortlist of 5-10 targets from industry scan results",
                    category="research",
                    timeout_seconds=45,
                ),
                AgentCapability(
                    name="score_lead",
                    description="Score a single lead on automation-readiness (0-100)",
                    category="research",
                    timeout_seconds=30,
                ),
            ],
        )

        self._data_dir = Path("./data/expansion_pulse/scout")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        logger.info("ScoutAgent initialized")

    def requires_approval_for(self, instruction: str) -> bool:
        return False  # Scouting is read-only research

    async def validate(self, task: AgentTask) -> bool:
        if not await super().validate(task):
            return False
        operation = task.params.get("operation", "")
        if not operation:
            logger.warning(f"Task {task.task_id}: Missing operation parameter")
            return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        operation = task.params.get("operation", "")
        try:
            if operation == "scan_industry":
                await self.emit_progress("Scanning industry for targets...")
                return await self._scan_industry(task)
            elif operation == "scan_company":
                await self.emit_progress("Deep-scanning company...")
                return await self._scan_company(task)
            elif operation == "build_target_list":
                await self.emit_progress("Building ranked target list...")
                return await self._build_target_list(task)
            elif operation == "score_lead":
                await self.emit_progress("Scoring lead...")
                return await self._score_lead(task)
            else:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            logger.error(f"Scout operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    async def _brave_search(self, query: str, count: int = 10) -> list[dict]:
        """Execute a Brave Search API call."""
        if not self.brave_api_key:
            return [{"title": f"[Mock] {query}", "url": "https://example.com", "description": "Mock result — set BRAVE_SEARCH_API_KEY for live results"}]
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"X-Subscription-Token": self.brave_api_key, "Accept": "application/json"},
                    params={"q": query, "count": count},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("web", {}).get("results", [])
        except Exception as e:
            logger.warning(f"Brave search failed: {e}")
            return []

    async def _scan_industry(self, task: AgentTask) -> AgentResult:
        """Scan an industry for automation-poor companies."""
        industry = task.params.get("industry", "")
        location = task.params.get("location", "United States")
        revenue_min = task.params.get("revenue_min", "1M")

        if not industry:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'industry' parameter")

        # Multi-query strategy to find automation gaps
        queries = [
            f"{industry} companies {location} outdated website manual processes",
            f"{industry} small business {location} no automation struggling operations",
            f"{industry} companies hiring for manual data entry {location}",
            f"'{industry}' business {location} 'looking to automate' OR 'need automation'",
            f"{industry} {location} companies {revenue_min}+ revenue slow website",
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        # Deduplicate by domain
        seen_domains = set()
        unique_targets = []
        for result in all_results:
            url = result.get("url", "")
            domain = url.split("/")[2] if len(url.split("/")) > 2 else url
            if domain not in seen_domains:
                seen_domains.add(domain)
                unique_targets.append({
                    "company_name": result.get("title", "Unknown"),
                    "url": url,
                    "description": result.get("description", ""),
                    "domain": domain,
                    "source_query": next((q for q in queries if result in all_results), queries[0]),
                })

        # Build automation-poverty indicators
        for target in unique_targets:
            target["automation_poverty_signals"] = self._detect_poverty_signals(target.get("description", ""))

        output = {
            "industry": industry,
            "location": location,
            "revenue_min": revenue_min,
            "scan_date": datetime.utcnow().isoformat(),
            "total_results": len(all_results),
            "unique_targets": len(unique_targets),
            "targets": unique_targets[:15],
            "queries_executed": len(queries),
        }

        # Save to file
        filename = f"industry_scan_{industry.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _detect_poverty_signals(self, description: str) -> list[str]:
        """Detect automation-poverty signals from text."""
        signals = []
        desc_lower = description.lower()
        signal_map = {
            "manual": "Manual processes mentioned",
            "spreadsheet": "Relies on spreadsheets",
            "data entry": "Manual data entry",
            "outdated": "Outdated technology",
            "legacy": "Legacy systems",
            "paper": "Paper-based processes",
            "hiring": "Hiring for automatable roles",
            "slow": "Performance/speed issues",
            "struggling": "Business struggling",
            "looking to automate": "Actively seeking automation",
            "no website": "Weak web presence",
            "fax": "Still using fax",
        }
        for keyword, signal in signal_map.items():
            if keyword in desc_lower:
                signals.append(signal)
        return signals

    async def _scan_company(self, task: AgentTask) -> AgentResult:
        """Deep-scan a specific company."""
        company = task.params.get("company", "")
        url = task.params.get("url", "")

        if not company and not url:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company' or 'url' parameter")

        search_term = company or url
        queries = [
            f'"{search_term}" technology stack automation',
            f'"{search_term}" reviews employees complaints',
            f'"{search_term}" linkedin company size revenue',
            f'site:{url} OR "{search_term}" hiring operations',
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        output = {
            "company": company,
            "url": url,
            "scan_date": datetime.utcnow().isoformat(),
            "findings": [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")} for r in all_results[:20]],
            "integration_opportunities": [
                "Customer service automation (Communication Agent)",
                "Social media management (Apex Architect)",
                "Market research automation (Research Agent + Scout)",
                "Internal process automation (Shell + File + Data agents)",
                "Monitoring & alerting (Monitor Agent)",
            ],
            "recommended_pitch_angle": f"Automate {company}'s operations with 20+ specialized AI agents",
        }

        filename = f"company_scan_{search_term.replace(' ', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _build_target_list(self, task: AgentTask) -> AgentResult:
        """Build ranked target list from existing scan data."""
        industry = task.params.get("industry", "all")
        max_targets = task.params.get("max_targets", 10)

        # Load all scan files
        scan_files = sorted(self._data_dir.glob("industry_scan_*.json"), reverse=True)
        all_targets = []

        for scan_file in scan_files[:5]:  # Last 5 scans
            try:
                data = json.loads(scan_file.read_text())
                if industry == "all" or industry.lower() in data.get("industry", "").lower():
                    all_targets.extend(data.get("targets", []))
            except Exception:
                continue

        # Score and rank targets
        scored_targets = []
        for target in all_targets:
            signals = target.get("automation_poverty_signals", [])
            score = len(signals) * 20  # 20 points per signal
            score = min(100, max(10, score))
            target["automation_score"] = score
            scored_targets.append(target)

        # Sort by score, deduplicate, take top N
        scored_targets.sort(key=lambda x: x.get("automation_score", 0), reverse=True)
        seen = set()
        final_list = []
        for t in scored_targets:
            domain = t.get("domain", "")
            if domain not in seen:
                seen.add(domain)
                final_list.append(t)
            if len(final_list) >= max_targets:
                break

        output = {
            "generated_at": datetime.utcnow().isoformat(),
            "industry_filter": industry,
            "total_scanned": len(all_targets),
            "shortlist_count": len(final_list),
            "shortlist": final_list,
            "recommendation": f"Top {len(final_list)} targets ranked by automation poverty score. Approve targets for Analyst Hand deep-dive.",
        }

        filename = f"target_list_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _score_lead(self, task: AgentTask) -> AgentResult:
        """Score a single lead on automation-readiness."""
        company = task.params.get("company", "")
        url = task.params.get("url", "")
        signals = task.params.get("signals", [])

        score = 0
        breakdown = {}

        # Web presence score (0-25)
        web_score = 15 if url else 5
        breakdown["web_presence"] = web_score
        score += web_score

        # Automation poverty signals (0-40)
        signal_score = min(40, len(signals) * 10)
        breakdown["automation_poverty"] = signal_score
        score += signal_score

        # Company size estimate (0-20)
        size_score = 15  # Default mid-range
        breakdown["company_size"] = size_score
        score += size_score

        # Revenue potential (0-15)
        revenue_score = 10  # Default estimate
        breakdown["revenue_potential"] = revenue_score
        score += revenue_score

        output = {
            "company": company,
            "url": url,
            "total_score": min(100, score),
            "grade": "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D",
            "breakdown": breakdown,
            "recommendation": "Proceed to Analyst" if score >= 50 else "Low priority — skip or revisit later",
            "scored_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
