"""
Market Pulse Agent — Real estate listing scanner for the Apex Asset Hunter.

Scans Zillow, Redfin, MLS proxies, and public records for motivated sellers
by tracking Days on Market (DOM), price drop frequency, pre-foreclosure
signals, and tax lien indicators.

Capabilities:
1. scan_listings — Pull new listings in a target market matching criteria
2. scan_motivated_sellers — Find properties with DOM > threshold + price drops
3. scan_preforeclosure — Find pre-foreclosure and tax lien properties
4. track_price_drops — Monitor price reduction history on tracked properties
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


class MarketPulseAgent(BaseAgent):
    """Scans real estate markets for motivated sellers and high-margin deal flow."""

    def __init__(self):
        super().__init__(
            name="market_pulse_agent",
            description="Real estate listing scanner — finds motivated sellers via DOM, price drops, pre-foreclosure, and tax liens",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="scan_listings",
                    description="Scan a geographic market for new listings matching investment criteria",
                    category="research",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="scan_motivated_sellers",
                    description="Find motivated sellers — high DOM, multiple price drops, estate sales, relocations",
                    category="research",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="scan_preforeclosure",
                    description="Find pre-foreclosure and tax lien properties in a target county",
                    category="research",
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="track_price_drops",
                    description="Track price reduction history and frequency for properties in pipeline",
                    category="research",
                    timeout_seconds=60,
                ),
            ],
        )

        self._data_dir = Path("./data/apex_asset_hunter/market_pulse")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._pipeline_dir = Path("./data/apex_asset_hunter/pipeline")
        self._pipeline_dir.mkdir(parents=True, exist_ok=True)
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.attom_api_key = os.getenv("ATTOM_API_KEY", "")
        self.propstream_api_key = os.getenv("PROPSTREAM_API_KEY", "")
        logger.info("MarketPulseAgent initialized")

    def requires_approval_for(self, instruction: str) -> bool:
        return False  # Read-only scanning

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
            if operation == "scan_listings":
                await self.emit_progress("Scanning market for new listings...")
                return await self._scan_listings(task)
            elif operation == "scan_motivated_sellers":
                await self.emit_progress("Hunting motivated sellers...")
                return await self._scan_motivated_sellers(task)
            elif operation == "scan_preforeclosure":
                await self.emit_progress("Scanning pre-foreclosure and tax lien records...")
                return await self._scan_preforeclosure(task)
            elif operation == "track_price_drops":
                await self.emit_progress("Tracking price drop history...")
                return await self._track_price_drops(task)
            else:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            logger.error(f"MarketPulse operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    async def _brave_search(self, query: str, count: int = 10) -> list[dict]:
        """Execute a Brave Search API call."""
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

    async def _attom_lookup(self, endpoint: str, params: dict) -> dict:
        """Call ATTOM Data API for property records."""
        if not self.attom_api_key:
            return {"mock": True, "message": "Set ATTOM_API_KEY for live property data"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://api.gateway.attomdata.com/propertyapi/v1.0.0/{endpoint}",
                    headers={"apikey": self.attom_api_key, "Accept": "application/json"},
                    params=params,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"ATTOM API failed: {e}")
            return {"error": str(e)}

    # ── SCAN LISTINGS ────────────────────────────────────────────────────
    async def _scan_listings(self, task: AgentTask) -> AgentResult:
        """Scan a geographic market for investment-grade listings."""
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        zip_code = task.params.get("zip_code", "")
        max_price = task.params.get("max_price", 500000)
        min_beds = task.params.get("min_beds", 2)
        property_types = task.params.get("property_types", ["single_family", "multi_family", "townhouse"])

        location = f"{city}, {state}" if city and state else zip_code
        if not location:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing city/state or zip_code")

        # Multi-query strategy for real estate listings
        queries = [
            f"homes for sale {location} under ${max_price:,} Zillow",
            f"new listings {location} {min_beds}+ bed investment property",
            f"foreclosure homes {location} fixer upper",
            f"motivated seller {location} real estate below market value",
            f"cash buyer deal {location} wholesale property",
            f"estate sale {location} probate property for sale",
            f"Redfin {location} price reduced recently",
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        # Also try ATTOM for structured property data
        attom_data = await self._attom_lookup("sale/snapshot", {
            "geoid": f"CS{state}{city.replace(' ', '')}".upper()[:12] if city else "",
            "minSaleAmt": 50000,
            "maxSaleAmt": max_price,
        })

        # Parse and deduplicate listings
        seen_urls = set()
        listings = []
        for result in all_results:
            url = result.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                listing = self._parse_listing(result)
                listing["source_type"] = "web_search"
                listings.append(listing)

        # Score each listing for investment potential
        for listing in listings:
            listing["investment_signals"] = self._detect_investment_signals(
                listing.get("title", ""), listing.get("description", "")
            )
            listing["signal_score"] = len(listing["investment_signals"]) * 15
            listing["signal_score"] = min(100, max(5, listing["signal_score"]))

        # Sort by signal score
        listings.sort(key=lambda x: x.get("signal_score", 0), reverse=True)

        output = {
            "location": location,
            "max_price": max_price,
            "min_beds": min_beds,
            "property_types": property_types,
            "scan_date": datetime.utcnow().isoformat(),
            "total_raw_results": len(all_results),
            "unique_listings": len(listings),
            "top_listings": listings[:20],
            "attom_available": not attom_data.get("mock", False),
            "queries_executed": len(queries),
        }

        filename = f"listing_scan_{location.replace(', ', '_').replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _parse_listing(self, result: dict) -> dict:
        """Extract structured listing data from a search result."""
        title = result.get("title", "")
        desc = result.get("description", "")
        url = result.get("url", "")

        # Try to extract price from title/description
        price = None
        for text in [title, desc]:
            import re
            price_match = re.search(r'\$[\d,]+(?:k)?', text, re.IGNORECASE)
            if price_match:
                raw = price_match.group().replace("$", "").replace(",", "")
                if raw.lower().endswith("k"):
                    price = int(float(raw[:-1]) * 1000)
                else:
                    try:
                        price = int(raw)
                    except ValueError:
                        pass
                break

        # Try to extract beds/baths
        beds = None
        baths = None
        bed_match = re.search(r'(\d+)\s*(?:bed|br|bd)', f"{title} {desc}", re.IGNORECASE)
        bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|ba)', f"{title} {desc}", re.IGNORECASE)
        if bed_match:
            beds = int(bed_match.group(1))
        if bath_match:
            baths = float(bath_match.group(1))

        # Extract square footage
        sqft = None
        sqft_match = re.search(r'([\d,]+)\s*(?:sq\s*ft|sqft|square feet)', f"{title} {desc}", re.IGNORECASE)
        if sqft_match:
            sqft = int(sqft_match.group(1).replace(",", ""))

        return {
            "title": title,
            "url": url,
            "description": desc,
            "price": price,
            "beds": beds,
            "baths": baths,
            "sqft": sqft,
            "domain": url.split("/")[2] if len(url.split("/")) > 2 else "",
        }

    def _detect_investment_signals(self, title: str, description: str) -> list[str]:
        """Detect signals indicating a high-value investment opportunity."""
        signals = []
        combined = f"{title} {description}".lower()

        signal_map = {
            "price reduced": "Price recently reduced",
            "price drop": "Price drop detected",
            "motivated": "Motivated seller",
            "must sell": "Must sell — urgent",
            "below market": "Listed below market value",
            "as-is": "Selling as-is (likely needs work)",
            "as is": "Selling as-is (likely needs work)",
            "fixer": "Fixer-upper",
            "handyman": "Handyman special",
            "needs work": "Needs renovation",
            "needs repair": "Needs repair",
            "needs updating": "Needs updating",
            "tlc": "Needs TLC",
            "investor": "Marketed to investors",
            "wholesale": "Wholesale deal",
            "foreclosure": "Foreclosure",
            "pre-foreclosure": "Pre-foreclosure",
            "bank owned": "Bank-owned (REO)",
            "reo": "Bank-owned (REO)",
            "estate sale": "Estate/probate sale",
            "probate": "Probate sale",
            "tax lien": "Tax lien property",
            "auction": "Auction property",
            "vacant": "Vacant property",
            "cash only": "Cash-only deal",
            "quick close": "Seller wants quick close",
            "relocation": "Seller relocating",
            "divorce": "Divorce sale",
            "distress": "Distressed property",
            "off market": "Off-market opportunity",
            "days on market": "Extended days on market noted",
        }

        for keyword, signal in signal_map.items():
            if keyword in combined:
                signals.append(signal)

        return signals

    # ── MOTIVATED SELLERS ────────────────────────────────────────────────
    async def _scan_motivated_sellers(self, task: AgentTask) -> AgentResult:
        """Find motivated sellers — high DOM, multiple price drops, distress indicators."""
        city = task.params.get("city", "")
        state = task.params.get("state", "")
        county = task.params.get("county", "")
        min_dom = task.params.get("min_dom", 60)  # Days on market threshold
        min_price_drops = task.params.get("min_price_drops", 2)

        location = f"{city}, {state}" if city else county
        if not location:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing city/state or county")

        queries = [
            f"'{location}' real estate 'days on market' 'price reduced' {min_dom}+ days",
            f"'{location}' property 'multiple price reductions' motivated seller",
            f"'{location}' homes 'back on market' 'price drop' fixer upper",
            f"'{location}' real estate expired listing re-listed below asking",
            f"'{location}' property 'estate sale' OR 'probate' OR 'relocation' OR 'divorce'",
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        # ATTOM pre-foreclosure data
        preforeclosure_data = await self._attom_lookup("sale/snapshot", {
            "geoid": f"CO{state}{county.replace(' ', '')}".upper()[:12] if county else "",
            "saletype": "Foreclosure",
        })

        seen_urls = set()
        motivated_sellers = []
        for result in all_results:
            url = result.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                listing = self._parse_listing(result)
                listing["motivation_signals"] = self._score_seller_motivation(
                    listing.get("title", ""), listing.get("description", "")
                )
                listing["motivation_score"] = listing["motivation_signals"]["total_score"]
                motivated_sellers.append(listing)

        # Filter to only genuinely motivated sellers
        motivated_sellers = [s for s in motivated_sellers if s["motivation_score"] >= 40]
        motivated_sellers.sort(key=lambda x: x["motivation_score"], reverse=True)

        output = {
            "location": location,
            "min_dom_threshold": min_dom,
            "min_price_drops": min_price_drops,
            "scan_date": datetime.utcnow().isoformat(),
            "total_found": len(motivated_sellers),
            "motivated_sellers": motivated_sellers[:15],
            "data_sources": {
                "brave_search": True,
                "attom_api": not preforeclosure_data.get("mock", False),
            },
        }

        filename = f"motivated_sellers_{location.replace(', ', '_').replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _score_seller_motivation(self, title: str, description: str) -> dict:
        """Score seller motivation based on signals found in listing."""
        combined = f"{title} {description}".lower()
        scores = {
            "price_reduced": 20 if any(kw in combined for kw in ["price reduced", "price drop", "price cut"]) else 0,
            "dom_extended": 15 if any(kw in combined for kw in ["days on market", "been listed", "months on market"]) else 0,
            "distress": 25 if any(kw in combined for kw in ["foreclosure", "pre-foreclosure", "bank owned", "reo", "tax lien", "auction"]) else 0,
            "life_event": 20 if any(kw in combined for kw in ["estate", "probate", "divorce", "relocation", "moving", "downsizing"]) else 0,
            "urgency": 15 if any(kw in combined for kw in ["must sell", "motivated", "quick close", "cash only", "bring offers"]) else 0,
            "condition": 10 if any(kw in combined for kw in ["as-is", "as is", "fixer", "needs work", "handyman", "tlc"]) else 0,
        }
        scores["total_score"] = min(100, sum(scores.values()))
        return scores

    # ── PRE-FORECLOSURE & TAX LIENS ─────────────────────────────────────
    async def _scan_preforeclosure(self, task: AgentTask) -> AgentResult:
        """Scan for pre-foreclosure and tax lien properties."""
        county = task.params.get("county", "")
        state = task.params.get("state", "")
        city = task.params.get("city", "")

        location = f"{county} County, {state}" if county else f"{city}, {state}"
        if not state:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing state parameter")

        queries = [
            f"pre-foreclosure homes {location} 2024 2025 2026 list",
            f"tax lien properties {location} county auction",
            f"sheriff sale {location} upcoming",
            f"notice of default {location} real estate",
            f"lis pendens filed {location} property",
            f"delinquent tax list {county or city} {state}",
        ]

        all_results = []
        for query in queries:
            results = await self._brave_search(query, count=5)
            all_results.extend(results)

        # ATTOM foreclosure data
        foreclosure_data = await self._attom_lookup("property/preforeclosure", {
            "geoid": f"CO{state}{(county or city).replace(' ', '')}".upper()[:12],
        })

        seen_urls = set()
        preforeclosure_listings = []
        for result in all_results:
            url = result.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                entry = {
                    "title": result.get("title", ""),
                    "url": url,
                    "description": result.get("description", ""),
                    "type": self._classify_distress_type(result.get("title", ""), result.get("description", "")),
                    "domain": url.split("/")[2] if len(url.split("/")) > 2 else "",
                }
                preforeclosure_listings.append(entry)

        output = {
            "location": location,
            "county": county,
            "state": state,
            "scan_date": datetime.utcnow().isoformat(),
            "total_found": len(preforeclosure_listings),
            "listings": preforeclosure_listings[:20],
            "type_breakdown": self._count_distress_types(preforeclosure_listings),
            "data_sources": {
                "brave_search": True,
                "attom_foreclosure": not foreclosure_data.get("mock", False),
            },
            "next_steps": "Route top properties to Profitability Analyst for 70% Rule calculation",
        }

        filename = f"preforeclosure_{location.replace(', ', '_').replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _classify_distress_type(self, title: str, desc: str) -> str:
        combined = f"{title} {desc}".lower()
        if any(kw in combined for kw in ["pre-foreclosure", "preforeclosure", "notice of default"]):
            return "pre-foreclosure"
        if any(kw in combined for kw in ["tax lien", "tax deed", "delinquent tax"]):
            return "tax_lien"
        if any(kw in combined for kw in ["sheriff sale", "auction"]):
            return "sheriff_sale"
        if any(kw in combined for kw in ["lis pendens"]):
            return "lis_pendens"
        if any(kw in combined for kw in ["bank owned", "reo", "foreclosure"]):
            return "reo"
        return "unknown"

    def _count_distress_types(self, listings: list[dict]) -> dict:
        counts = {}
        for listing in listings:
            dtype = listing.get("type", "unknown")
            counts[dtype] = counts.get(dtype, 0) + 1
        return counts

    # ── PRICE DROP TRACKER ───────────────────────────────────────────────
    async def _track_price_drops(self, task: AgentTask) -> AgentResult:
        """Track price reduction history for properties in the pipeline."""
        # Load existing pipeline properties
        pipeline_file = self._pipeline_dir / "active_pipeline.json"
        pipeline = []
        if pipeline_file.exists():
            try:
                pipeline = json.loads(pipeline_file.read_text())
            except Exception:
                pipeline = []

        # Also accept a specific address or URL to track
        address = task.params.get("address", "")
        url = task.params.get("url", "")

        if address or url:
            search_term = address or url
            results = await self._brave_search(f'"{search_term}" price history Zillow OR Redfin', count=5)

            price_history = {
                "address": address,
                "url": url,
                "search_date": datetime.utcnow().isoformat(),
                "price_history_sources": [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")}
                    for r in results[:5]
                ],
                "price_drops_detected": self._count_price_drop_mentions(results),
            }

            output = {
                "tracked_property": price_history,
                "pipeline_size": len(pipeline),
                "recommendation": "Add to pipeline for daily monitoring" if price_history["price_drops_detected"] > 0 else "No price drops detected yet",
            }
        else:
            # Track all properties in pipeline
            updated_pipeline = []
            for prop in pipeline:
                addr = prop.get("address", "")
                if addr:
                    results = await self._brave_search(f'"{addr}" price reduced OR "price drop"', count=3)
                    prop["last_checked"] = datetime.utcnow().isoformat()
                    prop["recent_price_drops"] = self._count_price_drop_mentions(results)
                    updated_pipeline.append(prop)

            pipeline_file.write_text(json.dumps(updated_pipeline, indent=2))

            output = {
                "pipeline_size": len(updated_pipeline),
                "properties_checked": len(updated_pipeline),
                "properties_with_drops": len([p for p in updated_pipeline if p.get("recent_price_drops", 0) > 0]),
                "pipeline": updated_pipeline[:10],
            }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    def _count_price_drop_mentions(self, results: list[dict]) -> int:
        count = 0
        for r in results:
            combined = f"{r.get('title', '')} {r.get('description', '')}".lower()
            if any(kw in combined for kw in ["price reduced", "price drop", "price cut", "lowered", "decreased"]):
                count += 1
        return count

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
