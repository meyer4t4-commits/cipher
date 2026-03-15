"""
Web Builder Agent — Website creation, modification, and deployment.

This agent fills the critical gap in Cipher's arsenal: the ability to actually
BUILD and MODIFY websites, not just scrape them. Combines code generation (LLM),
file management, and deployment capabilities.

Capabilities:
1. generate_page — Generate complete HTML/CSS/JS pages from description
2. generate_component — Generate a single component (header, product card, etc.)
3. modify_site — Modify existing website files (edit, add sections, restyle)
4. generate_storefront — Generate a full e-commerce storefront (multi-page)
5. analyze_competitor — Analyze a competitor's site and generate a better version
6. deploy_preview — Deploy to a preview URL for review
7. optimize_seo — Analyze and optimize a page for SEO

Architecture:
- LLM generates code based on detailed prompts
- Files written to workspace directory
- Can chain to image_agent for product photos
- Can chain to research_agent for competitor analysis
- Outputs are real HTML/CSS/JS files, not descriptions
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


# ── Templates & Constants ──────────────────────────────────────────

STOREFRONT_SECTIONS = [
    "hero",
    "product_grid",
    "about",
    "testimonials",
    "ingredients",
    "faq",
    "footer",
    "navigation",
]

MODERN_CSS_FRAMEWORK = """
/* Modern CSS Reset + Design System */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
    --color-primary: #2D5016;
    --color-secondary: #8B6914;
    --color-accent: #D4A843;
    --color-bg: #FAFAF5;
    --color-bg-warm: #F5F0E8;
    --color-text: #1A1A1A;
    --color-text-light: #6B6B6B;
    --color-white: #FFFFFF;
    --color-border: #E8E0D0;
    --font-heading: 'Playfair Display', Georgia, serif;
    --font-body: 'Inter', -apple-system, sans-serif;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
    --shadow-lg: 0 8px 30px rgba(0,0,0,0.12);
    --radius-sm: 6px;
    --radius-md: 12px;
    --radius-lg: 20px;
    --max-width: 1200px;
    --transition: 0.3s ease;
}
body { font-family: var(--font-body); color: var(--color-text); background: var(--color-bg); line-height: 1.6; }
h1, h2, h3, h4 { font-family: var(--font-heading); line-height: 1.2; }
img { max-width: 100%; height: auto; display: block; }
a { text-decoration: none; color: inherit; }
.container { max-width: var(--max-width); margin: 0 auto; padding: 0 24px; }
"""


class WebBuilderAgent(BaseAgent):
    """
    Web Builder Agent — generates, modifies, and deploys websites.
    The missing piece that lets Cipher actually build things, not just analyze.
    """

    name = "web_builder_agent"
    description = "Website builder — generates pages, storefronts, components, and deploys sites"
    version = "1.0.0"

    def __init__(self):
        super().__init__(
            name="web_builder_agent",
            description="Website builder — generates pages, storefronts, components, and deploys sites",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="generate_page",
                    description="Generate a complete HTML page from a description",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="generate_component",
                    description="Generate a single web component (header, card, form, etc.)",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="modify_site",
                    description="Modify an existing website file (edit HTML/CSS/JS)",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=90,
                ),
                AgentCapability(
                    name="generate_storefront",
                    description="Generate a full e-commerce storefront with multiple pages",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=300,
                ),
                AgentCapability(
                    name="analyze_competitor",
                    description="Analyze a competitor website and generate an improved version",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=180,
                ),
                AgentCapability(
                    name="optimize_seo",
                    description="Analyze and optimize a page for search engine optimization",
                    category="web",
                    requires_approval=False,
                    timeout_seconds=60,
                ),
            ],
        )
        self._workspace = Path("data/web_builder")
        try:
            self._workspace.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self._workspace = Path("/tmp/cipher_web_builder")
            self._workspace.mkdir(parents=True, exist_ok=True)

    async def validate(self, task: AgentTask) -> bool:
        operation = task.params.get("operation", "")
        valid = {cap.name for cap in self.capabilities}
        if operation not in valid:
            logger.warning(f"[web_builder] Unknown operation '{operation}'")
            return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        operation = task.params.get("operation", "")
        try:
            if operation == "generate_page":
                output = await self._generate_page(task)
            elif operation == "generate_component":
                output = await self._generate_component(task)
            elif operation == "modify_site":
                output = await self._modify_site(task)
            elif operation == "generate_storefront":
                output = await self._generate_storefront(task)
            elif operation == "analyze_competitor":
                output = await self._analyze_competitor(task)
            elif operation == "optimize_seo":
                output = await self._optimize_seo(task)
            else:
                output = {"error": f"Unknown operation: {operation}"}

            success = "error" not in output
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=success,
                output=output,
                error=output.get("error") if isinstance(output, dict) else None,
            )
        except Exception as e:
            logger.error(f"[web_builder] Execution failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def verify(self, result: AgentResult) -> bool:
        return result.success and result.output is not None

    # ── Operations ──────────────────────────────────────────────────

    async def _generate_page(self, task: AgentTask) -> dict:
        """Generate a complete HTML page from a description."""
        from app.services.llm_router import chat_completion
        from app.models.schemas import ModelTier

        description = task.params.get("description") or task.instruction
        style = task.params.get("style", "modern, clean, professional")
        page_type = task.params.get("page_type", "landing")
        brand_name = task.params.get("brand_name", "")
        color_scheme = task.params.get("color_scheme", "")

        await self.emit_progress(f"Generating {page_type} page...")

        prompt = f"""You are an expert web developer. Generate a COMPLETE, production-ready HTML page.

REQUIREMENTS:
- Page type: {page_type}
- Description: {description}
- Style: {style}
{f'- Brand name: {brand_name}' if brand_name else ''}
{f'- Color scheme: {color_scheme}' if color_scheme else ''}

CRITICAL RULES:
1. Output ONLY the complete HTML file — no explanation, no markdown
2. Include ALL CSS inline in a <style> tag (no external stylesheets except Google Fonts)
3. Include ALL JavaScript inline in a <script> tag
4. Use modern CSS (flexbox, grid, custom properties)
5. Must be fully responsive (mobile-first)
6. Use placeholder images from https://placehold.co/ (e.g., https://placehold.co/600x400)
7. Include meta tags for SEO
8. Use semantic HTML5 elements
9. Add smooth scroll, hover effects, and subtle animations
10. Typography: Use Google Fonts (Playfair Display for headings, Inter for body)

Start with <!DOCTYPE html> and end with </html>. Nothing else."""

        response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_tier=ModelTier.REASONING,
            temperature=0.3,
            max_tokens=8000,
        )

        content = response.get("content", "")
        # Extract HTML from response
        html = self._extract_html(content)

        if not html:
            return {"error": "LLM failed to generate valid HTML"}

        # Save to file
        filename = f"{page_type}_{int(time.time())}.html"
        filepath = self._workspace / filename
        filepath.write_text(html, encoding="utf-8")

        return {
            "page_type": page_type,
            "file_path": str(filepath),
            "filename": filename,
            "size_bytes": len(html),
            "description": description[:200],
        }

    async def _generate_component(self, task: AgentTask) -> dict:
        """Generate a single web component."""
        from app.services.llm_router import chat_completion
        from app.models.schemas import ModelTier

        component_type = task.params.get("component_type", "section")
        description = task.params.get("description") or task.instruction
        brand_name = task.params.get("brand_name", "")

        await self.emit_progress(f"Generating {component_type} component...")

        prompt = f"""Generate a single HTML component (with inline CSS) for:

Component type: {component_type}
Description: {description}
{f'Brand: {brand_name}' if brand_name else ''}

Output ONLY the HTML+CSS code. Include a <style> tag and the HTML elements.
Use modern CSS, be responsive, and make it visually stunning.
Use placeholder images from https://placehold.co/ where needed."""

        response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_tier=ModelTier.DEFAULT,
            temperature=0.4,
            max_tokens=4000,
        )

        content = response.get("content", "")
        html = self._extract_html(content) or content

        filename = f"component_{component_type}_{int(time.time())}.html"
        filepath = self._workspace / filename
        filepath.write_text(html, encoding="utf-8")

        return {
            "component_type": component_type,
            "file_path": str(filepath),
            "filename": filename,
            "size_bytes": len(html),
        }

    async def _modify_site(self, task: AgentTask) -> dict:
        """Modify an existing website file."""
        from app.services.llm_router import chat_completion
        from app.models.schemas import ModelTier

        file_path = task.params.get("file_path", "")
        modification = task.params.get("modification") or task.instruction

        if not file_path:
            return {"error": "file_path parameter required"}

        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        await self.emit_progress(f"Reading existing file: {path.name}...")
        original = path.read_text(encoding="utf-8")

        # Truncate for context window
        truncated = original[:15000]

        prompt = f"""You are modifying an existing HTML/CSS/JS file.

CURRENT FILE ({path.name}):
```
{truncated}
```

REQUESTED MODIFICATION:
{modification}

RULES:
1. Output the COMPLETE modified file — not just the changed parts
2. Preserve all existing functionality unless told to remove it
3. Keep the same coding style
4. Start with the first line of the file, end with the last line
5. Output ONLY the file content, no explanation

Start with <!DOCTYPE html> or the first line of the original file."""

        response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_tier=ModelTier.REASONING,
            temperature=0.2,
            max_tokens=12000,
        )

        new_content = response.get("content", "")
        new_html = self._extract_html(new_content) or new_content

        if not new_html or len(new_html) < 50:
            return {"error": "LLM produced invalid modification"}

        # Backup original
        backup_path = self._workspace / f"backup_{path.name}_{int(time.time())}"
        backup_path.write_text(original, encoding="utf-8")

        # Write modified file
        path.write_text(new_html, encoding="utf-8")

        return {
            "file_path": str(path),
            "backup_path": str(backup_path),
            "original_size": len(original),
            "new_size": len(new_html),
            "modification": modification[:200],
        }

    async def _generate_storefront(self, task: AgentTask) -> dict:
        """Generate a full e-commerce storefront — the crown jewel operation."""
        from app.services.llm_router import chat_completion
        from app.models.schemas import ModelTier

        brand_name = task.params.get("brand_name", "TallowRoots")
        brand_description = task.params.get("brand_description",
            "Premium grass-fed tallow skincare. 100% natural, handcrafted body butter and skin balm.")
        products = task.params.get("products", [
            {"name": "Original Tallow Balm", "price": "$38", "description": "Our signature grass-fed tallow body butter. Deeply moisturizing, all-natural."},
            {"name": "Whipped Tallow Cream", "price": "$42", "description": "Light, whipped texture. Perfect for daily face and body use."},
            {"name": "Tallow Lip Balm", "price": "$12", "description": "Nourishing lip treatment with tallow, beeswax, and honey."},
        ])
        style_reference = task.params.get("style_reference", "Vintage Tradition, Primally Pure — clean, earthy, premium natural aesthetic")
        color_scheme = task.params.get("color_scheme", "earthy greens, warm golds, cream whites")
        features = task.params.get("features", [
            "hero section with brand story",
            "product grid with hover effects",
            "about section with founder story",
            "testimonials carousel",
            "ingredients transparency section",
            "FAQ accordion",
            "email signup",
            "mobile responsive navigation",
        ])

        await self.emit_progress("Generating full storefront — this takes a minute...")

        # Build product JSON for prompt
        products_str = json.dumps(products, indent=2) if isinstance(products, list) else str(products)

        prompt = f"""You are a world-class web designer building a premium e-commerce storefront.

BRAND: {brand_name}
DESCRIPTION: {brand_description}
STYLE INSPIRATION: {style_reference}
COLOR SCHEME: {color_scheme}

PRODUCTS:
{products_str}

REQUIRED SECTIONS (in order):
{chr(10).join(f'- {f}' for f in features)}

CRITICAL DESIGN RULES:
1. Output a SINGLE complete HTML file with ALL CSS and JS inline
2. Google Fonts: Playfair Display (headings) + Inter (body)
3. Mobile-first responsive design
4. Smooth scroll navigation between sections
5. Product cards with hover zoom effect
6. Testimonials section (use realistic placeholder reviews)
7. Sticky/transparent navigation bar
8. Floating "Shop Now" CTA
9. FAQ accordion with JavaScript
10. Email signup form (styled, doesn't need backend)
11. Footer with links, social media icons (SVG), contact info
12. Subtle parallax or fade-in animations on scroll
13. SEO meta tags (title, description, OG tags)
14. Use placeholder images from https://placehold.co/
15. Make it look like a $10,000 custom website
16. Include structured data (JSON-LD) for products
17. Add CSS custom properties for easy theming

The page should feel premium, natural, trustworthy, and convert browsers into buyers.
Output ONLY the complete HTML file. Start with <!DOCTYPE html>."""

        response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_tier=ModelTier.REASONING,
            temperature=0.3,
            max_tokens=16000,
        )

        content = response.get("content", "")
        html = self._extract_html(content)

        if not html:
            return {"error": "Failed to generate storefront HTML"}

        # Save storefront
        site_dir = self._workspace / brand_name.lower().replace(" ", "_")
        site_dir.mkdir(parents=True, exist_ok=True)

        index_path = site_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")

        await self.emit_progress(f"Storefront saved: {index_path}")

        return {
            "brand_name": brand_name,
            "site_directory": str(site_dir),
            "index_path": str(index_path),
            "size_bytes": len(html),
            "sections": features,
            "products_count": len(products) if isinstance(products, list) else 0,
        }

    async def _analyze_competitor(self, task: AgentTask) -> dict:
        """Analyze a competitor website and generate an improved version."""
        from app.services.llm_router import chat_completion
        from app.models.schemas import ModelTier

        competitor_url = task.params.get("url", "")
        brand_name = task.params.get("brand_name", "TallowRoots")

        await self.emit_progress(f"Analyzing competitor: {competitor_url or 'from description'}...")

        # Try to scrape competitor — prefer headless browser (JS-rendered) over raw HTTP
        competitor_content = ""
        if competitor_url:
            try:
                from app.services.headless_browser import visit_page
                browser_result = await visit_page(
                    url=competitor_url,
                    extract_text=True,
                    extract_links=True,
                    scroll_to_bottom=True,
                )
                if browser_result.success:
                    competitor_content = browser_result.text[:5000]
                    if browser_result.metadata:
                        competitor_content += f"\n\nMETADATA: {json.dumps(browser_result.metadata)}"
            except Exception as e:
                logger.warning(f"[web_builder] Headless browser scrape failed, trying web_agent: {e}")
                try:
                    result = await self.invoke_agent(
                        "web_agent",
                        f"Scrape this website: {competitor_url}",
                        params={"operation": "scrape_html", "url": competitor_url},
                        timeout=30,
                    )
                    if result.success and result.output:
                        competitor_content = str(result.output)[:5000]
                except Exception as e2:
                    logger.warning(f"[web_builder] web_agent fallback also failed: {e2}")

        competitor_desc = task.params.get("description", "") or competitor_content

        prompt = f"""Analyze this competitor website and identify what makes it effective:

{f'Competitor URL: {competitor_url}' if competitor_url else ''}
{f'Competitor content/description: {competitor_desc[:3000]}' if competitor_desc else 'General tallow skincare competitor (Vintage Tradition, FATCO, Primally Pure style)'}

Provide a JSON analysis:
{{
    "strengths": ["list of what they do well"],
    "weaknesses": ["list of what could be improved"],
    "design_elements": ["specific design patterns to adopt"],
    "content_strategy": "how they position their products",
    "conversion_tactics": ["specific CTA and conversion elements"],
    "seo_keywords": ["keywords they target"],
    "recommendations": ["specific improvements for {brand_name}"]
}}

Output ONLY the JSON."""

        response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_tier=ModelTier.REASONING,
            temperature=0.3,
            max_tokens=2000,
        )

        content = response.get("content", "")
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                analysis = json.loads(content[start:end])
            else:
                analysis = {"raw_analysis": content}
        except json.JSONDecodeError:
            analysis = {"raw_analysis": content}

        analysis["competitor_url"] = competitor_url
        analysis["analyzed_for"] = brand_name

        return analysis

    async def _optimize_seo(self, task: AgentTask) -> dict:
        """Analyze and optimize a page for SEO."""
        from app.services.llm_router import chat_completion
        from app.models.schemas import ModelTier

        file_path = task.params.get("file_path", "")
        target_keywords = task.params.get("keywords", [])

        if not file_path:
            return {"error": "file_path parameter required"}

        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        html = path.read_text(encoding="utf-8")[:10000]

        prompt = f"""Analyze this HTML page for SEO and provide specific optimization recommendations.

HTML (truncated):
```
{html}
```

{f'Target keywords: {", ".join(target_keywords)}' if target_keywords else ''}

Provide a JSON response:
{{
    "score": 0-100,
    "title_tag": "optimized title tag suggestion",
    "meta_description": "optimized meta description",
    "issues": [
        {{"severity": "high|medium|low", "issue": "description", "fix": "how to fix"}}
    ],
    "keyword_suggestions": ["top 10 target keywords"],
    "structured_data_suggestions": "what schema.org markup to add",
    "performance_tips": ["loading speed and performance suggestions"]
}}

Output ONLY the JSON."""

        response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_tier=ModelTier.DEFAULT,
            temperature=0.2,
            max_tokens=2000,
        )

        content = response.get("content", "")
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        return {"raw_analysis": content}

    # ── Helpers ──────────────────────────────────────────────────────

    def _extract_html(self, content: str) -> str:
        """Extract HTML from LLM response, stripping markdown fences."""
        if not content:
            return ""

        # Remove markdown code fences
        if "```html" in content:
            start = content.index("```html") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            # Skip language identifier on same line
            newline = content.find("\n", start)
            if newline > 0 and newline - start < 20:
                start = newline + 1
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        # Ensure it starts with DOCTYPE or <html>
        content = content.strip()
        if content.startswith("<!DOCTYPE") or content.startswith("<html") or content.startswith("<"):
            return content

        # Try to find HTML start
        for marker in ["<!DOCTYPE", "<html", "<div", "<section", "<style"]:
            idx = content.find(marker)
            if idx >= 0:
                return content[idx:]

        return content if "<" in content else ""
