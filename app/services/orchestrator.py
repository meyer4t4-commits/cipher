"""
Orchestrator - The conductor of Cipher.
Ties together LLM routing, memory, conversation history, agent invocation,
and hallucination-proof response generation.

KEY PRINCIPLE: When a user asks for FACTUAL DATA (prices, news, weather, etc.),
we NEVER let the LLM hallucinate. We detect the data need, invoke the real agent,
get real data, and inject it into context so the LLM formats a response WITH facts.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import ConversationRecord, MessageRecord, UsageLog
from app.models.schemas import ChatRequest, ChatResponse, ImageAttachment, ModelTier, RecommendedAgentInfo
from app.services.llm_router import chat_completion, chat_completion_with_tools
from app.services.memory import recall_memories, store_conversation_context
from app.services.classifier import auto_classify
from app.services.cache import get_cached_response, cache_response
from app.services.voice_personalities import get_personality_manager
from app.services.tool_calling import CIPHER_TOOLS, execute_tool
from app.services.vision_service import analyze_images, build_vision_messages
from app.services.fact_checker import validate_response
from app.agents.models import AgentSignal, RiskLevel, SignalDirection

# Import the comprehensive system prompt from the dedicated module
from app.core.system_prompt import CIPHER_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# deCIPHER: Lightweight spelling normalization for keyword matching
# ---------------------------------------------------------------------------

_COMMON_CORRECTIONS = {
    "analize": "analyze", "anlyze": "analyze", "analze": "analyze",
    "proptery": "property", "proprty": "property", "proeprty": "property",
    "servar": "server", "servr": "server",
    "marekt": "market", "makret": "market", "maket": "market",
    "schdule": "schedule", "shedule": "schedule", "schedle": "schedule",
    "deploiy": "deploy", "deplyo": "deploy",
    "moniter": "monitor", "monitr": "monitor",
    "reserch": "research", "resarch": "research", "reasearch": "research",
    "teh": "the", "waht": "what", "taht": "that", "wiht": "with",
    "abuot": "about", "abotu": "about",
    "becuase": "because", "becasue": "because",
    "recieve": "receive", "recive": "receive",
    "seperate": "separate", "definately": "definitely",
    "enviornment": "environment", "enviroment": "environment",
    "rn": "right now", "tmrw": "tomorrow", "govt": "government",
    "prop": "property", "props": "properties", "biz": "business",
    "msg": "message", "msgs": "messages", "pls": "please", "plz": "please",
    # Stock ticker shortcuts
    "tsla": "TSLA", "aapl": "AAPL", "goog": "GOOG", "amzn": "AMZN",
    "msft": "MSFT", "nvda": "NVDA", "meta": "META", "btc": "BTC",
    "eth": "ETH", "spy": "SPY",
}

_CORRECTION_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in _COMMON_CORRECTIONS) + r')\b',
    re.IGNORECASE,
)


def _normalize_for_matching(text: str) -> str:
    """Lightweight spelling normalization for keyword matching only."""
    def _replace(match):
        key = match.group(0).lower()
        return _COMMON_CORRECTIONS.get(key, match.group(0))
    return _CORRECTION_PATTERN.sub(_replace, text)


# ---------------------------------------------------------------------------
# DATA QUERY DETECTION — identifies when we MUST use real agents
# If any of these match, we force agent execution BEFORE the LLM responds.
# This prevents hallucinated stock prices, fake news, made-up weather, etc.
# ---------------------------------------------------------------------------

_STOCK_PATTERN = re.compile(
    r'\b(?:price|quote|trading|stock|share|ticker|market cap|pe ratio|p/e)\b'
    r'|'
    r'\b(?:how much is|what(?:\'?s| is))\b.*\b(?:at|trading|worth|price)\b'
    r'|'
    r'\$[A-Z]{1,5}\b'
    r'|'
    r'\b(?:TSLA|AAPL|GOOG|GOOGL|AMZN|MSFT|NVDA|META|NFLX|AMD|INTC|BA|DIS|JPM|V|WMT|BTC|ETH|SOL|XRP|DOGE|SPY|QQQ|IWM|VTI)\b',
    re.IGNORECASE,
)

_NEWS_PATTERN = re.compile(
    r'\b(?:latest news|breaking news|what(?:\'?s| is) happening|current events|today(?:\'?s)? news|headlines)\b'
    r'|'
    r'\b(?:did .+ (?:announce|release|launch|acquire|merge|IPO|resign|fire))\b',
    re.IGNORECASE,
)

_SEARCH_PATTERN = re.compile(
    r'\b(?:search for|look up|find me|google|what is the current|latest data on)\b'
    r'|'
    r'\b(?:how (?:much|many|long|far|old)|when (?:is|was|did|does)|where (?:is|can))\b.*\b(?:today|now|currently|right now|2025|2026)\b',
    re.IGNORECASE,
)


async def _fetch_live_stock_data(message: str) -> Optional[str]:
    """
    Extract stock symbols from message and fetch REAL prices via yfinance.
    Returns formatted data string to inject into LLM context.
    """
    try:
        # Extract potential tickers — uppercase 1-5 letter words
        ticker_pattern = re.compile(r'\b([A-Z]{1,5})\b')
        normalized = _normalize_for_matching(message)
        potential_tickers = ticker_pattern.findall(normalized.upper())

        # Known tickers to check against
        known_tickers = {
            "TSLA", "AAPL", "GOOG", "GOOGL", "AMZN", "MSFT", "NVDA", "META",
            "NFLX", "AMD", "INTC", "BA", "DIS", "JPM", "V", "WMT", "PYPL",
            "CRM", "UBER", "ABNB", "COIN", "SQ", "SNAP", "RIVN", "LCID",
            "PLTR", "SOFI", "NIO", "LI", "XPEV", "F", "GM", "T", "VZ",
            "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "DOT", "AVAX",
            "SPY", "QQQ", "IWM", "VTI", "VOO", "DIA",
        }

        # Also try to extract from common patterns like "tesla" → TSLA
        name_to_ticker = {
            "tesla": "TSLA", "apple": "AAPL", "google": "GOOG",
            "amazon": "AMZN", "microsoft": "MSFT", "nvidia": "NVDA",
            "meta": "META", "netflix": "NFLX", "bitcoin": "BTC-USD",
            "ethereum": "ETH-USD", "solana": "SOL-USD", "dogecoin": "DOGE-USD",
            "xrp": "XRP-USD", "sp500": "SPY", "s&p": "SPY", "dow": "DIA",
            "nasdaq": "QQQ",
        }

        symbols = set()
        msg_lower = message.lower()
        for name, ticker in name_to_ticker.items():
            if name in msg_lower:
                symbols.add(ticker)

        for t in potential_tickers:
            if t in known_tickers:
                # Crypto tickers need -USD suffix for yfinance
                if t in {"BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "DOT", "AVAX"}:
                    symbols.add(f"{t}-USD")
                else:
                    symbols.add(t)

        if not symbols:
            return None

        import yfinance as yf

        data_parts = []
        for symbol in list(symbols)[:5]:  # Max 5 tickers
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2d")
                if hist.empty:
                    continue
                current_price = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
                change = current_price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0
                direction = "+" if change >= 0 else ""

                info = ticker.fast_info
                market_cap = getattr(info, "market_cap", None)
                cap_str = ""
                if market_cap:
                    if market_cap >= 1e12:
                        cap_str = f" | Market Cap: ${market_cap/1e12:.2f}T"
                    elif market_cap >= 1e9:
                        cap_str = f" | Market Cap: ${market_cap/1e9:.2f}B"

                high = float(hist["High"].iloc[-1]) if "High" in hist else 0
                low = float(hist["Low"].iloc[-1]) if "Low" in hist else 0
                vol = int(hist["Volume"].iloc[-1]) if "Volume" in hist else 0

                data_parts.append(
                    f"{symbol}: ${current_price:.2f} ({direction}{change:.2f}, {direction}{change_pct:.1f}%)"
                    f" | Day Range: ${low:.2f}-${high:.2f} | Vol: {vol:,}{cap_str}"
                )
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
                continue

        if not data_parts:
            return None

        return (
            "\n\n[LIVE MARKET DATA — fetched in real-time via yfinance, DO NOT override with training data]\n"
            + "\n".join(data_parts)
            + "\n[Use ONLY these numbers in your response. NEVER substitute with memorized prices.]\n"
        )
    except ImportError:
        logger.warning("yfinance not installed — stock data unavailable")
        return None
    except Exception as e:
        logger.error(f"Stock data fetch error: {e}")
        return None


async def _fetch_live_search_data(message: str) -> Optional[str]:
    """
    Run a real web search via Brave Search API and return results.
    Used when the user asks about current events, news, or real-time info.
    """
    try:
        import os
        import httpx

        api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
        if not api_key:
            logger.warning("Brave Search API key not available for live search")
            return None

        # Build a focused search query from the message
        query = message.strip()
        if len(query) > 200:
            query = query[:200]

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5, "freshness": "pw"},  # past week
                headers={
                    "X-Subscription-Token": api_key,
                    "Accept": "application/json",
                },
            )
            if resp.status_code != 200:
                logger.warning(f"Brave Search returned {resp.status_code}")
                return None

            data = resp.json()
            results = data.get("web", {}).get("results", [])
            if not results:
                return None

            parts = []
            for r in results[:5]:
                title = r.get("title", "")
                snippet = r.get("description", "")
                url = r.get("url", "")
                age = r.get("age", "")
                age_str = f" ({age})" if age else ""
                parts.append(f"- {title}{age_str}: {snippet}")

            return (
                "\n\n[LIVE SEARCH RESULTS — real-time data from Brave Search API]\n"
                + "\n".join(parts)
                + "\n[Base your response on these real results. NEVER fabricate information.]\n"
            )
    except Exception as e:
        logger.error(f"Live search error: {e}")
        return None


# ---------------------------------------------------------------------------
# HALLUCINATION GUARD — added to system prompt for every response
# ---------------------------------------------------------------------------

HALLUCINATION_GUARD = """

ANTI-HALLUCINATION PROTOCOL — ABSOLUTE RULE:

You have access to real-time data through your agents. When LIVE DATA is injected into your context (marked with [LIVE MARKET DATA] or [LIVE SEARCH RESULTS]), you MUST:
1. Use ONLY the provided numbers, facts, and sources — never substitute with your training data
2. If the data says Tesla is $412.50, you say Tesla is $412.50 — NOT whatever you "remember"
3. If you don't have live data and aren't sure of a fact, say "Let me check that" and recommend deploying an agent
4. NEVER state a specific price, statistic, or current fact without live data backing it
5. For stock prices, crypto, market data: ALWAYS use the injected yfinance data
6. For current events, news: ALWAYS use the injected search results
7. If no live data is available for a factual question, explicitly say you need to verify it rather than guessing

WHAT TO NEVER DO:
- Never state a stock price from memory — it WILL be wrong
- Never claim "as of my last update" — you have REAL-TIME access, use it
- Never approximate or estimate factual data points
- Never present LLM training data as current facts
- Never write bash/curl scripts for tasks your agents handle (image generation, web search, email, SMS)
- Never describe what you would do — USE YOUR TOOLS to actually do it

FOR ALL FACTUAL CLAIMS:
- If you can verify with search_web, do so before responding
- If you're unsure about a specific date, number, or name, say so
- Use delegate_to_agent(brave_search_agent) for any claim you're not confident about
- Your response will be fact-checked — confidence scores below 0.6 get flagged to Mark

YOUR DATA IS LIVE. YOUR AGENTS ARE REAL. USE THEM. NEVER HALLUCINATE.
"""


def _assess_tool_risk(tool_name: str, tool_args: dict) -> RiskLevel:
    """
    Risk validation gate — assess the risk level of a tool call before execution.
    Inspired by ai-hedge-fund's risk manager pattern.

    HIGH risk actions get logged prominently. CRITICAL actions would require
    confirmation (future: push notification to iOS for approval).
    """
    # Destructive file operations
    if tool_name == "run_shell":
        cmd = tool_args.get("command", "").lower()
        destructive_patterns = ["rm -rf", "drop table", "delete from", "format", "mkfs", "dd if="]
        if any(p in cmd for p in destructive_patterns):
            return RiskLevel.CRITICAL
        sensitive_patterns = ["sudo", "chmod", "chown", "kill", "pkill", "systemctl"]
        if any(p in cmd for p in sensitive_patterns):
            return RiskLevel.HIGH
        return RiskLevel.LOW

    # Self-modification
    if tool_name == "self_update":
        action = tool_args.get("action", "")
        if action in ("write", "patch"):
            return RiskLevel.HIGH
        return RiskLevel.LOW

    # Agent delegation — medium risk (agents have their own validation)
    if tool_name == "delegate_to_agent":
        return RiskLevel.MEDIUM

    # Communication — sending messages externally
    if tool_name == "delegate_to_agent":
        agent = tool_args.get("agent_name", "")
        if agent in ("communication_agent", "outreach_agent"):
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM

    # Chain execution — aggregate risk
    if tool_name == "chain_agents":
        return RiskLevel.MEDIUM

    # Browser — interacting with external sites
    if tool_name == "browser":
        action = tool_args.get("action", "")
        if action in ("login", "type", "click"):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    return RiskLevel.LOW


async def process_chat(
    request: ChatRequest,
    db: Session,
) -> ChatResponse:
    """
    Process a chat request through the full Cipher pipeline:
    1. Load or create conversation
    2. Auto-classify if using AUTO tier
    3. Check cache (skip for data queries)
    4. DETECT DATA QUERIES → invoke agents for real data
    5. Recall relevant memories
    6. Build context-enriched message list with live data
    7. Route to optimal LLM with hallucination guard
    8. Store response and update memory
    9. Check for agent recommendations
    """

    # 1. Load or create conversation
    conversation_id = request.conversation_id or str(uuid.uuid4())
    try:
        conversation = db.query(ConversationRecord).filter_by(id=conversation_id).first()
    except Exception as e:
        logger.warning(f"DB read failed (non-fatal): {e}")
        conversation = None

    # Auto-classify if using AUTO tier
    model_tier = request.model_tier
    if model_tier == ModelTier.AUTO:
        model_tier, confidence = auto_classify(request.message)
        logger.info(f"Auto-classified message to {model_tier.value} (confidence: {confidence:.2f})")
    else:
        confidence = None

    if not conversation:
        conversation = ConversationRecord(
            id=conversation_id,
            model_tier=model_tier.value,
        )
        try:
            db.add(conversation)
            db.flush()
        except Exception as e:
            logger.warning(f"DB write failed (non-fatal): {e}")
            try:
                db.rollback()
            except Exception:
                pass

    # 2. DETECT DATA QUERIES — do we need live data before LLM responds?
    normalized_message = _normalize_for_matching(request.message)
    msg_lower = request.message.lower()

    is_stock_query = bool(_STOCK_PATTERN.search(normalized_message)) or bool(_STOCK_PATTERN.search(request.message))
    is_news_query = bool(_NEWS_PATTERN.search(msg_lower))
    is_search_query = bool(_SEARCH_PATTERN.search(msg_lower))

    # Fetch live data BEFORE the LLM responds (prevents hallucination)
    live_data_context = ""

    if is_stock_query:
        logger.info(f"Stock query detected — fetching live market data")
        stock_data = await _fetch_live_stock_data(request.message)
        if stock_data:
            live_data_context += stock_data
            logger.info("Live stock data injected into context")

    if is_news_query or is_search_query:
        logger.info(f"Search/news query detected — fetching live results")
        search_data = await _fetch_live_search_data(request.message)
        if search_data:
            live_data_context += search_data
            logger.info("Live search data injected into context")

    # 3. Check cache (SKIP cache for data queries — data changes in real-time)
    if not live_data_context:
        cached = get_cached_response(
            message=request.message,
            model_tier=model_tier.value,
            conversation_id=conversation_id,
        )
        if cached:
            logger.info(f"Cache hit for message in conversation {conversation_id}")
            return ChatResponse(
                message=cached["content"],
                conversation_id=conversation_id,
                model_used=cached["model_used"],
                tokens_used=cached.get("total_tokens", 0),
                cost_usd=cached.get("cost_usd", 0.0),
            )

    # 4. Recall relevant memories
    memory_context = ""
    if request.include_memory:
        memories = recall_memories(request.message, n_results=5)
        if memories:
            memory_parts = []
            for mem in memories:
                if mem["relevance"] > 0.3:
                    memory_parts.append(f"- {mem['content'][:500]}")
            if memory_parts:
                memory_context = (
                    "\n\n[Relevant context from memory]\n"
                    + "\n".join(memory_parts)
                    + "\n[End memory context]\n"
                )

    # 5. Build message list from conversation history
    #    CONTEXT WINDOW GUARD: Estimate token count and truncate history
    #    to prevent context overflow on long prompts.
    #    Rule of thumb: 1 token ≈ 4 characters. Reserve 8K tokens for
    #    system prompt + enrichments + output.
    MAX_CONTEXT_CHARS = 600_000  # ~150K tokens — safe for most models
    RESERVED_CHARS = 32_000     # ~8K tokens for system prompt + output

    messages = []
    history = (
        db.query(MessageRecord)
        .filter_by(conversation_id=conversation_id)
        .order_by(MessageRecord.created_at)
        .limit(50)
        .all()
    )

    # Estimate user message + enrichment size
    user_msg_chars = len(request.message) + len(live_data_context) + len(memory_context)
    budget = MAX_CONTEXT_CHARS - RESERVED_CHARS - user_msg_chars

    # Add history from newest to oldest, then reverse (keeps most recent context)
    history_msgs = [{"role": msg.role, "content": msg.content} for msg in history]
    trimmed = []
    running_chars = 0
    for msg in reversed(history_msgs):
        msg_chars = len(msg.get("content", ""))
        if running_chars + msg_chars > budget:
            break
        trimmed.append(msg)
        running_chars += msg_chars
    messages = list(reversed(trimmed))

    if len(messages) < len(history_msgs):
        logger.info(f"Context guard: trimmed history from {len(history_msgs)} to {len(messages)} messages")

    # Enrich user message with live data + memory
    enriched_message = request.message
    if live_data_context:
        enriched_message = f"{request.message}\n{live_data_context}"
    if memory_context:
        enriched_message = f"{enriched_message}\n{memory_context}"

    # Handle image inputs — build multimodal message if images present
    has_images = bool(request.images)
    if has_images:
        logger.info(f"Processing {len(request.images)} image(s) in chat request")
        # Build multimodal content blocks for the user message
        user_content = build_vision_messages(enriched_message, request.images)
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": enriched_message})

    # 6. Build system prompt with hallucination guard
    system_prompt = request.system_prompt or CIPHER_SYSTEM_PROMPT
    system_prompt += HALLUCINATION_GUARD

    # Voice personality detection
    try:
        personality_mgr = get_personality_manager()
        voice_personality = personality_mgr.detect_voice_mode(
            text=request.message,
            emotion=getattr(request, 'detected_emotion', None),
            emotion_confidence=getattr(request, 'emotion_confidence', 0.0),
            explicit_mode=getattr(request, 'voice_mode', None),
        )
        if voice_personality.system_prompt_overlay:
            system_prompt = f"{system_prompt}\n\n{voice_personality.system_prompt_overlay}"
            logger.info(f"Voice personality active: {voice_personality.name}")
    except Exception as e:
        logger.warning(f"Voice personality detection skipped: {e}")

    # 7. Route to LLM with TOOL CALLING — the agentic loop
    #    The LLM can now call tools (run_shell, read_file, write_file, search_web,
    #    self_update, etc.) and we execute them, feeding results back until the LLM
    #    produces a final text response.
    max_tool_rounds = 10  # Safety limit to prevent infinite loops
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    model_used = ""
    tool_execution_log = []  # Track what tools were called

    # ── FORCED TOOL ROUTING ──────────────────────────────────────────
    # Detect specific request types and force the LLM to call the right tool
    # instead of hallucinating a text response.
    user_msg_lower = request.message.lower() if request.message else ""
    forced_tool_choice = None

    IMAGE_KEYWORDS = ["generate an image", "create an image", "draw ", "make an image", "generate image",
                      "create image", "make a picture", "generate a picture", "design a logo",
                      "create a logo", "make a logo", "illustration of", "artwork of", "picture of"]
    if any(kw in user_msg_lower for kw in IMAGE_KEYWORDS):
        forced_tool_choice = {"type": "function", "function": {"name": "generate_image"}}
        logger.info("[TOOL ROUTING] Image request detected — forcing generate_image tool call")

    SEARCH_KEYWORDS = ["search for", "search the web", "look up", "find information about", "google"]
    if any(kw in user_msg_lower for kw in SEARCH_KEYWORDS):
        forced_tool_choice = {"type": "function", "function": {"name": "search_web"}}
        logger.info("[TOOL ROUTING] Search request detected — forcing search_web tool call")

    for round_num in range(max_tool_rounds):
        # Only force tool_choice on the first round
        current_tool_choice = forced_tool_choice if round_num == 0 else None

        result = await chat_completion_with_tools(
            messages=messages,
            model_tier=model_tier,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system_prompt=system_prompt if round_num == 0 else None,
            tools=CIPHER_TOOLS,
            tool_choice=current_tool_choice,
        )

        total_input_tokens += result.get("input_tokens", 0)
        total_output_tokens += result.get("output_tokens", 0)
        total_cost += result.get("cost_usd", 0.0)
        total_latency += result.get("latency_ms", 0.0)
        model_used = result.get("model_used", "")

        tool_calls = result.get("tool_calls", [])

        if not tool_calls:
            # No tool calls — LLM produced a final text response
            break

        # LLM wants to call tools — execute them and feed results back
        # First, add the assistant message with tool calls to the conversation
        assistant_msg_content = result.get("content", "")
        assistant_tool_msg = {"role": "assistant", "content": assistant_msg_content}

        # Add tool_calls to the assistant message (LiteLLM format)
        assistant_tool_msg["tool_calls"] = tool_calls
        messages.append(assistant_tool_msg)

        # Execute each tool call and add results (with validation gates)
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            try:
                tool_args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                tool_args = {}

            logger.info(f"Tool call round {round_num + 1}: {tool_name}({json.dumps(tool_args)[:100]})")

            # RISK VALIDATION GATE — assess before executing
            risk = _assess_tool_risk(tool_name, tool_args)
            if risk == RiskLevel.CRITICAL:
                logger.warning(f"CRITICAL risk tool blocked: {tool_name}({json.dumps(tool_args)[:100]})")
                tool_result = json.dumps({
                    "error": "This action was blocked by the risk validation gate (CRITICAL risk). "
                             "Destructive operations require explicit operator confirmation.",
                    "risk_level": "critical",
                    "tool": tool_name,
                })
            else:
                if risk == RiskLevel.HIGH:
                    logger.warning(f"HIGH risk tool executing: {tool_name} — monitoring closely")
                # Execute the tool
                tool_result = await execute_tool(tool_name, tool_args)

            # VALIDATION GATE: Check if the tool result indicates an error.
            # If it does, log it and trigger self-healing before the LLM sees it.
            is_error = False
            try:
                parsed = json.loads(tool_result) if tool_result else {}
                if isinstance(parsed, dict) and parsed.get("error"):
                    is_error = True
                    error_msg = parsed['error'][:500]
                    logger.warning(
                        f"Tool {tool_name} returned error: {error_msg[:200]}"
                    )

                    # SELF-HEALING GATE: Try to auto-fix before giving up
                    try:
                        from app.services.self_healing import get_healing_loop
                        heal = get_healing_loop()
                        heal_result = await heal.handle_tool_failure(
                            tool_name=tool_name,
                            tool_args=tool_args,
                            error=error_msg,
                            stack_trace=parsed.get("traceback", ""),
                        )
                        if heal_result.get("action") == "fixed":
                            # Re-execute the tool after fix
                            logger.info(f"[SELF-HEAL] Retrying {tool_name} after auto-fix")
                            tool_result = await execute_tool(tool_name, tool_args)
                            # Re-check if the retry succeeded
                            retry_parsed = json.loads(tool_result) if tool_result else {}
                            if isinstance(retry_parsed, dict) and not retry_parsed.get("error"):
                                is_error = False
                                logger.info(f"[SELF-HEAL] {tool_name} succeeded after auto-fix")
                            else:
                                # Inject healing context so LLM knows what happened
                                tool_result = json.dumps({
                                    "error": error_msg,
                                    "self_healing": "Auto-fix attempted but tool still fails",
                                    "diagnosis": heal_result.get("diagnosis", {}),
                                })
                        elif heal_result.get("action") == "escalate":
                            # Add diagnosis context to the error for the LLM
                            diagnosis = heal_result.get("diagnosis", {})
                            tool_result = json.dumps({
                                "error": error_msg,
                                "self_healing_diagnosis": {
                                    "likely_causes": diagnosis.get("likely_causes", []),
                                    "suggested_actions": diagnosis.get("suggested_actions", []),
                                    "fixable_by_code": diagnosis.get("fixable", False),
                                },
                                "instruction": "Use diagnose_self or self_update to investigate and fix this.",
                            })
                    except Exception as heal_err:
                        logger.debug(f"Self-healing gate error (non-fatal): {heal_err}")

            except (json.JSONDecodeError, TypeError):
                pass

            # For image tools, keep full result so we can extract URLs later
            preview_limit = 5000 if tool_name in ("generate_image", "delegate_to_agent") else 200
            tool_execution_log.append({
                "tool": tool_name,
                "args": tool_args,
                "result_preview": tool_result[:preview_limit] if tool_result else "",
                "full_result": tool_result if tool_name == "generate_image" else None,
                "round": round_num + 1,
                "had_error": is_error,
                "risk_level": risk.value,
            })

            # Add tool result to messages — the LLM will see error details
            # and can choose to retry with different parameters
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })

        logger.info(f"Tool round {round_num + 1} complete, {len(tool_calls)} tools executed")

    # QUALITY GATE — Validate the LLM response before returning.
    # If the response is empty or trivially short, retry once with an explicit nudge.
    # This implements the "iterative refinement" pattern: check → fix → finalize.
    final_content = result.get("content", "").strip()

    if not final_content or len(final_content) < 5:
        logger.warning("Quality gate: Empty or near-empty response — retrying once")
        retry_messages = messages + [
            {"role": "assistant", "content": final_content or ""},
            {"role": "user", "content": (
                "[System: Your previous response was empty or incomplete. "
                "Please provide a complete, helpful response to the user's original message. "
                "If you need to use tools, do so now.]"
            )},
        ]
        try:
            retry_result = await chat_completion_with_tools(
                messages=retry_messages,
                model_tier=model_tier,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                tools=CIPHER_TOOLS,
            )
            retry_content = retry_result.get("content", "").strip()
            if retry_content and len(retry_content) > len(final_content):
                result = retry_result
                total_input_tokens += retry_result.get("input_tokens", 0)
                total_output_tokens += retry_result.get("output_tokens", 0)
                total_cost += retry_result.get("cost_usd", 0.0)
                total_latency += retry_result.get("latency_ms", 0.0)
                model_used = retry_result.get("model_used", model_used)
                logger.info("Quality gate: Retry produced better response")
        except Exception as e:
            logger.warning(f"Quality gate retry failed: {e}")

    # Reassemble result dict in the format the rest of the code expects
    result = {
        "content": result.get("content", ""),
        "model_used": model_used,
        "provider": result.get("provider", ""),
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "cost_usd": total_cost,
        "latency_ms": total_latency,
    }

    # Append tool execution log to response if tools were used
    if tool_execution_log:
        logger.info(f"Agentic response used {len(tool_execution_log)} tool calls across {round_num + 1} rounds")

    # 8. Cache the response (only if not a live data query and no tools used)
    if not live_data_context and not tool_execution_log:
        cache_response(
            message=request.message,
            model_tier=model_tier.value,
            response=result,
            conversation_id=conversation_id,
        )

    # 9. Store messages in database
    user_msg = MessageRecord(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )
    assistant_msg = MessageRecord(
        conversation_id=conversation_id,
        role="assistant",
        content=result["content"],
        model_used=result["model_used"],
        tokens_used=result["total_tokens"],
        cost_usd=result["cost_usd"],
    )
    try:
        db.add_all([user_msg, assistant_msg])

        # Update conversation
        conversation.updated_at = datetime.now(timezone.utc)
        if not conversation.title and len(request.message) > 0:
            conversation.title = request.message[:100]

        # Log usage
        usage_log = UsageLog(
            model=result["model_used"],
            provider=result["provider"],
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            total_tokens=result["total_tokens"],
            cost_usd=result["cost_usd"],
            latency_ms=result["latency_ms"],
            task_type=model_tier.value,
        )
        db.add(usage_log)
        db.commit()
    except Exception as e:
        logger.warning(f"DB persist failed (non-fatal, chat still works): {e}")
        try:
            db.rollback()
        except Exception:
            pass

    # Store in long-term memory
    try:
        store_conversation_context(
            conversation_id=conversation_id,
            user_message=request.message,
            assistant_response=result["content"],
        )
    except Exception as e:
        logger.warning(f"Failed to store memory: {e}")

    # 10. Check if an agent should be recommended
    recommended_agent = None
    try:
        from app.api.recommendations import _score_agent_match, AGENT_TRIGGERS
        best_score = 0.0
        best_agent = None
        best_info = None
        for agent_name, info in AGENT_TRIGGERS.items():
            score_original = _score_agent_match(request.message, agent_name, info)
            score_normalized = _score_agent_match(normalized_message, agent_name, info)
            score = max(score_original, score_normalized)
            if score > best_score:
                best_score = score
                best_agent = agent_name
                best_info = info
        if best_score >= 0.5 and best_agent and best_info:
            recommended_agent = RecommendedAgentInfo(
                agent_name=best_agent,
                display_name=best_info["display_name"],
                reason=best_info["description"],
                confidence=best_score,
                suggested_instruction=request.message,
            )
            logger.info(f"Recommending agent {best_info['display_name']} (confidence={best_score:.2f})")
    except Exception as e:
        logger.warning(f"Agent recommendation check failed: {e}")

    # 11. Run fact-checking on the response (non-blocking for speed)
    confidence_score = None
    validation_warnings = None
    try:
        validation = await validate_response(
            response_text=result["content"],
            user_query=request.message,
            live_data_used=bool(live_data_context),
        )
        if validation.get("checked"):
            confidence_score = validation.get("confidence")
            warnings = validation.get("warnings", [])
            validation_warnings = warnings if warnings else None
            logger.info(f"Fact-check complete: confidence={confidence_score}, warnings={len(warnings)}")
    except Exception as e:
        logger.warning(f"Fact-checking skipped: {e}")

    # 12. Extract any image URLs from the response (e.g., from image_agent)
    response_images = []
    for log_entry in tool_execution_log:
        tool = log_entry.get("tool", "")
        result_preview = log_entry.get("result_preview", "")

        # Direct generate_image tool — parse the structured JSON result
        if tool == "generate_image" and not log_entry.get("had_error"):
            try:
                # Use full_result if available, fall back to result_preview
                raw = log_entry.get("full_result") or result_preview
                parsed_result = json.loads(raw) if raw else {}
                # Extract from image_urls array or saved_locally paths
                for url in parsed_result.get("image_urls", []):
                    if url:
                        response_images.append(ImageAttachment(url=url))
                        logger.info(f"Extracted image URL from generate_image: {url[:80]}...")
                for path in parsed_result.get("saved_locally", []):
                    if path:
                        response_images.append(ImageAttachment(url=path))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse generate_image result: {e}")
                pass

        # Also check delegate_to_agent for image results
        if tool == "delegate_to_agent":
            if "image" in result_preview.lower() and ("http" in result_preview or "data/" in result_preview):
                import re as _re
                url_match = _re.search(r'(https?://\S+\.(?:png|jpg|jpeg|webp|gif))', result_preview)
                path_match = _re.search(r'(data/\S+\.(?:png|jpg|jpeg|webp|gif))', result_preview)
                if url_match:
                    response_images.append(ImageAttachment(url=url_match.group(1)))
                elif path_match:
                    response_images.append(ImageAttachment(url=path_match.group(1)))

        # Also scan any tool result for DALL-E / oaidalleapiprodscus URLs
        if "oaidalleapiprodscus" in result_preview or "replicate.delivery" in result_preview:
            import re as _re
            for url in _re.findall(r'(https?://[^\s"\']+)', result_preview):
                if any(ext in url.lower() for ext in ['.png', '.jpg', '.jpeg', '.webp']) or 'oaidalleapiprodscus' in url:
                    response_images.append(ImageAttachment(url=url))

    return ChatResponse(
        message=result["content"],
        conversation_id=conversation_id,
        model_used=result["model_used"],
        tokens_used=result["total_tokens"],
        cost_usd=result["cost_usd"],
        recommended_agent=recommended_agent,
        images=response_images,
        confidence_score=confidence_score,
        validation_warnings=validation_warnings,
    )
