"""
Self-Improvement Agent — Cipher's autonomous self-maintenance and upgrade system.

WHY THIS EXISTS:
Cipher has all the tools to modify itself (self_update, run_bash, diagnose_self,
test_and_verify) but lacks a structured playbook that breaks self-improvement into
small, context-window-friendly steps. Without this agent, Cipher tries to analyze
everything at once, runs out of context, and writes essays about what it *would* do.

This agent solves the context window problem by:
1. Breaking improvement into SMALL ATOMIC TASKS (one file, one fix at a time)
2. Using targeted reads (not full codebase scans)
3. Using patch mode (not full file rewrites)
4. Testing after every change
5. Rolling back on failure
6. Logging everything for the autonomous loop to learn from

CAPABILITIES:
- audit: Run targeted audit on specific subsystem
- fix: Apply a specific fix from an audit finding
- improve: Execute a prioritized improvement plan (audit → fix → test → next)
- benchmark: Run agent-specific health checks
- apply_insight: Take an insight from the absorber and implement it

DESIGN PRINCIPLE: Do ONE thing per step. Never try to rewrite the whole system at once.
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


# Maximum characters to read from a single file in one step.
# Raised from 6000 to 15000 — the old limit caused the LLM to see
# abruptly-truncated files and report phantom "incomplete" bugs.
MAX_FILE_CHARS = 15000

# Subsystems that can be audited independently
AUDITABLE_SUBSYSTEMS = {
    "memory": {
        "files": ["app/services/memory.py"],
        "test_cmd": "python -c \"from app.services.memory import recall_memories, store_memory, store_conversation_context, store_agent_result, store_learning, get_memory_stats, initialize_memory, delete_memory; print('memory OK — all 8 functions imported')\"",
        "description": "PostgreSQL-backed persistent memory. Functions: store_memory, recall_memories, store_conversation_context, store_agent_result, store_learning, get_memory_stats, delete_memory, initialize_memory. Uses MemoryEntry table. Has importance scoring (_score_importance), recency-weighted retrieval (_relevance_score), and priority boosting.",
    },
    "orchestrator": {
        "files": ["app/services/orchestrator.py"],
        "test_cmd": "python -c \"import ast; ast.parse(open('app/services/orchestrator.py').read()); print('syntax OK')\"",
        "description": "Main chat orchestrator — routing, bypasses, tool loop",
    },
    "agents": {
        "files": ["app/agents/skills/__init__.py", "app/api/agents.py"],
        "test_cmd": "python -c \"import ast; ast.parse(open('app/agents/skills/__init__.py').read()); print('init OK')\"",
        "description": "Agent registry and initialization",
    },
    "self_healing": {
        "files": ["app/services/self_healing.py"],
        "test_cmd": "python -c \"from app.services.self_healing import get_healing_loop; print('healing OK')\"",
        "description": "Error detection, diagnosis, auto-fix loop",
    },
    "routing": {
        "files": ["app/services/llm_router.py"],
        "test_cmd": "python -c \"import ast; ast.parse(open('app/services/llm_router.py').read()); print('router OK')\"",
        "description": "Multi-model LLM routing and failover",
    },
    "tools": {
        "files": ["app/services/tool_calling.py"],
        "test_cmd": "python -c \"from app.services.tool_calling import CIPHER_TOOLS; print(f'{len(CIPHER_TOOLS)} tools OK')\"",
        "description": "Tool definitions and execution",
    },
    "system_prompt": {
        "files": ["app/core/system_prompt.py"],
        "test_cmd": "python -c \"from app.core.system_prompt import CIPHER_SYSTEM_PROMPT; print(f'prompt {len(CIPHER_SYSTEM_PROMPT)} chars OK')\"",
        "description": "Cipher's identity, routing rules, and behavioral config",
    },
    "diagnostics": {
        "files": ["app/services/self_diagnostic.py", "app/services/self_test.py"],
        "test_cmd": "python -c \"import ast; ast.parse(open('app/services/self_diagnostic.py').read()); print('diag OK')\"",
        "description": "Self-test suite and diagnostic checks",
    },
}

# Agent files mapped to their names for individual audits
AGENT_FILES = {}  # Populated lazily


class SelfImprovementAgent(BaseAgent):
    """Cipher's autonomous self-improvement system.

    Breaks self-improvement into atomic, context-safe steps:
    audit one thing → fix one thing → test → move on.
    """

    def __init__(self):
        super().__init__(
            name="self_improvement_agent",
            description=(
                "Autonomous self-improvement: audit subsystems, identify issues, "
                "apply targeted fixes, test, and roll back on failure. "
                "Breaks work into small atomic steps to stay within context limits."
            ),
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="audit",
                    description=(
                        "Audit a specific subsystem for issues. "
                        "Params: subsystem (str — one of: memory, orchestrator, agents, "
                        "self_healing, routing, tools, system_prompt, diagnostics), "
                        "or 'all' for a quick scan of everything."
                    ),
                    category="maintenance",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="fix",
                    description=(
                        "Apply a specific fix. "
                        "Params: file_path (str), fix_type (str — patch/add/remove), "
                        "old_code (str, for patch), new_code (str), description (str)"
                    ),
                    category="maintenance",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="improve",
                    description=(
                        "Run a prioritized self-improvement cycle: "
                        "audit → prioritize → fix → test → next. "
                        "Params: focus (str, optional — subsystem to focus on), "
                        "max_fixes (int, default 3 — max fixes per cycle)"
                    ),
                    category="maintenance",
                    timeout_seconds=300,
                ),
                AgentCapability(
                    name="benchmark",
                    description=(
                        "Run health checks on a specific agent or all agents. "
                        "Params: agent_name (str, optional — specific agent to test)"
                    ),
                    category="maintenance",
                    timeout_seconds=120,
                ),
                AgentCapability(
                    name="apply_insight",
                    description=(
                        "Take an insight from the insight absorber and implement it. "
                        "Params: insight (dict with type, summary, detail, implementation_hint)"
                    ),
                    category="maintenance",
                    timeout_seconds=180,
                ),
            ],
        )
        self._project_root = Path(os.getenv("PROJECT_ROOT", ".")).resolve()
        self._log_dir = self._project_root / "data" / "self_improvement"
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self._log_dir = Path("/tmp/cipher_data/self_improvement")
            self._log_dir.mkdir(parents=True, exist_ok=True)
            logger.info("[SELF-IMPROVE] Using /tmp fallback for log_dir")

    async def validate(self, task: AgentTask) -> bool:
        cap = task.params.get("capability", "improve")
        if cap == "audit":
            subsystem = task.params.get("subsystem", "all")
            if subsystem != "all" and subsystem not in AUDITABLE_SUBSYSTEMS:
                return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        cap = task.params.get("capability", "improve")

        if cap == "audit":
            raw = await self._audit(task)
        elif cap == "fix":
            raw = await self._fix(task)
        elif cap == "improve":
            raw = await self._improve_cycle(task)
        elif cap == "benchmark":
            raw = await self._benchmark(task)
        elif cap == "apply_insight":
            raw = await self._apply_insight(task)
        else:
            raw = await self._improve_cycle(task)

        # Wrap raw dict in AgentResult so base run() can set execution_time_ms
        success = raw.get("status") in ("completed", "partial", "audit_complete", "benchmark_complete")
        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=success,
            output=raw,
            error=raw.get("error"),
            execution_time_ms=0,
            verified=False,
        )

    async def verify(self, result) -> bool:
        if not result:
            return False
        # result is an AgentResult — check the output dict inside it
        if isinstance(result, AgentResult):
            output = result.output
            if isinstance(output, dict):
                return output.get("status") in ("completed", "partial", "audit_complete", "benchmark_complete")
            return result.success
        # Fallback for raw dict
        if isinstance(result, dict):
            return result.get("status") in ("completed", "partial", "audit_complete", "benchmark_complete")
        return False

    # ------------------------------------------------------------------
    # AUDIT — Targeted subsystem inspection
    # ------------------------------------------------------------------

    async def _audit(self, task: AgentTask) -> dict:
        """Audit a specific subsystem or do a quick scan of all."""
        subsystem = task.params.get("subsystem", "all")
        findings = []

        if subsystem == "all":
            # Quick scan: check each subsystem's test command
            self.emit_progress("Running quick scan of all subsystems...")
            for name, info in AUDITABLE_SUBSYSTEMS.items():
                self.emit_progress(f"Checking {name}...")
                result = await self._check_subsystem(name, info)
                findings.append(result)
        else:
            # Deep audit: read the files and analyze with LLM
            info = AUDITABLE_SUBSYSTEMS[subsystem]
            self.emit_progress(f"Deep audit of {subsystem}...")
            result = await self._deep_audit_subsystem(subsystem, info)
            findings.append(result)

        # Prioritize findings
        issues = [f for f in findings if f.get("issues")]
        healthy = [f for f in findings if not f.get("issues")]

        return {
            "status": "audit_complete",
            "subsystem": subsystem,
            "total_checked": len(findings),
            "issues_found": sum(len(f.get("issues", [])) for f in findings),
            "healthy_count": len(healthy),
            "findings": findings,
            "priority_fixes": self._prioritize_issues(issues),
        }

    async def _check_subsystem(self, name: str, info: dict) -> dict:
        """Quick health check via test command."""
        try:
            result = await self.run_bash(info["test_cmd"], timeout=15)
            passed = result.get("exit_code", 1) == 0
            return {
                "subsystem": name,
                "description": info["description"],
                "passed": passed,
                "output": result.get("stdout", "")[:500],
                "error": result.get("stderr", "")[:500] if not passed else "",
                "issues": [] if passed else [{"type": "test_failure", "detail": result.get("stderr", "")[:300]}],
            }
        except Exception as e:
            return {
                "subsystem": name,
                "description": info["description"],
                "passed": False,
                "error": str(e),
                "issues": [{"type": "exception", "detail": str(e)[:300]}],
            }

    async def _deep_audit_subsystem(self, name: str, info: dict) -> dict:
        """Deep audit: read files and use LLM to find issues."""
        from app.services.llm_router import chat_completion

        # Read each file (truncated to context limit with explicit marker)
        file_contents = {}
        file_truncated = {}
        for fpath in info["files"]:
            full_path = self._project_root / fpath
            if full_path.exists():
                full_text = full_path.read_text()
                truncated = len(full_text) > MAX_FILE_CHARS
                content = full_text[:MAX_FILE_CHARS]
                if truncated:
                    content += f"\n\n# ... FILE TRUNCATED at {MAX_FILE_CHARS} of {len(full_text)} chars. Code continues beyond this point. Do NOT report issues about incomplete code near the end of this snippet.\n"
                file_contents[fpath] = content
                file_truncated[fpath] = truncated

        if not file_contents:
            return {
                "subsystem": name,
                "passed": False,
                "issues": [{"type": "missing_files", "detail": f"Files not found: {info['files']}"}],
            }

        # Run syntax check first
        quick_check = await self._check_subsystem(name, info)

        # LLM analysis — focused prompt to avoid essay responses
        files_text = "\n\n".join(
            f"=== {fp} ({len(c)} chars{', TRUNCATED — code continues beyond this snippet' if file_truncated.get(fp) else ''}) ===\n{c}"
            for fp, c in file_contents.items()
        )

        messages = [
            {"role": "system", "content": (
                "You are a code auditor. Analyze the code below for SPECIFIC, FIXABLE issues.\n\n"
                "CRITICAL RULES — FOLLOW ALL OF THESE:\n"
                "1. READ THE ACTUAL CODE before reporting. If a function exists in the code, do NOT report it as missing.\n"
                "2. The subsystem description lists what functions and features ALREADY EXIST. Do not report those as missing.\n"
                "3. Only report bugs you can point to with a specific line/function.\n"
                "4. Do NOT suggest adding features that already exist in the code.\n"
                "5. Do NOT report things as bugs just because they don't match your expectations — read what the code actually does.\n"
                "6. FILES MAY BE TRUNCATED. If you see '# ... FILE TRUNCATED' or the file ends mid-function, "
                "   the code CONTINUES beyond what you can see. Do NOT report 'incomplete function', 'missing closing bracket', "
                "   'truncated dictionary', or similar issues near the end of a truncated file.\n"
                "7. ONLY audit the subsystem you were asked about. Do NOT report issues in unrelated code that happens to be in the same file.\n"
                "8. If syntax checks passed (shown below), do NOT report syntax errors.\n\n"
                "For each REAL issue found, output a JSON object with:\n"
                "- type: bug|performance|missing_feature|dead_code|security|config\n"
                "- severity: critical|high|medium|low\n"
                "- file: which file\n"
                "- location: function/line description\n"
                "- description: what's wrong (one sentence)\n"
                "- fix: exact code change needed (old → new)\n\n"
                "Output ONLY a JSON array. No explanations. No essays.\n"
                "If no issues found, output: []\n"
                "PREFER returning [] over false positives. Only report issues you are CERTAIN about.\n"
                "A false positive wastes the team's time. An empty [] when things are fine is the RIGHT answer."
            )},
            {"role": "user", "content": (
                f"Subsystem: {name}\n"
                f"Description (these features ALREADY EXIST): {info['description']}\n"
                f"Quick check (syntax) passed: {quick_check.get('passed', False)}\n\n"
                f"Code:\n{files_text}"
            )},
        ]

        # Use reasoning tier (Opus 4.6) for deep audit — this is where model quality
        # matters most. Cheap models produce false positives and miss real issues.
        result = await chat_completion(
            messages=messages, model_tier="reasoning", max_tokens=2000, temperature=0.1,
        )

        issues = []
        if result and isinstance(result, dict):
            text = result.get("content", "")
            json_match = re.search(r'\[[\s\S]*\]', text)
            if json_match:
                try:
                    issues = json.loads(json_match.group())
                    if not isinstance(issues, list):
                        issues = []
                except json.JSONDecodeError:
                    issues = []

        return {
            "subsystem": name,
            "description": info["description"],
            "passed": quick_check.get("passed", False) and len(issues) == 0,
            "quick_check": quick_check,
            "issues": issues,
            "files_audited": list(file_contents.keys()),
        }

    def _prioritize_issues(self, subsystems_with_issues: list) -> list:
        """Sort all issues by severity."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_issues = []
        for sub in subsystems_with_issues:
            for issue in sub.get("issues", []):
                issue["subsystem"] = sub.get("subsystem", "unknown")
                all_issues.append(issue)
        return sorted(all_issues, key=lambda x: severity_order.get(x.get("severity", "low"), 4))

    # ------------------------------------------------------------------
    # FIX — Apply a single targeted fix
    # ------------------------------------------------------------------

    async def _fix(self, task: AgentTask) -> dict:
        """Apply a specific fix to a file using patch mode."""
        file_path = task.params.get("file_path", "")
        fix_type = task.params.get("fix_type", "patch")
        old_code = task.params.get("old_code", "")
        new_code = task.params.get("new_code", "")
        description = task.params.get("description", "Self-improvement fix")

        if not file_path:
            return {"status": "error", "error": "No file_path provided"}

        full_path = self._project_root / file_path
        if not full_path.exists():
            return {"status": "error", "error": f"File not found: {file_path}"}

        # Step 1: Backup
        self.emit_progress(f"Backing up {file_path}...")
        original_content = full_path.read_text()
        backup_path = full_path.with_suffix(full_path.suffix + ".self_improve_bak")
        backup_path.write_text(original_content)

        # Step 2: Apply fix
        self.emit_progress(f"Applying fix: {description}...")
        try:
            if fix_type == "patch" and old_code and new_code:
                if old_code not in original_content:
                    return {"status": "error", "error": "old_code not found in file — fix cannot be applied"}
                new_content = original_content.replace(old_code, new_code, 1)
                full_path.write_text(new_content)
            elif fix_type == "add" and new_code:
                # Append to file
                new_content = original_content + "\n" + new_code
                full_path.write_text(new_content)
            else:
                return {"status": "error", "error": f"Invalid fix_type or missing code: {fix_type}"}
        except Exception as e:
            # Rollback on write failure
            full_path.write_text(original_content)
            return {"status": "error", "error": f"Write failed: {e}"}

        # Step 3: Syntax check
        self.emit_progress("Verifying syntax...")
        syntax_result = await self.run_bash(
            f"python -c \"import ast; ast.parse(open('{file_path}').read()); print('OK')\"",
            timeout=10,
        )
        if syntax_result.get("exit_code", 1) != 0:
            # Rollback
            self.emit_progress("Syntax error — rolling back...")
            full_path.write_text(original_content)
            backup_path.unlink(missing_ok=True)
            return {
                "status": "rollback",
                "error": f"Syntax error after fix: {syntax_result.get('stderr', '')}",
                "description": description,
            }

        # Step 4: Log the fix
        self._log_fix(file_path, description, fix_type, old_code[:200], new_code[:200])

        # Clean up backup on success
        backup_path.unlink(missing_ok=True)

        return {
            "status": "completed",
            "file": file_path,
            "fix_type": fix_type,
            "description": description,
            "verified": True,
        }

    def _log_fix(self, file_path: str, description: str, fix_type: str, old: str, new: str):
        """Log a fix to the database (survives deploys) with /tmp fallback."""
        import hashlib

        old_hash = hashlib.sha256(old.encode()).hexdigest()[:16] if old else ""
        new_hash = hashlib.sha256(new.encode()).hexdigest()[:16] if new else ""

        # Primary: persist to database
        try:
            from app.db.database import SessionLocal
            from app.db.models import SelfFixLog
            db = SessionLocal()
            record = SelfFixLog(
                file_path=file_path,
                action=fix_type,
                old_content_hash=old_hash,
                new_content_hash=new_hash,
                description=description[:2000],
                success=True,
                verified=False,
            )
            db.add(record)
            db.commit()
            db.close()
            logger.info(f"[SELF-IMPROVE] Fix logged to database: {file_path}")
        except Exception as db_err:
            logger.debug(f"[SELF-IMPROVE] DB log failed (non-fatal): {db_err}")

            # Fallback: write to /tmp JSONL
            try:
                log_file = self._log_dir / "fix_history.jsonl"
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "file": file_path,
                    "description": description,
                    "fix_type": fix_type,
                    "old_hash": old_hash,
                    "new_hash": new_hash,
                }
                with open(log_file, "a") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass  # Don't let logging break fixes

    # ------------------------------------------------------------------
    # IMPROVE — Full improvement cycle
    # ------------------------------------------------------------------

    async def _improve_cycle(self, task: AgentTask) -> dict:
        """Run an improvement cycle: audit → report findings → optionally fix.

        GUARDRAILS:
        - Only audits the subsystem specified in 'focus' (never wanders to others)
        - Only fixes issues in files belonging to that subsystem
        - Max 3 fixes per cycle (hard-capped at 5)
        - All fixes are ephemeral (runtime patches wiped on deploy from git)
        - Default orchestrator routing sends 'audit' capability, not 'improve'
        """
        focus = task.params.get("focus", "all")
        max_fixes = min(task.params.get("max_fixes", 3), 5)  # Hard cap at 5

        # Determine which files are in-scope for this cycle
        allowed_files = set()
        if focus != "all" and focus in AUDITABLE_SUBSYSTEMS:
            allowed_files = set(AUDITABLE_SUBSYSTEMS[focus]["files"])
        elif focus == "all":
            for info in AUDITABLE_SUBSYSTEMS.values():
                allowed_files.update(info["files"])

        results = {
            "status": "completed",
            "cycle_started": datetime.now(timezone.utc).isoformat(),
            "focus": focus,
            "allowed_files": list(allowed_files),
            "audits": [],
            "fixes_applied": [],
            "fixes_failed": [],
            "fixes_rolled_back": [],
            "fixes_skipped_out_of_scope": [],
        }

        # Step 1: Audit (only the focused subsystem)
        self.emit_progress("Phase 1: Auditing...")
        audit_task = AgentTask(
            agent_name=self.name,
            instruction="Audit subsystems",
            params={"capability": "audit", "subsystem": focus},
        )
        audit_result = await self._audit(audit_task)
        results["audits"].append(audit_result)

        priority_fixes = audit_result.get("priority_fixes", [])
        if not priority_fixes:
            self.emit_progress("No issues found — system healthy.")
            results["status"] = "completed"
            results["summary"] = "Audit complete. No fixes needed."
            return results

        # Step 2: Apply fixes — ONLY in allowed files
        fixes_applied = 0
        for issue in priority_fixes[:max_fixes]:
            if fixes_applied >= max_fixes:
                break

            fix_info = issue.get("fix", "")
            file_path = issue.get("file", "")
            description = issue.get("description", "Unknown fix")

            if not fix_info or not file_path:
                continue

            # SCOPE CHECK: reject fixes to files outside the focused subsystem
            if allowed_files and file_path not in allowed_files:
                results["fixes_skipped_out_of_scope"].append({
                    "file": file_path,
                    "description": description,
                    "reason": f"File not in scope for '{focus}' subsystem. Allowed: {list(allowed_files)}",
                })
                logger.info(f"[SELF-IMPROVE] Skipping out-of-scope fix: {file_path} (focus={focus})")
                continue

            self.emit_progress(f"Phase 2: Fixing {description}...")

            # Parse fix — expect "old → new" format or structured data
            old_code = ""
            new_code = ""
            if isinstance(fix_info, dict):
                old_code = fix_info.get("old", "")
                new_code = fix_info.get("new", "")
            elif isinstance(fix_info, str) and "→" in fix_info:
                parts = fix_info.split("→", 1)
                old_code = parts[0].strip()
                new_code = parts[1].strip()
            else:
                results["fixes_failed"].append({
                    "description": description,
                    "reason": "Could not parse fix format",
                })
                continue

            # Apply the fix
            fix_task = AgentTask(
                agent_name=self.name,
                instruction="Apply fix",
                params={
                    "capability": "fix",
                    "file_path": file_path,
                    "fix_type": "patch",
                    "old_code": old_code,
                    "new_code": new_code,
                    "description": description,
                },
            )
            fix_result = await self._fix(fix_task)

            if fix_result.get("status") == "completed":
                results["fixes_applied"].append(fix_result)
                fixes_applied += 1
            elif fix_result.get("status") == "rollback":
                results["fixes_rolled_back"].append(fix_result)
            else:
                results["fixes_failed"].append(fix_result)

        skipped = len(results["fixes_skipped_out_of_scope"])
        results["summary"] = (
            f"Applied {len(results['fixes_applied'])} fixes, "
            f"{len(results['fixes_rolled_back'])} rolled back, "
            f"{len(results['fixes_failed'])} failed"
            f"{f', {skipped} skipped (out of scope)' if skipped else ''}."
        )
        return results

    # ------------------------------------------------------------------
    # BENCHMARK — Agent health checks
    # ------------------------------------------------------------------

    async def _benchmark(self, task: AgentTask) -> dict:
        """Run health checks on agents — syntax AND imports."""
        agent_name = task.params.get("agent_name", "")
        skip_imports = task.params.get("skip_imports", False)

        if agent_name:
            # Test specific agent
            return await self._test_single_agent(agent_name)

        # Test all registered agents
        self.emit_progress("Benchmarking all agents...")
        results = []

        # Get list of agent files
        skills_dir = self._project_root / "app" / "agents" / "skills"
        if not skills_dir.exists():
            return {"status": "error", "error": "Skills directory not found"}

        agent_files = sorted(skills_dir.glob("*_agent.py"))
        agent_files = [af for af in agent_files if not af.name.startswith("__")]

        # ── Phase 1: Syntax checks (fast, batched) ──
        check_script_parts = []
        for af in agent_files:
            check_script_parts.append(
                f'python3 -c "import ast; ast.parse(open(\'{af}\').read()); print(\'{af.stem}:SYNTAX_OK\')" 2>&1 || echo "{af.stem}:SYNTAX_FAIL"'
            )
        batch_size = 8
        all_outputs = []
        for i in range(0, len(check_script_parts), batch_size):
            batch = check_script_parts[i:i + batch_size]
            combined = " && ".join(batch)
            self.emit_progress(f"Syntax check {i+1}-{min(i+batch_size, len(agent_files))}...")
            batch_result = await self.run_bash(combined, timeout=30)
            all_outputs.append(batch_result.get("stdout", ""))

        syntax_output = "\n".join(all_outputs)

        # ── Phase 2: Import checks (slower but critical) ──
        import_output = ""
        if not skip_imports:
            import_parts = []
            for af in agent_files:
                module = af.stem
                import_parts.append(
                    f'python3 -c "from app.agents.skills.{module} import *; print(\'{module}:IMPORT_OK\')" 2>&1 || echo "{module}:IMPORT_FAIL"'
                )
            import_outputs = []
            for i in range(0, len(import_parts), batch_size):
                batch = import_parts[i:i + batch_size]
                combined = " && ".join(batch)
                self.emit_progress(f"Import check {i+1}-{min(i+batch_size, len(agent_files))}...")
                batch_result = await self.run_bash(combined, timeout=60)
                import_outputs.append(batch_result.get("stdout", ""))
                import_outputs.append(batch_result.get("stderr", ""))
            import_output = "\n".join(import_outputs)

        # ── Phase 3: Parse results ──
        for af in agent_files:
            name = af.stem
            syntax_ok = f"{name}:SYNTAX_OK" in syntax_output

            if skip_imports:
                import_ok = "skipped"
                import_error = ""
            else:
                import_ok = f"{name}:IMPORT_OK" in import_output
                import_error = ""
                if not import_ok:
                    # Extract the actual import error
                    for line in import_output.split("\n"):
                        if name in line and ("Error" in line or "Traceback" in line):
                            import_error = line.strip()[:300]
                            break

            syntax_error = ""
            if not syntax_ok:
                for line in syntax_output.split("\n"):
                    if name in line and "Error" in line:
                        syntax_error = line[:200]
                        break

            results.append({
                "agent": name,
                "syntax_ok": syntax_ok,
                "importable": import_ok,
                "syntax_error": syntax_error if not syntax_ok else "",
                "import_error": import_error if import_ok is False else "",
            })

        healthy = [r for r in results if r["syntax_ok"] and r["importable"] is True]
        syntax_only = [r for r in results if r["syntax_ok"] and r["importable"] is not True]
        broken = [r for r in results if not r["syntax_ok"]]
        import_broken = [r for r in results if r["syntax_ok"] and r["importable"] is False]

        return {
            "status": "benchmark_complete",
            "total_agents": len(results),
            "healthy": len(healthy),
            "syntax_only": len(syntax_only),
            "broken_syntax": len(broken),
            "broken_imports": len(import_broken),
            "results": results,
            "broken_agents": broken + import_broken,
        }

    async def _test_single_agent(self, agent_name: str) -> dict:
        """Deep test a single agent."""
        # Find the file
        file_name = f"{agent_name}.py" if agent_name.endswith("_agent") else f"{agent_name}_agent.py"
        file_path = self._project_root / "app" / "agents" / "skills" / file_name

        if not file_path.exists():
            return {"status": "error", "error": f"Agent file not found: {file_name}"}

        # Syntax check
        syntax = await self.run_bash(
            f"python -c \"import ast; ast.parse(open('{file_path}').read()); print('OK')\"",
            timeout=10,
        )

        # Import check
        module_name = file_path.stem
        import_check = await self.run_bash(
            f"python -c \"from app.agents.skills.{module_name} import *; print('OK')\"",
            timeout=15,
        )

        # Read capabilities
        content = file_path.read_text()[:MAX_FILE_CHARS]
        cap_count = content.count("AgentCapability(")

        return {
            "status": "benchmark_complete",
            "agent": agent_name,
            "file": str(file_path),
            "syntax_ok": syntax.get("exit_code", 1) == 0,
            "importable": import_check.get("exit_code", 1) == 0,
            "capabilities_count": cap_count,
            "file_size_chars": len(content),
            "errors": [
                e for e in [
                    syntax.get("stderr", "") if syntax.get("exit_code", 1) != 0 else "",
                    import_check.get("stderr", "") if import_check.get("exit_code", 1) != 0 else "",
                ] if e
            ],
        }

    # ------------------------------------------------------------------
    # APPLY INSIGHT — Implement a specific insight
    # ------------------------------------------------------------------

    async def _apply_insight(self, task: AgentTask) -> dict:
        """Take an insight from the absorber and try to implement it."""
        from app.services.llm_router import chat_completion

        insight = task.params.get("insight", {})
        if not insight:
            return {"status": "error", "error": "No insight provided"}

        insight_type = insight.get("type", "unknown")
        summary = insight.get("summary", "")
        detail = insight.get("detail", "")
        hint = insight.get("implementation_hint", "")

        self.emit_progress(f"Analyzing insight: {summary[:80]}...")

        # Step 1: Determine which file(s) need to change
        messages = [
            {"role": "system", "content": (
                "You are a code implementation planner. Given an insight about improving "
                "an AI system, determine the MINIMAL set of changes needed.\n\n"
                "Output ONLY a JSON object with:\n"
                "- target_file: string (relative path to modify)\n"
                "- change_type: patch|add_method|add_import|config_change\n"
                "- old_code: string (existing code to replace, for patch type)\n"
                "- new_code: string (replacement code)\n"
                "- description: string (one sentence)\n"
                "- risk: low|medium|high\n\n"
                "Keep changes SMALL. One file, one change. If the insight requires "
                "multiple files, pick the MOST IMPORTANT single change.\n"
                "Available files: app/services/orchestrator.py, app/core/system_prompt.py, "
                "app/services/memory.py, app/services/tool_calling.py, app/agents/skills/*.py"
            )},
            {"role": "user", "content": (
                f"Insight type: {insight_type}\n"
                f"Summary: {summary}\n"
                f"Detail: {detail}\n"
                f"Implementation hint: {hint}\n\n"
                "Plan the minimal code change."
            )},
        ]

        result = await chat_completion(
            messages=messages, model_tier="balanced", max_tokens=1500, temperature=0.2,
        )

        if not result or not isinstance(result, dict):
            return {"status": "error", "error": "LLM failed to plan implementation"}

        text = result.get("content", "")
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            return {"status": "error", "error": "LLM did not return valid JSON plan"}

        try:
            plan = json.loads(json_match.group())
        except json.JSONDecodeError:
            return {"status": "error", "error": "Invalid JSON in LLM response"}

        # Step 2: Verify the target file exists
        target = plan.get("target_file", "")
        if not target or not (self._project_root / target).exists():
            return {
                "status": "error",
                "error": f"Target file not found: {target}",
                "plan": plan,
            }

        # Step 3: Apply the change
        if plan.get("risk", "low") == "high":
            # Don't auto-apply high-risk changes
            return {
                "status": "partial",
                "message": "High-risk change planned but not auto-applied. Queued for review.",
                "plan": plan,
            }

        self.emit_progress(f"Applying change to {target}...")
        fix_task = AgentTask(
            agent_name=self.name,
            instruction="Apply insight fix",
            params={
                "capability": "fix",
                "file_path": target,
                "fix_type": plan.get("change_type", "patch"),
                "old_code": plan.get("old_code", ""),
                "new_code": plan.get("new_code", ""),
                "description": f"Insight: {summary}",
            },
        )
        fix_result = await self._fix(fix_task)

        return {
            "status": fix_result.get("status", "error"),
            "insight": summary,
            "plan": plan,
            "fix_result": fix_result,
        }
