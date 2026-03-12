"""
Chronos Agent - Energy-Aware Scheduling Agent for Cipher AI.
Handles time blocking, conflict resolution, deep work protection, and cognitive load management.
Optimizes schedule based on user's energy profile throughout the day.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


class ChronosAgent(BaseAgent):
    """
    Energy-aware precision scheduling agent.
    Manages time blocking, conflict resolution, and cognitive load optimization.
    """

    # Energy profile: maps hours (0-23) to energy levels
    # Peak hours: 9am-12pm (optimal for hard cognitive work)
    # High hours: 1pm-4pm, 8pm-11pm (good for focused work)
    # Moderate hours: 7am-8am, 5pm-7pm (routine tasks, meetings)
    # Low hours: 0am-6am, 11pm-midnight (recovery, light tasks, admin)
    # Recovery hours: built in (rest periods)
    ENERGY_PROFILE: dict[str, list[int]] = {
        "peak": [9, 10, 11, 12],
        "high": [13, 14, 15, 16, 20, 21, 22, 23],
        "moderate": [7, 8, 17, 18, 19],
        "low": [0, 1, 2, 3, 4, 5, 6],
        "recovery": [6, 12, 18],
    }

    # Task-to-energy mapping: what energy level is required for each task type
    TASK_ENERGY_MAP: dict[str, str] = {
        "coding": "peak",
        "creative": "peak",
        "planning": "high",
        "research": "high",
        "deep_work": "peak",
        "meeting": "moderate",
        "email": "low",
        "admin": "low",
        "review": "moderate",
        "standup": "moderate",
        "break": "recovery",
        "exercise": "low",
        "default": "moderate",
    }

    def __init__(self):
        """Initialize the Chronos Agent."""
        super().__init__(
            name="chronos_agent",
            description="Energy-aware precision scheduling — time blocking, conflict resolution, and cognitive load management",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="schedule_block",
                    description="Schedule a time block with energy-aware placement",
                    category="scheduling",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="reschedule_conflicts",
                    description="Detect and auto-resolve scheduling conflicts",
                    category="scheduling",
                    timeout_seconds=45,
                ),
                AgentCapability(
                    name="deep_work_guard",
                    description="Protect deep work sessions from interruptions",
                    category="scheduling",
                    timeout_seconds=20,
                ),
                AgentCapability(
                    name="daily_plan",
                    description="Generate energy-optimized daily plan",
                    category="scheduling",
                    timeout_seconds=60,
                ),
                AgentCapability(
                    name="sync_calendars",
                    description="Sync between Apple Calendar and Google Calendar",
                    category="scheduling",
                    timeout_seconds=45,
                ),
            ],
        )

        # Initialize data directory
        self.data_dir = Path("data/chronos")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Define file paths for persistence
        self.schedule_file = self.data_dir / "schedule.json"
        self.deep_work_file = self.data_dir / "deep_work_guards.json"
        self.calendar_sync_file = self.data_dir / "calendar_sync.json"
        self.friction_log_file = self.data_dir / "friction_log.json"

        # Initialize data files if they don't exist
        self._initialize_data_files()

    def _initialize_data_files(self) -> None:
        """Initialize JSON data files if they don't exist."""
        if not self.schedule_file.exists():
            self.schedule_file.write_text(json.dumps({"schedule": [], "metadata": {}}, indent=2))

        if not self.deep_work_file.exists():
            self.deep_work_file.write_text(json.dumps({"guards": [], "metadata": {}}, indent=2))

        if not self.calendar_sync_file.exists():
            self.calendar_sync_file.write_text(json.dumps({"synced_events": [], "last_sync": None}, indent=2))

        if not self.friction_log_file.exists():
            self.friction_log_file.write_text(json.dumps({"skipped_tasks": {}, "metadata": {}}, indent=2))

    async def validate(self, task: AgentTask) -> bool:
        """
        Validate Chronos scheduling task.

        Args:
            task: The task to validate

        Returns:
            True if task is valid, False otherwise
        """
        if not await super().validate(task):
            return False

        operation = task.params.get("operation")
        if not operation:
            logger.warning(f"Task {task.task_id}: Missing 'operation' parameter")
            return False

        # Validate operation-specific parameters
        if operation == "schedule_block":
            required = ["event_name", "duration_minutes", "task_type"]
            for param in required:
                if param not in task.params:
                    logger.warning(f"Task {task.task_id}: Missing '{param}' for schedule_block")
                    return False

        elif operation == "deep_work_guard":
            if "start_hour" not in task.params or "end_hour" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'start_hour' or 'end_hour' for deep_work_guard")
                return False

        elif operation == "sync_calendars":
            if "source" not in task.params or "destination" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing source/destination for sync_calendars")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """
        Execute scheduling operation.

        Args:
            task: The task to execute

        Returns:
            AgentResult with operation output
        """
        operation = task.params.get("operation")

        try:
            if operation == "schedule_block":
                return await self._schedule_block(task)
            elif operation == "reschedule_conflicts":
                return await self._reschedule_conflicts(task)
            elif operation == "deep_work_guard":
                return await self._deep_work_guard(task)
            elif operation == "daily_plan":
                return await self._daily_plan(task)
            elif operation == "sync_calendars":
                return await self._sync_calendars(task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )

        except Exception as e:
            logger.error(f"Chronos operation '{operation}' failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _schedule_block(self, task: AgentTask) -> AgentResult:
        """
        Schedule a time block with energy-aware placement.
        Finds the optimal time slot matching the task's energy requirements.

        Args:
            task: Task containing event_name, duration_minutes, task_type, preferred_date

        Returns:
            AgentResult with scheduled time slot
        """
        event_name = task.params.get("event_name")
        duration_minutes = task.params.get("duration_minutes")
        task_type = task.params.get("task_type", "default").lower()
        preferred_date = task.params.get("preferred_date")

        # Determine required energy level
        required_energy = self.TASK_ENERGY_MAP.get(task_type, "moderate")

        # Get available hours with matching energy level
        optimal_hours = self.ENERGY_PROFILE.get(required_energy, self.ENERGY_PROFILE["moderate"])

        # Find first available slot
        scheduled_time = self._find_available_slot(
            duration_minutes,
            optimal_hours,
            preferred_date,
        )

        if not scheduled_time:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"No available {required_energy}-energy slot found for {event_name}",
            )

        # Save to schedule
        schedule_data = json.loads(self.schedule_file.read_text())
        new_block = {
            "event_id": task.task_id,
            "event_name": event_name,
            "task_type": task_type,
            "energy_level": required_energy,
            "duration_minutes": duration_minutes,
            "scheduled_time": scheduled_time.isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "status": "scheduled",
        }
        schedule_data["schedule"].append(new_block)
        self.schedule_file.write_text(json.dumps(schedule_data, indent=2))

        logger.info(f"Scheduled {event_name} at {scheduled_time} ({required_energy} energy)")

        output = {
            "operation": "schedule_block",
            "event_name": event_name,
            "scheduled_time": scheduled_time.isoformat(),
            "duration_minutes": duration_minutes,
            "energy_level": required_energy,
            "status": "scheduled",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _reschedule_conflicts(self, task: AgentTask) -> AgentResult:
        """
        Detect and auto-resolve scheduling conflicts.
        Scans for overlapping blocks and bumps lower-priority items.

        Args:
            task: Task with optional target_date

        Returns:
            AgentResult with conflict resolution details
        """
        schedule_data = json.loads(self.schedule_file.read_text())
        blocks = schedule_data.get("schedule", [])

        # Group by date and detect conflicts
        conflicts = []
        for i, block1 in enumerate(blocks):
            for block2 in blocks[i + 1 :]:
                if self._blocks_overlap(block1, block2):
                    conflicts.append({
                        "block1": block1["event_name"],
                        "block2": block2["event_name"],
                        "resolution": f"Rescheduling {block2['event_name']} to next available slot",
                    })

                    # Find new slot for block2 (lower priority)
                    energy_level = block2.get("energy_level", "moderate")
                    optimal_hours = self.ENERGY_PROFILE.get(energy_level, self.ENERGY_PROFILE["moderate"])
                    new_time = self._find_available_slot(
                        block2["duration_minutes"],
                        optimal_hours,
                    )

                    if new_time:
                        block2["scheduled_time"] = new_time.isoformat()
                        logger.info(f"Rescheduled {block2['event_name']} to {new_time}")

        # Save updated schedule
        self.schedule_file.write_text(json.dumps(schedule_data, indent=2))

        output = {
            "operation": "reschedule_conflicts",
            "conflicts_detected": len(conflicts),
            "conflicts": conflicts,
            "status": "resolved" if conflicts else "no_conflicts",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _deep_work_guard(self, task: AgentTask) -> AgentResult:
        """
        Protect deep work sessions from interruptions.
        Marks a time range as protected and blocks conflicting assignments.

        Args:
            task: Task with start_hour, end_hour, session_name

        Returns:
            AgentResult with guard details
        """
        start_hour = task.params.get("start_hour")
        end_hour = task.params.get("end_hour")
        session_name = task.params.get("session_name", "Deep Work Session")
        guard_date = task.params.get("guard_date")

        guard_data = json.loads(self.deep_work_file.read_text())

        new_guard = {
            "guard_id": task.task_id,
            "session_name": session_name,
            "start_hour": start_hour,
            "end_hour": end_hour,
            "guard_date": guard_date or datetime.utcnow().date().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "status": "active",
        }
        guard_data["guards"].append(new_guard)
        self.deep_work_file.write_text(json.dumps(guard_data, indent=2))

        # Check for conflicts with existing schedule
        schedule_data = json.loads(self.schedule_file.read_text())
        conflicting_events = []
        for block in schedule_data.get("schedule", []):
            block_hour = datetime.fromisoformat(block["scheduled_time"]).hour
            if start_hour <= block_hour < end_hour:
                conflicting_events.append(block["event_name"])

        logger.info(f"Deep work guard set for {session_name}: {start_hour}:00-{end_hour}:00")

        output = {
            "operation": "deep_work_guard",
            "session_name": session_name,
            "protected_hours": f"{start_hour}:00-{end_hour}:00",
            "guard_date": new_guard["guard_date"],
            "conflicting_events": conflicting_events,
            "status": "active",
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _daily_plan(self, task: AgentTask) -> AgentResult:
        """
        Generate energy-optimized daily plan.
        Structures the day based on energy profile and scheduled events.

        Args:
            task: Task with optional plan_date

        Returns:
            AgentResult with structured daily plan
        """
        plan_date = task.params.get("plan_date") or datetime.utcnow().date().isoformat()

        plan = {
            "date": plan_date,
            "time_slots": [],
            "energy_curve": [],
            "break_recommendations": [],
        }

        # Build hourly plan
        for hour in range(24):
            energy_level = self._get_energy_level(hour)
            slot = {
                "hour": hour,
                "time": f"{hour:02d}:00",
                "energy_level": energy_level,
                "recommended_activities": self._get_activities_for_energy(energy_level),
            }
            plan["time_slots"].append(slot)

            # Track energy curve
            plan["energy_curve"].append({
                "hour": hour,
                "energy": self._energy_to_numeric(energy_level),
            })

        # Add break recommendations
        # Suggest breaks during transitions and before low-energy periods
        plan["break_recommendations"] = [
            {"time": "12:00-13:00", "reason": "Peak-to-high transition; good meal break"},
            {"time": "17:00-18:00", "reason": "Afternoon energy dip; recovery activity"},
            {"time": "20:00-21:00", "reason": "Evening wind-down; prepare for recovery"},
        ]

        # Load scheduled events for this day
        schedule_data = json.loads(self.schedule_file.read_text())
        day_events = [
            b for b in schedule_data.get("schedule", [])
            if b["scheduled_time"].startswith(plan_date)
        ]

        plan["scheduled_events"] = [
            {
                "name": e["event_name"],
                "time": e["scheduled_time"].split("T")[1][:5],
                "duration_minutes": e["duration_minutes"],
                "energy_match": e.get("energy_level", "moderate"),
            }
            for e in day_events
        ]

        output = {
            "operation": "daily_plan",
            "date": plan_date,
            "time_slots_count": len(plan["time_slots"]),
            "scheduled_events_count": len(day_events),
            "plan": plan,
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _sync_calendars(self, task: AgentTask) -> AgentResult:
        """
        Sync between Apple Calendar and Google Calendar.
        Requires Google Calendar API credentials (OAuth) to be configured.

        Args:
            task: Task with source, destination, direction

        Returns:
            AgentResult with sync details or configuration instructions
        """
        source = task.params.get("source", "apple")
        destination = task.params.get("destination", "google")
        direction = task.params.get("direction", "bidirectional")

        # Check for Google Calendar API credentials
        google_creds = getattr(settings, 'google_calendar_credentials', '') or ''

        if not google_creds:
            output = {
                "operation": "sync_calendars",
                "source": source,
                "destination": destination,
                "direction": direction,
                "status": "not_configured",
                "error": "Calendar sync requires Google Calendar API credentials which are not configured.",
                "setup_instructions": [
                    "1. Go to console.cloud.google.com and create a project",
                    "2. Enable the Google Calendar API",
                    "3. Create OAuth 2.0 credentials",
                    "4. Set GOOGLE_CALENDAR_CREDENTIALS environment variable with the JSON credentials",
                ],
                "note": "Local time blocking, conflict detection, and daily planning all work without this — only cross-calendar sync requires Google API setup.",
            }

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output=output,
                error="Calendar sync not configured — Google Calendar API credentials required",
            )

        # If credentials exist, attempt real Google Calendar sync
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds_data = json.loads(google_creds)
            creds = Credentials.from_authorized_user_info(creds_data)
            service = build('calendar', 'v3', credentials=creds)

            # Fetch events from Google Calendar
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=50,
                singleEvents=True,
                orderBy='startTime',
            ).execute()
            google_events = events_result.get('items', [])

            # Load local events
            local_events = json.loads(self.events_file.read_text()) if self.events_file.exists() else []

            synced_count = 0
            if direction in ("bidirectional", "pull"):
                # Pull Google events into local schedule
                for g_event in google_events:
                    local_events.append({
                        "id": g_event.get("id", ""),
                        "title": g_event.get("summary", "Untitled"),
                        "start": g_event.get("start", {}).get("dateTime", ""),
                        "end": g_event.get("end", {}).get("dateTime", ""),
                        "source": "google_calendar",
                    })
                    synced_count += 1

                self.events_file.write_text(json.dumps(local_events, indent=2))

            sync_data = json.loads(self.calendar_sync_file.read_text())
            sync_result = {
                "synced_at": datetime.utcnow().isoformat(),
                "source": source,
                "destination": destination,
                "direction": direction,
                "events_synced": synced_count,
                "conflicts_resolved": 0,
            }
            sync_data["synced_events"].append(sync_result)
            sync_data["last_sync"] = datetime.utcnow().isoformat()
            self.calendar_sync_file.write_text(json.dumps(sync_data, indent=2))

            output = {
                "operation": "sync_calendars",
                "source": source,
                "destination": destination,
                "direction": direction,
                "status": "completed",
                "events_synced": synced_count,
                "message": f"Successfully synced {synced_count} events from Google Calendar",
            }

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output=output,
            )

        except ImportError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output={"error": "Google Calendar API library not installed. Run: pip install google-api-python-client google-auth"},
                error="Missing google-api-python-client dependency",
            )
        except Exception as e:
            logger.error(f"Google Calendar sync failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                output={"error": str(e)},
                error=f"Calendar sync failed: {e}",
            )

    def _get_energy_level(self, hour: int) -> str:
        """Get energy level for a given hour."""
        for level, hours in self.ENERGY_PROFILE.items():
            if hour in hours:
                return level
        return "moderate"

    def _energy_to_numeric(self, energy_level: str) -> int:
        """Convert energy level to numeric value for graphing."""
        mapping = {
            "peak": 5,
            "high": 4,
            "moderate": 3,
            "low": 1,
            "recovery": 2,
        }
        return mapping.get(energy_level, 3)

    def _get_activities_for_energy(self, energy_level: str) -> list[str]:
        """Get recommended activities for an energy level."""
        activities = {
            "peak": ["Deep coding", "Creative work", "Complex problem-solving"],
            "high": ["Focused work", "Research", "Planning"],
            "moderate": ["Meetings", "Reviews", "Administrative tasks"],
            "low": ["Email", "Light admin", "Routine tasks"],
            "recovery": ["Breaks", "Exercise", "Meditation", "Rest"],
        }
        return activities.get(energy_level, ["General work"])

    def _find_available_slot(
        self,
        duration_minutes: int,
        optimal_hours: list[int],
        preferred_date: Optional[str] = None,
    ) -> Optional[datetime]:
        """
        Find the next available time slot matching optimal hours.

        Args:
            duration_minutes: Length of time block needed
            optimal_hours: Hours to prefer (matching energy level)
            preferred_date: Preferred date (YYYY-MM-DD)

        Returns:
            Datetime of available slot, or None if not found
        """
        schedule_data = json.loads(self.schedule_file.read_text())
        blocks = schedule_data.get("schedule", [])

        # Get start date
        if preferred_date:
            try:
                start_date = datetime.fromisoformat(preferred_date).date()
            except ValueError:
                start_date = datetime.utcnow().date()
        else:
            start_date = datetime.utcnow().date()

        # Search for available slot in next 7 days
        for day_offset in range(7):
            search_date = start_date + timedelta(days=day_offset)

            for hour in optimal_hours:
                candidate_time = datetime.combine(search_date, datetime.min.time()).replace(hour=hour)

                # Check if slot is available
                is_available = True
                for block in blocks:
                    block_time = datetime.fromisoformat(block["scheduled_time"])
                    block_duration = timedelta(minutes=block["duration_minutes"])
                    block_end = block_time + block_duration

                    candidate_end = candidate_time + timedelta(minutes=duration_minutes)

                    # Check for overlap
                    if candidate_time < block_end and candidate_end > block_time:
                        is_available = False
                        break

                # Check for deep work guards
                if is_available:
                    guard_data = json.loads(self.deep_work_file.read_text())
                    for guard in guard_data.get("guards", []):
                        if guard["guard_date"] == search_date.isoformat():
                            if guard["start_hour"] <= hour < guard["end_hour"]:
                                is_available = False
                                break

                if is_available:
                    return candidate_time

        return None

    def _blocks_overlap(self, block1: dict[str, Any], block2: dict[str, Any]) -> bool:
        """Check if two schedule blocks overlap."""
        try:
            time1 = datetime.fromisoformat(block1["scheduled_time"])
            time2 = datetime.fromisoformat(block2["scheduled_time"])

            end1 = time1 + timedelta(minutes=block1["duration_minutes"])
            end2 = time2 + timedelta(minutes=block2["duration_minutes"])

            return time1 < end2 and time2 < end1
        except (KeyError, ValueError):
            return False

    async def verify(self, result: AgentResult) -> bool:
        """
        Verify scheduling operation result.

        Args:
            result: The result to verify

        Returns:
            True if result is valid, False otherwise
        """
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        operation = result.output.get("operation")
        if not operation:
            logger.warning(f"Result {result.task_id}: Missing 'operation' in output")
            return False

        # Verify operation-specific output
        if operation == "schedule_block":
            required = ["event_name", "scheduled_time", "duration_minutes"]
            for field in required:
                if field not in result.output:
                    logger.warning(f"Result {result.task_id}: Missing '{field}' in schedule_block output")
                    return False

        elif operation == "daily_plan":
            if "plan" not in result.output:
                logger.warning(f"Result {result.task_id}: Missing 'plan' in daily_plan output")
                return False

        elif operation == "deep_work_guard":
            if "session_name" not in result.output:
                logger.warning(f"Result {result.task_id}: Missing 'session_name' in guard output")
                return False

        # Track friction: check if this task was skipped/ignored before
        self._track_friction(result)

        return True

    def _track_friction(self, result: AgentResult) -> None:
        """
        Track how many times scheduled items are ignored/skipped.
        Flag for re-evaluation if ignored 2+ times.

        Args:
            result: The execution result to track
        """
        friction_data = json.loads(self.friction_log_file.read_text())
        task_id = result.task_id

        if not result.success:
            skipped = friction_data.get("skipped_tasks", {})
            count = skipped.get(task_id, 0) + 1
            skipped[task_id] = count

            if count >= 2:
                logger.warning(f"Task {task_id} ignored {count} times; flagging for re-evaluation")

            friction_data["skipped_tasks"] = skipped
            self.friction_log_file.write_text(json.dumps(friction_data, indent=2))
