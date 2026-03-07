"""
Deal Flow Orchestrator — The brain of the Apex Asset Hunter.

Coordinates Market Pulse, Profitability Analyst, and Neighborhood Growth
agents into a unified deal-flow pipeline. Filters to the top 1% of
opportunities, generates daily high-upside reports, and creates
Investor PDFs for wholesale-ready properties.

Pipeline: Ingest → Filter (>$50K margin) → Analyze → Shortlist → PDF → Outreach

Capabilities:
1. daily_scan — Run full daily deal-flow pipeline for a target market
2. filter_deals — Apply margin and ROI filters to eliminate sub-threshold deals
3. generate_report — Create the "Daily High-Upside Report" with top 5 properties
4. generate_investor_pdf — Create a one-page Investor PDF for wholesale distribution
5. draft_seller_inquiry — Draft a personalized, non-bot inquiry to listing agent/owner
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


class DealFlowAgent(BaseAgent):
    """Orchestrates the full Apex Asset Hunter pipeline — filter, analyze, shortlist, PDF."""

    def __init__(self):
        super().__init__(
            name="deal_flow_agent",
            description="Deal Flow Orchestrator — runs full property scan pipeline, filters to top 1%, generates reports and Investor PDFs",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="daily_scan",
                    description="Run the full daily deal-flow pipeline for a target market",
                    category="research",
                    timeout_seconds=300,
                ),
                AgentCapability(
                    name="filter_deals",
                    description="Apply margin and ROI filters to raw listings — discard anything below threshold",
                    category="data",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="generate_report",
                    description="Generate the Daily High-Upside Report with top 5 properties and full analysis",
                    category="data",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="generate_investor_pdf",
                    description="Create a one-page Investor PDF with MAO, flip profit, and local comps",
                    category="data",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="draft_seller_inquiry",
                    description="Draft a personalized, non-bot-sounding inquiry to listing agent or property owner",
                    category="communication",
                    requires_approval=True,
                    timeout_seconds=45,
                ),
            ],
        )

        self._data_dir = Path("./data/apex_asset_hunter/deal_flow")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._reports_dir = Path("./data/apex_asset_hunter/reports")
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._pdf_dir = Path("./data/apex_asset_hunter/investor_pdfs")
        self._pdf_dir.mkdir(parents=True, exist_ok=True)
        self._outreach_dir = Path("./data/apex_asset_hunter/outreach")
        self._outreach_dir.mkdir(parents=True, exist_ok=True)
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        logger.info("DealFlowAgent initialized")

    def requires_approval_for(self, instruction: str) -> bool:
        lower = instruction.lower()
        # Sending outreach requires approval, scanning/analyzing does not
        return any(kw in lower for kw in ["send", "email", "contact", "reach out", "message"])

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
            if operation == "daily_scan":
                await self.emit_progress("Initiating daily deal-flow scan...")
                return await self._daily_scan(task)
            elif operation == "filter_deals":
                await self.emit_progress("Filtering deals by margin threshold...")
                return await self._filter_deals(task)
            elif operation == "generate_report":
                await self.emit_progress("Generating High-Upside Report...")
                return await self._generate_report(task)
            elif operation == "generate_investor_pdf":
                await self.emit_progress("Creating Investor PDF...")
                return await self._generate_investor_pdf(task)
            elif operation == "draft_seller_inquiry":
                await self.emit_progress("Drafting seller inquiry...")
                return await self._draft_seller_inquiry(task)
            else:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            logger.error(f"DealFlow operation failed: {e}")
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

    # ── DAILY SCAN PIPELINE ──────────────────────────────────────────────
    async def _daily_scan(self, task: AgentTask) -> AgentResult:
        """Run the full daily deal-flow pipeline."""
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        county = task.params.get("county", "")
        max_price = task.params.get("max_price", 500000)
        min_margin = task.params.get("min_margin", 50000)
        min_roi = task.params.get("min_roi", 15)
        property_types = task.params.get("property_types", ["single_family", "multi_family"])

        location = f"{city}, {state}" if city else f"{county} County, {state}"
        scan_id = f"daily_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        await self.emit_progress(f"Phase 1/5: Ingesting listings for {location}...")

        # Phase 1: INGEST — Pull all new listings
        listing_queries = [
            f"new listings {location} under ${max_price:,} for sale today",
            f"Zillow {location} recently listed homes under ${max_price:,}",
            f"Redfin {location} new listings price reduced",
            f"foreclosure {location} pre-foreclosure tax lien properties",
            f"fixer upper {location} as-is handyman special for sale",
            f"motivated seller {location} must sell fast cash buyer",
            f"wholesale deals {location} investor special below market",
            f"estate sale probate {location} real estate",
        ]

        raw_listings = []
        for query in listing_queries:
            results = await self._brave_search(query, count=5)
            raw_listings.extend(results)

        await self.emit_progress(f"Phase 2/5: Parsing {len(raw_listings)} raw results...")

        # Phase 2: PARSE — Extract structured data
        import re
        parsed = []
        seen_urls = set()
        for result in raw_listings:
            url = result.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = result.get("title", "")
            desc = result.get("description", "")
            combined = f"{title} {desc}"

            # Extract price
            price = None
            price_match = re.search(r'\$[\d,]+', combined)
            if price_match:
                try:
                    price = int(price_match.group().replace("$", "").replace(",", ""))
                    if price < 20000 or price > 10000000:
                        price = None
                except ValueError:
                    pass

            # Extract beds/baths/sqft
            beds = None
            bed_match = re.search(r'(\d+)\s*(?:bed|br|bd)', combined, re.IGNORECASE)
            if bed_match:
                beds = int(bed_match.group(1))

            sqft = None
            sqft_match = re.search(r'([\d,]+)\s*(?:sq\s*ft|sqft)', combined, re.IGNORECASE)
            if sqft_match:
                sqft = int(sqft_match.group(1).replace(",", ""))

            # Detect investment signals
            signals = []
            signal_keywords = {
                "price reduced": "Price drop",
                "motivated": "Motivated seller",
                "fixer": "Fixer-upper",
                "as-is": "As-is",
                "as is": "As-is",
                "foreclosure": "Foreclosure",
                "pre-foreclosure": "Pre-foreclosure",
                "estate sale": "Estate sale",
                "probate": "Probate",
                "tax lien": "Tax lien",
                "wholesale": "Wholesale",
                "investor": "Investor deal",
                "cash only": "Cash only",
                "handyman": "Handyman special",
                "needs work": "Needs work",
                "below market": "Below market",
                "must sell": "Must sell",
                "vacant": "Vacant",
            }
            for kw, label in signal_keywords.items():
                if kw in combined.lower():
                    signals.append(label)

            parsed.append({
                "title": title,
                "url": url,
                "description": desc[:300],
                "price": price,
                "beds": beds,
                "sqft": sqft or 1500,  # Default for estimation
                "signals": signals,
                "signal_count": len(signals),
            })

        await self.emit_progress(f"Phase 3/5: Running 70% Rule on {len(parsed)} properties...")

        # Phase 3: ANALYZE — Run 70% Rule on each property
        analyzed = []
        for prop in parsed:
            asking = prop.get("price")
            sqft = prop.get("sqft", 1500)

            # Quick ARV estimate (per-sqft based on market)
            arv_per_sqft = self._estimate_arv_per_sqft(city, state)
            arv = sqft * arv_per_sqft

            # Repair estimate based on signals
            repair_tier = "moderate" if len(prop["signals"]) >= 3 else "cosmetic" if len(prop["signals"]) >= 1 else "cosmetic"
            repair_per_sqft = {"cosmetic": 18, "moderate": 38, "heavy": 65, "full_gut": 110}.get(repair_tier, 38)
            repair_estimate = sqft * repair_per_sqft

            # 70% Rule
            mao = (arv * 0.70) - repair_estimate

            # Calculate margin and ROI
            if asking and mao > 0:
                margin = mao - asking if asking < mao else -(asking - mao)
                flip_profit = arv - asking - repair_estimate - (arv * 0.09)  # 9% closing + holding
                roi = (flip_profit / asking) * 100 if asking > 0 else 0
            else:
                margin = None
                flip_profit = None
                roi = 0

            prop["analysis"] = {
                "arv": round(arv, 2),
                "arv_per_sqft": arv_per_sqft,
                "repair_tier": repair_tier,
                "repair_estimate": round(repair_estimate, 2),
                "mao": round(mao, 2),
                "margin_vs_asking": round(margin, 2) if margin is not None else None,
                "flip_profit": round(flip_profit, 2) if flip_profit is not None else None,
                "roi_pct": round(roi, 1),
            }
            analyzed.append(prop)

        await self.emit_progress(f"Phase 4/5: Filtering to deals above ${min_margin:,} margin...")

        # Phase 4: FILTER — Discard below threshold
        qualified = [
            p for p in analyzed
            if p["analysis"].get("flip_profit") is not None
            and p["analysis"]["flip_profit"] >= min_margin
            and p["analysis"]["roi_pct"] >= min_roi
        ]
        qualified.sort(key=lambda x: x["analysis"]["flip_profit"], reverse=True)

        await self.emit_progress(f"Phase 5/5: Building shortlist — {len(qualified)} deals qualified...")

        # Phase 5: SHORTLIST — Top 5
        shortlist = qualified[:5]
        for i, deal in enumerate(shortlist):
            deal["rank"] = i + 1
            deal["deal_grade"] = self._grade_quick(deal["analysis"])

        # Save full scan data
        scan_data = {
            "scan_id": scan_id,
            "location": location,
            "scan_date": datetime.utcnow().isoformat(),
            "parameters": {
                "max_price": max_price,
                "min_margin": min_margin,
                "min_roi": min_roi,
                "property_types": property_types,
            },
            "pipeline_stats": {
                "raw_results": len(raw_listings),
                "parsed_listings": len(parsed),
                "analyzed": len(analyzed),
                "qualified_deals": len(qualified),
                "shortlisted": len(shortlist),
                "filter_pass_rate": f"{(len(qualified)/len(parsed)*100):.1f}%" if parsed else "0%",
            },
            "shortlist": shortlist,
            "all_qualified": qualified[:20],
        }

        scan_file = self._data_dir / f"{scan_id}.json"
        scan_file.write_text(json.dumps(scan_data, indent=2))

        # Auto-generate the daily report
        report_content = self._build_report_markdown(scan_data)
        report_date = datetime.utcnow().strftime('%Y-%m-%d')
        report_file = self._reports_dir / f"HIGH_UPSIDE_REPORT_{report_date}.md"
        report_file.write_text(report_content)

        output = {
            "scan_id": scan_id,
            "location": location,
            "pipeline_stats": scan_data["pipeline_stats"],
            "shortlist_count": len(shortlist),
            "shortlist": shortlist,
            "report_path": str(report_file),
            "recommendation": f"Found {len(qualified)} deals above ${min_margin:,} margin. Top deal: {shortlist[0]['title'][:60] if shortlist else 'None'} with ${shortlist[0]['analysis']['flip_profit']:,.0f} projected profit." if shortlist else "No deals met the margin threshold today. Consider expanding search radius or lowering min_margin.",
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _estimate_arv_per_sqft(self, city: str, state: str) -> float:
        """Rough ARV per sqft by market. Will be overridden by comp data when available."""
        # Northeast US defaults (NJ/PA/NY/DE corridor)
        market_rates = {
            "NJ": 220, "PA": 180, "NY": 280, "DE": 190, "CT": 250,
            "MD": 210, "VA": 210, "MA": 300, "FL": 230, "TX": 170,
            "CA": 450, "IL": 180, "OH": 130, "GA": 190, "NC": 185,
        }
        return market_rates.get(state.upper(), 200)

    def _grade_quick(self, analysis: dict) -> str:
        profit = analysis.get("flip_profit", 0)
        roi = analysis.get("roi_pct", 0)
        if profit >= 75000 and roi >= 25:
            return "A+"
        if profit >= 50000 and roi >= 20:
            return "A"
        if profit >= 50000:
            return "B+"
        if profit >= 35000:
            return "B"
        if profit >= 25000:
            return "C"
        return "D"

    # ── FILTER DEALS ─────────────────────────────────────────────────────
    async def _filter_deals(self, task: AgentTask) -> AgentResult:
        """Apply margin and ROI filters to a set of analyzed deals."""
        min_margin = task.params.get("min_margin", 50000)
        min_roi = task.params.get("min_roi", 15)
        deals = task.params.get("deals", [])

        if not deals:
            # Load latest scan
            scan_files = sorted(self._data_dir.glob("daily_*.json"), reverse=True)
            if scan_files:
                try:
                    scan_data = json.loads(scan_files[0].read_text())
                    deals = scan_data.get("all_qualified", []) + scan_data.get("shortlist", [])
                except Exception:
                    pass

        qualified = [
            d for d in deals
            if d.get("analysis", {}).get("flip_profit", 0) >= min_margin
            and d.get("analysis", {}).get("roi_pct", 0) >= min_roi
        ]
        qualified.sort(key=lambda x: x.get("analysis", {}).get("flip_profit", 0), reverse=True)

        output = {
            "input_count": len(deals),
            "qualified_count": len(qualified),
            "filter_criteria": {"min_margin": min_margin, "min_roi": min_roi},
            "qualified_deals": qualified[:20],
            "pass_rate": f"{(len(qualified)/len(deals)*100):.1f}%" if deals else "0%",
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    # ── GENERATE REPORT ──────────────────────────────────────────────────
    async def _generate_report(self, task: AgentTask) -> AgentResult:
        """Generate the Daily High-Upside Report."""
        scan_id = task.params.get("scan_id", "")

        # Load scan data
        if scan_id:
            scan_file = self._data_dir / f"{scan_id}.json"
        else:
            scan_files = sorted(self._data_dir.glob("daily_*.json"), reverse=True)
            scan_file = scan_files[0] if scan_files else None

        if not scan_file or not scan_file.exists():
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="No scan data found. Run daily_scan first.")

        scan_data = json.loads(scan_file.read_text())
        report_content = self._build_report_markdown(scan_data)

        report_date = datetime.utcnow().strftime('%Y-%m-%d')
        report_file = self._reports_dir / f"HIGH_UPSIDE_REPORT_{report_date}.md"
        report_file.write_text(report_content)

        output = {
            "report_path": str(report_file),
            "report_date": report_date,
            "deals_featured": len(scan_data.get("shortlist", [])),
            "pipeline_stats": scan_data.get("pipeline_stats", {}),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _build_report_markdown(self, scan_data: dict) -> str:
        """Build the Daily High-Upside Report in Markdown."""
        stats = scan_data.get("pipeline_stats", {})
        shortlist = scan_data.get("shortlist", [])
        location = scan_data.get("location", "Unknown")
        date = scan_data.get("scan_date", datetime.utcnow().isoformat())[:10]

        lines = [
            f"# Daily High-Upside Report",
            f"**Market:** {location}  ",
            f"**Date:** {date}  ",
            f"**Pipeline:** {stats.get('raw_results', 0)} raw → {stats.get('parsed_listings', 0)} parsed → {stats.get('analyzed', 0)} analyzed → {stats.get('qualified_deals', 0)} qualified → {stats.get('shortlisted', 0)} shortlisted  ",
            f"**Filter Pass Rate:** {stats.get('filter_pass_rate', 'N/A')}",
            "",
            "---",
            "",
        ]

        if not shortlist:
            lines.append("**No deals met the margin threshold today.** Consider expanding search radius or adjusting filters.")
        else:
            for deal in shortlist:
                analysis = deal.get("analysis", {})
                lines.append(f"## #{deal.get('rank', '?')} — {deal.get('title', 'Unknown')[:80]}")
                lines.append("")
                lines.append(f"**URL:** {deal.get('url', 'N/A')}  ")
                if deal.get("price"):
                    lines.append(f"**Asking:** ${deal['price']:,}  ")
                lines.append(f"**Beds:** {deal.get('beds', 'N/A')} | **Sqft:** {deal.get('sqft', 'N/A'):,}  ")
                lines.append(f"**Signals:** {', '.join(deal.get('signals', []))}")
                lines.append("")
                lines.append(f"| Metric | Value |")
                lines.append(f"|--------|-------|")
                lines.append(f"| ARV | ${analysis.get('arv', 0):,.0f} |")
                lines.append(f"| Repair Estimate | ${analysis.get('repair_estimate', 0):,.0f} ({analysis.get('repair_tier', 'N/A')}) |")
                lines.append(f"| MAO (70% Rule) | ${analysis.get('mao', 0):,.0f} |")
                lines.append(f"| Flip Profit | ${analysis.get('flip_profit', 0):,.0f} |")
                lines.append(f"| ROI | {analysis.get('roi_pct', 0):.1f}% |")
                lines.append(f"| Deal Grade | **{deal.get('deal_grade', 'N/A')}** |")
                lines.append("")
                lines.append("---")
                lines.append("")

        lines.append(f"*Generated by Apex Asset Hunter — Cipher Elysian Protocol*")
        return "\n".join(lines)

    # ── INVESTOR PDF GENERATOR ───────────────────────────────────────────
    async def _generate_investor_pdf(self, task: AgentTask) -> AgentResult:
        """Generate a one-page Investor PDF for wholesale distribution."""
        address = task.params.get("address", "Unknown Property")
        asking_price = task.params.get("asking_price", 0)
        arv = task.params.get("arv", 0)
        repair_estimate = task.params.get("repair_estimate", 0)
        mao = task.params.get("mao", 0)
        flip_profit = task.params.get("flip_profit", 0)
        roi_pct = task.params.get("roi_pct", 0)
        beds = task.params.get("beds", 0)
        baths = task.params.get("baths", 0)
        sqft = task.params.get("sqft", 0)
        repair_tier = task.params.get("repair_tier", "moderate")
        signals = task.params.get("signals", [])
        comps = task.params.get("comps", [])
        deal_grade = task.params.get("deal_grade", "B")

        # Build PDF content as structured data (to be rendered by PDF skill)
        pdf_content = {
            "title": "INVESTMENT PROPERTY ANALYSIS",
            "subtitle": address,
            "generated": datetime.utcnow().strftime("%B %d, %Y"),
            "sections": [
                {
                    "heading": "Property Overview",
                    "data": {
                        "Address": address,
                        "Asking Price": f"${asking_price:,}" if asking_price else "Contact for Price",
                        "Beds/Baths": f"{beds}BR / {baths}BA",
                        "Square Footage": f"{sqft:,} sqft" if sqft else "N/A",
                        "Investment Signals": ", ".join(signals) if signals else "Standard listing",
                    },
                },
                {
                    "heading": "Deal Numbers (70% Rule)",
                    "data": {
                        "After Repair Value (ARV)": f"${arv:,}",
                        "Estimated Repair Costs": f"${repair_estimate:,} ({repair_tier})",
                        "Maximum Allowable Offer": f"${mao:,}",
                        "Formula": f"(${arv:,} × 0.70) - ${repair_estimate:,} = ${mao:,}",
                    },
                },
                {
                    "heading": "Profit Projection",
                    "data": {
                        "Estimated Flip Profit": f"${flip_profit:,}",
                        "ROI": f"{roi_pct:.1f}%",
                        "Deal Grade": deal_grade,
                    },
                },
            ],
        }

        if comps:
            comp_section = {
                "heading": "Comparable Sales",
                "data": {},
            }
            for i, comp in enumerate(comps[:5]):
                comp_section["data"][f"Comp {i+1}"] = f"{comp.get('title', 'N/A')[:50]} — ${comp.get('price', 0):,}"
            pdf_content["sections"].append(comp_section)

        pdf_content["sections"].append({
            "heading": "Disclaimer",
            "text": "This analysis is for informational purposes only. All numbers are estimates based on publicly available data. Verify ARV with a licensed appraiser and repair costs with a licensed contractor before making any offers. Apex Asset Hunter — Cipher Elysian Protocol.",
        })

        # Save as JSON (PDF rendering handled by Cipher's PDF skill or external tool)
        safe_address = address.replace(" ", "_").replace(",", "")[:40]
        pdf_data_file = self._pdf_dir / f"INVESTOR_PDF_{safe_address}_{datetime.utcnow().strftime('%Y%m%d')}.json"
        pdf_data_file.write_text(json.dumps(pdf_content, indent=2))

        # Also save as readable Markdown
        md_content = self._build_investor_md(pdf_content)
        md_file = self._pdf_dir / f"INVESTOR_PDF_{safe_address}_{datetime.utcnow().strftime('%Y%m%d')}.md"
        md_file.write_text(md_content)

        output = {
            "address": address,
            "pdf_data_path": str(pdf_data_file),
            "markdown_path": str(md_file),
            "deal_grade": deal_grade,
            "flip_profit": flip_profit,
            "mao": mao,
            "generated_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _build_investor_md(self, pdf_content: dict) -> str:
        lines = [
            f"# {pdf_content['title']}",
            f"## {pdf_content['subtitle']}",
            f"*Generated: {pdf_content['generated']}*",
            "",
        ]
        for section in pdf_content.get("sections", []):
            lines.append(f"### {section['heading']}")
            if "data" in section:
                for key, val in section["data"].items():
                    lines.append(f"- **{key}:** {val}")
            if "text" in section:
                lines.append(f"\n*{section['text']}*")
            lines.append("")
        lines.append("---")
        lines.append("*Apex Asset Hunter — Cipher Elysian Protocol*")
        return "\n".join(lines)

    # ── SELLER INQUIRY DRAFTER ───────────────────────────────────────────
    async def _draft_seller_inquiry(self, task: AgentTask) -> AgentResult:
        """Draft a personalized, non-bot-sounding inquiry to listing agent or owner."""
        address = task.params.get("address", "")
        listing_agent = task.params.get("listing_agent", "")
        owner_name = task.params.get("owner_name", "")
        asking_price = task.params.get("asking_price", 0)
        property_type = task.params.get("property_type", "property")
        roi_threshold = task.params.get("roi_threshold", 30)
        buyer_name = task.params.get("buyer_name", "Mark")

        recipient = listing_agent or owner_name or "Property Owner"

        # Build personalized email
        email_subject = f"Inquiry about {address}" if address else f"Cash buyer interested in your {property_type}"

        email_body = f"""Hi {recipient},

I came across the listing at {address} and I'm interested in learning more. I'm a local cash buyer and I can close quickly — typically within 14-21 days with no financing contingencies.

I'm flexible on terms and happy to work with your timeline. If the property is still available, I'd love to schedule a walkthrough or get any additional details you can share (recent updates, known issues, seller motivation/timeline, etc.).

I'm serious and can provide proof of funds upon request. Would you be open to a quick conversation?

Best regards,
{buyer_name}"""

        # LinkedIn-style message (shorter)
        linkedin_msg = f"Hi {recipient} — I noticed the listing at {address}. I'm a local cash buyer looking to close fast (14-21 days). Would you be open to a quick chat about this property?"

        # Save drafts
        safe_address = address.replace(" ", "_").replace(",", "")[:30]
        draft_data = {
            "address": address,
            "recipient": recipient,
            "email": {
                "subject": email_subject,
                "body": email_body,
            },
            "linkedin_message": linkedin_msg,
            "drafted_at": datetime.utcnow().isoformat(),
            "status": "DRAFT — Requires Mark's approval before sending",
        }

        draft_file = self._outreach_dir / f"inquiry_{safe_address}_{datetime.utcnow().strftime('%Y%m%d')}.json"
        draft_file.write_text(json.dumps(draft_data, indent=2))

        output = {
            "address": address,
            "recipient": recipient,
            "email_subject": email_subject,
            "email_body": email_body,
            "linkedin_message": linkedin_msg,
            "draft_path": str(draft_file),
            "status": "DRAFT — Awaiting approval. Will NOT send without Mark's explicit approval.",
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
