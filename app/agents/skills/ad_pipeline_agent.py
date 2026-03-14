"""
Ad Pipeline Agent — Automated ad creative generation from brand URL.

Inspired by Mike Futia's workflow: brand URL → research → ad prompts → image generation.
This agent chains BraveSearchAgent + LLM + ImageAgent into a single pipeline.

Flow:
1. RESEARCH: Take a brand URL, scrape/search to understand the brand
2. ANALYZE: Identify brand voice, target audience, product highlights
3. GENERATE PROMPTS: Create N ad creative prompts (copy + image prompt)
4. GENERATE IMAGES: Batch-generate ad images from prompts
5. PACKAGE: Return complete ad set with copy + images

This is a real pipeline — not a description of one.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class AdPipelineAgent(BaseAgent):
    """Generate complete ad creative sets from a brand URL or description."""

    def __init__(self, output_dir: str = "./data/ad_pipeline"):
        super().__init__(
            name="ad_pipeline_agent",
            description=(
                "Automated ad creative pipeline: brand URL → research → ad prompts → image generation. "
                "Generates complete ad sets with copy and images."
            ),
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="generate_ad_set",
                    description=(
                        "Full pipeline: research a brand, generate ad copy and images. "
                        "Params: brand_url (str), num_ads (int, default 5), "
                        "style (str, optional), target_audience (str, optional), "
                        "ad_platforms (list[str], optional — e.g. ['instagram', 'facebook'])"
                    ),
                    category="creative",
                    timeout_seconds=300,
                ),
                AgentCapability(
                    name="generate_ad_prompts",
                    description=(
                        "Generate ad copy + image prompts without generating images. "
                        "Params: brand_url (str), num_ads (int), style (str, optional)"
                    ),
                    category="creative",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="batch_generate_images",
                    description=(
                        "Generate images from a list of pre-made prompts. "
                        "Params: prompts (list[str]), style (str, optional)"
                    ),
                    category="creative",
                    timeout_seconds=300,
                ),
            ],
        )
        self._output_dir = Path(output_dir)
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self._output_dir = Path("/tmp/cipher_data/ad_pipeline")
            self._output_dir.mkdir(parents=True, exist_ok=True)
            logger.info("[AD PIPELINE] Using /tmp fallback for output_dir")

    async def validate(self, task: AgentTask) -> bool:
        cap = task.params.get("capability", task.instruction.split()[0] if task.instruction else "")
        if cap in ("generate_ad_set", "generate_ad_prompts"):
            if not task.params.get("brand_url") and not task.params.get("brand_description"):
                return False
        elif cap == "batch_generate_images":
            if not task.params.get("prompts"):
                return False
        return True

    async def execute(self, task: AgentTask) -> dict[str, Any]:
        cap = task.params.get("capability", "generate_ad_set")
        self.emit_progress(f"Starting ad pipeline: {cap}")

        if cap == "generate_ad_set":
            return await self._full_pipeline(task)
        elif cap == "generate_ad_prompts":
            return await self._prompts_only(task)
        elif cap == "batch_generate_images":
            return await self._batch_images(task)
        else:
            return await self._full_pipeline(task)

    async def verify(self, result: dict[str, Any]) -> bool:
        if not result:
            return False
        if "ads" in result and len(result["ads"]) > 0:
            return True
        if "prompts" in result and len(result["prompts"]) > 0:
            return True
        if "images" in result and len(result["images"]) > 0:
            return True
        return False

    # ------------------------------------------------------------------
    # FULL PIPELINE
    # ------------------------------------------------------------------

    async def _full_pipeline(self, task: AgentTask) -> dict:
        brand_url = task.params.get("brand_url", "")
        brand_description = task.params.get("brand_description", "")
        num_ads = min(task.params.get("num_ads", 5), 20)  # cap at 20
        style = task.params.get("style", "")
        target_audience = task.params.get("target_audience", "")
        platforms = task.params.get("ad_platforms", ["instagram", "facebook"])

        # Step 1: Research the brand
        self.emit_progress("Step 1/4: Researching brand...")
        brand_intel = await self._research_brand(brand_url, brand_description)

        # Step 2: Analyze and build brand profile
        self.emit_progress("Step 2/4: Analyzing brand identity...")
        brand_profile = await self._build_brand_profile(
            brand_intel, brand_url, target_audience, style
        )

        # Step 3: Generate ad prompts (copy + image descriptions)
        self.emit_progress(f"Step 3/4: Generating {num_ads} ad concepts...")
        ad_concepts = await self._generate_ad_concepts(
            brand_profile, num_ads, platforms
        )

        # Step 4: Batch-generate images
        self.emit_progress(f"Step 4/4: Generating {len(ad_concepts)} ad images...")
        ads_with_images = await self._generate_images_for_ads(ad_concepts)

        # Package results
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = {
            "brand_url": brand_url,
            "brand_profile": brand_profile,
            "num_ads_requested": num_ads,
            "num_ads_generated": len(ads_with_images),
            "platforms": platforms,
            "ads": ads_with_images,
            "timestamp": ts,
            "pipeline": "brand_url → research → analyze → prompts → images",
        }

        # Save to disk
        save_path = self._output_dir / f"ad_set_{ts}.json"
        save_path.write_text(json.dumps(output, indent=2, default=str))
        output["saved_to"] = str(save_path)

        return output

    # ------------------------------------------------------------------
    # PROMPTS ONLY (no image generation)
    # ------------------------------------------------------------------

    async def _prompts_only(self, task: AgentTask) -> dict:
        brand_url = task.params.get("brand_url", "")
        brand_description = task.params.get("brand_description", "")
        num_ads = min(task.params.get("num_ads", 10), 40)
        style = task.params.get("style", "")
        target_audience = task.params.get("target_audience", "")

        self.emit_progress("Researching brand...")
        brand_intel = await self._research_brand(brand_url, brand_description)

        self.emit_progress("Building brand profile...")
        brand_profile = await self._build_brand_profile(
            brand_intel, brand_url, target_audience, style
        )

        self.emit_progress(f"Generating {num_ads} ad prompts...")
        ad_concepts = await self._generate_ad_concepts(
            brand_profile, num_ads, ["instagram", "facebook"]
        )

        return {
            "brand_profile": brand_profile,
            "prompts": ad_concepts,
            "num_prompts": len(ad_concepts),
        }

    # ------------------------------------------------------------------
    # BATCH IMAGE GENERATION
    # ------------------------------------------------------------------

    async def _batch_images(self, task: AgentTask) -> dict:
        prompts = task.params.get("prompts", [])
        style = task.params.get("style", "")

        results = []
        # Generate in parallel batches of 3 to avoid rate limits
        for i in range(0, len(prompts), 3):
            batch = prompts[i:i + 3]
            self.emit_progress(f"Generating images {i + 1}-{min(i + 3, len(prompts))} of {len(prompts)}...")
            tasks = [self._generate_single_image(p, style) for p in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for prompt, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results.append({"prompt": prompt, "error": str(result)})
                else:
                    results.append(result)

        return {
            "images": results,
            "total_generated": sum(1 for r in results if "error" not in r),
            "total_failed": sum(1 for r in results if "error" in r),
        }

    # ------------------------------------------------------------------
    # INTERNAL: Brand Research
    # ------------------------------------------------------------------

    async def _research_brand(self, brand_url: str, brand_description: str = "") -> dict:
        """Use BraveSearchAgent to research the brand."""
        research_data = {"url": brand_url, "search_results": [], "scraped_content": ""}

        # If we have a URL, extract the brand name for searching
        brand_name = ""
        if brand_url:
            # Extract domain as brand name hint
            from urllib.parse import urlparse
            parsed = urlparse(brand_url if brand_url.startswith("http") else f"https://{brand_url}")
            brand_name = parsed.netloc.replace("www.", "").split(".")[0]

        # Search for brand info
        if brand_name or brand_description:
            search_query = brand_description or f"{brand_name} brand products about"
            try:
                search_result = await self.invoke_agent(
                    "brave_search_agent",
                    f"Search for: {search_query}",
                    {"capability": "web_search", "query": search_query, "num_results": 5},
                )
                if search_result and search_result.get("success"):
                    research_data["search_results"] = search_result.get("output", {}).get("results", [])
            except Exception as e:
                logger.warning(f"[AD PIPELINE] Brand search failed: {e}")

        # Also try to scrape the actual URL
        if brand_url:
            try:
                scrape_result = await self.invoke_agent(
                    "content_extractor_agent",
                    f"Extract content from {brand_url}",
                    {"capability": "auto_extract", "url": brand_url},
                )
                if scrape_result and scrape_result.get("success"):
                    output = scrape_result.get("output", {})
                    research_data["scraped_content"] = (
                        output.get("text", "") or
                        output.get("content", "") or
                        json.dumps(output, default=str)
                    )[:4000]
            except Exception as e:
                logger.warning(f"[AD PIPELINE] URL scrape failed: {e}")

        if brand_description:
            research_data["provided_description"] = brand_description

        return research_data

    # ------------------------------------------------------------------
    # INTERNAL: Brand Profile Builder
    # ------------------------------------------------------------------

    async def _build_brand_profile(
        self, research_data: dict, brand_url: str, target_audience: str, style: str
    ) -> dict:
        """Use LLM to analyze research and build brand profile."""
        from app.services.llm_router import chat_completion

        search_snippets = "\n".join(
            f"- {r.get('title', '')}: {r.get('snippet', '')}"
            for r in research_data.get("search_results", [])[:5]
        )
        scraped = research_data.get("scraped_content", "")[:3000]
        provided = research_data.get("provided_description", "")

        messages = [
            {"role": "system", "content": (
                "You are an expert brand strategist. Analyze the provided research about a brand "
                "and create a concise brand profile for ad generation.\n\n"
                "Output ONLY a JSON object with these fields:\n"
                "- brand_name: string\n"
                "- tagline: string (create one if none found)\n"
                "- products_services: list of strings\n"
                "- brand_voice: string (e.g., 'warm and earthy', 'bold and technical')\n"
                "- target_audience: string\n"
                "- key_benefits: list of strings (top 3-5 selling points)\n"
                "- visual_style: string (e.g., 'natural tones, organic textures')\n"
                "- competitors: list of strings\n"
                "- unique_selling_prop: string\n"
            )},
            {"role": "user", "content": (
                f"Brand URL: {brand_url}\n"
                f"Provided description: {provided}\n"
                f"Target audience hint: {target_audience}\n"
                f"Style hint: {style}\n\n"
                f"Search results:\n{search_snippets}\n\n"
                f"Scraped content:\n{scraped}\n\n"
                "Build the brand profile JSON."
            )},
        ]

        result = await chat_completion(
            messages=messages, model_tier="balanced", max_tokens=1024, temperature=0.3,
        )

        if result and isinstance(result, dict):
            import re
            text = result.get("content", "")
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        # Fallback profile
        return {
            "brand_name": brand_url.split("//")[-1].split(".")[0] if brand_url else "Unknown",
            "tagline": "",
            "products_services": [],
            "brand_voice": style or "professional",
            "target_audience": target_audience or "general consumers",
            "key_benefits": [],
            "visual_style": "clean and modern",
            "competitors": [],
            "unique_selling_prop": "",
        }

    # ------------------------------------------------------------------
    # INTERNAL: Ad Concept Generator
    # ------------------------------------------------------------------

    async def _generate_ad_concepts(
        self, brand_profile: dict, num_ads: int, platforms: list[str]
    ) -> list[dict]:
        """Use LLM to generate ad copy + image prompts."""
        from app.services.llm_router import chat_completion

        messages = [
            {"role": "system", "content": (
                "You are a world-class advertising creative director. Generate ad concepts "
                "that include both copy (headline + body) and a detailed image generation prompt.\n\n"
                f"Generate exactly {num_ads} ad concepts.\n\n"
                "For each ad, output a JSON object with:\n"
                "- headline: string (punchy, under 10 words)\n"
                "- body_copy: string (compelling, 1-2 sentences)\n"
                "- cta: string (call to action, e.g., 'Shop Now')\n"
                "- image_prompt: string (detailed DALL-E prompt — describe the visual, "
                "lighting, composition, style. Do NOT include text in the image.)\n"
                "- platform: string (which platform this ad is designed for)\n"
                "- ad_format: string (e.g., 'square post', 'story', 'carousel card')\n"
                "- emotional_hook: string (what emotion this targets)\n\n"
                "RULES for image_prompt:\n"
                "- Be SPECIFIC: describe exact scene, colors, objects, lighting\n"
                "- Match the brand's visual style\n"
                "- No text or logos in the image\n"
                "- Include style keywords (photography style, rendering style, etc.)\n"
                "- Each prompt should be distinct — show different angles of the brand\n\n"
                "Output ONLY a JSON array of ad concept objects."
            )},
            {"role": "user", "content": (
                f"Brand Profile:\n{json.dumps(brand_profile, indent=2, default=str)}\n\n"
                f"Target platforms: {', '.join(platforms)}\n"
                f"Number of ads: {num_ads}\n\n"
                "Generate the ad concepts now."
            )},
        ]

        result = await chat_completion(
            messages=messages, model_tier="balanced", max_tokens=3000, temperature=0.7,
        )

        if result and isinstance(result, dict):
            import re
            text = result.get("content", "")
            json_match = re.search(r'\[[\s\S]*\]', text)
            if json_match:
                try:
                    concepts = json.loads(json_match.group())
                    if isinstance(concepts, list):
                        return concepts[:num_ads]
                except json.JSONDecodeError:
                    pass

        return []

    # ------------------------------------------------------------------
    # INTERNAL: Image Generation
    # ------------------------------------------------------------------

    async def _generate_images_for_ads(self, ad_concepts: list[dict]) -> list[dict]:
        """Generate images for each ad concept using ImageAgent."""
        results = []

        # Process in batches of 3 to respect rate limits
        for i in range(0, len(ad_concepts), 3):
            batch = ad_concepts[i:i + 3]
            tasks = []
            for concept in batch:
                prompt = concept.get("image_prompt", "")
                if prompt:
                    tasks.append(self._generate_single_image(prompt, ""))
                else:
                    tasks.append(asyncio.coroutine(lambda: {"error": "no prompt"})())

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for concept, img_result in zip(batch, batch_results):
                ad_entry = {**concept}
                if isinstance(img_result, Exception):
                    ad_entry["image_error"] = str(img_result)
                    ad_entry["image_url"] = None
                elif isinstance(img_result, dict) and "error" not in img_result:
                    images = img_result.get("images", [])
                    ad_entry["image_url"] = images[0].get("url", "") if images else None
                    ad_entry["image_saved_path"] = (
                        img_result.get("saved_paths", [None])[0]
                    )
                else:
                    ad_entry["image_error"] = str(img_result)
                    ad_entry["image_url"] = None
                results.append(ad_entry)

            # Small delay between batches to avoid rate limits
            if i + 3 < len(ad_concepts):
                await asyncio.sleep(1)

        return results

    async def _generate_single_image(self, prompt: str, style: str = "") -> dict:
        """Generate a single image using ImageAgent."""
        try:
            full_prompt = f"{prompt}. {style}" if style else prompt
            result = await self.invoke_agent(
                "image_agent",
                f"Generate image: {full_prompt}",
                {
                    "capability": "generate_image",
                    "prompt": full_prompt,
                    "size": "1024x1024",
                    "quality": "standard",
                },
            )
            if result and result.get("success"):
                return result.get("output", {})
            return {"error": result.get("error", "Image generation failed")}
        except Exception as e:
            logger.error(f"[AD PIPELINE] Image generation failed: {e}")
            return {"error": str(e)}
