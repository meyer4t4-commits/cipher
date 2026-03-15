"""
Cipher Internal Cron Registry — Autonomous scheduled task execution.

Manages all recurring tasks that Cipher runs independently:
- Apex Asset Hunter (daily 7 AM)
- Expansion Pulse (weekly Monday 9 AM)
- Health checks, report generation, etc.

Uses asyncio scheduling with cron expression parsing.
Persists task state to disk so tasks survive restarts.
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.logging import logger


class CronTask:
    """A single scheduled cron task."""

    def __init__(
        self,
        task_id: str,
        name: str,
        cron_expression: str,
        agent_name: str,
        operation: str,
        params: dict,
        enabled: bool = True,
        description: str = "",
    ):
        self.task_id = task_id
        self.name = name
        self.cron_expression = cron_expression
        self.agent_name = agent_name
        self.operation = operation
        self.params = params
        self.enabled = enabled
        self.description = description
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.run_count: int = 0
        self.last_result: Optional[dict] = None
        self.last_error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "cron_expression": self.cron_expression,
            "agent_name": self.agent_name,
            "operation": self.operation,
            "params": self.params,
            "enabled": self.enabled,
            "description": self.description,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "last_error": self.last_error,
        }


def _parse_cron_field(field: str, min_val: int, max_val: int) -> list[int]:
    """Parse a single cron field into list of matching values."""
    values = set()

    for part in field.split(","):
        part = part.strip()

        if part == "*":
            values.update(range(min_val, max_val + 1))
        elif "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            start = min_val if base == "*" else int(base)
            values.update(range(start, max_val + 1, step))
        elif "-" in part:
            low, high = part.split("-", 1)
            values.update(range(int(low), int(high) + 1))
        else:
            values.add(int(part))

    return sorted(values)


def next_cron_time(cron_expr: str, after: Optional[datetime] = None) -> datetime:
    """Calculate the next run time for a cron expression.

    Format: minute hour day_of_month month day_of_week
    """
    if after is None:
        after = datetime.now()

    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr}")

    minutes = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    days = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12)
    weekdays = _parse_cron_field(parts[4], 0, 6)

    # Start from next minute
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Search up to 366 days ahead
    for _ in range(366 * 24 * 60):
        if (
            candidate.month in months
            and candidate.day in days
            and (candidate.weekday() + 1) % 7 in weekdays  # Convert Python Mon=0 → cron Sun=0
            and candidate.hour in hours
            and candidate.minute in minutes
        ):
            return candidate
        candidate += timedelta(minutes=1)

    raise ValueError(f"No matching time found for cron: {cron_expr}")


class CronRegistry:
    """Registry and executor for Cipher's internal cron tasks."""

    def __init__(self):
        self._tasks: dict[str, CronTask] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._state_file = Path("./data/cron_state.json")
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._executor_callback: Optional[Callable] = None

        # Register default tasks first, then overlay persisted state
        self._register_defaults()
        self._load_state()

        logger.info(f"CronRegistry initialized with {len(self._tasks)} tasks")

    def set_executor(self, callback: Callable):
        """Set the callback for executing agent tasks."""
        self._executor_callback = callback

    def _register_defaults(self):
        """Register all default Cipher cron tasks."""

        # === APEX ASSET HUNTER — Daily 7 AM ===
        self.register(CronTask(
            task_id="apex-asset-hunter",
            name="Apex Asset Hunter Daily Scan",
            cron_expression="0 7 * * *",
            agent_name="deal_flow_agent",
            operation="daily_scan",
            params={
                "city": "",
                "state": "NJ",
                "county": "Gloucester",
                "max_price": 350000,
                "min_margin": 50000,
                "min_roi": 15,
            },
            description="Daily property scan — NJ/PA corridor, $50K+ margin filter",
        ))

        # === EXPANSION PULSE — Monday 9 AM ===
        self.register(CronTask(
            task_id="expansion-pulse",
            name="Global Expansion Pulse",
            cron_expression="0 9 * * 1",
            agent_name="scout_agent",
            operation="scan_industry",
            params={
                "industry": "e-commerce",
                "location": "Northeast United States",
                "revenue_min": "50K",
            },
            description="Weekly B2B lead scan — automation-poor companies in NE US",
        ))

        # === CIPHER HEALTH CHECK — Every 4 Hours ===
        self.register(CronTask(
            task_id="cipher-health-check",
            name="Cipher Self-Health Check",
            cron_expression="0 */4 * * *",
            agent_name="monitor_agent",
            operation="health_check",
            params={"target": "self"},
            description="Self-diagnostic health check every 4 hours",
        ))

        # === DAILY BIBLE UPDATE — 10 PM ===
        self.register(CronTask(
            task_id="daily-bible-update",
            name="Bible Document Sync",
            cron_expression="0 22 * * *",
            agent_name="file_agent",
            operation="sync",
            params={"targets": ["BIBLE_CIPHER_ELYSIAN.md", "BIBLE_MARK_MEYER_MASTER.md"]},
            description="Nightly bible document sync and update",
        ))

        # === MORNING BRIEFING — 7 AM ===
        self.register(CronTask(
            task_id="morning-briefing",
            name="Morning Briefing",
            cron_expression="0 7 * * *",
            agent_name="research_agent",
            operation="briefing",
            params={"scope": "all_ventures"},
            description="Daily morning briefing across all ventures",
        ))

        # === WEEKLY PROGRESS REPORT — Sunday 8 PM ===
        self.register(CronTask(
            task_id="weekly-progress-report",
            name="Weekly Progress Report",
            cron_expression="0 20 * * 0",
            agent_name="research_agent",
            operation="progress_report",
            params={"scope": "weekly"},
            description="Weekly progress summary across all ventures",
        ))

        # === EVENING WORK SPRINT — Mon-Sat 8 PM ===
        self.register(CronTask(
            task_id="evening-work-sprint",
            name="Evening Work Sprint",
            cron_expression="0 20 * * 1-6",
            agent_name="research_agent",
            operation="sprint_plan",
            params={"duration_hours": 2},
            description="Nightly 2-hour prioritized action plan",
        ))

        # === LEAD GENERATION SCANNER — Mon-Sat 8:30 PM ===
        self.register(CronTask(
            task_id="lead-generation-scanner",
            name="TallowRoots Lead Scanner",
            cron_expression="30 20 * * 1-6",
            agent_name="scout_agent",
            operation="scan_industry",
            params={
                "industry": "wholesale retail",
                "location": "Mantua NJ",
            },
            description="Nightly wholesale prospect scan for TallowRoots",
        ))

        # =====================================================
        # OMNI-SAVANT ORGANIZATION — Central Nervous System
        # =====================================================

        # === LIFE-AUDIT PULSE — Daily 9 PM ===
        self.register(CronTask(
            task_id="life-audit-nightly",
            name="Life-Audit Nightly Pulse",
            cron_expression="0 21 * * *",
            agent_name="archivist_agent",
            operation="context_brief",
            params={
                "topic": "all_ventures_daily_reconciliation",
                "scope": "daily",
                "actions": ["reconcile", "prioritize", "optimize"],
            },
            description="Nightly life audit — reconcile tasks, rank top 3 objectives, identify dead time",
        ))

        # === LIFE-AUDIT PULSE — Monday 6 AM Strategic Briefing ===
        self.register(CronTask(
            task_id="life-audit-monday",
            name="Life-Audit Monday Strategic Briefing",
            cron_expression="0 6 * * 1",
            agent_name="synthesis_agent",
            operation="executive_brief",
            params={
                "topic": "weekly_strategic_overview",
                "scope": "all_ventures",
                "depth": "exhaustive",
            },
            description="Monday 6 AM strategic briefing — weekly priorities, cross-agent sync, optimization plan",
        ))

        # === SENTINEL EMAIL SCAN — Every 2 Hours (8AM-10PM) ===
        self.register(CronTask(
            task_id="sentinel-email-scan",
            name="Sentinel Email Monitor",
            cron_expression="0 8,10,12,14,16,18,20,22 * * *",
            agent_name="sentinel_agent",
            operation="monitor_email",
            params={"scan_depth": "unread"},
            description="Proactive email scan every 2 hours — urgency detection and deadline extraction",
        ))

        # === SENTINEL ALERT DIGEST — Daily 8 PM ===
        self.register(CronTask(
            task_id="sentinel-daily-digest",
            name="Sentinel Daily Alert Digest",
            cron_expression="0 20 * * *",
            agent_name="sentinel_agent",
            operation="alert_digest",
            params={"timeframe": "today"},
            description="Daily prioritized alert digest with recommended actions",
        ))

        # === CHRONOS DAILY PLAN — Daily 6:30 AM ===
        self.register(CronTask(
            task_id="chronos-daily-plan",
            name="Chronos Energy-Optimized Daily Plan",
            cron_expression="30 6 * * *",
            agent_name="chronos_agent",
            operation="daily_plan",
            params={"include_breaks": True},
            description="Morning daily plan optimized by energy levels and cognitive load",
        ))

        # === ARCHIVIST INDEX SWEEP — Daily 11 PM ===
        self.register(CronTask(
            task_id="archivist-index-sweep",
            name="Archivist Cross-Agent Index",
            cron_expression="0 23 * * *",
            agent_name="archivist_agent",
            operation="cross_agent_search",
            params={"query": "__index_sweep__", "full_reindex": True},
            description="Nightly sweep — index all new agent outputs into the knowledge base",
        ))

        # === MODEL REGISTRY AUTO-UPDATE — Daily 3 AM ===
        self.register(CronTask(
            task_id="model-registry-update",
            name="Model Registry Auto-Update",
            cron_expression="0 3 * * *",
            agent_name="research_agent",
            operation="update_model_registry",
            params={"run_benchmarks": True, "check_new_models": True},
            description="Nightly model discovery + benchmark — keeps routing tables current with latest releases",
        ))

        # === X/TWITTER SCANNER — Every 3 Hours (7AM-11PM) ===
        self.register(CronTask(
            task_id="x-scanner",
            name="X/Twitter Intelligence Scanner",
            cron_expression="0 7,10,13,16,19,22 * * *",
            agent_name="sentinel_agent",
            operation="scan_x",
            params={"use_browser": True},
            description="X/Twitter scan for AI news, crypto signals, and competitor activity",
        ))

        # === IDLE SELF-TRAINING — Every 15 Minutes ===
        # Checks if user is idle and runs self-improvement if so.
        # Won't actually train unless user has been idle 30+ minutes
        # and there's a 2-hour cooldown between training sessions.
        self.register(CronTask(
            task_id="idle-self-training",
            name="Idle Self-Training Check",
            cron_expression="*/15 * * * *",
            agent_name="self_improvement_agent",
            operation="idle_train",
            params={"trigger": "idle_check"},
            description="Check if user is idle and run self-improvement training",
        ))

        # === SWARM: MEMORY CONSOLIDATION — Daily 3 AM ===
        self.register(CronTask(
            task_id="swarm-memory-consolidate",
            name="Agent Memory Consolidation",
            cron_expression="0 3 * * *",
            agent_name="swarm_agent",
            operation="memory_consolidate",
            params={},
            description="Consolidate agent memories into patterns — merges repeated observations",
        ))

        # === SWARM: KNOWLEDGE GRAPH STATS — Daily 6 AM ===
        self.register(CronTask(
            task_id="swarm-graph-maintenance",
            name="Knowledge Graph Maintenance",
            cron_expression="0 6 * * *",
            agent_name="swarm_agent",
            operation="graph_stats",
            params={},
            description="Check knowledge graph health and compile statistics",
        ))

        # === AUTONOMOUS SELF-IMPROVEMENT LOOP — Daily 2 AM ===
        # The real self-learning loop: audit → experiment → measure → keep/discard
        self.register(CronTask(
            task_id="autonomous-self-improve",
            name="Autonomous Self-Improvement Loop",
            cron_expression="0 2 * * *",
            agent_name="self_improvement_agent",
            operation="improve",
            params={"focus": "all", "max_fixes": 3},
            description="Nightly autonomous improvement — audit all subsystems, apply safe fixes, verify",
        ))

        # === TALLOWROOTS COMPETITOR SCAN — Weekly Wednesday 10 PM ===
        self.register(CronTask(
            task_id="tallowroots-competitor-scan",
            name="TallowRoots Competitor Intelligence",
            cron_expression="0 22 * * 3",
            agent_name="research_agent",
            operation="competitor_analysis",
            params={
                "competitors": ["Vintage Tradition", "FATCO", "Primally Pure", "Beef Tallow Co"],
                "industry": "tallow skincare",
            },
            description="Weekly competitor scan for TallowRoots — tracks pricing, products, and market moves",
        ))

    def register(self, task: CronTask) -> None:
        """Register a cron task (won't overwrite existing unless forced)."""
        if task.task_id not in self._tasks:
            # Calculate next run
            try:
                task.next_run = next_cron_time(task.cron_expression)
            except Exception as e:
                logger.warning(f"Invalid cron for {task.task_id}: {e}")
            self._tasks[task.task_id] = task

    def unregister(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save_state()
            return True
        return False

    def enable(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._save_state()
            return True
        return False

    def disable(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            self._save_state()
            return True
        return False

    def list_tasks(self) -> list[dict]:
        return [t.to_dict() for t in self._tasks.values()]

    def get_task(self, task_id: str) -> Optional[dict]:
        task = self._tasks.get(task_id)
        return task.to_dict() if task else None

    async def start(self):
        """Start the cron execution loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("CronRegistry execution loop started")

    async def stop(self):
        """Stop the cron execution loop."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        self._save_state()
        logger.info("CronRegistry execution loop stopped")

    async def _run_loop(self):
        """Main cron loop — checks every 30 seconds for tasks due."""
        while self._running:
            try:
                now = datetime.now()
                for task in self._tasks.values():
                    if not task.enabled or not task.next_run:
                        continue
                    if now >= task.next_run:
                        await self._execute_task(task)
                        # Calculate next run
                        try:
                            task.next_run = next_cron_time(task.cron_expression, after=now)
                        except Exception:
                            task.enabled = False
                        self._save_state()
            except Exception as e:
                logger.error(f"Cron loop error: {e}")

            await asyncio.sleep(30)  # Check every 30 seconds

    async def _execute_task(self, task: CronTask):
        """Execute a single cron task via the agent executor."""
        logger.info(f"Cron executing: {task.task_id} ({task.name})")
        task.last_run = datetime.now()
        task.run_count += 1

        # Special handling for idle self-training — bypasses normal agent executor
        # because it needs to check idle state and run its own training loop
        if task.operation == "idle_train":
            try:
                from app.services.idle_trainer import maybe_train
                result = await maybe_train()
                task.last_result = result
                task.last_error = None if result.get("action") != "error" else result.get("error")
                logger.info(f"Idle training check: {result.get('action', 'unknown')}")
            except Exception as e:
                task.last_error = str(e)
                logger.error(f"Idle training failed: {e}")
            return

        if self._executor_callback:
            try:
                result = await self._executor_callback(
                    agent_name=task.agent_name,
                    operation=task.operation,
                    params=task.params,
                )
                task.last_result = result if isinstance(result, dict) else {"success": True}
                task.last_error = None
                logger.info(f"Cron task {task.task_id} completed successfully")
            except Exception as e:
                task.last_error = str(e)
                logger.error(f"Cron task {task.task_id} failed: {e}")
        else:
            task.last_error = "No executor callback set"
            logger.warning(f"Cron task {task.task_id} skipped — no executor callback")

    def _save_state(self):
        """Persist task state to disk."""
        try:
            state = {}
            for task_id, task in self._tasks.items():
                state[task_id] = {
                    "enabled": task.enabled,
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "run_count": task.run_count,
                    "last_error": task.last_error,
                }
            self._state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save cron state: {e}")

    def _load_state(self):
        """Load persisted task state from disk."""
        if not self._state_file.exists():
            return
        try:
            state = json.loads(self._state_file.read_text())
            for task_id, data in state.items():
                if task_id in self._tasks:
                    task = self._tasks[task_id]
                    task.enabled = data.get("enabled", True)
                    task.run_count = data.get("run_count", 0)
                    task.last_error = data.get("last_error")
                    if data.get("last_run"):
                        task.last_run = datetime.fromisoformat(data["last_run"])
        except Exception as e:
            logger.warning(f"Failed to load cron state: {e}")


# Singleton
_registry: Optional[CronRegistry] = None


def get_cron_registry() -> CronRegistry:
    global _registry
    if _registry is None:
        _registry = CronRegistry()
    return _registry
