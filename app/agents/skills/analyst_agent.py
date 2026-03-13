"""
Analyst Agent v2.0.0 — Technical audit for the Global Expansion Pulse.

Takes targets from the Scout Agent and performs deep technical audits:
- Website technology stack detection (Shopify, WordPress, custom, etc.)
- Social media presence and engagement analysis
- SEO health check (meta tags, page speed indicators, mobile-readiness)
- Automation gap scoring (where Cipher's agents fit)
- Real HTTP checks on target websites for tech fingerprinting

NO MOCK DATA. Uses Brave Search with DuckDuckGo fallback + direct HTTP probing.

Capabilities:
1. audit_tech_stack — Detect website technology and infrastructure
2. audit_social — Analyze social media presence and gaps
3. audit_seo — SEO health check on target's website
4. full_audit — Run all three audits and produce combined report
5. rank_targets — Rank a list of audited targets by integration suitability
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


class AnalystAgent(BaseAgent):
    """Technical audit and integration suitability analysis for expansion targets."""

    def __init__(self):
        super().__init__(
            name="analyst_agent",
            description="Technical auditor — analyzes target companies for automation gaps and Cipher integration suitability",
            version="2.0.0",
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
        logger.info("AnalystAgent v2.0.0 initialized — no mock data")

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

    async def _web_search(self, query: str, count: int = 5) -> list[dict]:
        """Search via Brave with DuckDuckGo fallback. No mock data."""
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
                logger.warning(f"Brave search failed for analyst query: {e}")

        # DuckDuckGo fallback
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if resp.status_code == 200:
                    results = []
                    links = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.+?)</a>', resp.text)
                    snippets = re.findall(r'<a class="result__snippet"[^>]*>(.+?)</a>', resp.text)
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

        return []

    async def _probe_website(self, url: str) -> dict:
        """Directly probe a website to fingerprint technology stack via HTTP headers and HTML."""
        probe = {"reachable": False, "headers": {}, "technologies": [], "response_time_ms": 0}
        if not url:
            return probe
        if not url.startswith("http"):
            url = f"https://{url}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                import time
                start = time.time()
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CipherBot/2.0)"})
                probe["response_time_ms"] = int((time.time() - start) * 1000)
                probe["reachable"] = resp.status_code < 500
                probe["status_code"] = resp.status_code

                # Check headers for tech signals
                headers = dict(resp.headers)
                probe["headers"] = {k: v for k, v in headers.items() if k.lower() in [
                    "server", "x-powered-by", "x-shopify-stage", "x-wix-request-id",
                    "x-squarespace-version", "x-wordpress", "x-drupal-cache",
                ]}

                html = resp.text[:10000].lower()  # First 10KB

                # Technology fingerprinting from HTML/headers
                tech_checks = {
                    "Shopify": "shopify" in html or "x-shopify" in str(headers).lower() or "cdn.shopify.com" in html,
                    "WordPress": "wp-content" in html or "wordpress" in html or "wp-json" in html,
                    "Wix": "wix.com" in html or "x-wix" in str(headers).lower(),
                    "Squarespace": "squarespace" in html or "x-squarespace" in str(headers).lower(),
                    "Webflow": "webflow" in html,
                    "React": "react" in html or "_next" in html or "__next" in html,
                    "Next.js": "_next/static" in html or "__next" in html,
                    "Google Analytics": "google-analytics.com" in html or "gtag" in html or "ga4" in html,
                    "Google Tag Manager": "googletagmanager.com" in html,
                    "Meta Pixel": "facebook.com/tr" in html or "fbq(" in html,
                    "Klaviyo": "klaviyo" in html,
                    "Mailchimp": "mailchimp" in html or "mc.js" in html,
                    "HubSpot": "hubspot" in html or "hs-scripts" in html,
                    "Zendesk": "zendesk" in html or "zdassets" in html,
                    "Intercom": "intercom" in html or "widget.intercom.io" in html,
                    "Drift": "drift.com" in html or "driftt" in html,
                    "Crisp": "crisp.chat" in html,
                    "Hotjar": "hotjar" in html,
                    "Stripe": "stripe.com" in html or "stripe.js" in html,
                    "PayPal": "paypal.com" in html,
                    "TikTok Pixel": "analytics.tiktok.com" in html,
                }

                probe["technologies"] = [tech for tech, detected in tech_checks.items() if detected]
        except Exception as e:
            logger.warning(f"Website probe failed for {url}: {e}")

        return probe

    async def _audit_tech_stack(self, task: AgentTask) -> AgentResult:
        """Detect website technology stack via direct HTTP probe + search signals."""
        url = task.params.get("url", "")
        company = task.params.get("company", "")

        if not url and not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'url' or 'company'")

        target = url or company

        # Direct probe if URL provided
        probe_data = {}
        if url:
            await self.emit_progress(f"Probing {url}...")
            probe_data = await self._probe_website(url)

        # Search for additional tech intelligence
        await self.emit_progress("Searching for technology signals...")
        results = await self._web_search(f'"{target}" technology stack', count=5)
        results += await self._web_search(f'site:builtwith.com "{target}"', count=3)

        all_text = " ".join(r.get("description", "") + " " + r.get("title", "") for r in results).lower()

        # Combine probe + search signals
        detected_tech = list(set(probe_data.get("technologies", [])))

        # Add search-detected tech that probe missed
        search_tech = {
            "Shopify": "shopify" in all_text,
            "WordPress": "wordpress" in all_text or "wp-" in all_text,
            "Wix": "wix" in all_text,
            "Squarespace": "squarespace" in all_text,
            "React": "react" in all_text and "react" not in [t.lower() for t in detected_tech],
        }
        for tech, found in search_tech.items():
            if found and tech not in detected_tech:
                detected_tech.append(tech)

        # Identify automation gaps
        missing_automation = []
        has_email_marketing = any(t in detected_tech for t in ["Klaviyo", "Mailchimp", "HubSpot"])
        has_support = any(t in detected_tech for t in ["Zendesk", "Intercom", "Drift", "Crisp"])
        has_analytics = any(t in detected_tech for t in ["Google Analytics", "Google Tag Manager", "Hotjar"])
        has_chat = any(t in detected_tech for t in ["Intercom", "Drift", "Crisp"])

        if not has_email_marketing:
            missing_automation.append("No email marketing platform detected")
        if not has_support:
            missing_automation.append("No customer support automation detected")
        if not has_analytics:
            missing_automation.append("No analytics tracking detected")
        if not has_chat:
            missing_automation.append("No live chat / chatbot detected")

        # Score
        gap_score = min(100, len(missing_automation) * 20 + (15 if not detected_tech else 0))
        if probe_data.get("response_time_ms", 0) > 3000:
            gap_score = min(100, gap_score + 10)
            missing_automation.append(f"Slow website ({probe_data['response_time_ms']}ms)")

        output = {
            "target": target,
            "detected_technologies": detected_tech,
            "missing_automation": missing_automation,
            "automation_gap_score": gap_score,
            "website_probe": {
                "reachable": probe_data.get("reachable", False),
                "response_time_ms": probe_data.get("response_time_ms", 0),
                "status_code": probe_data.get("status_code"),
                "server_headers": probe_data.get("headers", {}),
            } if probe_data else None,
            "cipher_fit": {
                "communication_agent": not has_support,
                "data_agent": True,
                "monitor_agent": not has_analytics,
                "apex_architect": True,
                "research_agent": True,
            },
            "audited_at": datetime.utcnow().isoformat(),
        }

        filename = f"tech_audit_{target.replace('/', '_').replace(' ', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _audit_social(self, task: AgentTask) -> AgentResult:
        """Analyze social media presence with targeted searches."""
        company = task.params.get("company", "")
        url = task.params.get("url", "")
        target = company or url

        if not target:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company' or 'url'")

        platforms = {
            "instagram": "instagram.com",
            "tiktok": "tiktok.com",
            "facebook": "facebook.com",
            "linkedin": "linkedin.com",
            "twitter": "x.com",
            "youtube": "youtube.com",
        }
        social_audit = {}

        # Use targeted search queries with company name
        for platform, domain in platforms.items():
            # More specific search: company name + platform domain
            query = f'"{target}" site:{domain}'
            results = await self._web_search(query, count=3)

            # Verify the result actually belongs to this company
            found = False
            profile_url = None
            for r in results:
                r_url = r.get("url", "").lower()
                r_title = r.get("title", "").lower()
                target_lower = target.lower()
                # Check if result URL contains platform domain AND title/url references company
                if domain in r_url and (target_lower in r_title or target_lower.replace(" ", "") in r_url):
                    found = True
                    profile_url = r.get("url", "")
                    break

            social_audit[platform] = {
                "detected": found,
                "url": profile_url,
                "activity_signal": "active" if found else "not found",
            }

        active_count = sum(1 for p in social_audit.values() if p["detected"])
        total_platforms = len(platforms)

        # Score: 0-100 where higher = more gaps
        social_gap_score = max(0, min(100, int((1 - active_count / total_platforms) * 100)))

        opportunities = []
        if not social_audit.get("tiktok", {}).get("detected"):
            opportunities.append("No TikTok presence — Apex Architect can build short-form video strategy")
        if not social_audit.get("instagram", {}).get("detected"):
            opportunities.append("No Instagram — Image Agent + Apex Architect can build visual content pipeline")
        if not social_audit.get("youtube", {}).get("detected"):
            opportunities.append("No YouTube — Video Agent can produce product demos and tutorials")
        if not social_audit.get("linkedin", {}).get("detected"):
            opportunities.append("No LinkedIn company page — missing B2B visibility")
        if active_count < 3:
            opportunities.append(f"Only {active_count}/{total_platforms} platforms active — major multi-channel opportunity")

        output = {
            "target": target,
            "platforms": social_audit,
            "active_platforms": active_count,
            "total_platforms_checked": total_platforms,
            "social_gap_score": social_gap_score,
            "opportunities": opportunities,
            "audited_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _audit_seo(self, task: AgentTask) -> AgentResult:
        """SEO health check via search signals + direct probe."""
        url = task.params.get("url", "")
        company = task.params.get("company", "")
        target = url or company

        if not target:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'url' or 'company'")

        # Check search visibility
        brand_results = await self._web_search(f'"{target}"', count=10)
        site_results = await self._web_search(f'site:{url}', count=10) if url else []

        seo_score = 50
        issues = []

        if len(brand_results) < 5:
            issues.append("Low brand search visibility")
            seo_score -= 15
        if url and len(site_results) < 5:
            issues.append("Few indexed pages — thin content")
            seo_score -= 10
        if url and len(site_results) == 0:
            issues.append("No indexed pages found — major SEO problem")
            seo_score -= 15

        all_text = " ".join(r.get("description", "") for r in brand_results).lower()
        if "reviews" not in all_text and "review" not in all_text:
            issues.append("No review presence detected in search results")
            seo_score -= 10
        if len(brand_results) >= 8:
            seo_score += 20

        # Direct probe for meta tags if URL provided
        meta_data = {}
        if url:
            try:
                probe_url = url if url.startswith("http") else f"https://{url}"
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    resp = await client.get(probe_url, headers={"User-Agent": "Mozilla/5.0"})
                    html = resp.text[:15000].lower()

                    # Check for meta tags
                    has_title = "<title>" in html and "</title>" in html
                    has_description = 'name="description"' in html or 'property="og:description"' in html
                    has_og = 'property="og:' in html
                    has_viewport = 'name="viewport"' in html
                    has_canonical = 'rel="canonical"' in html
                    has_schema = "schema.org" in html or "application/ld+json" in html

                    meta_data = {
                        "has_title_tag": has_title,
                        "has_meta_description": has_description,
                        "has_open_graph": has_og,
                        "has_viewport": has_viewport,
                        "has_canonical": has_canonical,
                        "has_schema_markup": has_schema,
                    }

                    if not has_title:
                        issues.append("Missing <title> tag")
                        seo_score -= 10
                    if not has_description:
                        issues.append("Missing meta description")
                        seo_score -= 10
                    if not has_viewport:
                        issues.append("Missing viewport meta — not mobile-optimized")
                        seo_score -= 10
                    if has_schema:
                        seo_score += 5
                    if has_og:
                        seo_score += 5
            except Exception as e:
                logger.warning(f"SEO meta probe failed for {url}: {e}")

        seo_score = max(0, min(100, seo_score))

        output = {
            "target": target,
            "seo_score": seo_score,
            "seo_gap_score": 100 - seo_score,
            "issues": issues,
            "brand_visibility": len(brand_results),
            "indexed_pages": len(site_results),
            "meta_tags": meta_data,
            "cipher_seo_fit": {
                "research_agent": "content strategy and keyword research",
                "apex_architect": "product listing optimization and content calendar",
                "data_agent": "analytics setup and reporting automation",
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

        await self.emit_progress("Running tech stack audit...")
        tech_task = AgentTask(agent_name=self.name, instruction="audit tech", params={"operation": "audit_tech_stack", "company": company, "url": url})
        tech_result = await self._audit_tech_stack(tech_task)

        await self.emit_progress("Running social media audit...")
        social_task = AgentTask(agent_name=self.name, instruction="audit social", params={"operation": "audit_social", "company": company, "url": url})
        social_result = await self._audit_social(social_task)

        await self.emit_progress("Running SEO audit...")
        seo_task = AgentTask(agent_name=self.name, instruction="audit seo", params={"operation": "audit_seo", "company": company, "url": url})
        seo_result = await self._audit_seo(seo_task)

        tech_gap = tech_result.output.get("automation_gap_score", 50) if tech_result.success else 50
        social_gap = social_result.output.get("social_gap_score", 50) if social_result.success else 50
        seo_gap = seo_result.output.get("seo_gap_score", 50) if seo_result.success else 50

        composite_score = int(tech_gap * 0.45 + social_gap * 0.30 + seo_gap * 0.25)

        # Build agent recommendations based on actual gaps
        agents = set()
        if tech_result.success:
            missing = tech_result.output.get("missing_automation", [])
            if any("support" in m.lower() for m in missing):
                agents.add("Communication Agent")
            if any("analytics" in m.lower() for m in missing):
                agents.update(["Monitor Agent", "Data Agent"])
            if any("email" in m.lower() for m in missing):
                agents.add("Communication Agent")
            if any("chat" in m.lower() for m in missing):
                agents.add("Communication Agent")
        if social_gap >= 40:
            agents.update(["Apex Architect", "Image Agent", "Video Agent"])
        if seo_gap >= 40:
            agents.update(["Research Agent", "Web Agent"])
        # Always recommend these
        agents.update(["Data Agent", "Research Agent"])

        agents = list(agents)
        agent_value = len(agents) * 200

        if composite_score >= 70:
            action = "HIGH PRIORITY — Pass to Outreach Agent immediately"
        elif composite_score >= 50:
            action = "MEDIUM PRIORITY — Queue for outreach next cycle"
        else:
            action = "LOW PRIORITY — Monitor and re-evaluate in 30 days"

        output = {
            "company": company,
            "url": url,
            "audit_date": datetime.utcnow().isoformat(),
            "composite_integration_score": composite_score,
            "grade": "A+" if composite_score >= 85 else "A" if composite_score >= 70 else "B" if composite_score >= 55 else "C" if composite_score >= 40 else "D",
            "tech_audit": tech_result.output if tech_result.success else {"error": tech_result.error},
            "social_audit": social_result.output if social_result.success else {"error": social_result.error},
            "seo_audit": seo_result.output if seo_result.success else {"error": seo_result.error},
            "recommended_cipher_agents": agents,
            "estimated_monthly_value": f"${agent_value}",
            "recommended_action": action,
        }

        filename = f"full_audit_{(company or url).replace(' ', '_').replace('/', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _rank_targets(self, task: AgentTask) -> AgentResult:
        """Rank audited targets by integration suitability."""
        top_n = task.params.get("top_n", 5)

        audit_files = sorted(self._data_dir.glob("full_audit_*.json"), reverse=True)
        if not audit_files:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="No audit data found. Run full_audit on targets first.",
            )

        audits = []
        for f in audit_files[:20]:
            try:
                audits.append(json.loads(f.read_text()))
            except Exception:
                continue

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
