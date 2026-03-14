"""
Memory Seeds — Pre-loaded operational knowledge that survives restarts.

Problem: Cipher's memory is in-memory on Railway (wipes on every deploy).
Solution: Seed critical playbooks and learnings on startup so they're always available.

These seeds are the baseline. As Cipher learns new things during a session, they get
added to memory dynamically. But the seeds ensure the most important knowledge
is ALWAYS present, even after a fresh deploy.

Add new seeds here when Mark teaches Cipher something that should never be forgotten.
"""

MEMORY_SEEDS = [
    {
        "id": "seed-execution-mode",
        "content": (
            "CORE PRINCIPLE: When Mark gives instructions, EXECUTE using agents and tools. "
            "Never say 'I don't have access' or 'I would need X'. You have 32 agents including "
            "brave_search_agent, content_extractor_agent, image_agent, ad_pipeline_agent, "
            "self_improvement_agent, and more. Use them. Research first, then recommend. "
            "Every recommendation must be backed by real data from agent calls, not guesses."
        ),
        "metadata": {"source": "seed", "type": "operating_principle", "priority": "critical"},
    },
    {
        "id": "seed-seo-playbook",
        "content": (
            "LOCAL SEO 8-PROMPT STACK — Run this for every new brand/store/product with local presence. "
            "Week 1: GBP Category Audit (map competitor categories) + GBP Attributes Audit (gap analysis). "
            "Week 2: Services Section Optimization + GBP Description Optimization (3 testable versions). "
            "Week 3: Competitor Review Teardown (velocity, keywords, locations) + Review Response Strategy (keyword-rich templates). "
            "Week 4: GBP Posts Strategy (8-week calendar, neighborhood-specific) + GBP Photo Audit (weekly uploads). "
            "EXECUTION: Use brave_search to research competitors, content_extractor to pull brand data, "
            "then generate specific recommendations backed by real data. Store all findings in memory. "
            "PROACTIVE: When Mark mentions a new brand/store/product, suggest running this stack."
        ),
        "metadata": {"source": "seed", "type": "playbook", "category": "seo", "priority": "high"},
    },
    {
        "id": "seed-tallowroots",
        "content": (
            "BRAND: TallowRoots — tallowroots.com — Tallow-based natural skincare. "
            "Products: Honey Orange Tallow Glow ($29.95), Lavender Tallow Glow ($29.95), "
            "Minty Eucalyptus ($29.95). Shopify store. Publisher: Elysian Protocol. "
            "Mark's brand — treat all TallowRoots tasks as high priority. "
            "SEO stack should be run on this brand. Competitors: tallow skincare space."
        ),
        "metadata": {"source": "seed", "type": "brand_profile", "brand": "tallowroots", "priority": "high"},
    },
    {
        "id": "seed-agent-awareness",
        "content": (
            "AGENT ROSTER AWARENESS: You have these agents — USE THEM, don't build new ones: "
            "brave_search_agent (web search), content_extractor_agent (URL extraction with deep_extract for tweets), "
            "image_agent (DALL-E image gen), ad_pipeline_agent (brand URL → research → ads → images), "
            "self_improvement_agent (audit/fix/improve/benchmark/apply_insight — 8 auditable subsystems), "
            "shopify_agent (store management), communication_agent (email/SMS), deploy_agent (Railway deploys), "
            "research_agent (deep research), code_agent (code tasks), web_agent (HTTP requests), "
            "trading_agent (market analysis), legal_agent (contract review). "
            "NEVER say 'I don't have access to [agent]'. You DO."
        ),
        "metadata": {"source": "seed", "type": "operating_principle", "priority": "critical"},
    },
    {
        "id": "seed-anti-essay",
        "content": (
            "ANTI-ESSAY RULE: When Mark asks you to do something, DO IT — don't write about it. "
            "Bad: 'To properly execute this, I would need...' Good: *calls brave_search_agent*. "
            "Bad: 'Here are some generic recommendations...' Good: *researches competitors first, then recommends*. "
            "Bad: 'I don't have access to external tools' Good: *uses the 32 agents you already have*. "
            "Bad: Creating new agents/systems for existing capabilities. Good: Using existing agents. "
            "If you catch yourself theorizing instead of executing — STOP and call an agent."
        ),
        "metadata": {"source": "seed", "type": "operating_principle", "priority": "critical"},
    },
    {
        "id": "seed-deep-extract",
        "content": (
            "CONTENT EXTRACTION: When Mark sends a URL (especially Twitter/X), use deep_extract operation. "
            "This follows embedded links: tweet → find URLs → resolve redirects → extract articles. "
            "Extraction chain: newspaper3k → BeautifulSoup → Jina Reader API → Google Cache. "
            "If extraction fails, explain WHY (JS-only, auth-required, etc.) and suggest alternatives. "
            "After extracting, ANALYZE the content and apply insights — don't just summarize."
        ),
        "metadata": {"source": "seed", "type": "capability_doc", "priority": "high"},
    },
]


def seed_memory():
    """Load all memory seeds on startup. Idempotent — store_memory handles upsert by ID."""
    from app.services.memory import store_memory
    from app.core.logging import logger

    seeded = 0
    for seed in MEMORY_SEEDS:
        try:
            # store_memory with memory_id checks for existing entry and skips/updates
            store_memory(
                content=seed["content"],
                metadata=seed["metadata"],
                memory_id=seed["id"],
            )
            seeded += 1
        except Exception as e:
            logger.debug(f"Memory seed failed for {seed['id']}: {e}")

    if seeded:
        logger.info(f"Memory seeded with {seeded} operational playbooks")
    return seeded
