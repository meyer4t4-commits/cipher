"""
Neighborhood Growth Scraper — "Path of Progress" zone detector for Apex Asset Hunter.

Cross-references census data, building permits, and local economic indicators
to find neighborhoods where property values are rising but pockets of
undervalued homes still exist — the sweet spot for flips and wholesales.

Capabilities:
1. scan_growth_zones — Find neighborhoods with rising values but undervalued pockets
2. analyze_permits — Scan building permit data for renovation/construction activity
3. census_analysis — Pull demographic and economic trends for a ZIP/county
4. path_of_progress — Full "Path of Progress" analysis combining all data sources
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


# ── GROWTH SIGNAL INDICATORS ────────────────────────────────────────────
GROWTH_SIGNALS = {
    # Construction & development
    "new construction": {"category": "development", "weight": 20, "direction": "bullish"},
    "building permits": {"category": "development", "weight": 18, "direction": "bullish"},
    "rezoning": {"category": "development", "weight": 15, "direction": "bullish"},
    "mixed-use": {"category": "development", "weight": 15, "direction": "bullish"},
    "planned development": {"category": "development", "weight": 17, "direction": "bullish"},
    "ground breaking": {"category": "development", "weight": 16, "direction": "bullish"},
    "redevelopment": {"category": "development", "weight": 18, "direction": "bullish"},

    # Commercial expansion
    "new business": {"category": "commercial", "weight": 12, "direction": "bullish"},
    "restaurant opening": {"category": "commercial", "weight": 10, "direction": "bullish"},
    "retail expansion": {"category": "commercial", "weight": 12, "direction": "bullish"},
    "shopping center": {"category": "commercial", "weight": 14, "direction": "bullish"},
    "grocery store": {"category": "commercial", "weight": 15, "direction": "bullish"},
    "starbucks": {"category": "commercial", "weight": 10, "direction": "bullish"},
    "whole foods": {"category": "commercial", "weight": 15, "direction": "bullish"},
    "trader joe": {"category": "commercial", "weight": 15, "direction": "bullish"},

    # Infrastructure
    "highway": {"category": "infrastructure", "weight": 14, "direction": "bullish"},
    "transit": {"category": "infrastructure", "weight": 16, "direction": "bullish"},
    "light rail": {"category": "infrastructure", "weight": 18, "direction": "bullish"},
    "new school": {"category": "infrastructure", "weight": 15, "direction": "bullish"},
    "hospital": {"category": "infrastructure", "weight": 14, "direction": "bullish"},
    "park": {"category": "infrastructure", "weight": 10, "direction": "bullish"},
    "trail": {"category": "infrastructure", "weight": 8, "direction": "bullish"},

    # Employment
    "hiring": {"category": "employment", "weight": 12, "direction": "bullish"},
    "corporate headquarters": {"category": "employment", "weight": 20, "direction": "bullish"},
    "tech company": {"category": "employment", "weight": 18, "direction": "bullish"},
    "distribution center": {"category": "employment", "weight": 14, "direction": "bullish"},
    "amazon": {"category": "employment", "weight": 16, "direction": "bullish"},
    "warehouse": {"category": "employment", "weight": 10, "direction": "bullish"},

    # Gentrification signals
    "gentrification": {"category": "demographic", "weight": 15, "direction": "bullish"},
    "up and coming": {"category": "demographic", "weight": 14, "direction": "bullish"},
    "revitalization": {"category": "demographic", "weight": 16, "direction": "bullish"},
    "arts district": {"category": "demographic", "weight": 14, "direction": "bullish"},
    "breweries": {"category": "demographic", "weight": 10, "direction": "bullish"},
    "coffee shop": {"category": "demographic", "weight": 8, "direction": "bullish"},
    "young professionals": {"category": "demographic", "weight": 12, "direction": "bullish"},

    # Negative signals (still track them)
    "crime increase": {"category": "risk", "weight": -15, "direction": "bearish"},
    "factory closing": {"category": "risk", "weight": -18, "direction": "bearish"},
    "plant closing": {"category": "risk", "weight": -18, "direction": "bearish"},
    "layoffs": {"category": "risk", "weight": -14, "direction": "bearish"},
    "flood zone": {"category": "risk", "weight": -12, "direction": "bearish"},
    "environmental": {"category": "risk", "weight": -10, "direction": "bearish"},
    "contamination": {"category": "risk", "weight": -20, "direction": "bearish"},
}


class NeighborhoodGrowthAgent(BaseAgent):
    """Finds 'Path of Progress' zones — rising areas with undervalued pockets."""

    def __init__(self):
        super().__init__(
            name="neighborhood_growth_agent",
            description="Path of Progress detector — finds neighborhoods where values are rising but undervalued pockets remain",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="scan_growth_zones",
                    description="Find neighborhoods with bullish growth signals and remaining undervalued properties",
                    category="research",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="analyze_permits",
                    description="Scan building permit data for renovation and construction activity in a market",
                    category="research",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="census_analysis",
                    description="Pull demographic and economic trends from census data for a target area",
                    category="research",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="path_of_progress",
                    description="Full Path of Progress analysis — combines permits, census, commercial activity, and infrastructure",
                    category="research",
                    timeout_seconds=180,
                ),
            ],
        )

        self._data_dir = Path("./data/apex_asset_hunter/neighborhoods")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.census_api_key = os.getenv("CENSUS_API_KEY", "")
        logger.info("NeighborhoodGrowthAgent initialized")

    def requires_approval_for(self, instruction: str) -> bool:
        return False  # Read-only research

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
            if operation == "scan_growth_zones":
                await self.emit_progress("Scanning for growth zones...")
                return await self._scan_growth_zones(task)
            elif operation == "analyze_permits":
                await self.emit_progress("Analyzing building permit activity...")
                return await self._analyze_permits(task)
            elif operation == "census_analysis":
                await self.emit_progress("Pulling census demographic data...")
                return await self._census_analysis(task)
            elif operation == "path_of_progress":
                await self.emit_progress("Running full Path of Progress analysis...")
                return await self._path_of_progress(task)
            else:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            logger.error(f"NeighborhoodGrowth operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    async def _brave_search(self, query: str, count: int = 10) -> list[dict]:
        if not self.brave_api_key:
            return [{"title": f"[Mock] {query}", "url": "https://example.com", "description": f"Mock result for: {query}"}]
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

    # ── GROWTH ZONE SCANNER ──────────────────────────────────────────────
    async def _scan_growth_zones(self, task: AgentTask) -> AgentResult:
        """Find neighborhoods with rising values but remaining undervalued pockets."""
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        county = task.params.get("county", "")
        radius_miles = task.params.get("radius_miles", 25)

        location = f"{city}, {state}" if city else f"{county} County, {state}"
        if not state:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing state parameter")

        # Multi-query strategy for growth signals
        queries = [
            f"'{location}' new development construction 2025 2026",
            f"'{location}' real estate 'values rising' 'up and coming' neighborhood",
            f"'{location}' building permits issued commercial residential",
            f"'{location}' 'best neighborhoods to invest' real estate 2026",
            f"'{location}' gentrification revitalization new businesses opening",
            f"'{location}' transit expansion highway project infrastructure",
            f"'{location}' corporate relocation headquarters jobs growth",
            f"'{location}' 'undervalued' OR 'affordable' neighborhood near new development",
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        # Analyze each result for growth signals
        neighborhoods = {}
        for result in all_results:
            title = result.get("title", "")
            desc = result.get("description", "")
            combined = f"{title} {desc}".lower()

            # Detect growth signals
            detected = []
            total_weight = 0
            for keyword, signal in GROWTH_SIGNALS.items():
                if keyword in combined:
                    detected.append({
                        "signal": keyword,
                        "category": signal["category"],
                        "weight": signal["weight"],
                        "direction": signal["direction"],
                    })
                    total_weight += signal["weight"]

            if detected:
                # Try to extract neighborhood name from title
                hood_name = title[:60]
                if hood_name not in neighborhoods:
                    neighborhoods[hood_name] = {
                        "name": hood_name,
                        "signals": [],
                        "total_score": 0,
                        "sources": [],
                        "bullish_count": 0,
                        "bearish_count": 0,
                    }
                neighborhoods[hood_name]["signals"].extend(detected)
                neighborhoods[hood_name]["total_score"] += total_weight
                neighborhoods[hood_name]["sources"].append(result.get("url", ""))
                neighborhoods[hood_name]["bullish_count"] += len([d for d in detected if d["direction"] == "bullish"])
                neighborhoods[hood_name]["bearish_count"] += len([d for d in detected if d["direction"] == "bearish"])

        # Rank neighborhoods by growth score
        ranked = sorted(neighborhoods.values(), key=lambda x: x["total_score"], reverse=True)

        # Categorize signal distribution
        category_summary = {}
        for hood in ranked:
            for signal in hood["signals"]:
                cat = signal["category"]
                category_summary[cat] = category_summary.get(cat, 0) + 1

        output = {
            "location": location,
            "radius_miles": radius_miles,
            "scan_date": datetime.utcnow().isoformat(),
            "growth_zones_found": len(ranked),
            "top_zones": ranked[:10],
            "signal_category_distribution": category_summary,
            "queries_executed": len(queries),
            "total_results_analyzed": len(all_results),
            "next_steps": "Route top 3 growth zones to Market Pulse for listing scans in those areas",
        }

        filename = f"growth_zones_{location.replace(', ', '_').replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    # ── BUILDING PERMIT ANALYZER ─────────────────────────────────────────
    async def _analyze_permits(self, task: AgentTask) -> AgentResult:
        """Analyze building permit activity for investment signals."""
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        county = task.params.get("county", "")
        zip_code = task.params.get("zip_code", "")

        location = f"{city}, {state}" if city else f"{county} County, {state}" if county else zip_code
        if not location:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing location parameter")

        queries = [
            f"building permits issued {location} 2025 2026",
            f"construction permits {location} new residential commercial",
            f"renovation permits {location} major projects",
            f"{location} planning commission approved projects",
            f"{location} zoning changes approved 2025 2026",
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        # Categorize permit activity
        permit_types = {
            "residential_new": 0,
            "residential_renovation": 0,
            "commercial_new": 0,
            "commercial_renovation": 0,
            "mixed_use": 0,
            "infrastructure": 0,
            "demolition": 0,
        }

        permit_entries = []
        for result in all_results:
            combined = f"{result.get('title', '')} {result.get('description', '')}".lower()
            entry = {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("description", ""),
                "type": "unknown",
            }

            if any(kw in combined for kw in ["new home", "residential construction", "subdivision", "new build"]):
                entry["type"] = "residential_new"
                permit_types["residential_new"] += 1
            elif any(kw in combined for kw in ["renovation", "remodel", "rehab", "addition"]):
                entry["type"] = "residential_renovation"
                permit_types["residential_renovation"] += 1
            elif any(kw in combined for kw in ["commercial", "office", "retail", "restaurant"]):
                entry["type"] = "commercial_new"
                permit_types["commercial_new"] += 1
            elif any(kw in combined for kw in ["mixed-use", "mixed use"]):
                entry["type"] = "mixed_use"
                permit_types["mixed_use"] += 1
            elif any(kw in combined for kw in ["road", "bridge", "sewer", "water main", "utility"]):
                entry["type"] = "infrastructure"
                permit_types["infrastructure"] += 1
            elif any(kw in combined for kw in ["demolition", "teardown"]):
                entry["type"] = "demolition"
                permit_types["demolition"] += 1

            permit_entries.append(entry)

        # Calculate activity score
        activity_score = (
            permit_types["residential_new"] * 15 +
            permit_types["residential_renovation"] * 8 +
            permit_types["commercial_new"] * 20 +
            permit_types["commercial_renovation"] * 10 +
            permit_types["mixed_use"] * 18 +
            permit_types["infrastructure"] * 12 +
            permit_types["demolition"] * 5
        )
        activity_score = min(100, activity_score)

        output = {
            "location": location,
            "scan_date": datetime.utcnow().isoformat(),
            "permit_activity_score": activity_score,
            "activity_level": "Hot" if activity_score >= 70 else "Active" if activity_score >= 40 else "Moderate" if activity_score >= 20 else "Low",
            "permit_type_breakdown": permit_types,
            "total_permits_found": len(permit_entries),
            "permits": permit_entries[:15],
            "investment_signal": "BULLISH" if activity_score >= 50 else "NEUTRAL" if activity_score >= 25 else "BEARISH",
        }

        filename = f"permits_{location.replace(', ', '_').replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    # ── CENSUS ANALYSIS ──────────────────────────────────────────────────
    async def _census_analysis(self, task: AgentTask) -> AgentResult:
        """Pull demographic and economic trends for a target area."""
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        county = task.params.get("county", "")
        zip_code = task.params.get("zip_code", "")

        location = f"{city}, {state}" if city else f"{county} County, {state}" if county else zip_code
        if not location:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing location parameter")

        # Census data queries
        queries = [
            f"{location} census population growth trend",
            f"{location} median household income trend",
            f"{location} median home value appreciation",
            f"{location} demographics age education employment",
            f"{location} poverty rate crime rate statistics",
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        # Extract demographic indicators from search results
        indicators = {
            "population_trend": self._detect_trend(all_results, ["population growth", "growing population", "population increase"]),
            "income_trend": self._detect_trend(all_results, ["income rising", "income growth", "higher income", "median income"]),
            "home_value_trend": self._detect_trend(all_results, ["home values rising", "appreciation", "property values up", "prices increasing"]),
            "employment_trend": self._detect_trend(all_results, ["employment growth", "jobs added", "unemployment low", "hiring"]),
            "education_level": self._detect_trend(all_results, ["college educated", "university", "educated workforce"]),
        }

        # Calculate composite growth score
        trend_scores = {"bullish": 20, "neutral": 10, "bearish": 0, "unknown": 5}
        composite_score = sum(trend_scores.get(v, 5) for v in indicators.values())
        composite_score = min(100, composite_score)

        output = {
            "location": location,
            "scan_date": datetime.utcnow().isoformat(),
            "demographic_indicators": indicators,
            "composite_growth_score": composite_score,
            "growth_outlook": "Strong Growth" if composite_score >= 80 else "Moderate Growth" if composite_score >= 50 else "Flat" if composite_score >= 30 else "Declining",
            "total_data_points": len(all_results),
            "data_sources": [{"title": r.get("title", ""), "url": r.get("url", "")} for r in all_results[:10]],
            "investment_signal": "BULLISH" if composite_score >= 60 else "NEUTRAL" if composite_score >= 35 else "BEARISH",
        }

        filename = f"census_{location.replace(', ', '_').replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _detect_trend(self, results: list[dict], keywords: list[str]) -> str:
        """Detect if search results indicate a positive, neutral, or negative trend."""
        positive_hits = 0
        negative_hits = 0
        for r in results:
            combined = f"{r.get('title', '')} {r.get('description', '')}".lower()
            for kw in keywords:
                if kw in combined:
                    positive_hits += 1
            if any(neg in combined for neg in ["decline", "decrease", "falling", "dropping", "shrinking"]):
                negative_hits += 1

        if positive_hits >= 3:
            return "bullish"
        elif positive_hits >= 1 and negative_hits == 0:
            return "neutral"
        elif negative_hits >= 2:
            return "bearish"
        return "unknown"

    # ── FULL PATH OF PROGRESS ────────────────────────────────────────────
    async def _path_of_progress(self, task: AgentTask) -> AgentResult:
        """Complete Path of Progress analysis combining all data sources."""
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        county = task.params.get("county", "")

        await self.emit_progress("Step 1/3: Analyzing building permit activity...")

        # Step 1: Permits
        permit_task = AgentTask(
            agent_name=self.name,
            instruction="Analyze permits",
            params={"operation": "analyze_permits", "city": city, "state": state, "county": county},
        )
        permit_result = await self._analyze_permits(permit_task)

        await self.emit_progress("Step 2/3: Pulling census demographic data...")

        # Step 2: Census
        census_task = AgentTask(
            agent_name=self.name,
            instruction="Census analysis",
            params={"operation": "census_analysis", "city": city, "state": state, "county": county},
        )
        census_result = await self._census_analysis(census_task)

        await self.emit_progress("Step 3/3: Scanning for growth zone signals...")

        # Step 3: Growth zones
        growth_task = AgentTask(
            agent_name=self.name,
            instruction="Scan growth zones",
            params={"operation": "scan_growth_zones", "city": city, "state": state, "county": county},
        )
        growth_result = await self._scan_growth_zones(growth_task)

        # Combine scores
        permit_score = permit_result.output.get("permit_activity_score", 0) if permit_result.success else 0
        census_score = census_result.output.get("composite_growth_score", 0) if census_result.success else 0
        growth_zones = growth_result.output.get("top_zones", []) if growth_result.success else []
        top_zone_score = growth_zones[0]["total_score"] if growth_zones else 0

        # Weighted composite: Permits 35%, Census 30%, Growth signals 35%
        composite = round(permit_score * 0.35 + census_score * 0.30 + min(100, top_zone_score) * 0.35, 1)

        location = f"{city}, {state}" if city else f"{county} County, {state}"

        output = {
            "location": location,
            "analysis_date": datetime.utcnow().isoformat(),
            "path_of_progress_score": composite,
            "verdict": self._pop_verdict(composite),
            "component_scores": {
                "permit_activity": permit_score,
                "census_demographics": census_score,
                "growth_signal_strength": min(100, top_zone_score),
            },
            "weight_formula": "Permits 35% + Census 30% + Growth Signals 35%",
            "top_growth_zones": growth_zones[:5],
            "permit_summary": {
                "activity_level": permit_result.output.get("activity_level", "Unknown") if permit_result.success else "Unknown",
                "breakdown": permit_result.output.get("permit_type_breakdown", {}) if permit_result.success else {},
            },
            "census_summary": {
                "outlook": census_result.output.get("growth_outlook", "Unknown") if census_result.success else "Unknown",
                "indicators": census_result.output.get("demographic_indicators", {}) if census_result.success else {},
            },
            "recommendation": self._pop_recommendation(composite, growth_zones),
        }

        filename = f"path_of_progress_{location.replace(', ', '_').replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _pop_verdict(self, score: float) -> str:
        if score >= 75:
            return "STRONG PATH OF PROGRESS — High confidence investment zone"
        elif score >= 55:
            return "MODERATE PATH OF PROGRESS — Good potential, do deeper due diligence"
        elif score >= 35:
            return "WEAK SIGNALS — Some growth indicators but not convincing"
        return "NO PATH OF PROGRESS DETECTED — Avoid or wait for catalysts"

    def _pop_recommendation(self, score: float, zones: list) -> str:
        if score >= 75:
            zone_names = ", ".join([z.get("name", "Unknown")[:40] for z in zones[:3]])
            return f"INVEST: Active Path of Progress detected. Focus listings search on: {zone_names}. Route these ZIP codes to Market Pulse for immediate listing scans."
        elif score >= 55:
            return "WATCH: Growth signals present but not overwhelming. Set up weekly monitoring via Market Pulse. Look for properties at 60-65% of ARV for extra margin."
        elif score >= 35:
            return "HOLD: Weak growth signals. Only pursue deals with 40%+ margin (use 60% rule instead of 70%). Check back quarterly."
        return "PASS: No meaningful growth indicators. Capital better deployed in stronger markets."

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
