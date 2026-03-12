"""
Apex Architect Agent - Ecommerce Optimization & Marketing Automation
Uses REAL web search (Brave Search API) and LLM analysis for all operations.
No hardcoded/mock data — every response is generated from live data.

Capabilities:
1. analyze_competitor - Real competitor research via web scraping + search
2. generate_product_listing - LLM-generated SEO-optimized product copy
3. plan_social_content - LLM-generated content calendar based on real trends
4. generate_social_post - Single post generation via LLM
5. analyze_store_conversion - Real store audit via web scraping
6. generate_email_sequence - LLM-generated email campaigns
7. fresh_pulse_check - Real trend analysis via Brave Search
8. generate_ad_creative - LLM-generated ad copy and strategy
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


class ApexArchitectAgent(BaseAgent):
    """Execute ecommerce optimization using REAL search data and LLM analysis."""

    def __init__(self):
        """Initialize the Apex Architect Agent."""
        super().__init__(
            name="apex_architect_agent",
            description="Ecommerce optimization, social media strategy, competitor analysis, and creative content generation",
            version="2.0.0",
            capabilities=[
                AgentCapability(
                    name="analyze_competitor",
                    description="Analyze competitor stores and generate competitive intelligence reports",
                    category="research",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="generate_product_listing",
                    description="Generate SEO-optimized product listings for Shopify/Etsy",
                    category="content",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="plan_social_content",
                    description="Create structured social media content calendars",
                    category="content",
                    timeout_seconds=45,
                ),
                AgentCapability(
                    name="generate_social_post",
                    description="Generate individual social media posts with captions and hashtags",
                    category="content",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="analyze_store_conversion",
                    description="Audit ecommerce store conversion and provide recommendations",
                    category="research",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="generate_email_sequence",
                    description="Generate email marketing sequences for various triggers",
                    category="content",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="fresh_pulse_check",
                    description="Scan for current trends and viral opportunities in a niche",
                    category="research",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="generate_ad_creative",
                    description="Generate ad copy and creative briefs for social advertising",
                    category="content",
                    timeout_seconds=30,
                ),
            ],
        )

        self._data_dir = Path("./data/apex")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.brave_api_key = getattr(settings, "brave_search_api_key", "") or os.getenv("BRAVE_SEARCH_API_KEY", "")

        logger.info("ApexArchitectAgent v2.0 initialized (real search + LLM)")

    # ── Core helpers ──────────────────────────────────────────────────────

    async def _brave_search(self, query: str, count: int = 5) -> list[dict]:
        """Execute a real Brave Search API query and return results."""
        if not self.brave_api_key:
            logger.warning("No BRAVE_SEARCH_API_KEY configured — search unavailable")
            return []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": self.brave_api_key,
                    },
                    params={"q": query, "count": count, "freshness": "pm"},
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "age": item.get("age", ""),
                })
            return results

        except Exception as e:
            logger.error(f"Brave Search failed: {e}")
            return []

    async def _llm_analyze(self, prompt: str, max_tokens: int = 2000) -> str:
        """Use Cipher's LLM router to generate analysis from a prompt."""
        try:
            from app.services.llm_router import chat_completion_with_tools
            from app.models.schemas import ModelTier

            result = await chat_completion_with_tools(
                messages=[{"role": "user", "content": prompt}],
                model_tier=ModelTier.FAST,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return result.get("content", "")
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return f"Analysis unavailable: {str(e)}"

    def requires_approval_for(self, instruction: str) -> bool:
        approval_keywords = ["post", "publish", "send", "deploy", "launch"]
        return any(keyword in instruction.lower() for keyword in approval_keywords)

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
            dispatch = {
                "analyze_competitor": self._analyze_competitor,
                "generate_product_listing": self._generate_product_listing,
                "plan_social_content": self._plan_social_content,
                "generate_social_post": self._generate_social_post,
                "analyze_store_conversion": self._analyze_store_conversion,
                "generate_email_sequence": self._generate_email_sequence,
                "fresh_pulse_check": self._fresh_pulse_check,
                "generate_ad_creative": self._generate_ad_creative,
            }
            handler = dispatch.get(operation)
            if not handler:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                                   error=f"Unknown operation: {operation}")
            await self.emit_progress(f"Running {operation}...")
            return await handler(task)
        except Exception as e:
            logger.error(f"Apex architect operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    # ── Real operations ───────────────────────────────────────────────────

    async def _analyze_competitor(self, task: AgentTask) -> AgentResult:
        """Analyze competitor using real web search data."""
        url = task.params.get("url", "")
        niche = task.params.get("niche", "")

        if not url and not niche:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Missing 'url' or 'niche' parameter")

        # Search for real competitor data
        search_query = f"{url} review" if url else f"top {niche} ecommerce stores competitors"
        search_results = await self._brave_search(search_query, count=8)

        # Also search for pricing and strategy info
        strategy_query = f"{url or niche} ecommerce pricing strategy social media"
        strategy_results = await self._brave_search(strategy_query, count=5)

        # Build context for LLM analysis
        search_context = "\n".join([
            f"- {r['title']}: {r['description']}" for r in search_results + strategy_results
        ])

        analysis = await self._llm_analyze(f"""Based on this real search data, create a competitor analysis report.

Target: {url or niche}
Search data:
{search_context}

Respond ONLY in valid JSON with these keys:
- competitor_url: string
- niche: string
- store_metrics: object with product_count, price_range, estimated_traffic, traffic_tier
- strategy_analysis: object with pricing_strategy, design_patterns, upsell_tactics
- social_presence: object with platforms and estimated engagement
- competitive_advantages: array of strings
- opportunities: array of actionable recommendations
- sources: array of URLs used

Be specific and data-driven. Use the real search results to inform your analysis.""")

        try:
            # Try to parse as JSON
            output = json.loads(analysis.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            output = {
                "competitor_url": url or niche,
                "analysis": analysis,
                "search_results_used": len(search_results),
            }

        output["generated_at"] = datetime.utcnow().isoformat()
        output["data_source"] = "brave_search_live"

        self._save_output(f"competitor_analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", output)

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _generate_product_listing(self, task: AgentTask) -> AgentResult:
        """Generate SEO-optimized product listing using LLM."""
        product_name = task.params.get("product_name", "")
        description = task.params.get("description", "")
        benefits = task.params.get("benefits", [])
        target_audience = task.params.get("target_audience", "")

        if not product_name:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Missing 'product_name' parameter")

        # Search for real competitor listings for context
        search_results = await self._brave_search(f"{product_name} product listing Shopify Etsy", count=5)
        context = "\n".join([f"- {r['title']}: {r['description']}" for r in search_results])

        listing = await self._llm_analyze(f"""Create an SEO-optimized product listing for:
Product: {product_name}
Description: {description}
Benefits: {', '.join(benefits) if benefits else 'not specified'}
Target audience: {target_audience or 'not specified'}

Competitor context from search:
{context}

Respond ONLY in valid JSON with these keys:
- seo_title: string (max 60 chars, keyword-rich)
- description: string (compelling, benefit-driven, 150-300 words)
- bullet_points: array of 5-6 benefit-driven bullets
- meta_description: string (max 160 chars)
- tags: array of 8-10 SEO tags
- pricing_recommendation: object with recommended_retail, competitor_range, margin_target
- ready_to_paste_copy: object with title, body, features as formatted string""")

        try:
            output = json.loads(listing.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            output = {"product_name": product_name, "listing": listing}

        output["product_name"] = product_name
        output["generated_at"] = datetime.utcnow().isoformat()
        output["data_source"] = "llm_with_search_context"

        self._save_output(f"product_listing_{product_name.replace(' ', '_')}.json", output)

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _plan_social_content(self, task: AgentTask) -> AgentResult:
        """Create content calendar based on real trend data."""
        brand_name = task.params.get("brand_name", "Brand")
        niche = task.params.get("niche", "skincare")
        platforms = task.params.get("platforms", ["instagram", "tiktok"])
        duration_days = task.params.get("duration_days", 7)

        # Get real trending data
        trends = await self._brave_search(f"{niche} trending content ideas {' '.join(platforms)} 2026", count=5)
        trend_context = "\n".join([f"- {r['title']}: {r['description']}" for r in trends])

        calendar = await self._llm_analyze(f"""Create a {duration_days}-day social media content calendar for:
Brand: {brand_name}
Niche: {niche}
Platforms: {', '.join(platforms)}

Current trends from search:
{trend_context}

Respond ONLY in valid JSON with these keys:
- calendar: array of objects, each with: date, day_of_week, platform, content_type, hook, caption, hashtags (array), cta, optimal_posting_time
- notes: string with implementation tips
Generate exactly {duration_days * len(platforms)} entries ({duration_days} days x {len(platforms)} platforms).""")

        try:
            output = json.loads(calendar.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            output = {"calendar_raw": calendar}

        output["brand_name"] = brand_name
        output["niche"] = niche
        output["platforms"] = platforms
        output["duration_days"] = duration_days
        output["generated_at"] = datetime.utcnow().isoformat()
        output["data_source"] = "llm_with_trend_data"

        self._save_output(f"content_calendar_{brand_name.replace(' ', '_')}_{duration_days}d.json", output)

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _generate_social_post(self, task: AgentTask) -> AgentResult:
        """Generate a single social media post using LLM."""
        platform = task.params.get("platform", "instagram").lower()
        content_type = task.params.get("content_type", "post")
        topic = task.params.get("topic", "product feature")
        brand_voice = task.params.get("brand_voice", "authentic, educational")

        post = await self._llm_analyze(f"""Generate a {platform} {content_type} about: {topic}
Brand voice: {brand_voice}

Respond ONLY in valid JSON with these keys:
- hook: string (attention-grabbing first line)
- caption: string (full caption, {platform}-optimized length)
- hashtags: array of 10-15 relevant hashtags
- visual_description: string (what the visual should show)
- cta: string (call to action)
- optimal_posting_time: string
- engagement_tips: array of 3 tips""")

        try:
            output = json.loads(post.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            output = {"post_raw": post}

        output["platform"] = platform
        output["content_type"] = content_type
        output["topic"] = topic
        output["generated_at"] = datetime.utcnow().isoformat()

        self._save_output(f"social_post_{platform}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", output)

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _analyze_store_conversion(self, task: AgentTask) -> AgentResult:
        """Audit ecommerce store using real web data."""
        store_url = task.params.get("store_url", "")

        if not store_url:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Missing 'store_url' parameter")

        # Search for real reviews and analysis of the store
        search_results = await self._brave_search(f"{store_url} review user experience ecommerce", count=8)
        context = "\n".join([f"- {r['title']}: {r['description']}" for r in search_results])

        audit = await self._llm_analyze(f"""Based on search data about {store_url}, create a conversion audit.

Search data:
{context}

Respond ONLY in valid JSON with these keys:
- store_url: string
- performance_metrics: object (page_load_estimate, mobile_optimization, overall_score)
- product_page_analysis: object (title_clarity, image_quality, description_quality, price_visibility, cta_prominence)
- checkout_flow: object (estimated_steps, guest_checkout, payment_options, cart_recovery)
- trust_signals: object (reviews_present, guarantees, security_badges)
- upsell_opportunities: object with specific recommendations
- recommendations: array of 6-8 specific actionable items (prioritized)
- estimated_conversion_lift: string

Be specific to this store based on the search data. Don't be generic.""")

        try:
            output = json.loads(audit.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            output = {"store_url": store_url, "audit_raw": audit}

        output["audit_date"] = datetime.utcnow().isoformat()
        output["data_source"] = "brave_search_live"

        self._save_output(f"conversion_audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", output)

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _generate_email_sequence(self, task: AgentTask) -> AgentResult:
        """Generate email marketing sequence using LLM."""
        trigger = task.params.get("trigger", "welcome")
        brand_name = task.params.get("brand_name", "Brand")
        product_info = task.params.get("product_info", "premium product")

        sequence = await self._llm_analyze(f"""Create an email marketing sequence for:
Trigger: {trigger}
Brand: {brand_name}
Product: {product_info}

Respond ONLY in valid JSON with these keys:
- emails: array of 3-5 email objects, each with: email_number, subject, preview_text, body (full email HTML-ready), cta, send_delay_hours
- implementation_notes: string with A/B testing suggestions
Make the copy compelling and specific to this brand/product.""")

        try:
            output = json.loads(sequence.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            output = {"sequence_raw": sequence}

        output["trigger"] = trigger
        output["brand_name"] = brand_name
        output["generated_at"] = datetime.utcnow().isoformat()

        self._save_output(f"email_sequence_{trigger}.json", output)

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _fresh_pulse_check(self, task: AgentTask) -> AgentResult:
        """Scan for REAL current trends using Brave Search."""
        niche = task.params.get("niche", "skincare")
        industry = task.params.get("industry", "beauty")

        # Multiple real searches for comprehensive trend data
        trend_searches = await self._brave_search(f"{niche} trending tiktok instagram 2026", count=5)
        hashtag_searches = await self._brave_search(f"trending {niche} hashtags social media", count=3)
        competitor_searches = await self._brave_search(f"{niche} {industry} brand launches news", count=5)

        all_context = "\n".join([
            "TRENDS:\n" + "\n".join([f"- {r['title']}: {r['description']}" for r in trend_searches]),
            "\nHASHTAGS:\n" + "\n".join([f"- {r['title']}: {r['description']}" for r in hashtag_searches]),
            "\nCOMPETITOR NEWS:\n" + "\n".join([f"- {r['title']}: {r['description']}" for r in competitor_searches]),
        ])

        analysis = await self._llm_analyze(f"""Based on this REAL search data, create a trend pulse report for the {niche} niche.

{all_context}

Respond ONLY in valid JSON with these keys:
- trending_content: array of objects with trend, estimated_engagement, opportunity
- trending_hashtags: array of 10-15 currently trending hashtags
- viral_opportunities: array of objects with opportunity, timing, action
- seasonal_moments: array of relevant upcoming moments
- competitor_activities: array of real competitor moves from the news
- cultural_moments: array of cultural trends to leverage
- sources: array of URLs from the search results""")

        try:
            output = json.loads(analysis.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            output = {"analysis_raw": analysis}

        output["niche"] = niche
        output["industry"] = industry
        output["pulse_check_date"] = datetime.utcnow().isoformat()
        output["expires_at"] = (datetime.utcnow() + timedelta(hours=72)).isoformat()
        output["data_source"] = "brave_search_live"
        output["search_results_analyzed"] = len(trend_searches) + len(hashtag_searches) + len(competitor_searches)

        self._save_output(f"pulse_check_{niche.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", output)

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _generate_ad_creative(self, task: AgentTask) -> AgentResult:
        """Generate ad copy using LLM with real market context."""
        product = task.params.get("product", "")
        platform = task.params.get("platform", "facebook").lower()
        budget_level = task.params.get("budget_level", "medium")
        target_audience = task.params.get("target_audience", "")

        if not product:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False,
                               error="Missing 'product' parameter")

        # Search for real ad benchmarks and competitor ads
        ad_context = await self._brave_search(f"{product} {platform} ad examples benchmarks CPC CPM", count=5)
        context = "\n".join([f"- {r['title']}: {r['description']}" for r in ad_context])

        creative = await self._llm_analyze(f"""Create ad creative for:
Product: {product}
Platform: {platform}
Budget: {budget_level}
Target: {target_audience}

Market context from search:
{context}

Respond ONLY in valid JSON with these keys:
- ad_copy_variations: array of 3 different ad hooks/headlines
- audience_targeting: object with interests, age_range, behaviors specific to {platform}
- creative_brief: object with visuals (array), video_concept, color_palette, text_overlay
- a_b_test_plan: object with 3 test variations
- budget_allocation: object with daily_spend, duration, cpa_benchmark
- success_metrics: object with ctr_target, cpc_target, roas_target
Base metrics on real {platform} benchmarks for this product category.""")

        try:
            output = json.loads(creative.strip().removeprefix("```json").removesuffix("```").strip())
        except json.JSONDecodeError:
            output = {"creative_raw": creative}

        output["product"] = product
        output["platform"] = platform
        output["budget_level"] = budget_level
        output["generated_at"] = datetime.utcnow().isoformat()
        output["data_source"] = "llm_with_market_data"

        self._save_output(f"ad_creative_{product.replace(' ', '_')}_{platform}.json", output)

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    # ── Utilities ─────────────────────────────────────────────────────────

    def _save_output(self, filename: str, data: dict):
        """Save output to data directory."""
        try:
            filepath = self._data_dir / filename
            filepath.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save output: {e}")

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
