"""
Scout Agent v2.0.0 — High-velocity lead discovery for the Global Expansion Pulse.

Finds companies that are high-revenue but "automation-poor" — meaning they
have outdated tech stacks, manual processes, weak online presence, or gaps
where Cipher's agent ecosystem could be plugged in.

Uses Brave Search API (required) with DuckDuckGo fallback.
NO MOCK DATA — fails honestly if no search backend is available.

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
            version="2.0.0",
            capabilities=[
                AgentCapability(name="scan_industry", description="Scan an industry for companies with weak automation/tech infrastructure", category="research", timeout_seconds=90),
                AgentCapability(name="scan_company", description="Deep-scan a specific company for automation gaps and integration opportunities", category="research", timeout_seconds=60),
                AgentCapability(name="build_target_list", description="Generate a ranked shortlist of 5-10 targets from industry scan results", category="research", timeout_seconds=45),
                AgentCapability(name="score_lead", description="Score a single lead on automation-readiness (0-100)", category="research", timeout_seconds=30),
            ],
        )

        self._data_dir = Path("./data/expansion_pulse/scout")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        logger.info("ScoutAgent v2.0.0 initialized — no mock data")

    def requires_approval_for(self, instruction: str) -> bool:
        return False

    async def validate(self, task: AgentTask) -> bool:
        if not await super().validate(task):
            return False
        if not task.params.get("operation"):
            logger.warning(f"Task {task.task_id}: Missing operation parameter")
            return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        operation = task.params.get("operation", "")
        try:
            handler = {
                "scan_industry": self._scan_industry,
                "scan_company": self._scan_company,
                "build_target_list": self._build_target_list,
                "score_lead": self._score_lead,
            }.get(operation)
            if not handler:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")
            await self.emit_progress(f"Running {operation}...")
            return await handler(task)
        except Exception as e:
            logger.error(f"Scout operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    async def _web_search(self, query: str, count: int = 10) -> list[dict]:
        """Search via Brave API with DuckDuckGo fallback. No mock data."""
        # Try Brave first
        if self.brave_api_key:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        headers={"X-Subscription-Token": self.brave_api_key, "Accept": "application/json"},
                        params={"q": query, "count": count},
                    )
                    resp.raise_for_status()
                    results = resp.json().get("web", {}).get("results", [])
                    if results:
                        return results
            except Exception as e:
                logger.warning(f"Brave search failed for '{query[:50]}': {e}")

        # DuckDuckGo fallback
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if resp.status_code == 200:
                    text = resp.text
                    results = []
                    # Parse DuckDuckGo HTML results
                    import re
                    links = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.+?)</a>', text)
                    snippets = re.findall(r'<a class="result__snippet"[^>]*>(.+?)</a>', text)
                    for i, (url, title) in enumerate(links[:count]):
                        results.append({
                            "title": re.sub(r'<[^>]+>', '', title).strip(),
                            "url": url,
                            "description": re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else "",
                        })
                    if results:
                        return results
        except Exception as e:
            logger.warning(f"DuckDuckGo fallback failed: {e}")

        # No search backend available — return empty, not mock data
        if not self.brave_api_key:
            logger.error("No search API available: BRAVE_SEARCH_API_KEY not set and DuckDuckGo fallback failed")
        return []

    async def _scan_industry(self, task: AgentTask) -> AgentResult:
        """Scan an industry for automation-poor companies."""
        industry = task.params.get("industry", "")
        location = task.params.get("location", "United States")
        revenue_min = task.params.get("revenue_min", "1M")

        if not industry:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'industry' parameter")

        queries = [
            f"{industry} companies {location} outdated website manual processes",
            f"{industry} small business {location} no automation struggling operations",
            f"{industry} companies hiring for manual data entry {location}",
            f"'{industry}' business {location} 'looking to automate' OR 'need automation'",
            f"{industry} {location} companies {revenue_min}+ revenue slow website",
        ]

        all_results = []
        query_map = {}  # Track which query produced which results
        for query in queries:
            results = await self._web_search(query, count=5)
            for r in results:
                query_map[r.get("url", "")] = query
            all_results.extend(results)

        if not all_results:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error=f"No search results found for industry '{industry}'. "
                      f"{'BRAVE_SEARCH_API_KEY is not configured.' if not self.brave_api_key else 'Search APIs returned no results.'}",
            )

        # Deduplicate by domain
        seen_domains = set()
        unique_targets = []
        for result in all_results:
            url = result.get("url", "")
            parts = url.split("/")
            domain = parts[2] if len(parts) > 2 else url
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                unique_targets.append({
                    "company_name": result.get("title", "Unknown"),
                    "url": url,
                    "description": result.get("description", ""),
                    "domain": domain,
                    "source_query": query_map.get(url, queries[0]),
                })

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
            "search_backend": "brave" if self.brave_api_key else "duckduckgo",
        }

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
            "excel": "Heavy Excel/spreadsheet dependency",
            "pen and paper": "Pen and paper workflows",
            "phone calls": "Phone-dependent operations",
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
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company' or 'url'")

        search_term = company or url
        queries = [
            f'"{search_term}" technology stack automation',
            f'"{search_term}" reviews employees complaints',
            f'"{search_term}" linkedin company size revenue',
            f'site:{url} OR "{search_term}" hiring operations' if url else f'"{search_term}" hiring operations',
        ]

        all_results = []
        for query in queries:
            results = await self._web_search(query, count=5)
            all_results.extend(results)

        if not all_results:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error=f"No results found for '{search_term}'. Check the company name or URL.",
            )

        # Analyze findings for automation signals
        all_text = " ".join(r.get("description", "") for r in all_results).lower()
        poverty_signals = self._detect_poverty_signals(all_text)

        # Build integration opportunities based on actual findings
        opportunities = []
        if "customer" in all_text or "support" in all_text:
            opportunities.append("Customer service automation (Communication Agent)")
        if "social" in all_text or "marketing" in all_text or "content" in all_text:
            opportunities.append("Social media & content management (Apex Architect)")
        if "research" in all_text or "market" in all_text or "competitor" in all_text:
            opportunities.append("Market research automation (Research Agent)")
        if "data" in all_text or "report" in all_text or "analytics" in all_text:
            opportunities.append("Data analysis & reporting (Data Agent)")
        if "monitor" in all_text or "uptime" in all_text or "alert" in all_text:
            opportunities.append("Monitoring & alerting (Monitor Agent)")
        if not opportunities:
            opportunities = [
                "Internal process automation (Shell + File + Data agents)",
                "Market intelligence (Research Agent + Scout)",
                "Content & marketing (Apex Architect)",
            ]

        output = {
            "company": company,
            "url": url,
            "scan_date": datetime.utcnow().isoformat(),
            "findings": [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")} for r in all_results[:20]],
            "automation_poverty_signals": poverty_signals,
            "integration_opportunities": opportunities,
            "signal_count": len(poverty_signals),
        }

        filename = f"company_scan_{search_term.replace(' ', '_').replace('/', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _build_target_list(self, task: AgentTask) -> AgentResult:
        """Build ranked target list from existing scan data."""
        industry = task.params.get("industry", "all")
        max_targets = task.params.get("max_targets", 10)

        scan_files = sorted(self._data_dir.glob("industry_scan_*.json"), reverse=True)
        if not scan_files:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="No industry scan data found. Run scan_industry first.",
            )

        all_targets = []
        for scan_file in scan_files[:5]:
            try:
                data = json.loads(scan_file.read_text())
                if industry == "all" or industry.lower() in data.get("industry", "").lower():
                    all_targets.extend(data.get("targets", []))
            except Exception:
                continue

        if not all_targets:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error=f"No targets found for industry filter '{industry}'.",
            )

        scored_targets = []
        for target in all_targets:
            signals = target.get("automation_poverty_signals", [])
            score = min(100, max(10, len(signals) * 20))
            target["automation_score"] = score
            scored_targets.append(target)

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
            "recommendation": f"Top {len(final_list)} targets ranked by automation poverty score. Approve targets for Analyst deep-dive.",
        }

        filename = f"target_list_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _score_lead(self, task: AgentTask) -> AgentResult:
        """Score a single lead — enriched with real web search data."""
        company = task.params.get("company", "")
        url = task.params.get("url", "")
        signals = task.params.get("signals", [])

        if not company and not url:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company' or 'url'")

        # If no signals provided, do a quick search to find some
        if not signals and (company or url):
            search_term = company or url
            results = await self._web_search(f'"{search_term}" automation technology', count=5)
            all_text = " ".join(r.get("description", "") for r in results).lower()
            signals = self._detect_poverty_signals(all_text)

        score = 0
        breakdown = {}

        # Web presence score (0-25)
        web_score = 15 if url else 5
        breakdown["web_presence"] = web_score
        score += web_score

        # Automation poverty signals (0-40)
        signal_score = min(40, len(signals) * 10)
        breakdown["automation_poverty"] = signal_score
        breakdown["signals_detected"] = signals
        score += signal_score

        # Company size estimate (0-20)
        size_score = 15
        breakdown["company_size"] = size_score
        score += size_score

        # Revenue potential (0-15)
        revenue_score = 10
        breakdown["revenue_potential"] = revenue_score
        score += revenue_score

        total_score = min(100, score)

        output = {
            "company": company,
            "url": url,
            "total_score": total_score,
            "grade": "A" if total_score >= 80 else "B" if total_score >= 60 else "C" if total_score >= 40 else "D",
            "breakdown": breakdown,
            "recommendation": "Proceed to Analyst" if total_score >= 50 else "Low priority — skip or revisit later",
            "scored_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
