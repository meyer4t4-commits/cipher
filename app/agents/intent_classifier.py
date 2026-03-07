"""
Intent Classifier — Detects when a chat message is an agentic request
and routes it to the correct agent skill.

This is the bridge between Cipher's chat and his execution hands.
When the operator says "deploy this to Railway" in conversation,
Cipher should recognize that as a deploy_agent task, not just
generate text about deployment.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.logging import logger


@dataclass
class AgentIntent:
    """Detected intent from a chat message."""
    is_agentic: bool  # Whether this message requires agent execution
    agent_name: Optional[str] = None  # Which agent to use
    action: Optional[str] = None  # What action to perform
    params: dict = None  # Extracted parameters
    confidence: float = 0.0  # How confident we are (0.0 - 1.0)
    requires_approval: bool = False  # Whether operator must approve
    original_message: str = ""  # The original message

    def __post_init__(self):
        if self.params is None:
            self.params = {}


# Intent patterns: (regex_pattern, agent_name, action, requires_approval, confidence_boost)
INTENT_PATTERNS = [
    # === SHELL AGENT ===
    (r"\b(run|execute|exec)\s+(the\s+)?(command|script|shell|bash|terminal)\b", "shell", "execute_command", True, 0.85),
    (r"\b(run|execute|exec)\s+[a-z/~.]", "shell", "execute_command", True, 0.75),  # bare "run <cmd>"
    (r"\b(install|pip install|npm install|brew install)\s+", "shell", "execute_command", True, 0.80),
    (r"\b(restart|start|stop|kill)\s+(the\s+)?(server|service|process|daemon)\b", "shell", "execute_command", True, 0.85),
    (r"```\s*(bash|sh|shell|zsh)\n", "shell", "execute_command", True, 0.90),

    # === WEB AGENT ===
    (r"\b(fetch|scrape|crawl|get)\s+(the\s+)?(page|website|url|site|data from)\b", "web", "http_request", False, 0.80),
    (r"\b(hit|call|ping)\s+(the\s+)?(api|endpoint|url)\b", "web", "http_request", False, 0.80),
    (r"\bhttps?://\S+", "web", "http_request", False, 0.60),  # Lower confidence for bare URLs
    (r"\b(check|monitor)\s+(the\s+)?(status of|uptime|health)\b", "web", "http_request", False, 0.70),

    # === CODE AGENT ===
    (r"\b(run|execute)\s+(this|the|my)\s+(python|javascript|js|code|script)\b", "code", "execute_python", False, 0.85),
    (r"\b(test|debug|evaluate)\s+(this|the|my)\s+(code|function|script)\b", "code", "execute_python", False, 0.80),
    (r"```\s*(python|py)\n", "code", "execute_python", False, 0.75),
    (r"```\s*(javascript|js|node)\n", "code", "execute_javascript", False, 0.75),

    # === FILE AGENT ===
    (r"\b(read|open|show|cat|view)\s+(the\s+)?(file|contents of)\b", "file", "read_file", False, 0.80),
    (r"\b(write|create|save|make)\s+(a\s+)?(new\s+)?(file|config|script)\b", "file", "write_file", False, 0.80),
    (r"\b(delete|remove|rm)\s+(the\s+)?(file|directory|folder)\b", "file", "delete_file", True, 0.85),
    (r"\b(find|search|locate|grep)\s+(for\s+)?(files?|in\s+files?)\b", "file", "search_files", False, 0.75),
    (r"\b(list|ls)\s+(the\s+)?(files?|directory|folder|contents)\b", "file", "list_directory", False, 0.75),

    # === TRADING AGENT ===
    (r"\b(buy|sell|trade|order)\s+(\d+\s+)?(shares?|stocks?)\b", "trading", "place_order", True, 0.95),
    (r"\b(buy|sell|trade)\s+\$?[A-Z]{1,5}\b", "trading", "place_order", True, 0.90),
    (r"\b(check|get|show|what'?s?)\s+(my\s+)?(portfolio|positions?|holdings?|balance)\b", "trading", "get_portfolio", False, 0.85),
    (r"\b(stock|quote|price|ticker)\s+(for|of|on)\s+\$?[A-Z]{1,5}\b", "trading", "get_quote", False, 0.85),
    (r"\b(analyze|analysis|rsi|macd|sma|ema|vwap)\s+(for|of|on)?\s*\$?[A-Z]{1,5}\b", "trading", "technical_analysis", False, 0.85),
    (r"\b(watchlist|watch list)\b", "trading", "get_watchlist", False, 0.80),
    (r"\b(market|markets)\s+(status|open|close|hours)\b", "trading", "market_status", False, 0.80),

    # === DEPLOY AGENT ===
    (r"\b(deploy|push|ship)\s+(?:(?:this|it|the\s+\w+)\s+)?(?:to|on)\s+(railway|fly|cloud|production|staging)\b", "deploy", "deploy_railway", True, 0.90),
    (r"\b(git\s+)?(commit|push|pull|status|diff|log)\b", "deploy", "git_operation", True, 0.80),
    (r"\b(docker|container)\s+(build|run|stop|ps|logs)\b", "deploy", "docker_operation", True, 0.80),
    (r"\b(set|update|change)\s+(the\s+)?(env|environment)\s*(var|variable)\b", "deploy", "set_env_var", True, 0.85),
    (r"\b(check|get|show)\s+(the\s+)?(deploy|deployment)\s*(logs?|status)\b", "deploy", "get_logs", False, 0.80),

    # === RESEARCH AGENT ===
    (r"\b(research|look up|look into|investigate|find out about)\b", "research", "web_search", False, 0.75),
    (r"\b(search|google|look up)\s+(the web|online|internet)\s+for\b", "research", "web_search", False, 0.85),
    (r"\b(competitor|competitive)\s+(analysis|research|intel)\b", "research", "competitor_analysis", False, 0.85),
    (r"\b(market\s+research|industry\s+analysis|trend\s+analysis)\b", "research", "market_research", False, 0.85),
    (r"\b(latest|recent)\s+(news|articles|updates)\s+(about|on|for)\b", "research", "news_search", False, 0.80),
    (r"\b(fact.?check|verify)\s+(this|that|the claim)\b", "research", "fact_check", False, 0.80),

    # === COMMUNICATION AGENT ===
    (r"\b(send|write|compose|draft)\s+(an?\s+)?(email|mail)\b", "communication", "send_email", True, 0.90),
    (r"\b(read|check|get)\s+(my\s+)?(email|inbox|mail)\b", "communication", "read_email", False, 0.85),
    (r"\b(send|post)\s+(a?\s*)?(message|msg|notification)\s+(to|on|via)\s+(slack|telegram|sms|text)\b", "communication", "send_message", True, 0.90),
    (r"\b(send|push)\s+(a?\s*)?(push\s+)?(notification|alert)\s+(to\s+)?(user|device|everyone|all)\b", "communication", "send_push", True, 0.90),
    (r"\b(notify|alert)\s+(all\s+)?(users|subscribers|everyone)\b", "communication", "send_push_topic", True, 0.85),
    (r"\b(broadcast|announce)\s+(to\s+)?(all|users|subscribers)\b", "communication", "send_push_topic", True, 0.85),

    # === SCHEDULER AGENT ===
    (r"\b(schedule|set up|create)\s+(a\s+)?(task|job|cron|recurring|reminder)\b", "scheduler", "schedule_task", False, 0.80),
    (r"\b(every|at)\s+(\d+\s+)?(hour|minute|day|week|month|morning|night)\b", "scheduler", "schedule_task", False, 0.70),
    (r"\b(cancel|delete|remove)\s+(the\s+)?(scheduled|recurring)\s+(task|job)\b", "scheduler", "cancel_task", False, 0.80),
    (r"\b(list|show)\s+(all\s+)?(scheduled|recurring)\s+(tasks?|jobs?)\b", "scheduler", "list_tasks", False, 0.80),

    # === DATA AGENT ===
    (r"\b(analyze|analysis)\s+(the\s+)?(data|csv|excel|spreadsheet|dataset)\b", "data", "analyze_data", False, 0.85),
    (r"\b(create|make|generate)\s+(a\s+)?(chart|graph|plot|visualization)\b", "data", "create_chart", False, 0.80),
    (r"\b(run|execute)\s+(a\s+)?(sql|query|database)\b", "data", "execute_sql", False, 0.80),
    (r"\b(clean|transform|process)\s+(the\s+)?(data|csv|file)\b", "data", "clean_data", False, 0.80),
    (r"\b(generate|create)\s+(a\s+)?(report)\b", "data", "generate_report", False, 0.75),

    # === MONITOR AGENT ===
    (r"\b(monitor|watch|track)\s+(the\s+)?(server|api|endpoint|service|uptime)\b", "monitor", "start_monitor", False, 0.80),
    (r"\b(set|create)\s+(an?\s+)?(alert|alarm|threshold)\b", "monitor", "set_alert", False, 0.80),
    (r"\b(cost|spending|usage)\s+(report|tracking|breakdown)\b", "monitor", "cost_tracking", False, 0.80),
    (r"\b(how much|what'?s?)\s+(am i|are we)\s+(spending|using)\b", "monitor", "cost_tracking", False, 0.75),

    # === SKILL CREATOR AGENT ===
    (r"\b(create|build|make|add)\s+(a\s+)?(new\s+)?(\w+\s+)?(skill|agent|capability)\b", "skill_creator", "create_skill", True, 0.90),
    (r"\b(list|show|what)\s+(all\s+)?(skills?|agents?|capabilities)\b", "skill_creator", "list_skills", False, 0.75),
    (r"\b(i\s+need|we\s+need|build\s+me)\s+(a\s+)?(\w+)\s+(skill|agent|capability)\b", "skill_creator", "create_skill", True, 0.85),
    (r"\b(create|generate|write)\s+(a\s+)?(standalone\s+)?(script|python\s+script)\b", "skill_creator", "create_script", True, 0.80),

    # === IMAGE AGENT ===
    (r"\b(generate|create|make|draw|render)\s+(an?\s+)?(image|picture|photo|artwork|illustration|logo|icon|banner)\b", "image", "generate_image", False, 0.90),
    (r"\b(generate|create|make)\s+(an?\s+)?(ai\s+)?(image|picture|art)\b", "image", "generate_image", False, 0.90),
    (r"\b(dall.?e|stable\s*diffusion|midjourney|image\s+gen)\b", "image", "generate_image", False, 0.85),
    (r"\b(edit|modify|change)\s+(the\s+)?(image|picture|photo)\b", "image", "edit_image", False, 0.85),
    (r"\b(variation|variations)\s+of\s+(the\s+)?(image|picture|photo)\b", "image", "variation", False, 0.85),
    (r"\b(design|visualize|illustrate)\s+(a\s+)?", "image", "generate_image", False, 0.70),

    # === VIDEO AGENT ===
    (r"\b(generate|create|make|render)\s+(a\s+)?(video|clip|animation|movie|film)\b", "video", "generate_video", False, 0.90),
    (r"\b(text.?to.?video|t2v)\b", "video", "generate_video", False, 0.95),
    (r"\b(image.?to.?video|i2v|animate)\s+(this\s+)?(image|picture|photo)\b", "video", "image_to_video", False, 0.90),
    (r"\b(animate|bring to life)\s+(this|the|my)\s+", "video", "image_to_video", False, 0.80),
    (r"\b(chain|stitch|combine|extend)\s+(the\s+)?(video|clips?|scenes?)\b", "video", "chain_video", False, 0.85),
    (r"\b(long|longer|extended|multi.?scene)\s+(video|clip|animation)\b", "video", "chain_video", False, 0.85),
    (r"\b(runway|kling|hailuo|veo|sora)\b", "video", "generate_video", False, 0.80),
    (r"\b(video\s+of|video\s+showing|video\s+with)\b", "video", "generate_video", False, 0.85),

    # === LEGAL AGENT ===
    (r"\b(patent|prior art|provisional|invention)\b", "legal", "patent_search", False, 0.85),
    (r"\b(file|register|form)\s+(an?\s+)?(llc|corporation|business|company)\b", "legal", "llc_formation", True, 0.90),
    (r"\b(draft|write|create|draw up)\s+(an?\s+)?(contract|agreement|nda|mou|nondisclosure)\b", "legal", "contract_draft", False, 0.90),
    (r"\b(trademark|service mark)\s+(search|check|register|file|available)\b", "legal", "trademark_search", False, 0.85),
    (r"\b(can i trademark|is .+ trademarked)\b", "legal", "trademark_search", False, 0.80),
    (r"\b(legal|law|statute|regulation|case law|precedent|court)\b", "legal", "legal_research", False, 0.70),
    (r"\b(legal requirements?|compliance|regulatory)\s+(for|to|in)\b", "legal", "legal_research", False, 0.80),
    (r"\b(draft|write|create)\s+(an?\s+)?(proposal|grant|application)\b", "legal", "document_generate", False, 0.75),
    (r"\b(llc|incorporate|formation|certificate of formation)\b", "legal", "llc_formation", True, 0.80),
    (r"\b(intellectual property|ip assignment|ip rights)\b", "legal", "contract_draft", False, 0.80),

    # === APEX ARCHITECT AGENT ===
    (r"\b(analyze|audit|review)\s+(this\s+)?(competitor|store|website|shopify|etsy|ecommerce)\b", "apex", "analyze_competitor", False, 0.85),
    (r"\b(analyze\s+)?store\s+(conversion|performance|optimization)\b", "apex", "analyze_store_conversion", False, 0.85),
    (r"\b(create|write|generate)\s+(a\s+)?(product\s+)?listing\b", "apex", "generate_product_listing", False, 0.85),
    (r"\b(plan|create|write|build)\s+(a\s+)?(social\s+content\s+)?calendar\b", "apex", "plan_social_content", False, 0.85),
    (r"\b(write|create|generate|draft)\s+(a\s+)?(social\s+)?(post|caption)\s+(for|on)\s+(instagram|tiktok|facebook|x|twitter)\b", "apex", "generate_social_post", False, 0.85),
    (r"\b(create|write|generate)\s+(an?\s+)?(email\s+)?(sequence|campaign|flow)\b", "apex", "generate_email_sequence", False, 0.85),
    (r"\b(what'?s?\s+)?(trending|viral|hot)\s+(in|for)\b", "apex", "fresh_pulse_check", False, 0.80),
    (r"\b(trend|pulse)\s+(check|report|analysis)\b", "apex", "fresh_pulse_check", False, 0.85),
    (r"\b(create|generate|write)\s+(an?\s+)?(ad|advertisement|ad\s+copy)\b", "apex", "generate_ad_creative", False, 0.85),
    (r"\b(shopify|etsy|ecommerce|store|storefront)\s+(optimization|marketing|strategy)\b", "apex", "analyze_competitor", False, 0.80),
    (r"\b(social\s+)?(media|content|marketing)\s+(strategy|plan|calendar)\b", "apex", "plan_social_content", False, 0.80),

    # === SCOUT AGENT (Expansion Pulse) ===
    (r"\b(scout|find|discover|hunt)\s+(for\s+)?(leads?|targets?|companies|businesses|prospects?)\b", "scout", "scan_industry", False, 0.90),
    (r"\b(scan|search)\s+(the\s+)?(\w+\s+)?(industry|niche|market|sector)\s+(for\s+)?(leads?|targets?|companies)\b", "scout", "scan_industry", False, 0.85),
    (r"\b(find|discover)\s+(\w+\s+)?companies\s+(that|who|with)\s+", "scout", "scan_industry", False, 0.80),
    (r"\b(automation.?poor|low.?tech|outdated)\s+(companies|businesses)\b", "scout", "scan_industry", False, 0.90),
    (r"\b(build|generate|create)\s+(a\s+)?(target|prospect|lead)\s+(list|pipeline)\b", "scout", "build_target_list", False, 0.90),
    (r"\b(score|rate|evaluate)\s+(this\s+)?(lead|prospect|company)\b", "scout", "score_lead", False, 0.85),
    (r"\bexpansion\s+pulse\b", "scout", "scan_industry", False, 0.95),

    # === ANALYST AGENT (Expansion Pulse) ===
    (r"\b(tech|technical)\s+(audit|analysis|stack|review)\s+(of|for|on)\b", "analyst", "audit_tech_stack", False, 0.90),
    (r"\b(audit|analyze)\s+(this\s+)?(company|business|target)\s*(for integration|for automation)?\b", "analyst", "full_audit", False, 0.85),
    (r"\b(full|complete|comprehensive)\s+(audit|analysis)\s+(of|for)\b", "analyst", "full_audit", False, 0.90),
    (r"\b(social\s+media|social)\s+(audit|analysis|presence)\s+(of|for)\b", "analyst", "audit_social", False, 0.85),
    (r"\bseo\s+(audit|analysis|check|health)\b", "analyst", "audit_seo", False, 0.85),
    (r"\b(rank|sort|prioritize)\s+(the\s+)?(audited\s+)?(targets?|companies|prospects?)\b", "analyst", "rank_targets", False, 0.85),
    (r"\b(integration\s+)?suitability\s+(score|report|analysis)\b", "analyst", "full_audit", False, 0.85),

    # === OUTREACH AGENT (Expansion Pulse) ===
    (r"\b(draft|write|create)\s+(a\s+)?(cold|outreach|intro)\s+(email|message)\b", "outreach", "draft_cold_email", False, 0.90),
    (r"\b(draft|write|create)\s+(a\s+)?linkedin\s+(message|connection|request)\b", "outreach", "draft_linkedin_message", False, 0.90),
    (r"\b(draft|write|create|generate)\s+(an?\s+)?(integration\s+)?proposal\s+(for|to)\b", "outreach", "draft_proposal", False, 0.85),
    (r"\b(create|build|set up)\s+(an?\s+)?(outreach|engagement|sales)\s+(sequence|cadence|campaign)\b", "outreach", "create_sequence", False, 0.90),
    (r"\b(outreach|engagement|conversion)\s+(metrics?|tracking|stats?|report)\b", "outreach", "track_engagement", False, 0.85),
    (r"\b(reach out|contact|engage)\s+(this\s+)?(company|target|prospect|lead)\b", "outreach", "create_sequence", True, 0.85),

    # === PROVISIONING AGENT (Expansion Pulse) ===
    (r"\b(provision|onboard|set up|configure)\s+(a?\s*)?(new\s+)?(client|customer|account)\b", "provisioning", "provision_client", True, 0.90),
    (r"\b(generate|create)\s+(a?\s*)?(client\s+)?(config|configuration)\b", "provisioning", "generate_config", True, 0.85),
    (r"\b(generate|create)\s+(a?\s*)?(onboarding|welcome)\s+(doc|guide|package)\b", "provisioning", "generate_onboarding", False, 0.85),
    (r"\b(generate|create|build)\s+(an?\s+)?(activation|deployment)\s+(plan|schedule)\b", "provisioning", "generate_activation_plan", False, 0.85),
    (r"\b(generate|create)\s+(a?\s*)?(training|tutorial)\s+(materials?|guide|docs?)\b", "provisioning", "generate_training", False, 0.85),
    (r"\b(prepare|ready)\s+(the\s+)?(integration|environment|setup)\s+(for|of)\b", "provisioning", "provision_client", True, 0.85),

    # === MARKET PULSE AGENT (Apex Asset Hunter) ===
    (r"\b(scan|search|find|pull)\s+(for\s+)?(listings?|properties|homes|houses)\s+(in|near|around)\b", "market_pulse", "scan_listings", False, 0.90),
    (r"\b(motivated\s+sellers?|distressed\s+properties|pre.?foreclosure|tax\s+liens?)\b", "market_pulse", "scan_motivated_sellers", False, 0.90),
    (r"\b(price\s+drop|price\s+reduced|dom|days\s+on\s+market)\b", "market_pulse", "track_price_drops", False, 0.85),
    (r"\b(foreclosure|sheriff\s+sale|lis\s+pendens|notice\s+of\s+default)\b", "market_pulse", "scan_preforeclosure", False, 0.90),
    (r"\b(real\s+estate|property)\s+(scan|search|listings?)\b", "market_pulse", "scan_listings", False, 0.85),
    (r"\b(zillow|redfin|mls|realtor)\s+(scan|search|listings?|properties)\b", "market_pulse", "scan_listings", False, 0.85),

    # === PROFITABILITY ANALYST AGENT (Apex Asset Hunter) ===
    (r"\b(70\s*%\s*rule|seventy\s+percent\s+rule|mao|maximum\s+allowable\s+offer)\b", "profitability", "calculate_mao", False, 0.95),
    (r"\b(arv|after\s+repair\s+value|comp(arable)?s?\s+analysis)\b", "profitability", "estimate_arv", False, 0.90),
    (r"\b(repair\s+(estimate|costs?|assessment)|rehab\s+(estimate|costs?|budget))\b", "profitability", "assess_repairs", False, 0.90),
    (r"\b(deal\s+analysis|flip\s+analysis|wholesale\s+analysis|property\s+analysis)\b", "profitability", "full_deal_analysis", False, 0.90),
    (r"\b(calculate|compute|run)\s+(the\s+)?(numbers?|profit|roi|margin)\s+(on|for)\b", "profitability", "full_deal_analysis", False, 0.85),
    (r"\b(is\s+this\s+a\s+good\s+deal|should\s+i\s+(buy|offer|flip))\b", "profitability", "full_deal_analysis", False, 0.85),

    # === NEIGHBORHOOD GROWTH AGENT (Apex Asset Hunter) ===
    (r"\b(path\s+of\s+progress|growth\s+zone|up\s+and\s+coming)\b", "neighborhood", "path_of_progress", False, 0.95),
    (r"\b(neighborhood|area|zone)\s+(growth|analysis|trends?|outlook)\b", "neighborhood", "scan_growth_zones", False, 0.85),
    (r"\b(building\s+)?permits?\s+(data|analysis|activity|trends?)\b", "neighborhood", "analyze_permits", False, 0.85),
    (r"\b(census|demographic|population)\s+(data|analysis|trends?)\b", "neighborhood", "census_analysis", False, 0.85),
    (r"\b(gentrification|revitalization|redevelopment)\s+(in|near|around)\b", "neighborhood", "scan_growth_zones", False, 0.85),
    (r"\b(where\s+should\s+i\s+(invest|buy|look)|best\s+area\s+to\s+(invest|buy|flip))\b", "neighborhood", "path_of_progress", False, 0.90),

    # === DEAL FLOW AGENT (Apex Asset Hunter) ===
    (r"\b(daily\s+scan|property\s+scan|deal\s+scan|asset\s+hunt(er)?)\b", "deal_flow", "daily_scan", False, 0.95),
    (r"\b(apex\s+asset\s+hunter|apex\s+pulse|deal\s+flow|deal.?flow)\b", "deal_flow", "daily_scan", False, 0.95),
    (r"\b(high.?upside|daily)\s+(report|shortlist)\b", "deal_flow", "generate_report", False, 0.90),
    (r"\b(investor\s+pdf|wholesale\s+pdf|deal\s+sheet)\b", "deal_flow", "generate_investor_pdf", False, 0.90),
    (r"\b(filter|screen)\s+(the\s+)?(deals?|properties|listings?)\b", "deal_flow", "filter_deals", False, 0.85),
    (r"\b(contact|reach\s+out|inquire|write\s+to)\s+(the\s+)?(seller|owner|agent|listing\s+agent)\b", "deal_flow", "draft_seller_inquiry", True, 0.85),
    (r"\b(run|start|execute)\s+(the\s+)?(property|real\s+estate|house)\s+(pipeline|scan|search)\b", "deal_flow", "daily_scan", False, 0.90),

    # === CHRONOS AGENT (Omni-Savant — Precision Scheduling) ===
    (r"\b(schedule|block\s+off|time\s+block|book)\s+(a\s+)?(meeting|session|call|block|slot)\b", "chronos", "schedule_block", False, 0.90),
    (r"\b(deep\s+work|focus\s+time|protect\s+my|do\s+not\s+disturb|dnd)\b", "chronos", "deep_work_guard", False, 0.90),
    (r"\b(daily\s+plan|plan\s+my\s+day|optimize\s+my\s+schedule|energy.?aware)\b", "chronos", "daily_plan", False, 0.90),
    (r"\b(reschedule|resolve\s+conflict|fix\s+my\s+calendar|calendar\s+conflict)\b", "chronos", "reschedule_conflicts", False, 0.85),
    (r"\b(sync\s+calendar|calendar\s+sync|merge\s+calendar)\b", "chronos", "sync_calendars", False, 0.85),
    (r"\b(when\s+should\s+i|best\s+time\s+to|optimal\s+time)\b", "chronos", "schedule_block", False, 0.80),
    (r"\bchronos\b", "chronos", "daily_plan", False, 0.95),

    # === ARCHIVIST AGENT (Omni-Savant — Contextual Memory / RAG) ===
    (r"\b(remember|recall|what\s+did\s+we|what\s+was\s+the|when\s+did\s+we)\b", "archivist", "recall", False, 0.85),
    (r"\b(search\s+across|cross.?agent|search\s+all\s+agents|find\s+in\s+history)\b", "archivist", "cross_agent_search", False, 0.90),
    (r"\b(index|store|save\s+this|remember\s+this|archive)\s+(this|the|my)?\s*(document|note|conversation|decision)\b", "archivist", "index_document", False, 0.85),
    (r"\b(context\s+brief|brief\s+me|catch\s+me\s+up|what.?s\s+the\s+status\s+of)\b", "archivist", "context_brief", False, 0.85),
    (r"\b(timeline|history\s+of|what\s+happened\s+between|events?\s+from)\b", "archivist", "timeline_query", False, 0.80),
    (r"\barchivist\b", "archivist", "recall", False, 0.95),

    # === SENTINEL AGENT (Omni-Savant — Proactive Alerts) ===
    (r"\b(check\s+my\s+email|scan\s+(my\s+)?inbox|unread\s+emails?|email\s+alerts?)\b", "sentinel", "monitor_email", False, 0.90),
    (r"\b(check\s+my\s+(texts?|sms|messages?)|unread\s+(texts?|sms|messages?))\b", "sentinel", "monitor_sms", False, 0.90),
    (r"\b(alert\s+digest|urgent\s+alerts?|priority\s+alerts?|what.?s\s+urgent)\b", "sentinel", "alert_digest", False, 0.90),
    (r"\b(predict|anticipate|upcoming\s+needs?|what.?s\s+coming\s+up)\b", "sentinel", "predict_needs", False, 0.80),
    (r"\b(draft\s+response|auto.?respond|preemptive\s+response)\b", "sentinel", "auto_respond", True, 0.85),
    (r"\bsentinel\b", "sentinel", "alert_digest", False, 0.95),

    # === SYNTHESIS AGENT (Omni-Savant — Deep Research & Scoping) ===
    (r"\b(deep\s+scope|deep\s+research|deep\s+dive\s+on|research\s+everything\s+about)\b", "synthesis", "deep_scope", False, 0.95),
    (r"\b(executive\s+brief|one.?pager|brief\s+on|briefing\s+on)\b", "synthesis", "executive_brief", False, 0.90),
    (r"\b(compare|comparison|versus|vs\.?|pros?\s+and\s+cons?|which\s+is\s+better)\b", "synthesis", "compare_options", False, 0.80),
    (r"\b(trend|trending|market\s+trend|industry\s+trend|forecast)\b", "synthesis", "trend_analysis", False, 0.80),
    (r"\b(quick\s+intel|quick\s+research|fast\s+lookup|rapid\s+research)\b", "synthesis", "quick_intel", False, 0.85),
    (r"\b(scope\s+out|investigate|look\s+into|dig\s+into)\b", "synthesis", "deep_scope", False, 0.75),
    (r"\bsynthesis\b", "synthesis", "deep_scope", False, 0.95),
]

# Agent name to full agent class name mapping
AGENT_NAME_MAP = {
    "shell": "shell_agent",
    "web": "web_agent",
    "code": "code_agent",
    "file": "file_agent",
    "trading": "trading_agent",
    "deploy": "deploy_agent",
    "research": "research_agent",
    "communication": "communication_agent",
    "scheduler": "scheduler_agent",
    "data": "data_agent",
    "monitor": "monitor_agent",
    "skill_creator": "skill_creator_agent",
    "image": "image_agent",
    "video": "video_agent",
    "legal": "legal_agent",
    "apex": "apex_architect_agent",
    "scout": "scout_agent",
    "analyst": "analyst_agent",
    "outreach": "outreach_agent",
    "provisioning": "provisioning_agent",
    "market_pulse": "market_pulse_agent",
    "profitability": "profitability_analyst_agent",
    "neighborhood": "neighborhood_growth_agent",
    "deal_flow": "deal_flow_agent",
    "chronos": "chronos_agent",
    "archivist": "archivist_agent",
    "sentinel": "sentinel_agent",
    "synthesis": "synthesis_agent",
}


def classify_intent(message: str) -> AgentIntent:
    """
    Classify whether a chat message requires agentic execution
    and route to the correct agent.

    Args:
        message: The operator's chat message

    Returns:
        AgentIntent with classification results
    """
    message_lower = message.lower().strip()

    best_match = AgentIntent(
        is_agentic=False,
        original_message=message,
        confidence=0.0,
    )

    for pattern, agent_short, action, requires_approval, confidence in INTENT_PATTERNS:
        match = re.search(pattern, message_lower)
        if match and confidence > best_match.confidence:
            agent_name = AGENT_NAME_MAP.get(agent_short, agent_short)
            best_match = AgentIntent(
                is_agentic=True,
                agent_name=agent_name,
                action=action,
                params=_extract_params(message, agent_short, action, match),
                confidence=confidence,
                requires_approval=requires_approval,
                original_message=message,
            )

    # Only classify as agentic if confidence is above threshold
    if best_match.confidence < 0.65:
        best_match.is_agentic = False
        best_match.agent_name = None
        best_match.action = None

    if best_match.is_agentic:
        logger.info(
            f"Agentic intent detected: agent={best_match.agent_name}, "
            f"action={best_match.action}, confidence={best_match.confidence:.2f}"
        )

    return best_match


def _extract_params(message: str, agent: str, action: str, match: re.Match) -> dict:
    """
    Extract relevant parameters from the message based on agent and action.
    This is the critical bridge between natural language and structured agent params.

    Args:
        message: Original message
        agent: Agent short name
        action: Detected action
        match: Regex match object

    Returns:
        Dict of extracted parameters
    """
    params = {}

    if agent == "shell":
        # Strategy: try multiple extraction methods, most specific first
        # 1. Code block
        code_match = re.search(r"```(?:bash|sh|shell|zsh)?\n(.*?)```", message, re.DOTALL)
        if code_match:
            params["command"] = code_match.group(1).strip()
        else:
            # 2. Backtick-wrapped command
            cmd_match = re.search(r"`([^`]+)`", message)
            if cmd_match:
                params["command"] = cmd_match.group(1).strip()
            else:
                # 3. Natural language: "run echo hello" → "echo hello"
                # This MUST come before quoted string extraction so we get the full command
                cmd_match = re.search(
                    r"(?:run|execute|exec)\s+(?:the\s+)?(?:command\s+)?(.+?)$",
                    message, re.IGNORECASE
                )
                if cmd_match:
                    params["command"] = cmd_match.group(1).strip()
                else:
                    # 4. Install pattern: "install X" → "pip install X"
                    install_match = re.search(
                        r"\b(pip\s+install|npm\s+install|brew\s+install)\s+(.+?)$",
                        message, re.IGNORECASE
                    )
                    if install_match:
                        params["command"] = f"{install_match.group(1)} {install_match.group(2).strip()}"
                    else:
                        install_match = re.search(r"\binstall\s+(.+?)$", message, re.IGNORECASE)
                        if install_match:
                            params["command"] = f"pip install {install_match.group(1).strip()}"
                        else:
                            # 5. Service control
                            svc_match = re.search(
                                r"\b(restart|start|stop|kill)\s+(?:the\s+)?(server|service|process|daemon)\b",
                                message, re.IGNORECASE
                            )
                            if svc_match:
                                verb = svc_match.group(1).lower()
                                orchid_dir = str(Path.home() / "Desktop" / "orchid")
                                if verb == "restart":
                                    params["command"] = "lsof -ti:8000 | xargs kill -9; sleep 1; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &"
                                    params["cwd"] = orchid_dir
                                elif verb in ("stop", "kill"):
                                    params["command"] = "lsof -ti:8000 | xargs kill -9"
                                elif verb == "start":
                                    params["command"] = "nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &"
                                    params["cwd"] = orchid_dir

    elif agent == "web":
        # Extract URLs
        url_match = re.search(r"https?://\S+", message)
        if url_match:
            params["url"] = url_match.group(0).rstrip(".,;)\"'")
            params["method"] = "GET"
        else:
            # Natural language: "fetch the Google homepage" → construct URL
            domain_match = re.search(r"\b(\w+\.(?:com|org|net|io|dev|ai|co))\b", message, re.IGNORECASE)
            if domain_match:
                params["url"] = f"https://{domain_match.group(1)}"
                params["method"] = "GET"

    elif agent == "code":
        # Detect language from message
        if re.search(r"\b(javascript|js|node)\b", message, re.IGNORECASE):
            params["language"] = "javascript"
        else:
            params["language"] = "python"

        # Extract code from code blocks (highest priority)
        code_match = re.search(r"```(?:python|py|javascript|js|node)?\n(.*?)```", message, re.DOTALL)
        if code_match:
            params["code"] = code_match.group(1).strip()
        else:
            # Single backtick code
            inline_match = re.search(r"`([^`]+)`", message)
            if inline_match:
                params["code"] = inline_match.group(1).strip()
            else:
                # Natural language: "run this python code: print(42)" → "print(42)"
                code_match = re.search(
                    r"(?:run|execute|test|debug)\s+(?:this\s+)?(?:python|javascript|js|my)?\s*(?:code|script)?[:\s]+(.+?)$",
                    message, re.IGNORECASE
                )
                if code_match:
                    params["code"] = code_match.group(1).strip()
                else:
                    # Fallback: everything after "code" or ":"
                    code_match = re.search(r"(?:code|script)\s*[:\s]\s*(.+?)$", message, re.IGNORECASE)
                    if code_match:
                        params["code"] = code_match.group(1).strip()

    elif agent == "file":
        # Extract file paths — multiple strategies
        path_match = re.search(r"`([/~][\w/.%-]+)`", message)
        if not path_match:
            path_match = re.search(r"['\"]([/~][\w/.%-]+)['\"]", message)
        if not path_match:
            path_match = re.search(r"\b([\w/.%-]+\.(?:py|js|ts|txt|json|yaml|yml|md|html|css|sh|toml|cfg|ini|env))\b", message)
        if not path_match:
            path_match = re.search(r"(?:file|path|called|named)\s+([/~\w/.%-]+)", message, re.IGNORECASE)
        if path_match:
            params["path"] = path_match.group(1)

    elif agent == "trading":
        # Extract ticker symbols
        ticker_match = re.findall(r"\$([A-Z]{1,5})\b", message)
        if not ticker_match:
            ticker_match = re.findall(r"\b([A-Z]{1,5})\b", message)
        if ticker_match:
            common_words = {"I", "A", "THE", "AND", "OR", "FOR", "IN", "ON", "TO", "OF",
                            "MY", "ALL", "BUY", "SELL", "GET", "SET", "IS", "IT", "BE",
                            "DO", "AM", "AT", "IF", "SO", "NO", "UP", "HE", "WE", "AN"}
            tickers = [t for t in ticker_match if t not in common_words]
            if tickers:
                params["symbol"] = tickers[0]
                if len(tickers) > 1:
                    params["symbols"] = tickers

        qty_match = re.search(r"(\d+)\s+shares?", message, re.IGNORECASE)
        if qty_match:
            params["quantity"] = int(qty_match.group(1))

        if re.search(r"\bbuy\b", message, re.IGNORECASE):
            params["side"] = "buy"
        elif re.search(r"\bsell\b", message, re.IGNORECASE):
            params["side"] = "sell"

    elif agent == "deploy":
        for platform in ["railway", "fly", "docker", "heroku", "vercel", "aws", "gcp"]:
            if platform in message.lower():
                params["platform"] = platform
                break
        if "platform" not in params:
            params["platform"] = "railway"

    elif agent == "research":
        for pattern in [
            r"(?:research|look up|investigate|find out about|look into)\s+(.+?)(?:\.|$)",
            r"(?:search|google)\s+(?:the web|online|internet|for)\s+(.+?)(?:\.|$)",
            r"(?:latest|recent)\s+(?:news|articles|updates)\s+(?:about|on|for)\s+(.+?)(?:\.|$)",
            r"(?:find)\s+(?:news|info|information)\s+(?:about|on)\s+(.+?)(?:\.|$)",
        ]:
            query_match = re.search(pattern, message, re.IGNORECASE)
            if query_match:
                params["query"] = query_match.group(1).strip()
                break
        if "query" not in params:
            params["query"] = message.strip()

    elif agent == "communication":
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", message)
        if email_match:
            params["to"] = email_match.group(0)
        subject_match = re.search(r"(?:subject|about|regarding)\s+['\"]?(.+?)['\"]?\s*$", message, re.IGNORECASE)
        if subject_match:
            params["subject"] = subject_match.group(1).strip()

    elif agent == "data":
        file_match = re.search(r"[`'\"]?([\w/.-]+\.(?:csv|json|xlsx|xls|tsv|parquet|sqlite|db))[`'\"]?", message, re.IGNORECASE)
        if file_match:
            params["file"] = file_match.group(1)

    elif agent == "scheduler":
        sched_match = re.search(r"\b(?:every|at)\s+(.+?)(?:\s+(?:do|run|execute)|$)", message, re.IGNORECASE)
        if sched_match:
            params["schedule"] = sched_match.group(1).strip()

    elif agent == "monitor":
        target_match = re.search(r"\b(?:monitor|watch|track|check)\s+(?:the\s+)?(.+?)(?:\s+(?:for|and)|$)", message, re.IGNORECASE)
        if target_match:
            params["target"] = target_match.group(1).strip()

    elif agent == "image":
        # Extract the image prompt from natural language
        prompt_patterns = [
            r"(?:generate|create|make|draw|render|design|visualize|illustrate)\s+(?:an?\s+)?(?:image|picture|photo|artwork|illustration|logo|icon|banner)\s+(?:of|showing|depicting|with|that shows)\s+(.+?)(?:\.|$)",
            r"(?:generate|create|make|draw|render)\s+(?:an?\s+)?(?:ai\s+)?(?:image|picture|art)\s+(?:of|showing|depicting|with)\s+(.+?)(?:\.|$)",
            r"(?:generate|create|make|draw|render)\s+(.+?)(?:\s+image|\s+picture|\s+art|\.|$)",
        ]
        for pattern in prompt_patterns:
            prompt_match = re.search(pattern, message, re.IGNORECASE)
            if prompt_match:
                params["prompt"] = prompt_match.group(1).strip()
                break
        if "prompt" not in params:
            params["prompt"] = message.strip()

        # Extract size if mentioned
        size_match = re.search(r"(\d{3,4})\s*[xX×]\s*(\d{3,4})", message)
        if size_match:
            params["size"] = f"{size_match.group(1)}x{size_match.group(2)}"

        # Extract quality
        if re.search(r"\b(hd|high.?def|high.?quality|ultra)\b", message, re.IGNORECASE):
            params["quality"] = "hd"

        # Extract style
        if re.search(r"\bnatural\b", message, re.IGNORECASE):
            params["style"] = "natural"

        # Extract image path for edit/variation
        path_match = re.search(r"[`'\"]?([\w/.-]+\.(?:png|jpg|jpeg|gif|webp))[`'\"]?", message, re.IGNORECASE)
        if path_match:
            params["image_path"] = path_match.group(1)

    elif agent == "video":
        # Extract video prompt
        prompt_patterns = [
            r"(?:generate|create|make|render)\s+(?:a\s+)?(?:video|clip|animation)\s+(?:of|showing|depicting|with|that shows)\s+(.+?)(?:\.|$)",
            r"(?:video\s+of|video\s+showing|video\s+with)\s+(.+?)(?:\.|$)",
            r"(?:generate|create|make)\s+(.+?)(?:\s+video|\s+clip|\s+animation|\.|$)",
        ]
        for pattern in prompt_patterns:
            prompt_match = re.search(pattern, message, re.IGNORECASE)
            if prompt_match:
                params["prompt"] = prompt_match.group(1).strip()
                break
        if "prompt" not in params:
            params["prompt"] = message.strip()

        # Extract duration
        dur_match = re.search(r"(\d+)\s*(?:second|sec|s)\b", message, re.IGNORECASE)
        if dur_match:
            params["duration"] = int(dur_match.group(1))

        # Extract aspect ratio
        ar_match = re.search(r"(\d+:\d+)", message)
        if ar_match:
            params["aspect_ratio"] = ar_match.group(1)

        # Extract model preference
        for model in ["runway", "kling", "hailuo", "veo", "wan", "minimax", "ltx"]:
            if model in message.lower():
                params["model"] = model
                break

        # Extract scenes for chaining
        scene_match = re.findall(r"(?:scene\s*\d*[:\s]+)(.+?)(?=scene\s*\d|$)", message, re.IGNORECASE)
        if scene_match:
            params["scenes"] = [s.strip() for s in scene_match if s.strip()]

        # Extract image path for img2vid
        path_match = re.search(r"[`'\"]?([\w/.-]+\.(?:png|jpg|jpeg|gif|webp))[`'\"]?", message, re.IGNORECASE)
        if path_match:
            params["image_path"] = path_match.group(1)

        # Extract image URL for img2vid
        url_match = re.search(r"(https?://\S+\.(?:png|jpg|jpeg|gif|webp))", message, re.IGNORECASE)
        if url_match:
            params["image_url"] = url_match.group(1)

    elif agent == "skill_creator":
        if action == "create_skill":
            # Extract skill name from natural language
            name_match = re.search(
                r"(?:create|build|make|add)\s+(?:a\s+)?(?:new\s+)?(\w+)\s+(?:skill|agent|capability)",
                message, re.IGNORECASE
            )
            if name_match:
                params["skill_name"] = name_match.group(1).lower()
            # Extract description — everything after "that" or "which" or "to"
            desc_match = re.search(
                r"(?:that|which|to)\s+(.+?)(?:\.|$)",
                message, re.IGNORECASE
            )
            if desc_match:
                params["description"] = desc_match.group(1).strip()
            elif "skill_name" in params:
                params["description"] = f"{params['skill_name']} agent skill"
        elif action == "create_script":
            # Extract script name
            script_match = re.search(r"(?:called|named)\s+['\"]?(\w+\.py)['\"]?", message, re.IGNORECASE)
            if script_match:
                params["script_name"] = script_match.group(1)
            # Extract code from code blocks
            code_match = re.search(r"```(?:python|py)?\n(.*?)```", message, re.DOTALL)
            if code_match:
                params["code"] = code_match.group(1).strip()

    elif agent == "apex":
        params["operation"] = action  # analyze_competitor, generate_product_listing, etc.

        if action == "analyze_competitor":
            # Extract URL if present
            url_match = re.search(r"https?://\S+", message)
            if url_match:
                params["url"] = url_match.group(0).rstrip(".,;)\"'")
            # Extract niche keyword
            niche_match = re.search(r"(?:in|for|about)\s+(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:niche|space|market)", message, re.IGNORECASE)
            if niche_match:
                params["niche"] = niche_match.group(1).strip()
            elif not url_match:
                # Use the remaining message as niche
                params["niche"] = message.strip()

        elif action == "generate_product_listing":
            # Extract product name
            name_match = re.search(r"(?:for|listing\s+for)\s+['\"]?(.+?)['\"]?(?:\s+with|\s+including|\.|$)", message, re.IGNORECASE)
            if name_match:
                params["product_name"] = name_match.group(1).strip()
            # Extract description
            desc_match = re.search(r"(?:description|about)[:\s]+(.+?)(?:\.|$)", message, re.IGNORECASE)
            if desc_match:
                params["description"] = desc_match.group(1).strip()
            # Extract target audience
            audience_match = re.search(r"(?:for|targeting)\s+(.+?)(?:\.|$)", message, re.IGNORECASE)
            if audience_match:
                params["target_audience"] = audience_match.group(1).strip()

        elif action == "plan_social_content":
            # Extract brand name
            brand_match = re.search(r"(?:for|brand)\s+['\"]?([A-Z][a-zA-Z\s]+?)['\"]?(?:\s+for|on|across|\.|$)", message, re.IGNORECASE)
            if brand_match:
                params["brand_name"] = brand_match.group(1).strip()
            # Extract platforms
            platforms = []
            for platform in ["instagram", "tiktok", "facebook", "x", "twitter", "pinterest", "linkedin"]:
                if platform in message.lower():
                    if platform == "x":
                        platforms.append("twitter")
                    else:
                        platforms.append(platform)
            if platforms:
                params["platforms"] = list(set(platforms))
            # Extract duration
            dur_match = re.search(r"(\d+)\s*(?:day|week|month)", message, re.IGNORECASE)
            if dur_match:
                params["duration_days"] = int(dur_match.group(1))

        elif action == "generate_social_post":
            # Extract platform
            for platform in ["instagram", "tiktok", "facebook", "linkedin", "twitter", "x"]:
                if platform in message.lower() or (platform == "x" and "twitter" in message.lower()):
                    params["platform"] = platform if platform != "x" else "twitter"
                    break
            # Extract content type
            for ctype in ["reel", "carousel", "story", "video", "post", "static"]:
                if ctype in message.lower():
                    params["content_type"] = ctype
                    break
            # Extract topic
            topic_match = re.search(r"(?:about|topic|subject)[:\s]+(.+?)(?:\.|$)", message, re.IGNORECASE)
            if topic_match:
                params["topic"] = topic_match.group(1).strip()

        elif action == "analyze_store_conversion":
            # Extract store URL
            url_match = re.search(r"https?://\S+", message)
            if url_match:
                params["store_url"] = url_match.group(0).rstrip(".,;)\"'")
            # Detect store type
            if "shopify" in message.lower():
                params["store_type"] = "shopify"
            elif "etsy" in message.lower():
                params["store_type"] = "etsy"
            else:
                params["store_type"] = "shopify"

        elif action == "generate_email_sequence":
            # Extract trigger
            for trigger in ["welcome", "abandoned cart", "post-purchase", "win-back", "wholesale"]:
                if trigger.replace(" ", "-") in message.lower() or trigger in message.lower():
                    params["trigger"] = trigger.replace(" ", "_")
                    break
            if "trigger" not in params:
                params["trigger"] = "welcome"
            # Extract brand name
            brand_match = re.search(r"(?:for|brand)\s+['\"]?([A-Z][a-zA-Z\s]+?)['\"]?(?:\.|$)", message, re.IGNORECASE)
            if brand_match:
                params["brand_name"] = brand_match.group(1).strip()

        elif action == "fresh_pulse_check":
            # Extract niche
            niche_match = re.search(r"(?:in|for|about)\s+(?:the\s+)?([\w\s]+?)(?:\s+niche|market|\.|$)", message, re.IGNORECASE)
            if niche_match:
                params["niche"] = niche_match.group(1).strip()
            else:
                params["niche"] = message.strip()

        elif action == "generate_ad_creative":
            # Extract product
            product_match = re.search(r"(?:for|product)\s+['\"]?(.+?)['\"]?(?:\s+on|for|using|\.|$)", message, re.IGNORECASE)
            if product_match:
                params["product"] = product_match.group(1).strip()
            # Extract platform
            for platform in ["facebook", "instagram", "tiktok"]:
                if platform in message.lower():
                    params["platform"] = platform
                    break
            # Extract budget
            if "small" in message.lower() or "low" in message.lower():
                params["budget_level"] = "small"
            elif "large" in message.lower() or "high" in message.lower():
                params["budget_level"] = "large"
            else:
                params["budget_level"] = "medium"

    elif agent == "legal":
        params["operation"] = action  # patent_search, contract_draft, etc.

        if action == "patent_search":
            # Extract invention description
            for pattern in [
                r"(?:patent|prior art|search for patents?)\s+(?:for|on|about|related to)\s+(.+?)(?:\.|$)",
                r"(?:invention|invented|created)\s+(.+?)(?:\.|$)",
            ]:
                q_match = re.search(pattern, message, re.IGNORECASE)
                if q_match:
                    params["query"] = q_match.group(1).strip()
                    break
            if "query" not in params:
                params["query"] = message.strip()

        elif action == "contract_draft":
            # Detect contract type
            type_map = {
                "nda": "nda", "non-disclosure": "nda", "nondisclosure": "nda",
                "mutual nda": "mutual_nda",
                "service agreement": "service_agreement", "service contract": "service_agreement",
                "consulting": "consulting", "consultant": "consulting",
                "partnership": "partnership", "partner": "partnership",
                "licensing": "licensing", "license": "licensing",
                "ip assignment": "ip_assignment", "intellectual property": "ip_assignment",
                "employment": "employment", "employee": "employment",
                "vendor": "vendor", "supplier": "vendor",
            }
            for keyword, ctype in type_map.items():
                if keyword in message.lower():
                    params["contract_type"] = ctype
                    break
            if "contract_type" not in params:
                params["contract_type"] = "nda"

            # Extract party names: "between X and Y"
            party_match = re.search(r"between\s+(.+?)\s+and\s+(.+?)(?:\s+for|\s+regarding|\.|$)", message, re.IGNORECASE)
            if party_match:
                params["party_a"] = party_match.group(1).strip()
                params["party_b"] = party_match.group(2).strip()
            else:
                # Try "with X"
                with_match = re.search(r"(?:with|for)\s+([A-Z][a-zA-Z\s]+?)(?:\.|$)", message)
                if with_match:
                    params["party_b"] = with_match.group(1).strip()

        elif action == "llc_formation":
            # Extract company name
            name_match = re.search(r"(?:register|form|create|file)\s+(.+?)\s+(?:as|in|llc|corporation)", message, re.IGNORECASE)
            if name_match:
                params["company_name"] = name_match.group(1).strip()
            # Extract state
            if "delaware" in message.lower() or " de " in message.lower():
                params["state"] = "DE"
            else:
                params["state"] = "NJ"

        elif action == "trademark_search":
            # Extract the mark to search
            mark_match = re.search(r"(?:trademark|service mark)\s+(?:search|check|for|register)?\s*['\"]?(.+?)['\"]?(?:\?|\.|$)", message, re.IGNORECASE)
            if not mark_match:
                mark_match = re.search(r"(?:can i trademark|is)\s+['\"]?(.+?)['\"]?\s+(?:trademarked|available)", message, re.IGNORECASE)
            if mark_match:
                params["mark"] = mark_match.group(1).strip()

        elif action == "legal_research":
            # Extract the legal question
            for pattern in [
                r"(?:legal|law|statute|regulation|requirement|compliance)\s+(?:for|to|about|regarding|on)\s+(.+?)(?:\?|\.|$)",
                r"(?:what are the|what is the)\s+(.+?)(?:\?|\.|$)",
            ]:
                q_match = re.search(pattern, message, re.IGNORECASE)
                if q_match:
                    params["query"] = q_match.group(1).strip()
                    break
            if "query" not in params:
                params["query"] = message.strip()

        elif action == "document_generate":
            # Extract document type and title
            doc_match = re.search(r"(?:draft|write|create)\s+(?:a\s+)?(.+?)(?:\s+for|\s+about|\.|$)", message, re.IGNORECASE)
            if doc_match:
                params["title"] = doc_match.group(1).strip()

    elif agent == "scout":
        params["operation"] = action

        if action == "scan_industry":
            # Extract industry
            industry_match = re.search(r"(?:in|for|the)\s+(\w+(?:\s+\w+)?)\s+(?:industry|niche|market|sector|space)", message, re.IGNORECASE)
            if industry_match:
                params["industry"] = industry_match.group(1).strip()
            else:
                # Try to extract from natural language
                ind_match = re.search(r"(?:find|scout|discover|scan)\s+(?:for\s+)?(?:leads?\s+)?(?:in\s+)?(.+?)(?:\s+companies|\s+businesses|\.|$)", message, re.IGNORECASE)
                if ind_match:
                    params["industry"] = ind_match.group(1).strip()
            # Extract location
            loc_match = re.search(r"(?:in|near|around)\s+([\w\s,]+?)(?:\s+that|\s+with|\.|$)", message, re.IGNORECASE)
            if loc_match and "industry" not in loc_match.group(1).lower():
                params["location"] = loc_match.group(1).strip()

        elif action in ("scan_company", "score_lead"):
            # Extract company name
            company_match = re.search(r"(?:scan|score|rate|evaluate)\s+(?:this\s+)?(?:company\s+)?['\"]?(.+?)['\"]?(?:\s+for|\.|$)", message, re.IGNORECASE)
            if company_match:
                params["company"] = company_match.group(1).strip()
            # Extract URL
            url_match = re.search(r"https?://\S+", message)
            if url_match:
                params["url"] = url_match.group(0).rstrip(".,;)\"'")

    elif agent == "analyst":
        params["operation"] = action

        # Extract company/url for all analyst operations
        company_match = re.search(r"(?:of|for|on)\s+['\"]?([A-Z][\w\s]+?)['\"]?(?:\s+for|\.|$)", message)
        if company_match:
            params["company"] = company_match.group(1).strip()
        url_match = re.search(r"https?://\S+", message)
        if url_match:
            params["url"] = url_match.group(0).rstrip(".,;)\"'")
        # Extract top_n for rank_targets
        if action == "rank_targets":
            n_match = re.search(r"(?:top|best|first)\s+(\d+)", message, re.IGNORECASE)
            if n_match:
                params["top_n"] = int(n_match.group(1))

    elif agent == "outreach":
        params["operation"] = action

        # Extract company
        company_match = re.search(r"(?:for|to|at)\s+['\"]?([A-Z][\w\s]+?)['\"]?(?:\s+about|\.|$)", message)
        if company_match:
            params["company"] = company_match.group(1).strip()
        # Extract contact name
        contact_match = re.search(r"(?:to|contact|for)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)", message)
        if contact_match:
            params["contact_name"] = contact_match.group(1).strip()
        # Extract email
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", message)
        if email_match:
            params["contact_email"] = email_match.group(0)

    elif agent == "provisioning":
        params["operation"] = action

        # Extract company
        company_match = re.search(r"(?:for|client|customer)\s+['\"]?([A-Z][\w\s]+?)['\"]?(?:\s+on|\s+with|\.|$)", message)
        if company_match:
            params["company"] = company_match.group(1).strip()
        # Extract tier
        for tier_name in ["enterprise", "business", "pro", "free"]:
            if tier_name in message.lower():
                params["tier"] = tier_name
                break
        # Extract contact
        contact_match = re.search(r"(?:contact|for)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)", message)
        if contact_match:
            params["contact_name"] = contact_match.group(1).strip()
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", message)
        if email_match:
            params["contact_email"] = email_match.group(0)

    elif agent == "market_pulse":
        params["operation"] = action

        # Extract city/state
        city_state = re.search(r"(?:in|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*([A-Z]{2})", message)
        if city_state:
            params["city"] = city_state.group(1).strip()
            params["state"] = city_state.group(2).strip()
        # Extract county
        county_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Cc]ounty", message)
        if county_match:
            params["county"] = county_match.group(1).strip()
        # Extract max price
        price_match = re.search(r"\$?([\d,]+)(?:k)?", message)
        if price_match:
            raw = price_match.group(1).replace(",", "")
            try:
                val = int(raw)
                if val < 1000:
                    val *= 1000
                params["max_price"] = val
            except ValueError:
                pass
        # Extract zip
        zip_match = re.search(r"\b(\d{5})\b", message)
        if zip_match:
            params["zip_code"] = zip_match.group(1)

    elif agent == "profitability":
        params["operation"] = action

        # Extract address
        addr_match = re.search(r"(\d+\s+[A-Z][a-z]+(?:\s+[A-Za-z]+){1,4}(?:\s+(?:St|Ave|Blvd|Dr|Rd|Ln|Way|Ct|Pl|Cir)))", message)
        if addr_match:
            params["address"] = addr_match.group(1).strip()
        # Extract dollar amounts (ARV, repair, price)
        dollar_matches = re.findall(r"\$?([\d,]+)(?:k)?", message)
        if dollar_matches:
            values = []
            for d in dollar_matches:
                try:
                    val = int(d.replace(",", ""))
                    if val < 1000:
                        val *= 1000
                    values.append(val)
                except ValueError:
                    pass
            if action == "calculate_mao" and len(values) >= 2:
                params["arv"] = values[0]
                params["repair_costs"] = values[1]
            elif action == "full_deal_analysis" and values:
                params["asking_price"] = values[0]
        # Extract beds/baths/sqft
        bed_match = re.search(r"(\d+)\s*(?:bed|br|bd)", message, re.IGNORECASE)
        if bed_match:
            params["beds"] = int(bed_match.group(1))
        sqft_match = re.search(r"([\d,]+)\s*(?:sq\s*ft|sqft)", message, re.IGNORECASE)
        if sqft_match:
            params["sqft"] = int(sqft_match.group(1).replace(",", ""))

    elif agent == "neighborhood":
        params["operation"] = action

        # Extract city/state
        city_state = re.search(r"(?:in|near|around|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*([A-Z]{2})", message)
        if city_state:
            params["city"] = city_state.group(1).strip()
            params["state"] = city_state.group(2).strip()
        # Extract county
        county_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Cc]ounty", message)
        if county_match:
            params["county"] = county_match.group(1).strip()
        # Extract zip
        zip_match = re.search(r"\b(\d{5})\b", message)
        if zip_match:
            params["zip_code"] = zip_match.group(1)

    elif agent == "chronos":
        params["operation"] = action
        # Extract event name
        event_match = re.search(r"(?:schedule|block|book)\s+(?:a\s+)?(?:meeting|session|call|block)?\s*(?:for|called|named|about)?\s*['\"]?([^'\"]+?)['\"]?\s*(?:at|on|for|from|$)", message, re.IGNORECASE)
        if event_match:
            params["event_name"] = event_match.group(1).strip()
        # Extract duration
        dur_match = re.search(r"(\d+)\s*(?:min(?:ute)?s?|hrs?|hours?)", message, re.IGNORECASE)
        if dur_match:
            val = int(dur_match.group(1))
            if "hour" in message.lower() or "hr" in message.lower():
                val *= 60
            params["duration_minutes"] = val
        # Extract task type
        for ttype in ["coding", "meeting", "email", "research", "creative", "admin", "planning", "review"]:
            if ttype in message.lower():
                params["task_type"] = ttype
                break

    elif agent == "archivist":
        params["operation"] = action
        # Extract query
        query_match = re.search(r"(?:recall|remember|search|find|what\s+was|what\s+did)\s+(?:the\s+|about\s+|for\s+)?(.+?)(?:\?|$)", message, re.IGNORECASE)
        if query_match:
            params["query"] = query_match.group(1).strip()
        # Extract date range for timeline
        date_match = re.search(r"(?:from|between|since)\s+(\d{4}-\d{2}-\d{2})", message)
        if date_match:
            params["start_date"] = date_match.group(1)
        end_match = re.search(r"(?:to|until|through)\s+(\d{4}-\d{2}-\d{2})", message)
        if end_match:
            params["end_date"] = end_match.group(1)
        # Extract topic for context brief
        topic_match = re.search(r"(?:brief\s+(?:me\s+)?on|status\s+of|catch\s+me\s+up\s+on)\s+(.+?)(?:\?|$)", message, re.IGNORECASE)
        if topic_match:
            params["topic"] = topic_match.group(1).strip()

    elif agent == "sentinel":
        params["operation"] = action
        # Extract time range for digest
        if re.search(r"\btoday\b", message, re.IGNORECASE):
            params["timeframe"] = "today"
        elif re.search(r"\bthis\s+week\b", message, re.IGNORECASE):
            params["timeframe"] = "week"
        elif re.search(r"\blast\s+(\d+)\s+hours?\b", message, re.IGNORECASE):
            h_match = re.search(r"\blast\s+(\d+)\s+hours?\b", message, re.IGNORECASE)
            params["timeframe_hours"] = int(h_match.group(1))

    elif agent == "synthesis":
        params["operation"] = action
        # Extract topic
        topic_match = re.search(r"(?:research|scope|brief|compare|trend|investigate|look\s+into|dig\s+into)\s+(?:on\s+|about\s+|for\s+|everything\s+about\s+)?(.+?)(?:\?|$)", message, re.IGNORECASE)
        if topic_match:
            params["topic"] = topic_match.group(1).strip()
        # Extract depth
        if re.search(r"\b(exhaustive|thorough|comprehensive|deep)\b", message, re.IGNORECASE):
            params["depth"] = "exhaustive"
        elif re.search(r"\b(quick|fast|rapid|brief)\b", message, re.IGNORECASE):
            params["depth"] = "shallow"
        # Extract comparison options
        vs_match = re.search(r"(.+?)\s+(?:vs\.?|versus|or|compared?\s+to)\s+(.+?)(?:\?|$)", message, re.IGNORECASE)
        if vs_match:
            params["options"] = [vs_match.group(1).strip(), vs_match.group(2).strip()]

    elif agent == "deal_flow":
        params["operation"] = action

        # Extract city/state
        city_state = re.search(r"(?:in|near|around|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*([A-Z]{2})", message)
        if city_state:
            params["city"] = city_state.group(1).strip()
            params["state"] = city_state.group(2).strip()
        # Extract county
        county_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Cc]ounty", message)
        if county_match:
            params["county"] = county_match.group(1).strip()
        # Extract min margin
        margin_match = re.search(r"(?:margin|profit|minimum)\s*(?:of\s*)?\$?([\d,]+)(?:k)?", message, re.IGNORECASE)
        if margin_match:
            raw = margin_match.group(1).replace(",", "")
            try:
                val = int(raw)
                if val < 1000:
                    val *= 1000
                params["min_margin"] = val
            except ValueError:
                pass
        # Extract max price
        price_match = re.search(r"(?:under|below|max|up to)\s*\$?([\d,]+)(?:k)?", message, re.IGNORECASE)
        if price_match:
            raw = price_match.group(1).replace(",", "")
            try:
                val = int(raw)
                if val < 1000:
                    val *= 1000
                params["max_price"] = val
            except ValueError:
                pass
        # Extract address for seller inquiry
        if action == "draft_seller_inquiry":
            addr_match = re.search(r"(\d+\s+[A-Z][a-z]+(?:\s+[A-Za-z]+){1,4})", message)
            if addr_match:
                params["address"] = addr_match.group(1).strip()

    return params


def get_agent_for_intent(intent: AgentIntent) -> Optional[str]:
    """
    Get the full agent name for a detected intent.

    Args:
        intent: The classified intent

    Returns:
        Full agent name or None
    """
    if not intent.is_agentic:
        return None
    return intent.agent_name
