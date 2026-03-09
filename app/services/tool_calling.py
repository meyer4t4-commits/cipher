"""
Tool Calling Integration — Bridges LLM function calls to real agent execution.

This is the missing piece: when Cipher wants to DO something (run a command,
read a file, search the web, update its own code), the LLM emits a tool call,
this module executes it via the agent framework, and feeds the result back.

Supports Anthropic Claude tool_use format natively via LiteLLM.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from app.core.logging import logger

# ---------------------------------------------------------------------------
# Tool Definitions — These are sent to the LLM so it knows what it can do
# ---------------------------------------------------------------------------

CIPHER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Execute a shell command on the server. Use for: checking system status, "
                "running scripts, installing packages, git operations, building projects, "
                "any terminal command. Returns stdout, stderr, and exit code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute (bash)",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Optional working directory for the command",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file. Use to inspect code, configs, logs, "
                "or any text file. Returns the file contents as a string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file to read",
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum number of lines to read (default: 500)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file. Creates the file if it doesn't exist, "
                "overwrites if it does. Use for: creating scripts, updating configs, "
                "writing code, saving data. For modifying existing files, read first then write."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for current information using Brave Search API. "
                "Use for: finding current news, looking up facts, researching topics, "
                "getting real-time information. Returns search results with titles, "
                "snippets, and URLs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 10)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "self_update",
            "description": (
                "Modify Cipher's own source code. Use this to fix bugs in yourself, "
                "add new features, update your system prompt, or improve your capabilities. "
                "This is your self-improvement mechanism. Be careful and precise — "
                "bad edits can break things. Always read the file first, then write the updated version."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path relative to the project root (e.g., 'app/services/orchestrator.py')",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "patch"],
                        "description": "'read' to inspect current code, 'write' to replace file contents, 'patch' to apply a targeted edit",
                    },
                    "content": {
                        "type": "string",
                        "description": "For 'write': the new file content. For 'patch': JSON with 'old' and 'new' strings to find-and-replace.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what this change does and why",
                    },
                },
                "required": ["file_path", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": (
                "List files and directories at a given path. "
                "Use to explore the project structure, find files, or check what exists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (default: project root)",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "List recursively (default: false, use sparingly on large dirs)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_store",
            "description": (
                "Store information in long-term memory for future recall. "
                "Use to remember facts, decisions, preferences, or insights "
                "that should persist across conversations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The information to store",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags for categorization",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_recall",
            "description": (
                "Search long-term memory for relevant information. "
                "Use to recall past decisions, stored facts, or preferences."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in memory",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": (
                "Generate an AI image from a text prompt using DALL-E 3 (primary) or Stability AI (fallback). "
                "MUST USE when user says any of: 'create/draw/design/generate/make an image', 'logo', "
                "'illustration', 'artwork', 'canvas', 'mockup', 'visualize', 'picture of'. "
                "Do NOT use delegate_to_agent for images — call this tool DIRECTLY. "
                "Do NOT describe what the image would look like — GENERATE IT. "
                "Write detailed prompts: include style, lighting, composition, colors, mood."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Detailed description of the image to generate. Be specific about style, lighting, composition.",
                    },
                    "size": {
                        "type": "string",
                        "description": "Image size: '1024x1024' (square), '1792x1024' (landscape), '1024x1792' (portrait). Default: 1024x1024",
                    },
                    "quality": {
                        "type": "string",
                        "description": "'hd' for high detail or 'standard'. Default: standard",
                    },
                    "style": {
                        "type": "string",
                        "description": "'vivid' for hyper-real or 'natural' for more realistic. Default: vivid",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_agent",
            "description": (
                "Delegate a task to a specialized Cipher agent by name. Use when the task needs "
                "domain expertise beyond simple tool execution. Key routing: "
                "video generation → video_agent, "
                "email/SMS/Slack → communication_agent, "
                "bulk outreach → outreach_agent, "
                "deep research → research_agent, "
                "real estate analysis → apex_architect_agent, "
                "property search → scout_agent, "
                "stock/crypto → trading_agent, "
                "market monitoring → market_pulse_agent, "
                "code review → code_agent, "
                "deploy → deploy_agent, "
                "security → sentinel_agent, "
                "schedule/remind → scheduler_agent, "
                "legal/contracts → legal_agent, "
                "database queries → data_agent, "
                "synthesize sources → synthesis_agent. "
                "Do NOT use for images (use generate_image directly). "
                "Do NOT use for web search (use search_web directly). "
                "Validate: if agent returns an error, try an alternative agent or approach."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of the agent to delegate to (e.g., 'shell_agent', 'research_agent')",
                    },
                    "instruction": {
                        "type": "string",
                        "description": "Clear instruction for what the agent should do",
                    },
                    "params": {
                        "type": "object",
                        "description": "Optional parameters to pass to the agent (operation-specific)",
                    },
                },
                "required": ["agent_name", "instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "chain_agents",
            "description": (
                "Execute multiple agents in sequence, where each agent's output feeds into "
                "the next. Use for complex multi-step tasks like: research a topic → analyze "
                "results → draft an email → send it. Each step in the chain runs after the "
                "previous one completes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "agent_name": {"type": "string"},
                                "instruction": {"type": "string"},
                                "params": {"type": "object"},
                            },
                            "required": ["agent_name", "instruction"],
                        },
                        "description": "Ordered list of agent tasks to execute sequentially",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of the overall chain goal",
                    },
                },
                "required": ["steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser",
            "description": (
                "Universal browser automation — acts as a real human browsing the web. "
                "Use this to interact with ANY website: log in, scrape data, fill forms, "
                "click buttons, extract text, take screenshots. "
                "This is how you access X/Twitter (no API needed), ElevenLabs voice library, "
                "dashboards, and any site that requires a browser. "
                "Actions: navigate, extract_text, extract_elements, click, type, scroll, "
                "screenshot, wait_for, evaluate, login, scrape_x, scrape_structured, save_session. "
                "Session cookies persist — log in once, stay logged in. "
                "For X/Twitter: use action='scrape_x' with query or account params. "
                "For any site: navigate first, then extract_text or extract_elements. "
                "For login: use action='login' with credentials. "
                "Do NOT use search_web when you need to actually interact with a site — use this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "navigate", "extract_text", "extract_elements",
                            "click", "type", "scroll", "screenshot",
                            "wait_for", "evaluate", "get_page_info",
                            "login", "save_session", "scrape_x",
                            "scrape_structured", "close",
                        ],
                        "description": "The browser action to perform",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to (for 'navigate', 'login', 'scrape_structured')",
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector to target (for click, type, extract, wait_for, scroll)",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type (for 'type'), or visible text to click (for 'click'), or text to wait for (for 'wait_for')",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (for 'scrape_x')",
                    },
                    "account": {
                        "type": "string",
                        "description": "X/Twitter account to scrape (for 'scrape_x', e.g., 'AnthropicAI')",
                    },
                    "press_enter": {
                        "type": "boolean",
                        "description": "Press Enter after typing (for 'type')",
                    },
                    "script": {
                        "type": "string",
                        "description": "JavaScript to execute (for 'evaluate')",
                    },
                    "tab_id": {
                        "type": "string",
                        "description": "Tab identifier for multi-tab browsing (default: 'main')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum items to extract (for extract_elements, scrape_x)",
                    },
                    "username_selector": {"type": "string", "description": "CSS selector for username input (for 'login')"},
                    "username": {"type": "string", "description": "Username to enter (for 'login')"},
                    "password_selector": {"type": "string", "description": "CSS selector for password input (for 'login')"},
                    "password": {"type": "string", "description": "Password to enter (for 'login')"},
                    "submit_selector": {"type": "string", "description": "CSS selector for submit button (for 'login')"},
                    "session_name": {"type": "string", "description": "Name for saving/loading sessions (default: 'default')"},
                    "item_selector": {"type": "string", "description": "CSS selector for repeated items (for 'scrape_structured')"},
                    "fields": {"type": "object", "description": "Field name → CSS selector mapping (for 'scrape_structured')"},
                    "direction": {"type": "string", "description": "Scroll direction: 'up' or 'down' (for 'scroll')"},
                    "full_page": {"type": "boolean", "description": "Capture full page screenshot (for 'screenshot')"},
                },
                "required": ["action"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Execution — Maps tool calls to real agent/system operations
# ---------------------------------------------------------------------------

# Base path for the Cipher project (auto-detected)
_PROJECT_ROOT: Optional[str] = None


def _get_project_root() -> str:
    """Get the project root directory."""
    global _PROJECT_ROOT
    if _PROJECT_ROOT:
        return _PROJECT_ROOT

    # Try common locations
    candidates = [
        Path(__file__).parent.parent.parent,  # cipher-app/app/services/ → cipher-app/
        Path.cwd(),
        Path("/app"),
    ]
    for c in candidates:
        if (c / "app" / "main.py").exists():
            _PROJECT_ROOT = str(c)
            return _PROJECT_ROOT

    _PROJECT_ROOT = str(Path.cwd())
    return _PROJECT_ROOT


async def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    Execute a tool call and return the result as a string.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments from the LLM

    Returns:
        String result to feed back to the LLM
    """
    logger.info(f"Executing tool: {tool_name} with args: {json.dumps(arguments)[:200]}")

    try:
        if tool_name == "run_shell":
            return await _exec_shell(arguments)
        elif tool_name == "read_file":
            return await _exec_read_file(arguments)
        elif tool_name == "write_file":
            return await _exec_write_file(arguments)
        elif tool_name == "search_web":
            return await _exec_search_web(arguments)
        elif tool_name == "self_update":
            return await _exec_self_update(arguments)
        elif tool_name == "list_directory":
            return await _exec_list_directory(arguments)
        elif tool_name == "memory_store":
            return await _exec_memory_store(arguments)
        elif tool_name == "memory_recall":
            return await _exec_memory_recall(arguments)
        elif tool_name == "generate_image":
            return await _exec_generate_image(arguments)
        elif tool_name == "delegate_to_agent":
            return await _exec_delegate_to_agent(arguments)
        elif tool_name == "chain_agents":
            return await _exec_chain_agents(arguments)
        elif tool_name == "browser":
            return await _exec_browser(arguments)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name}: {e}")
        return json.dumps({"error": str(e), "tool": tool_name})


async def _exec_shell(args: dict) -> str:
    """Execute a shell command via the ShellAgent."""
    command = args.get("command", "")
    cwd = args.get("working_directory", _get_project_root())

    if not command.strip():
        return json.dumps({"error": "Empty command"})

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

        stdout_str = stdout.decode("utf-8", errors="replace").strip()
        stderr_str = stderr.decode("utf-8", errors="replace").strip()

        # Truncate very long output
        if len(stdout_str) > 10000:
            stdout_str = stdout_str[:10000] + "\n... (output truncated)"

        result = {
            "exit_code": process.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "success": process.returncode == 0,
        }
        return json.dumps(result)

    except asyncio.TimeoutError:
        return json.dumps({"error": "Command timed out after 60s", "command": command})
    except Exception as e:
        return json.dumps({"error": str(e), "command": command})


async def _exec_read_file(args: dict) -> str:
    """Read a file's contents."""
    path = args.get("path", "")
    max_lines = args.get("max_lines", 500)

    if not path:
        return json.dumps({"error": "No path specified"})

    # Resolve relative paths against project root
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(_get_project_root()) / file_path

    if not file_path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    if not file_path.is_file():
        return json.dumps({"error": f"Not a file: {file_path}"})

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines])
            content += f"\n... ({len(lines) - max_lines} more lines truncated)"

        return json.dumps({
            "path": str(file_path),
            "content": content,
            "lines": min(len(lines), max_lines),
            "total_lines": len(lines),
        })
    except Exception as e:
        return json.dumps({"error": str(e), "path": str(file_path)})


async def _exec_write_file(args: dict) -> str:
    """Write content to a file."""
    path = args.get("path", "")
    content = args.get("content", "")

    if not path:
        return json.dumps({"error": "No path specified"})

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(_get_project_root()) / file_path

    try:
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        return json.dumps({
            "success": True,
            "path": str(file_path),
            "bytes_written": len(content.encode("utf-8")),
        })
    except Exception as e:
        return json.dumps({"error": str(e), "path": str(file_path)})


async def _exec_search_web(args: dict) -> str:
    """Search the web via Brave Search API."""
    import httpx

    query = args.get("query", "")
    count = min(args.get("count", 5), 10)

    if not query:
        return json.dumps({"error": "No query specified"})

    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    if not api_key:
        return json.dumps({"error": "Brave Search API key not configured"})

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": count},
                headers={
                    "X-Subscription-Token": api_key,
                    "Accept": "application/json",
                },
            )
            if resp.status_code != 200:
                return json.dumps({"error": f"Search API returned {resp.status_code}"})

            data = resp.json()
            results = data.get("web", {}).get("results", [])

            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                    "age": r.get("age", ""),
                })

            return json.dumps({"query": query, "results": formatted})

    except Exception as e:
        return json.dumps({"error": str(e), "query": query})


async def _exec_self_update(args: dict) -> str:
    """Self-update: read, write, or patch Cipher's own source code."""
    file_path_str = args.get("file_path", "")
    action = args.get("action", "read")
    content = args.get("content", "")
    description = args.get("description", "No description")

    if not file_path_str:
        return json.dumps({"error": "No file_path specified"})

    project_root = Path(_get_project_root())
    file_path = project_root / file_path_str

    # Security: don't allow escaping project root
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(project_root.resolve())):
            return json.dumps({"error": "Path escape attempt blocked"})
    except Exception:
        return json.dumps({"error": "Invalid path"})

    if action == "read":
        if not file_path.exists():
            return json.dumps({"error": f"File not found: {file_path_str}"})
        try:
            code = file_path.read_text(encoding="utf-8")
            return json.dumps({
                "action": "read",
                "path": file_path_str,
                "content": code,
                "lines": len(code.split("\n")),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    elif action == "write":
        if not content:
            return json.dumps({"error": "No content provided for write action"})
        try:
            # Backup the original
            if file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                backup_path.write_text(file_path.read_text(), encoding="utf-8")

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            logger.info(f"Self-update: wrote {file_path_str} — {description}")

            return json.dumps({
                "action": "write",
                "path": file_path_str,
                "success": True,
                "description": description,
                "bytes": len(content.encode("utf-8")),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    elif action == "patch":
        if not content:
            return json.dumps({"error": "No patch content provided"})
        try:
            patch_data = json.loads(content)
            old_str = patch_data.get("old", "")
            new_str = patch_data.get("new", "")

            if not old_str:
                return json.dumps({"error": "Patch missing 'old' string"})

            if not file_path.exists():
                return json.dumps({"error": f"File not found: {file_path_str}"})

            current = file_path.read_text(encoding="utf-8")
            if old_str not in current:
                return json.dumps({"error": f"'old' string not found in {file_path_str}"})

            # Backup
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            backup_path.write_text(current, encoding="utf-8")

            updated = current.replace(old_str, new_str, 1)
            file_path.write_text(updated, encoding="utf-8")

            logger.info(f"Self-update patch: {file_path_str} — {description}")

            return json.dumps({
                "action": "patch",
                "path": file_path_str,
                "success": True,
                "description": description,
            })
        except json.JSONDecodeError:
            return json.dumps({"error": "Patch content must be JSON with 'old' and 'new' keys"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    else:
        return json.dumps({"error": f"Unknown action: {action}"})


async def _exec_list_directory(args: dict) -> str:
    """List files in a directory."""
    path = args.get("path", "")
    recursive = args.get("recursive", False)

    dir_path = Path(path) if path else Path(_get_project_root())
    if not dir_path.is_absolute():
        dir_path = Path(_get_project_root()) / dir_path

    if not dir_path.exists():
        return json.dumps({"error": f"Directory not found: {dir_path}"})

    if not dir_path.is_dir():
        return json.dumps({"error": f"Not a directory: {dir_path}"})

    try:
        entries = []
        if recursive:
            for p in sorted(dir_path.rglob("*"))[:200]:  # Limit to 200 entries
                rel = p.relative_to(dir_path)
                entries.append({
                    "name": str(rel),
                    "type": "dir" if p.is_dir() else "file",
                    "size": p.stat().st_size if p.is_file() else None,
                })
        else:
            for p in sorted(dir_path.iterdir()):
                entries.append({
                    "name": p.name,
                    "type": "dir" if p.is_dir() else "file",
                    "size": p.stat().st_size if p.is_file() else None,
                })

        return json.dumps({
            "path": str(dir_path),
            "entries": entries,
            "count": len(entries),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _exec_memory_store(args: dict) -> str:
    """Store info in long-term memory."""
    from app.services.memory import store_memory

    content = args.get("content", "")
    tags = args.get("tags", "")

    if not content:
        return json.dumps({"error": "No content to store"})

    try:
        metadata = {}
        if tags:
            metadata["tags"] = [t.strip() for t in tags.split(",")]

        memory_id = store_memory(content, metadata=metadata)
        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "stored": content[:100],
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _exec_memory_recall(args: dict) -> str:
    """Recall info from long-term memory."""
    from app.services.memory import recall_memories

    query = args.get("query", "")

    if not query:
        return json.dumps({"error": "No query specified"})

    try:
        memories = recall_memories(query, n_results=5)
        results = []
        for mem in memories:
            if mem.get("relevance", 0) > 0.2:
                results.append({
                    "content": mem["content"][:500],
                    "relevance": round(mem["relevance"], 2),
                })

        return json.dumps({
            "query": query,
            "results": results,
            "count": len(results),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def _exec_generate_image(args: dict) -> str:
    """Generate an image using the ImageAgent (DALL-E 3 / Stability AI)."""
    try:
        from app.agents.skills.image_agent import ImageAgent
        from app.agents.models import AgentTask

        agent = ImageAgent()
        task = AgentTask(
            agent_name="image_agent",
            instruction=args.get("prompt", ""),
            params={
                "prompt": args.get("prompt", ""),
                "size": args.get("size", "1024x1024"),
                "quality": args.get("quality", "standard"),
                "style": args.get("style", "vivid"),
                "operation": "generate_image",
            },
            timeout_seconds=60,
        )

        is_valid = await agent.validate(task)
        if not is_valid:
            return json.dumps({"error": "Image generation validation failed. Check OPENAI_API_KEY or STABILITY_API_KEY in .env"})

        result = await agent.execute(task)

        if result.success:
            output = result.output or {}
            # Build a user-friendly response
            images = output.get("images", [])
            saved = output.get("saved_paths", [])
            return json.dumps({
                "success": True,
                "provider": output.get("provider", "unknown"),
                "prompt": output.get("prompt", args.get("prompt", "")),
                "revised_prompt": output.get("revised_prompt", ""),
                "num_images": len(images),
                "image_urls": [img.get("url", "") for img in images if img.get("url")],
                "saved_locally": saved,
                "message": f"Generated {len(images)} image(s) successfully.",
            })
        else:
            return json.dumps({"error": result.error or "Image generation failed"})

    except Exception as e:
        logger.error(f"generate_image tool failed: {e}")
        return json.dumps({"error": f"Image generation error: {str(e)}"})


async def _exec_delegate_to_agent(args: dict) -> str:
    """Delegate a task to a specific Cipher agent."""
    from app.agents.registry import get_registry
    from app.agents.executor import get_executor
    from app.agents.models import AgentTask

    agent_name = args.get("agent_name", "")
    instruction = args.get("instruction", "")
    params = args.get("params", {})

    if not agent_name:
        return json.dumps({"error": "No agent_name specified"})
    if not instruction:
        return json.dumps({"error": "No instruction specified"})

    try:
        registry = get_registry()
        executor = get_executor()

        if not registry.is_registered(agent_name):
            available = registry.list_agents() if hasattr(registry, 'list_agents') else []
            return json.dumps({
                "error": f"Agent '{agent_name}' not found in registry",
                "available_agents": [a.name for a in available] if available else [],
            })

        # Build the task
        task = AgentTask(
            agent_name=agent_name,
            instruction=instruction,
            params=params or {},
        )

        # Execute via the executor
        result = await executor.execute(task)

        return json.dumps({
            "agent": agent_name,
            "success": result.success,
            "output": str(result.output)[:5000] if result.output else None,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
            "task_id": result.task_id,
        })

    except Exception as e:
        logger.error(f"Agent delegation failed: {agent_name}: {e}")
        return json.dumps({"error": str(e), "agent": agent_name})


async def _exec_chain_agents(args: dict) -> str:
    """Execute a chain of agents sequentially, feeding output forward."""
    from app.agents.registry import get_registry
    from app.agents.executor import get_executor
    from app.agents.models import AgentTask

    steps = args.get("steps", [])
    description = args.get("description", "Agent chain execution")

    if not steps:
        return json.dumps({"error": "No steps provided"})

    if len(steps) > 10:
        return json.dumps({"error": "Maximum 10 steps in a chain"})

    try:
        registry = get_registry()
        executor = get_executor()

        chain_results = []
        previous_output = None

        for i, step in enumerate(steps):
            agent_name = step.get("agent_name", "")
            instruction = step.get("instruction", "")
            params = step.get("params", {})

            if not agent_name or not instruction:
                chain_results.append({
                    "step": i + 1,
                    "error": "Missing agent_name or instruction",
                    "skipped": True,
                })
                continue

            if not registry.is_registered(agent_name):
                chain_results.append({
                    "step": i + 1,
                    "agent": agent_name,
                    "error": f"Agent '{agent_name}' not found",
                    "skipped": True,
                })
                continue

            # Inject previous output into instruction context
            enriched_instruction = instruction
            if previous_output:
                enriched_instruction = (
                    f"{instruction}\n\n"
                    f"[Context from previous step]\n{str(previous_output)[:3000]}\n"
                    f"[End context]"
                )

            task = AgentTask(
                agent_name=agent_name,
                instruction=enriched_instruction,
                params=params or {},
            )

            result = await executor.execute(task)

            step_result = {
                "step": i + 1,
                "agent": agent_name,
                "success": result.success,
                "output": str(result.output)[:2000] if result.output else None,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
            }
            chain_results.append(step_result)

            # Feed output to next step
            if result.success and result.output:
                previous_output = result.output
            elif result.error:
                # Stop chain on error unless it's a non-critical agent
                logger.warning(f"Chain step {i + 1} ({agent_name}) failed: {result.error}")
                break

        return json.dumps({
            "description": description,
            "total_steps": len(steps),
            "completed_steps": len(chain_results),
            "results": chain_results,
            "final_output": str(previous_output)[:3000] if previous_output else None,
        })

    except Exception as e:
        logger.error(f"Agent chain failed: {e}")
        return json.dumps({"error": str(e)})


async def _exec_browser(args: dict) -> str:
    """Execute a browser automation action."""
    from app.services.browser_service import execute_browser_action

    action = args.get("action", "")
    if not action:
        return json.dumps({"error": "No action specified"})

    # Build params dict from all non-action args
    params = {k: v for k, v in args.items() if k != "action" and v is not None}

    return await execute_browser_action(action, params)
