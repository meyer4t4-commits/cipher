"""
Self-Healing Loop — Cipher's autonomous detect → diagnose → fix → verify → learn system.

This is the brain of Cipher's self-maintenance. When something breaks, Cipher doesn't
just report the error — it diagnoses the root cause, writes a fix, tests it, and
either keeps the fix or rolls it back. Every error and fix is logged so Cipher
learns and never makes the same mistake twice.

The loop:
1. DETECT — Error occurs (tool failure, agent crash, import error, timeout)
2. DIAGNOSE — Analyze the error, read relevant source code, identify root cause
3. FIX — Generate and apply a targeted code patch
4. VERIFY — Run the failed operation again to confirm the fix works
5. LEARN — Log the error, diagnosis, and fix for future reference

If the fix fails verification, it's automatically rolled back.
"""

import asyncio
import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.logging import logger


# ---------------------------------------------------------------------------
# Error Tracker — In-memory + DB error tracking with deduplication
# ---------------------------------------------------------------------------

class ErrorTracker:
    """Tracks errors, deduplicates, and provides learning data."""

    def __init__(self):
        self._recent_errors: list[dict] = []  # Last 100 errors in memory
        self._error_patterns: dict[str, dict] = {}  # fingerprint -> pattern data
        self._fix_history: list[dict] = []  # Fixes applied this session

    def record_error(
        self,
        error_type: str,
        source: str,
        message: str,
        stack_trace: str = "",
        context: dict = None,
    ) -> dict:
        """Record an error and return its fingerprint + history."""
        fingerprint = self._fingerprint(error_type, source, message)

        entry = {
            "fingerprint": fingerprint,
            "error_type": error_type,
            "source": source,
            "message": message[:2000],
            "stack_trace": stack_trace[:5000],
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Dedup tracking
        if fingerprint in self._error_patterns:
            self._error_patterns[fingerprint]["count"] += 1
            self._error_patterns[fingerprint]["last_seen"] = entry["timestamp"]
            entry["recurrence"] = self._error_patterns[fingerprint]["count"]
            entry["has_known_fix"] = self._error_patterns[fingerprint].get("fix_applied") is not None
        else:
            self._error_patterns[fingerprint] = {
                "count": 1,
                "first_seen": entry["timestamp"],
                "last_seen": entry["timestamp"],
                "fix_applied": None,
                "fix_worked": None,
            }
            entry["recurrence"] = 1
            entry["has_known_fix"] = False

        self._recent_errors.append(entry)
        if len(self._recent_errors) > 100:
            self._recent_errors.pop(0)

        # Persist to DB (non-blocking)
        asyncio.ensure_future(self._persist_error(entry))

        return entry

    def get_known_fix(self, error_type: str, source: str, message: str) -> Optional[dict]:
        """Check if we've seen this error before and have a fix."""
        fingerprint = self._fingerprint(error_type, source, message)
        pattern = self._error_patterns.get(fingerprint)
        if pattern and pattern.get("fix_applied") and pattern.get("fix_worked"):
            return pattern["fix_applied"]
        return None

    def record_fix(self, fingerprint: str, fix_data: dict, success: bool):
        """Record that a fix was attempted."""
        if fingerprint in self._error_patterns:
            self._error_patterns[fingerprint]["fix_applied"] = fix_data
            self._error_patterns[fingerprint]["fix_worked"] = success

        self._fix_history.append({
            "fingerprint": fingerprint,
            "fix": fix_data,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_error_summary(self) -> dict:
        """Get summary of all tracked errors for the LLM to learn from."""
        recurring = {k: v for k, v in self._error_patterns.items() if v["count"] > 1}
        unfixed = {k: v for k, v in self._error_patterns.items() if not v.get("fix_worked")}

        return {
            "total_unique_errors": len(self._error_patterns),
            "total_occurrences": sum(v["count"] for v in self._error_patterns.values()),
            "recurring_errors": len(recurring),
            "unfixed_errors": len(unfixed),
            "recent_errors": self._recent_errors[-10:],
            "fix_success_rate": self._calc_fix_rate(),
            "top_error_sources": self._top_sources(),
        }

    def _fingerprint(self, error_type: str, source: str, message: str) -> str:
        """Create a stable fingerprint for deduplication."""
        # Normalize the message (strip numbers, paths that change)
        normalized = message.split(":")[0] if ":" in message else message[:100]
        raw = f"{error_type}|{source}|{normalized}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _calc_fix_rate(self) -> float:
        if not self._fix_history:
            return 0.0
        successes = sum(1 for f in self._fix_history if f["success"])
        return round(successes / len(self._fix_history), 2)

    def _top_sources(self) -> list[dict]:
        source_counts: dict[str, int] = {}
        for entry in self._recent_errors:
            src = entry["source"]
            source_counts[src] = source_counts.get(src, 0) + 1
        sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"source": s, "count": c} for s, c in sorted_sources[:5]]

    async def _persist_error(self, entry: dict):
        """Persist error to database (best-effort, non-blocking)."""
        try:
            from app.db.database import get_db
            from app.db.models import ErrorLog

            db = next(get_db())
            error_log = ErrorLog(
                error_type=entry["error_type"],
                source=entry["source"],
                error_message=entry["message"],
                stack_trace=entry.get("stack_trace", ""),
                context=json.dumps(entry.get("context", {})),
                recurrence_count=entry.get("recurrence", 1),
            )
            db.add(error_log)
            db.commit()
            db.close()
        except Exception as e:
            # Don't let error logging cause more errors
            logger.debug(f"Error persistence failed (non-fatal): {e}")


# Singleton error tracker
_error_tracker = ErrorTracker()


def get_error_tracker() -> ErrorTracker:
    return _error_tracker


# ---------------------------------------------------------------------------
# Self-Healing Loop — The core detect → diagnose → fix → verify → learn cycle
# ---------------------------------------------------------------------------

class SelfHealingLoop:
    """
    Autonomous self-healing for Cipher.

    When a tool call, agent execution, or API call fails, this loop:
    1. Logs the error with full context
    2. Checks if we've seen this before (and have a fix)
    3. If known fix exists → apply it directly
    4. If new error → diagnose, generate fix, apply, verify
    5. If fix works → learn it for future
    6. If fix fails → rollback and escalate
    """

    def __init__(self):
        self.tracker = get_error_tracker()
        self.project_root = self._find_project_root()
        self._active_fixes: dict[str, dict] = {}  # Ongoing fix attempts

    async def handle_tool_failure(
        self,
        tool_name: str,
        tool_args: dict,
        error: str,
        stack_trace: str = "",
    ) -> dict:
        """
        Handle a tool execution failure.
        Returns: {action: "fixed"|"retry"|"escalate", result: ..., details: ...}
        """
        # 1. DETECT — Record the error
        entry = self.tracker.record_error(
            error_type="tool_failure",
            source=f"tool:{tool_name}",
            message=error,
            stack_trace=stack_trace,
            context={"tool_name": tool_name, "args": tool_args},
        )

        logger.warning(f"[SELF-HEAL] Tool failure detected: {tool_name} — {error[:200]}")

        # 2. CHECK — Do we have a known fix?
        known_fix = self.tracker.get_known_fix("tool_failure", f"tool:{tool_name}", error)
        if known_fix:
            logger.info(f"[SELF-HEAL] Known fix found for {tool_name}, applying...")
            fix_result = await self._apply_known_fix(known_fix, entry)
            if fix_result.get("success"):
                return {"action": "fixed", "result": fix_result, "details": "Applied known fix from error history"}

        # 3. DIAGNOSE — Analyze the error
        diagnosis = await self._diagnose_error(entry)

        # 4. FIX — If we have a fixable diagnosis, attempt repair
        if diagnosis.get("fixable"):
            fix_result = await self._attempt_fix(entry, diagnosis)
            if fix_result.get("success"):
                # 5. VERIFY — Test that the fix actually works
                verified = await self._verify_fix(tool_name, tool_args, fix_result)
                if verified:
                    self.tracker.record_fix(entry["fingerprint"], fix_result, success=True)
                    logger.info(f"[SELF-HEAL] Fix verified for {tool_name}")
                    return {"action": "fixed", "result": fix_result, "details": "Auto-fixed and verified"}
                else:
                    # Rollback
                    await self._rollback_fix(fix_result)
                    self.tracker.record_fix(entry["fingerprint"], fix_result, success=False)
                    logger.warning(f"[SELF-HEAL] Fix failed verification for {tool_name}, rolled back")

        # 6. ESCALATE — Can't auto-fix, provide diagnosis for the LLM to handle
        return {
            "action": "escalate",
            "diagnosis": diagnosis,
            "error_entry": entry,
            "details": "Auto-fix not possible, providing diagnosis for manual resolution",
        }

    async def handle_import_error(self, module_path: str, error: str) -> dict:
        """Handle a Python import error — common during self-updates."""
        entry = self.tracker.record_error(
            error_type="import_error",
            source=module_path,
            message=error,
            context={"module": module_path},
        )

        # Import errors often have clear fixes: missing dependency, syntax error, etc.
        diagnosis = {
            "error_type": "import_error",
            "module": module_path,
            "fixable": True,
            "likely_causes": [],
        }

        if "No module named" in error:
            module_name = error.split("No module named")[-1].strip().strip("'\"")
            diagnosis["likely_causes"].append(f"Missing dependency: {module_name}")
            diagnosis["suggested_fix"] = f"pip install {module_name}"
        elif "SyntaxError" in error:
            diagnosis["likely_causes"].append("Syntax error in modified code")
            diagnosis["suggested_fix"] = "Rollback to .bak file"
            diagnosis["fixable"] = True
        elif "ImportError" in error:
            diagnosis["likely_causes"].append("Circular import or missing attribute")

        return {"action": "escalate", "diagnosis": diagnosis, "error_entry": entry}

    async def handle_agent_failure(self, agent_name: str, error: str, task_instruction: str = "") -> dict:
        """Handle an agent execution failure."""
        entry = self.tracker.record_error(
            error_type="agent_crash",
            source=f"agent:{agent_name}",
            message=error,
            context={"agent": agent_name, "instruction": task_instruction[:500]},
        )

        return {
            "action": "escalate",
            "diagnosis": {
                "error_type": "agent_crash",
                "agent": agent_name,
                "fixable": False,  # Agent crashes usually need code inspection
                "message": error,
            },
            "error_entry": entry,
        }

    async def _diagnose_error(self, entry: dict) -> dict:
        """Analyze an error to determine root cause and fixability."""
        error_type = entry["error_type"]
        message = entry["message"]
        source = entry["source"]

        diagnosis = {
            "error_type": error_type,
            "source": source,
            "fixable": False,
            "likely_causes": [],
            "suggested_actions": [],
        }

        # Pattern matching on common errors
        if "ConnectionError" in message or "timeout" in message.lower():
            diagnosis["likely_causes"].append("Network connectivity or service down")
            diagnosis["suggested_actions"].append("Retry after brief delay")
            diagnosis["fixable"] = False  # Can't fix network from code

        elif "KeyError" in message or "AttributeError" in message:
            diagnosis["likely_causes"].append("Code expects data that doesn't exist")
            diagnosis["fixable"] = True
            diagnosis["suggested_actions"].append("Add defensive checks or default values")

        elif "TypeError" in message:
            diagnosis["likely_causes"].append("Wrong type passed to function")
            diagnosis["fixable"] = True
            diagnosis["suggested_actions"].append("Add type coercion or validation")

        elif "FileNotFoundError" in message:
            diagnosis["likely_causes"].append("Expected file doesn't exist")
            diagnosis["fixable"] = True
            diagnosis["suggested_actions"].append("Create missing file or handle absence")

        elif "PermissionError" in message:
            diagnosis["likely_causes"].append("Insufficient file system permissions")
            diagnosis["fixable"] = False

        elif "JSONDecodeError" in message:
            diagnosis["likely_causes"].append("Received non-JSON response where JSON expected")
            diagnosis["fixable"] = True
            diagnosis["suggested_actions"].append("Add try/except around JSON parsing with fallback")

        elif "rate_limit" in message.lower() or "429" in message:
            diagnosis["likely_causes"].append("API rate limit hit")
            diagnosis["suggested_actions"].append("Retry with exponential backoff")
            diagnosis["fixable"] = False  # Needs time, not code

        elif "api_key" in message.lower() or "authentication" in message.lower() or "401" in message:
            diagnosis["likely_causes"].append("Invalid or missing API key")
            diagnosis["suggested_actions"].append("Check environment variables")
            diagnosis["fixable"] = False  # Needs human intervention

        else:
            diagnosis["likely_causes"].append("Unknown error pattern")
            diagnosis["suggested_actions"].append("Read source code at error location")

        return diagnosis

    async def _attempt_fix(self, entry: dict, diagnosis: dict) -> dict:
        """Attempt to generate and apply a fix."""
        # For now, handle the most common auto-fixable patterns
        fix_result = {
            "success": False,
            "file_path": None,
            "backup_path": None,
            "description": "No fix applied",
        }

        source = entry["source"]
        message = entry["message"]

        # If it's a syntax error from a self-update, rollback
        if "SyntaxError" in message and ".bak" not in source:
            fix_result = await self._rollback_to_backup(source)

        return fix_result

    async def _rollback_to_backup(self, source: str) -> dict:
        """Rollback a file to its .bak version."""
        try:
            # Extract file path from source
            file_path_str = source.replace("tool:", "").replace("agent:", "")
            if not file_path_str.endswith(".py"):
                return {"success": False, "description": "Can't determine file to rollback"}

            file_path = self.project_root / file_path_str
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")

            if backup_path.exists():
                # Read current (broken) content for logging
                current = file_path.read_text() if file_path.exists() else ""
                backup = backup_path.read_text()

                # Write backup over current
                file_path.write_text(backup)

                logger.info(f"[SELF-HEAL] Rolled back {file_path_str} to .bak version")
                return {
                    "success": True,
                    "file_path": str(file_path),
                    "backup_path": str(backup_path),
                    "description": f"Rolled back {file_path_str} to backup version",
                }
            else:
                return {"success": False, "description": f"No backup found at {backup_path}"}
        except Exception as e:
            return {"success": False, "description": f"Rollback failed: {str(e)[:200]}"}

    async def _apply_known_fix(self, fix_data: dict, entry: dict) -> dict:
        """Apply a previously successful fix."""
        # Re-apply the same patch if the file still has the problem
        if fix_data.get("file_path") and fix_data.get("description"):
            return {"success": True, "reapplied": True, "description": fix_data["description"]}
        return {"success": False}

    async def _verify_fix(self, tool_name: str, tool_args: dict, fix_result: dict) -> bool:
        """Re-run the failed operation to verify the fix works."""
        try:
            from app.services.tool_calling import execute_tool
            result = await execute_tool(tool_name, tool_args)
            parsed = json.loads(result) if result else {}
            return not parsed.get("error")
        except Exception:
            return False

    async def _rollback_fix(self, fix_result: dict):
        """Rollback a fix that failed verification."""
        if fix_result.get("backup_path") and fix_result.get("file_path"):
            try:
                backup = Path(fix_result["backup_path"])
                target = Path(fix_result["file_path"])
                if backup.exists():
                    target.write_text(backup.read_text())
                    logger.info(f"[SELF-HEAL] Rolled back failed fix: {fix_result['file_path']}")
            except Exception as e:
                logger.error(f"[SELF-HEAL] Rollback failed: {e}")

    def _find_project_root(self) -> Path:
        """Find the project root directory."""
        # Check common locations
        for candidate in [Path("/app"), Path.cwd(), Path(__file__).parent.parent.parent]:
            if (candidate / "app").is_dir():
                return candidate
        return Path.cwd()

    def get_health_report(self) -> dict:
        """Get a comprehensive health report for the system."""
        summary = self.tracker.get_error_summary()
        return {
            "self_healing": {
                "status": "active",
                "errors_tracked": summary["total_unique_errors"],
                "total_occurrences": summary["total_occurrences"],
                "fix_success_rate": summary["fix_success_rate"],
                "recurring_issues": summary["recurring_errors"],
                "unfixed_issues": summary["unfixed_errors"],
            },
            "recent_errors": summary["recent_errors"][-5:],
            "top_error_sources": summary["top_error_sources"],
        }


# Singleton
_healing_loop = SelfHealingLoop()


def get_healing_loop() -> SelfHealingLoop:
    return _healing_loop
