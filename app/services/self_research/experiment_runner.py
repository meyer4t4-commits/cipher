"""
Experiment Runner — The core autonomous loop engine.

This is the heart of CipherResearch. It runs a continuous loop:
  snapshot → modify → test → evaluate → keep/discard → log → repeat

Designed to run as a background task while the operator sleeps.
"""

import asyncio
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.logging import logger

# Experiment storage directory
RESEARCH_DIR = Path(os.getenv("CIPHER_RESEARCH_DIR", "data/research"))
EXPERIMENTS_DIR = RESEARCH_DIR / "experiments"
SNAPSHOTS_DIR = RESEARCH_DIR / "snapshots"
LOGS_DIR = RESEARCH_DIR / "logs"


class ExperimentResult:
    """Result of a single experiment iteration."""

    def __init__(
        self,
        experiment_id: str,
        hypothesis: str,
        target_file: str,
        modification_type: str,  # "agent_improve", "prompt_tune", "capability_add", "bug_fix", "simplify"
        baseline_score: float,
        experiment_score: float,
        tests_passed: int,
        tests_total: int,
        kept: bool,
        duration_seconds: float,
        details: str = "",
        error: Optional[str] = None,
    ):
        self.experiment_id = experiment_id
        self.hypothesis = hypothesis
        self.target_file = target_file
        self.modification_type = modification_type
        self.baseline_score = baseline_score
        self.experiment_score = experiment_score
        self.tests_passed = tests_passed
        self.tests_total = tests_total
        self.kept = kept
        self.duration_seconds = duration_seconds
        self.details = details
        self.error = error
        self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def improvement(self) -> float:
        if self.baseline_score == 0:
            return 0
        return (self.experiment_score - self.baseline_score) / self.baseline_score

    @property
    def verdict(self) -> str:
        if self.error:
            return "ERROR"
        if self.kept:
            return "KEPT"
        return "DISCARDED"

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "hypothesis": self.hypothesis,
            "target_file": self.target_file,
            "modification_type": self.modification_type,
            "baseline_score": self.baseline_score,
            "experiment_score": self.experiment_score,
            "improvement": round(self.improvement, 4),
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "verdict": self.verdict,
            "kept": self.kept,
            "duration_seconds": round(self.duration_seconds, 1),
            "details": self.details,
            "error": self.error,
        }

    def to_log_line(self) -> str:
        """One-line summary for the experiment log."""
        emoji = "✅" if self.kept else ("❌" if self.error else "⏭️")
        return (
            f"{emoji} [{self.experiment_id[:8]}] {self.modification_type}: "
            f"{self.hypothesis[:60]}... "
            f"score: {self.baseline_score:.3f} → {self.experiment_score:.3f} "
            f"({self.improvement:+.1%}) tests: {self.tests_passed}/{self.tests_total} "
            f"→ {self.verdict} ({self.duration_seconds:.0f}s)"
        )


class FileSnapshot:
    """Manages file snapshots for safe experimentation with rollback."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    def take_snapshot(self, file_path: str) -> str:
        """Snapshot a file before modification. Returns snapshot ID."""
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        src = self.project_root / file_path
        if not src.exists():
            raise FileNotFoundError(f"Cannot snapshot: {file_path}")

        dest = SNAPSHOTS_DIR / snapshot_id
        dest.mkdir(parents=True, exist_ok=True)

        # Store the file content and metadata
        (dest / "content").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        (dest / "metadata.json").write_text(json.dumps({
            "file_path": file_path,
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "size_bytes": src.stat().st_size,
        }), encoding="utf-8")

        return snapshot_id

    def rollback(self, snapshot_id: str) -> bool:
        """Restore a file from a snapshot."""
        snap_dir = SNAPSHOTS_DIR / snapshot_id
        if not snap_dir.exists():
            logger.error(f"Snapshot not found: {snapshot_id}")
            return False

        metadata = json.loads((snap_dir / "metadata.json").read_text())
        content = (snap_dir / "content").read_text(encoding="utf-8")

        dest = self.project_root / metadata["file_path"]
        dest.write_text(content, encoding="utf-8")
        logger.info(f"Rolled back {metadata['file_path']} from snapshot {snapshot_id}")
        return True

    def cleanup_old(self, max_age_hours: int = 72):
        """Clean up snapshots older than max_age_hours."""
        cutoff = time.time() - (max_age_hours * 3600)
        for snap_dir in SNAPSHOTS_DIR.iterdir():
            if snap_dir.is_dir():
                meta_file = snap_dir / "metadata.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                        ts = datetime.fromisoformat(meta["timestamp"]).timestamp()
                        if ts < cutoff:
                            shutil.rmtree(snap_dir)
                    except Exception:
                        pass


class ExperimentLog:
    """Persistent experiment log — the research journal."""

    def __init__(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.log_file = LOGS_DIR / "experiment_log.jsonl"
        self.summary_file = LOGS_DIR / "summary.md"

    def append(self, result: ExperimentResult):
        """Append an experiment result to the log."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(result.to_dict()) + "\n")

        # Also append to human-readable summary
        with open(self.summary_file, "a", encoding="utf-8") as f:
            f.write(result.to_log_line() + "\n")

        logger.info(f"Experiment logged: {result.to_log_line()}")

    def get_recent(self, n: int = 20) -> list[dict]:
        """Get the N most recent experiments."""
        if not self.log_file.exists():
            return []

        lines = self.log_file.read_text().strip().split("\n")
        results = []
        for line in lines[-n:]:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return results

    def get_stats(self) -> dict:
        """Get aggregate stats from the experiment log."""
        all_results = self.get_recent(1000)
        if not all_results:
            return {"total": 0}

        kept = [r for r in all_results if r["kept"]]
        errors = [r for r in all_results if r.get("error")]
        discarded = [r for r in all_results if not r["kept"] and not r.get("error")]

        total_improvement = sum(r["improvement"] for r in kept) if kept else 0

        return {
            "total_experiments": len(all_results),
            "kept": len(kept),
            "discarded": len(discarded),
            "errors": len(errors),
            "keep_rate": round(len(kept) / len(all_results), 3) if all_results else 0,
            "total_improvement": round(total_improvement, 4),
            "avg_improvement_when_kept": round(total_improvement / len(kept), 4) if kept else 0,
            "total_runtime_hours": round(sum(r["duration_seconds"] for r in all_results) / 3600, 2),
        }

    def get_best_experiments(self, n: int = 5) -> list[dict]:
        """Get the N best experiments by improvement."""
        all_results = self.get_recent(1000)
        kept = [r for r in all_results if r["kept"]]
        kept.sort(key=lambda r: r["improvement"], reverse=True)
        return kept[:n]
