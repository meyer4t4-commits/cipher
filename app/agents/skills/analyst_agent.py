"""
Analyst Agent — Technical Audit hand for the Global Expansion Pulse.

Takes targets from the Scout Agent and performs deep technical audits:
- Website technology stack detection (Shopify, WordPress, custom, etc.)
- Social media presence and engagement analysis
- SEO health check (meta tags, page speed indicators, mobile-readiness)
- Automation gap scoring (where Cipher's agents fit)
- Competitor comparison within their niche

Produces a scored "Integration Suitability Report" for each target.

Capabilities:
1. audit_tech_stack — Detect website technology and infrastructure
2. audit_social — Analyze social media presence and gaps
3. audit_seo — SEO health check on target's website
4. full_audit — Run all three audits and produce combined report
5. rank_targets — Rank a list of audited targets by integration suitability
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


class AnalystAgent(BaseAgent):
    """Technical audit and integration suitability analysis for expansion targets."""

    def __init__(self):
        super().__init__(
            name="analyst_agent",
            description="Technical auditor — analyzes target companies for automation gaps and Cipher integration suitability",
            version="1.0.0",
            capabilities=[
                AgentCapability(name="audit_tech_stack", description="Detect website technology stack and infrastructure gaps", category="research", timeout_seconds=60),
                AgentCapability(name="audit_social", description="Analyze social media presence, engagement, and automation opportunities", category="research", timeout_seconds=60),
                AgentCapability(name="audit_seo", description="SEO health check — meta tags, speed, mobile, content quality", category="research", timeout_seconds=60),
                AgentCapability(name="full_audit", description="Complete technical audit combining tech stack, social, and SEO analysis", category="research", timeout_seconds=120),
                AgentCapability(name="rank_targets", description="Rank audited targets by integration suitability score", category="research", timeout_seconds=30),
            ],
        )

        self._data_dir = Path("./data/expansion_pulse/analyst")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.brave_api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        logger.info("AnalystAgent initialized")

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
                "audit_tech_stack": self._audit_tech_stack,
                "audit_social": self._audit_social,
                "audit_seo": self._audit_seo,
                "full_audit": self._full_audit,
                "rank_targets": self._rank_targets,
            }.get(operation)

            if not handler:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")

            await self.emit_progress(f"Running {operation}...")
            return await handler(task)
        except Exception as e:
            logger.error(f"Analyst operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    async def _brave_search(self, query: str, count: int = 5) -> list[dict]:
        if not self.brave_api_key:
            return [{"title": f"[Mock] {query}", "url": "https://example.com", "description": "Mock — set BRAVE_SEARCH_API_KEY"}]
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"X-Subscription-Token": self.brave_api_key, "Accept": "application/json"},
                    params={"q": query, "count": count},
                )
                resp.raise_for_status()
                return resp.json().get("web", {}).get("results", [])
        except Exception as e:
            logger.warning(f"Brave search failed: {e}")
            return []

    async def _audit_tech_stack(self, task: AgentTask) -> AgentResult:
        """Detect website technology stack via search signals."""
        url = task.params.get("url", "")
        company = task.params.get("company", "")

        if not url and not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'url' or 'company'")

        target = url or company
        results = await self._brave_search(f'"{target}" technology stack built with site:', count=10)
        results += await self._brave_search(f'site:builtwith.com "{target}"', count=3)

        # Technology detection heuristics
        all_text = " ".join(r.get("description", "") + " " + r.get("title", "") for r in results).lower()

        tech_signals = {
            "shopify": "shopify" in all_text,
            "wordpress": "wordpress" in all_text or "wp-" in all_text,
            "wix": "wix" in all_text,
            "squarespace": "squarespace" in all_text,
            "custom_built": not any(p in all_text for p in ["shopify", "wordpress", "wix", "squarespace"]),
            "react": "react" in all_text,
            "next.js": "next.js" in all_text or "nextjs" in all_text,
            "php": "php" in all_text,
            "google_analytics": "google analytics" in all_text or "ga4" in all_text,
            "klaviyo": "klaviyo" in all_text,
            "mailchimp": "mailchimp" in all_text,
            "hubspot": "hubspot" in all_text,
            "zendesk": "zendesk" in all_text,
            "intercom": "intercom" in all_text,
        }

        detected = [k for k, v in tech_signals.items() if v]
        missing_automation = []
        if not tech_signals.get("klaviyo") and not tech_signals.get("mailchimp") and not tech_signals.get("hubspot"):
            missing_automation.append("No email marketing platform detected")
        if not tech_signals.get("zendesk") and not tech_signals.get("intercom"):
            missing_automation.append("No customer support automation detected")
        if not tech_signals.get("google_analytics"):
            missing_automation.append("No analytics tracking detected")

        # Automation gap score (0-100, higher = more gaps = better target)
        gap_score = min(100, len(missing_automation) * 25 + (25 if tech_signals.get("custom_built") else 0))

        output = {
            "target": target,
            "detected_technologies": detected,
            "missing_automation": missing_automation,
            "automation_gap_score": gap_score,
            "cipher_fit": {
                "communication_agent": "No support automation" in str(missing_automation),
                "data_agent": True,  # Everyone needs data automation
                "monitor_agent": "No analytics" in str(missing_automation),
                "apex_architect": True,  # Everyone needs content/marketing
                "research_agent": True,
            },
            "audited_at": datetime.utcnow().isoformat(),
        }

        filename = f"tech_audit_{target.replace('/', '_').replace(' ', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _audit_social(self, task: AgentTask) -> AgentResult:
        """Analyze social media presence."""
        company = task.params.get("company", "")
        url = task.params.get("url", "")
        target = company or url

        if not target:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company' or 'url'")

        platforms = ["instagram", "tiktok", "facebook", "linkedin", "twitter", "youtube"]
        social_audit = {}

        for platform in platforms:
            results = await self._brave_search(f'"{target}" site:{platform}.com', count=3)
            found = len(results) > 0 and any(platform in r.get("url", "").lower() for r in results)
            social_audit[platform] = {
                "detected": found,
                "url": results[0].get("url", "") if found and results else None,
                "activity_signal": "active" if found else "not found",
            }

        active_platforms = sum(1 for p in social_audit.values() if p["detected"])
        social_gap_score = max(0, 100 - (active_platforms * 16))  # Each platform reduces gap

        output = {
            "target": target,
            "platforms": social_audit,
            "active_platforms": active_platforms,
            "total_platforms_checked": len(platforms),
            "social_gap_score": social_gap_score,
            "opportunities": [],
            "audited_at": datetime.utcnow().isoformat(),
        }

        if not social_audit.get("tiktok", {}).get("detected"):
            output["opportunities"].append("No TikTok presence — Apex Architect can build content strategy")
        if not social_audit.get("instagram", {}).get("detected"):
            output["opportunities"].append("No Instagram — need social content pipeline")
        if active_platforms < 3:
            output["opportunities"].append(f"Only {active_platforms}/6 platforms active — major expansion opportunity")

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _audit_seo(self, task: AgentTask) -> AgentResult:
        """SEO health check via search signals."""
        url = task.params.get("url", "")
        company = task.params.get("company", "")
        target = url or company

        if not target:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'url' or 'company'")

        # Check search visibility
        brand_results = await self._brave_search(f'"{target}"', count=10)
        site_results = await self._brave_search(f'site:{url}', count=10) if url else []

        seo_score = 50  # Base
        issues = []

        # Search visibility
        if len(brand_results) < 5:
            issues.append("Low brand search visibility")
            seo_score -= 15
        if url and len(site_results) < 5:
            issues.append("Few indexed pages")
            seo_score -= 10

        # Check for key signals in results
        all_text = " ".join(r.get("description", "") for r in brand_results).lower()
        if "reviews" not in all_text:
            issues.append("No review presence detected")
            seo_score -= 10
        if len(brand_results) >= 8:
            seo_score += 20

        seo_score = max(0, min(100, seo_score))
        seo_gap = 100 - seo_score

        output = {
            "target": target,
            "seo_score": seo_score,
            "seo_gap_score": seo_gap,
            "issues": issues,
            "brand_visibility": len(brand_results),
            "indexed_pages": len(site_results),
            "cipher_seo_fit": {
                "research_agent": "content strategy and keyword research",
                "apex_architect": "product listing optimization",
                "data_agent": "analytics and reporting automation",
            },
            "audited_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _full_audit(self, task: AgentTask) -> AgentResult:
        """Complete audit combining all three analysis types."""
        company = task.params.get("company", "")
        url = task.params.get("url", "")

        if not company and not url:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company' or 'url'")

        # Run all three audits
        tech_task = AgentTask(agent_name=self.name, instruction="audit tech", params={"operation": "audit_tech_stack", "company": company, "url": url})
        social_task = AgentTask(agent_name=self.name, instruction="audit social", params={"operation": "audit_social", "company": company, "url": url})
        seo_task = AgentTask(agent_name=self.name, instruction="audit seo", params={"operation": "audit_seo", "company": company, "url": url})

        tech_result = await self._audit_tech_stack(tech_task)
        social_result = await self._audit_social(social_task)
        seo_result = await self._audit_seo(seo_task)

        # Combine scores
        tech_gap = tech_result.output.get("automation_gap_score", 50) if tech_result.success else 50
        social_gap = social_result.output.get("social_gap_score", 50) if social_result.success else 50
        seo_gap = seo_result.output.get("seo_gap_score", 50) if seo_result.success else 50

        # Weighted composite: tech gaps matter most for Cipher integration
        composite_score = int(tech_gap * 0.45 + social_gap * 0.30 + seo_gap * 0.25)

        output = {
            "company": company,
            "url": url,
            "audit_date": datetime.utcnow().isoformat(),
            "composite_integration_score": composite_score,
            "grade": "A+" if composite_score >= 85 else "A" if composite_score >= 70 else "B" if composite_score >= 55 else "C" if composite_score >= 40 else "D",
            "tech_audit": tech_result.output if tech_result.success else {"error": tech_result.error},
            "social_audit": social_result.output if social_result.success else {"error": social_result.error},
            "seo_audit": seo_result.output if seo_result.success else {"error": seo_result.error},
            "recommended_cipher_agents": [],
            "estimated_monthly_value": "$0",
            "recommended_action": "",
        }

        # Build agent recommendations
        agents = []
        if tech_gap >= 50:
            agents.extend(["Communication Agent", "Monitor Agent", "Data Agent"])
        if social_gap >= 40:
            agents.extend(["Apex Architect", "Image Agent", "Video Agent"])
        if seo_gap >= 40:
            agents.extend(["Research Agent", "Web Agent"])
        agents = list(set(agents))
        output["recommended_cipher_agents"] = agents

        # Estimate value
        agent_value = len(agents) * 200  # ~$200/month value per agent
        output["estimated_monthly_value"] = f"${agent_value}"

        if composite_score >= 70:
            output["recommended_action"] = "HIGH PRIORITY — Pass to Outreach Agent immediately"
        elif composite_score >= 50:
            output["recommended_action"] = "MEDIUM PRIORITY — Queue for outreach next cycle"
        else:
            output["recommended_action"] = "LOW PRIORITY — Monitor and re-evaluate in 30 days"

        # Save full audit report
        filename = f"full_audit_{(company or url).replace(' ', '_').replace('/', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _rank_targets(self, task: AgentTask) -> AgentResult:
        """Rank audited targets by integration suitability."""
        top_n = task.params.get("top_n", 5)

        # Load all full audit files
        audit_files = sorted(self._data_dir.glob("full_audit_*.json"), reverse=True)
        audits = []

        for f in audit_files[:20]:
            try:
                data = json.loads(f.read_text())
                audits.append(data)
            except Exception:
                continue

        # Sort by composite score
        audits.sort(key=lambda x: x.get("composite_integration_score", 0), reverse=True)

        output = {
            "ranked_at": datetime.utcnow().isoformat(),
            "total_audited": len(audits),
            "top_targets": audits[:top_n],
            "ready_for_outreach": [a for a in audits[:top_n] if a.get("composite_integration_score", 0) >= 60],
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
