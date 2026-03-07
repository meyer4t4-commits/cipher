"""
Profitability Analyst Agent — The 70% Rule calculator for Apex Asset Hunter.

Calculates Maximum Allowable Offer (MAO) using the gold standard:
  MAO = (ARV * 0.70) - Estimated Repair Costs

Uses AI-powered analysis of property photos for "distress signals" —
outdated kitchens, roof damage, overgrown yards — to estimate repair
cost tiers. Pulls comparable sales (comps) for ARV estimation.

Capabilities:
1. calculate_mao — Run 70% Rule on a property (ARV, repair estimate, MAO)
2. estimate_arv — Pull comparable sales to estimate After Repair Value
3. assess_repairs — Analyze property condition and estimate repair costs
4. full_deal_analysis — Complete flip/wholesale analysis with ROI projection
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


# ── REPAIR COST TIERS ────────────────────────────────────────────────────
REPAIR_TIERS = {
    "cosmetic": {
        "label": "Cosmetic / Light Rehab",
        "per_sqft_low": 10,
        "per_sqft_high": 25,
        "description": "Paint, flooring, fixtures, minor landscaping. No structural work.",
        "typical_total_range": "$15K-$40K",
    },
    "moderate": {
        "label": "Moderate Rehab",
        "per_sqft_low": 25,
        "per_sqft_high": 50,
        "description": "Kitchen/bath remodel, HVAC, electrical updates, some drywall. No foundation work.",
        "typical_total_range": "$40K-$80K",
    },
    "heavy": {
        "label": "Heavy Rehab",
        "per_sqft_low": 50,
        "per_sqft_high": 80,
        "description": "Full gut renovation. New kitchen, baths, HVAC, roof, possible structural repairs.",
        "typical_total_range": "$80K-$150K",
    },
    "full_gut": {
        "label": "Full Gut / Down to Studs",
        "per_sqft_low": 80,
        "per_sqft_high": 150,
        "description": "Complete tear-down and rebuild of interior. Foundation work, new everything.",
        "typical_total_range": "$150K-$300K+",
    },
}

# ── DISTRESS SIGNAL PATTERNS ────────────────────────────────────────────
DISTRESS_SIGNAL_MAP = {
    # Kitchen indicators
    "outdated kitchen": {"category": "kitchen", "severity": "moderate", "cost_weight": 15000},
    "old kitchen": {"category": "kitchen", "severity": "moderate", "cost_weight": 15000},
    "original kitchen": {"category": "kitchen", "severity": "moderate", "cost_weight": 15000},
    "kitchen needs": {"category": "kitchen", "severity": "heavy", "cost_weight": 25000},
    "no kitchen updates": {"category": "kitchen", "severity": "moderate", "cost_weight": 18000},

    # Bathroom indicators
    "outdated bathroom": {"category": "bathroom", "severity": "moderate", "cost_weight": 10000},
    "old bathroom": {"category": "bathroom", "severity": "moderate", "cost_weight": 10000},
    "bathroom needs": {"category": "bathroom", "severity": "heavy", "cost_weight": 15000},

    # Roof indicators
    "roof damage": {"category": "roof", "severity": "heavy", "cost_weight": 12000},
    "roof leak": {"category": "roof", "severity": "heavy", "cost_weight": 15000},
    "old roof": {"category": "roof", "severity": "moderate", "cost_weight": 10000},
    "needs new roof": {"category": "roof", "severity": "heavy", "cost_weight": 18000},
    "roof replace": {"category": "roof", "severity": "heavy", "cost_weight": 18000},

    # Foundation/structural
    "foundation": {"category": "structure", "severity": "full_gut", "cost_weight": 25000},
    "structural": {"category": "structure", "severity": "full_gut", "cost_weight": 30000},
    "settling": {"category": "structure", "severity": "heavy", "cost_weight": 20000},
    "crack": {"category": "structure", "severity": "moderate", "cost_weight": 8000},

    # Exterior/yard
    "overgrown": {"category": "exterior", "severity": "cosmetic", "cost_weight": 3000},
    "landscaping": {"category": "exterior", "severity": "cosmetic", "cost_weight": 5000},
    "curb appeal": {"category": "exterior", "severity": "cosmetic", "cost_weight": 5000},
    "siding": {"category": "exterior", "severity": "moderate", "cost_weight": 12000},

    # Systems
    "hvac": {"category": "systems", "severity": "moderate", "cost_weight": 8000},
    "plumbing": {"category": "systems", "severity": "moderate", "cost_weight": 10000},
    "electrical": {"category": "systems", "severity": "moderate", "cost_weight": 12000},
    "water heater": {"category": "systems", "severity": "cosmetic", "cost_weight": 3000},
    "furnace": {"category": "systems", "severity": "moderate", "cost_weight": 6000},

    # General condition
    "needs work": {"category": "general", "severity": "moderate", "cost_weight": 20000},
    "fixer": {"category": "general", "severity": "moderate", "cost_weight": 25000},
    "handyman": {"category": "general", "severity": "moderate", "cost_weight": 20000},
    "as-is": {"category": "general", "severity": "moderate", "cost_weight": 25000},
    "as is": {"category": "general", "severity": "moderate", "cost_weight": 25000},
    "tlc": {"category": "general", "severity": "cosmetic", "cost_weight": 15000},
    "dated": {"category": "general", "severity": "cosmetic", "cost_weight": 15000},
    "cosmetic": {"category": "general", "severity": "cosmetic", "cost_weight": 10000},
    "gut rehab": {"category": "general", "severity": "full_gut", "cost_weight": 80000},
    "condemned": {"category": "general", "severity": "full_gut", "cost_weight": 100000},
    "fire damage": {"category": "general", "severity": "full_gut", "cost_weight": 75000},
    "water damage": {"category": "general", "severity": "heavy", "cost_weight": 30000},
    "mold": {"category": "general", "severity": "heavy", "cost_weight": 15000},
}


class ProfitabilityAnalystAgent(BaseAgent):
    """Calculates deal profitability using the 70% Rule with AI-powered repair estimation."""

    def __init__(self):
        super().__init__(
            name="profitability_analyst_agent",
            description="70% Rule calculator — computes MAO, estimates repairs from distress signals, pulls comps for ARV",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="calculate_mao",
                    description="Calculate Maximum Allowable Offer using 70% Rule: (ARV * 0.70) - Repair Costs",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="estimate_arv",
                    description="Estimate After Repair Value using comparable sales data",
                    category="research",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="assess_repairs",
                    description="Analyze property condition and estimate repair costs from listing text and photo signals",
                    category="data",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="full_deal_analysis",
                    description="Complete flip/wholesale analysis — ARV, repairs, MAO, ROI, hold costs, profit projection",
                    category="data",
                    timeout_seconds=120,
                ),
            ],
        )

        self._data_dir = Path("./data/apex_asset_hunter/profitability")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        logger.info("ProfitabilityAnalystAgent initialized")

    def requires_approval_for(self, instruction: str) -> bool:
        return False  # All calculations, no external actions

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
            if operation == "calculate_mao":
                await self.emit_progress("Running 70% Rule calculation...")
                return await self._calculate_mao(task)
            elif operation == "estimate_arv":
                await self.emit_progress("Pulling comparable sales for ARV...")
                return await self._estimate_arv(task)
            elif operation == "assess_repairs":
                await self.emit_progress("Analyzing distress signals and estimating repairs...")
                return await self._assess_repairs(task)
            elif operation == "full_deal_analysis":
                await self.emit_progress("Running full deal analysis...")
                return await self._full_deal_analysis(task)
            else:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            logger.error(f"ProfitabilityAnalyst operation failed: {e}")
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

    # ── 70% RULE CALCULATOR ──────────────────────────────────────────────
    async def _calculate_mao(self, task: AgentTask) -> AgentResult:
        """Calculate Maximum Allowable Offer using the 70% Rule."""
        arv = task.params.get("arv", 0)
        repair_costs = task.params.get("repair_costs", 0)
        rule_pct = task.params.get("rule_pct", 0.70)  # Allow override for conservative deals
        closing_costs_pct = task.params.get("closing_costs_pct", 0.03)
        holding_months = task.params.get("holding_months", 4)
        monthly_hold_cost = task.params.get("monthly_hold_cost", 1500)  # Insurance, taxes, utilities, loan interest

        if not arv:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'arv' parameter — provide After Repair Value")

        # Core 70% Rule
        mao = (arv * rule_pct) - repair_costs

        # Extended cost analysis
        buying_closing = arv * closing_costs_pct
        selling_closing = arv * 0.06  # Typical 6% agent commissions + closing
        holding_costs = holding_months * monthly_hold_cost
        total_costs = repair_costs + buying_closing + selling_closing + holding_costs

        # Profit projections at different purchase prices
        flip_profit_at_mao = arv - mao - total_costs
        wholesale_fee = mao * 0.10  # Typical 10% wholesale assignment fee

        output = {
            "arv": arv,
            "rule_pct": rule_pct,
            "repair_costs": repair_costs,
            "mao": round(mao, 2),
            "formula": f"({arv:,} × {rule_pct}) - {repair_costs:,} = {mao:,.2f}",
            "extended_costs": {
                "buying_closing": round(buying_closing, 2),
                "selling_closing": round(selling_closing, 2),
                "holding_costs": round(holding_costs, 2),
                "holding_months": holding_months,
                "monthly_hold_cost": monthly_hold_cost,
                "total_all_in_costs": round(total_costs, 2),
            },
            "profit_projections": {
                "flip_profit_at_mao": round(flip_profit_at_mao, 2),
                "flip_roi_pct": round((flip_profit_at_mao / mao) * 100, 1) if mao > 0 else 0,
                "wholesale_assignment_fee": round(wholesale_fee, 2),
            },
            "deal_grade": self._grade_deal(flip_profit_at_mao, arv, mao),
            "calculated_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _grade_deal(self, profit: float, arv: float, mao: float) -> dict:
        """Grade a deal based on profit margin and ROI."""
        if arv <= 0 or mao <= 0:
            return {"grade": "F", "label": "Invalid deal numbers"}

        roi = (profit / mao) * 100 if mao > 0 else 0
        margin = (profit / arv) * 100 if arv > 0 else 0

        if profit >= 50000 and roi >= 20:
            grade, label = "A+", "Home run deal — maximum margin"
        elif profit >= 50000:
            grade, label = "A", "Excellent — strong profit potential"
        elif profit >= 35000 and roi >= 15:
            grade, label = "B+", "Good deal — solid margins"
        elif profit >= 25000:
            grade, label = "B", "Decent deal — proceed with caution"
        elif profit >= 15000:
            grade, label = "C", "Thin margin — experienced flippers only"
        elif profit > 0:
            grade, label = "D", "Marginal — high risk of break-even"
        else:
            grade, label = "F", "No deal — negative profit"

        return {
            "grade": grade,
            "label": label,
            "estimated_profit": round(profit, 2),
            "roi_pct": round(roi, 1),
            "margin_pct": round(margin, 1),
        }

    # ── ARV ESTIMATION ───────────────────────────────────────────────────
    async def _estimate_arv(self, task: AgentTask) -> AgentResult:
        """Estimate After Repair Value using comparable sales (comps)."""
        address = task.params.get("address", "")
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        zip_code = task.params.get("zip_code", "")
        beds = task.params.get("beds", 3)
        baths = task.params.get("baths", 2)
        sqft = task.params.get("sqft", 1500)

        location = address or f"{city}, {state}" or zip_code
        if not location:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing address, city/state, or zip_code")

        # Search for comparable sales
        queries = [
            f"recently sold homes near {location} {beds} bed {baths} bath {sqft} sqft",
            f"comparable sales {location} renovated {beds}BR Zillow sold",
            f"Redfin sold homes {location} {beds} bedroom {sqft} sq ft 2025 2026",
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        # Extract price data from comps
        comps = []
        for result in all_results:
            comp = self._extract_comp_data(result)
            if comp.get("price"):
                comps.append(comp)

        # Calculate ARV from comps
        prices = [c["price"] for c in comps if c.get("price")]
        if prices:
            avg_price = sum(prices) / len(prices)
            median_price = sorted(prices)[len(prices) // 2]
            arv_estimate = round((avg_price * 0.6 + median_price * 0.4), 2)  # Weighted blend
        else:
            # Fallback: estimate from sqft and area
            arv_estimate = sqft * 200  # Conservative national average per sqft for renovated
            avg_price = arv_estimate
            median_price = arv_estimate

        output = {
            "subject_property": {
                "address": address,
                "location": location,
                "beds": beds,
                "baths": baths,
                "sqft": sqft,
            },
            "arv_estimate": round(arv_estimate, 2),
            "price_per_sqft": round(arv_estimate / sqft, 2) if sqft else 0,
            "comp_analysis": {
                "comps_found": len(comps),
                "avg_comp_price": round(avg_price, 2) if prices else None,
                "median_comp_price": round(median_price, 2) if prices else None,
                "price_range": {"low": min(prices) if prices else None, "high": max(prices) if prices else None},
            },
            "comps": comps[:10],
            "confidence": "high" if len(comps) >= 5 else "medium" if len(comps) >= 3 else "low",
            "method": "comp_analysis" if prices else "sqft_fallback",
            "estimated_at": datetime.utcnow().isoformat(),
        }

        filename = f"arv_{location.replace(', ', '_').replace(' ', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _extract_comp_data(self, result: dict) -> dict:
        """Extract comparable sale data from search result."""
        title = result.get("title", "")
        desc = result.get("description", "")
        combined = f"{title} {desc}"

        price = None
        price_match = re.search(r'\$[\d,]+(?:k)?', combined, re.IGNORECASE)
        if price_match:
            raw = price_match.group().replace("$", "").replace(",", "")
            if raw.lower().endswith("k"):
                price = int(float(raw[:-1]) * 1000)
            else:
                try:
                    val = int(raw)
                    if 50000 <= val <= 5000000:  # Reasonable home price range
                        price = val
                except ValueError:
                    pass

        sqft = None
        sqft_match = re.search(r'([\d,]+)\s*(?:sq\s*ft|sqft)', combined, re.IGNORECASE)
        if sqft_match:
            sqft = int(sqft_match.group(1).replace(",", ""))

        return {
            "title": title,
            "url": result.get("url", ""),
            "price": price,
            "sqft": sqft,
            "price_per_sqft": round(price / sqft, 2) if price and sqft else None,
        }

    # ── REPAIR ASSESSMENT ────────────────────────────────────────────────
    async def _assess_repairs(self, task: AgentTask) -> AgentResult:
        """Analyze property condition and estimate repair costs."""
        listing_text = task.params.get("listing_text", "")
        address = task.params.get("address", "")
        sqft = task.params.get("sqft", 1500)
        year_built = task.params.get("year_built", None)
        photo_descriptions = task.params.get("photo_descriptions", [])

        # Combine all text sources for signal detection
        all_text = f"{listing_text} {' '.join(photo_descriptions)}".lower()

        # If no listing text, try to find it
        if not all_text.strip() and address:
            results = await self._brave_search(f'"{address}" listing details condition', count=3)
            for r in results:
                all_text += f" {r.get('description', '')}"
            all_text = all_text.lower()

        # Detect distress signals
        detected_signals = []
        total_cost_weight = 0
        categories_hit = set()
        max_severity = "cosmetic"
        severity_order = {"cosmetic": 0, "moderate": 1, "heavy": 2, "full_gut": 3}

        for keyword, signal_data in DISTRESS_SIGNAL_MAP.items():
            if keyword in all_text:
                detected_signals.append({
                    "signal": keyword,
                    "category": signal_data["category"],
                    "severity": signal_data["severity"],
                    "estimated_cost_impact": signal_data["cost_weight"],
                })
                total_cost_weight += signal_data["cost_weight"]
                categories_hit.add(signal_data["category"])
                if severity_order.get(signal_data["severity"], 0) > severity_order.get(max_severity, 0):
                    max_severity = signal_data["severity"]

        # Age-based adjustments
        age_adjustment = 0
        if year_built:
            age = datetime.now().year - year_built
            if age > 50:
                age_adjustment = 15000
                max_severity = max(max_severity, "heavy", key=lambda x: severity_order.get(x, 0))
            elif age > 30:
                age_adjustment = 8000
            elif age > 20:
                age_adjustment = 3000

        # Calculate repair estimate
        tier = REPAIR_TIERS.get(max_severity, REPAIR_TIERS["moderate"])
        per_sqft_estimate = (tier["per_sqft_low"] + tier["per_sqft_high"]) / 2
        sqft_based_estimate = per_sqft_estimate * sqft
        signal_based_estimate = total_cost_weight + age_adjustment

        # Blend both methods (60% signal-based, 40% sqft-based)
        repair_estimate = round(signal_based_estimate * 0.6 + sqft_based_estimate * 0.4, 2)

        # Apply floor and ceiling
        repair_estimate = max(repair_estimate, 5000)  # Minimum $5K
        repair_estimate = min(repair_estimate, sqft * 150)  # Cap at full gut per sqft

        output = {
            "address": address,
            "sqft": sqft,
            "year_built": year_built,
            "repair_tier": max_severity,
            "repair_tier_label": tier["label"],
            "repair_estimate": round(repair_estimate, 2),
            "repair_range": {
                "low": round(repair_estimate * 0.75, 2),
                "high": round(repair_estimate * 1.35, 2),
            },
            "distress_signals_detected": len(detected_signals),
            "signals": detected_signals,
            "categories_affected": list(categories_hit),
            "age_adjustment": age_adjustment,
            "estimation_method": {
                "signal_based": round(signal_based_estimate, 2),
                "sqft_based": round(sqft_based_estimate, 2),
                "blend_ratio": "60% signal / 40% sqft",
            },
            "assessed_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    # ── FULL DEAL ANALYSIS ───────────────────────────────────────────────
    async def _full_deal_analysis(self, task: AgentTask) -> AgentResult:
        """Complete flip/wholesale analysis — combines ARV, repairs, MAO, and ROI."""
        address = task.params.get("address", "")
        asking_price = task.params.get("asking_price", 0)
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        beds = task.params.get("beds", 3)
        baths = task.params.get("baths", 2)
        sqft = task.params.get("sqft", 1500)
        year_built = task.params.get("year_built", None)
        listing_text = task.params.get("listing_text", "")
        holding_months = task.params.get("holding_months", 4)

        await self.emit_progress("Step 1/4: Estimating ARV from comps...")

        # Step 1: Estimate ARV
        arv_task = AgentTask(
            agent_name=self.name,
            instruction="Estimate ARV",
            params={"operation": "estimate_arv", "address": address, "city": city, "state": state, "beds": beds, "baths": baths, "sqft": sqft},
        )
        arv_result = await self._estimate_arv(arv_task)
        arv = arv_result.output.get("arv_estimate", sqft * 200) if arv_result.success else sqft * 200

        await self.emit_progress("Step 2/4: Assessing repair costs...")

        # Step 2: Assess repairs
        repair_task = AgentTask(
            agent_name=self.name,
            instruction="Assess repairs",
            params={"operation": "assess_repairs", "address": address, "sqft": sqft, "year_built": year_built, "listing_text": listing_text},
        )
        repair_result = await self._assess_repairs(repair_task)
        repair_costs = repair_result.output.get("repair_estimate", 30000) if repair_result.success else 30000
        repair_tier = repair_result.output.get("repair_tier", "moderate") if repair_result.success else "moderate"

        await self.emit_progress("Step 3/4: Calculating MAO via 70% Rule...")

        # Step 3: Calculate MAO
        mao_task = AgentTask(
            agent_name=self.name,
            instruction="Calculate MAO",
            params={"operation": "calculate_mao", "arv": arv, "repair_costs": repair_costs, "holding_months": holding_months},
        )
        mao_result = await self._calculate_mao(mao_task)
        mao_data = mao_result.output if mao_result.success else {}

        await self.emit_progress("Step 4/4: Generating deal summary...")

        # Step 4: Build comprehensive deal analysis
        mao = mao_data.get("mao", 0)
        deal_grade = mao_data.get("deal_grade", {})

        # Is the asking price good?
        price_vs_mao = asking_price - mao if asking_price and mao else None
        price_verdict = "unknown"
        if price_vs_mao is not None:
            if price_vs_mao <= 0:
                price_verdict = "BELOW MAO — strong buy signal"
            elif price_vs_mao <= 10000:
                price_verdict = "Near MAO — negotiate down"
            elif price_vs_mao <= 25000:
                price_verdict = "Above MAO — only if ARV is conservative"
            else:
                price_verdict = "Too expensive — pass or lowball"

        output = {
            "property": {
                "address": address,
                "city": city,
                "state": state,
                "beds": beds,
                "baths": baths,
                "sqft": sqft,
                "year_built": year_built,
                "asking_price": asking_price,
            },
            "arv_analysis": arv_result.output if arv_result.success else {"error": "ARV estimation failed"},
            "repair_analysis": {
                "repair_tier": repair_tier,
                "repair_estimate": repair_costs,
                "repair_range": repair_result.output.get("repair_range", {}) if repair_result.success else {},
                "signals_detected": repair_result.output.get("distress_signals_detected", 0) if repair_result.success else 0,
            },
            "deal_numbers": {
                "arv": arv,
                "repair_costs": repair_costs,
                "mao": mao,
                "formula": f"({arv:,.0f} × 0.70) - {repair_costs:,.0f} = {mao:,.0f}",
                "asking_price": asking_price,
                "asking_vs_mao": price_vs_mao,
                "price_verdict": price_verdict,
            },
            "profit_projections": mao_data.get("profit_projections", {}),
            "extended_costs": mao_data.get("extended_costs", {}),
            "deal_grade": deal_grade,
            "recommendation": self._generate_recommendation(mao, asking_price, deal_grade, repair_tier),
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        # Save full analysis
        filename = f"deal_analysis_{address.replace(' ', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _generate_recommendation(self, mao: float, asking: float, grade: dict, repair_tier: str) -> str:
        """Generate human-readable deal recommendation."""
        grade_letter = grade.get("grade", "F")
        profit = grade.get("estimated_profit", 0)

        if grade_letter in ("A+", "A"):
            action = "STRONG BUY"
            detail = f"Estimated profit ${profit:,.0f}. Submit offer at or below MAO (${mao:,.0f})."
        elif grade_letter in ("B+", "B"):
            action = "CONDITIONAL BUY"
            detail = f"Decent margin at ${profit:,.0f} profit. Negotiate hard — offer 5-10% below MAO."
        elif grade_letter == "C":
            action = "CAUTION"
            detail = f"Thin margin (${profit:,.0f}). Only pursue if you can control repair costs tightly."
        else:
            action = "PASS"
            detail = f"Numbers don't work. Profit too thin or negative (${profit:,.0f})."

        if repair_tier == "full_gut":
            detail += " WARNING: Full gut rehab — budget overruns likely. Add 20% contingency."
        elif repair_tier == "heavy":
            detail += " Note: Heavy rehab required — verify repair estimates with contractor before offer."

        if asking and mao and asking > mao * 1.15:
            detail += f" Asking (${asking:,.0f}) is significantly above MAO (${mao:,.0f}) — seller expectations need adjustment."

        return f"{action}: {detail}"

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
