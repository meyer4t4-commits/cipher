"""
Autonomous Research Loop — Cipher's overnight self-improvement engine.

Inspired by Karpathy's autoresearch: an LLM agent iterates on code autonomously,
keeping improvements and discarding regressions. The operator sleeps while
Cipher evolves.

ARCHITECTURE:
  1. Load research_program.md for operator directives (what to focus on)
  2. Run baseline self-tests → get baseline score
  3. Ask the LLM to propose an experiment (which file to modify, how, why)
  4. Snapshot the target file
  5. Apply the LLM-generated modification
  6. Run self-tests again → get experiment score
  7. If score improved and all critical tests pass → KEEP (commit)
  8. If score regressed or tests broke → DISCARD (rollback)
  9. Log the result
  10. Repeat forever until manually stopped

The loop does NOT pause to ask the operator.
The operator may be asleep. Cipher is autonomous.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.logging import logger
from app.services.self_research.experiment_runner import (
    ExperimentLog,
    ExperimentResult,
    FileSnapshot,
    RESEARCH_DIR,
)
from app.services.self_research.self_test import run_self_tests

# Where the operator's directives live
RESEARCH_PROGRAM_PATH = RESEARCH_DIR / "research_program.md"
DEFAULT_RESEARCH_PROGRAM = """# Cipher Research Program

## Operator Directives
Focus areas for autonomous self-improvement:

### Priority 1: Model Optimization (SELF-UPDATING)
- Periodically evaluate all available LLM models against Cipher-specific benchmarks
- When new models are discovered, benchmark them and promote if superior
- Track model performance over time to detect regressions
- Ensure the best model is used for each agent type (coding, reasoning, creative, etc.)
- Run model evaluations at the START of every research session

### Priority 2: Agent Reliability
- Improve error handling in agents that fail silently
- Add retry logic where network calls are involved
- Ensure all agents validate their inputs before execution
- Ensure agents that generate media (images, videos) properly return results

### Priority 3: Response Quality
- Improve system prompt for more natural, less robotic responses
- Ensure Cipher uses its agents instead of suggesting bash scripts
- Improve fact-checking accuracy on financial and date-related claims
- Ensure every response uses the correct model tier for the task

### Priority 4: Performance
- Reduce latency in the orchestrator pipeline
- Optimize memory recall relevance scoring
- Cache frequently-used LLM responses

### Priority 5: Capability Expansion
- Improve vision service error handling
- Add better image format support
- Enhance agent chaining for multi-step workflows

## Constraints
- NEVER modify database schemas or migration files
- NEVER change API endpoint paths (would break iOS client)
- NEVER remove existing agent capabilities
- NEVER change the .env configuration format
- Prefer simplification over complexity (Karpathy's autoresearch principle)
- All changes must pass the self-test suite
"""

# LLM model to use for generating experiments
RESEARCH_MODEL = None  # Auto-detect at runtime


def _get_research_model() -> str:
    """Get the best available model for research generation."""
    global RESEARCH_MODEL
    if RESEARCH_MODEL:
        return RESEARCH_MODEL

    if os.getenv("ANTHROPIC_API_KEY"):
        RESEARCH_MODEL = "anthropic/claude-sonnet-4-20250514"
    elif os.getenv("OPENAI_API_KEY"):
        RESEARCH_MODEL = "openai/gpt-4o"
    elif os.getenv("GROQ_API_KEY"):
        RESEARCH_MODEL = "groq/llama-3.1-70b-versatile"
    else:
        RESEARCH_MODEL = "anthropic/claude-3-5-haiku-20241022"

    return RESEARCH_MODEL


def _load_research_program() -> str:
    """Load the operator's research program directives."""
    if RESEARCH_PROGRAM_PATH.exists():
        return RESEARCH_PROGRAM_PATH.read_text(encoding="utf-8")

    # Create default research program
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_PROGRAM_PATH.write_text(DEFAULT_RESEARCH_PROGRAM, encoding="utf-8")
    return DEFAULT_RESEARCH_PROGRAM


def _get_project_root() -> str:
    """Get the Cipher project root."""
    candidates = [
        Path(__file__).parent.parent.parent.parent,
        Path.cwd(),
    ]
    for c in candidates:
        if (c / "app" / "main.py").exists():
            return str(c)
    return str(Path.cwd())


async def _propose_experiment(
    research_program: str,
    recent_experiments: list[dict],
    baseline_results: dict,
    project_root: str,
) -> Optional[dict]:
    """
    Ask the LLM to propose the next experiment.

    Returns:
        {
            "hypothesis": str,           # What we're trying
            "target_file": str,           # Relative path to modify
            "modification_type": str,     # Type of change
            "new_content": str,           # The modified file content
            "reasoning": str,             # Why this change should help
        }
    """
    import litellm

    model = _get_research_model()

    # Build context about recent experiments
    recent_summary = ""
    if recent_experiments:
        recent_lines = []
        for exp in recent_experiments[-10:]:
            recent_lines.append(
                f"  - [{exp['verdict']}] {exp['modification_type']}: {exp['hypothesis'][:80]}... "
                f"(score: {exp['baseline_score']:.3f}→{exp['experiment_score']:.3f})"
            )
        recent_summary = "Recent experiments:\n" + "\n".join(recent_lines)

    # Build context about current test failures
    failures_summary = ""
    if baseline_results.get("failures"):
        failure_lines = [f"  - {f['name']}: {f.get('error', 'failed')}" for f in baseline_results["failures"]]
        failures_summary = "Current test failures:\n" + "\n".join(failure_lines)

    # Read available files for modification
    available_files = []
    root = Path(project_root)
    for pattern in ["app/services/*.py", "app/agents/skills/*.py", "app/core/system_prompt.py"]:
        for f in root.glob(pattern):
            rel = str(f.relative_to(root))
            size = f.stat().st_size
            available_files.append(f"  - {rel} ({size} bytes)")

    prompt = f"""You are Cipher's autonomous research engine. Your job is to propose ONE experiment
that will improve Cipher's capabilities or fix a known issue.

## Operator Research Program
{research_program}

## Current Self-Test Results
Aggregate score: {baseline_results.get('aggregate_score', 'N/A')}
Tests passed: {baseline_results.get('tests_passed', 0)}/{baseline_results.get('tests_total', 0)}
{failures_summary}

{recent_summary}

## Available Files to Modify
{chr(10).join(available_files[:30])}

## Rules
1. Propose exactly ONE modification to ONE file
2. Simpler is better — don't add complexity unless the improvement justifies it
3. Removing unnecessary code and getting equal results is a WIN (simplification)
4. Don't repeat experiments that were already DISCARDED (check recent list)
5. Focus on the operator's priority areas
6. The modification must be complete — provide the FULL new file content
7. Stay within the constraints listed in the research program

## Response Format (JSON only, no markdown)
{{
    "hypothesis": "Brief description of what this experiment tests",
    "target_file": "relative/path/to/file.py",
    "modification_type": "agent_improve|prompt_tune|bug_fix|simplify|capability_add",
    "reasoning": "Why this change should improve the score",
    "new_content": "THE COMPLETE NEW FILE CONTENT (not a diff, the whole file)"
}}

Respond with ONLY the JSON object, no other text."""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000,
            temperature=0.7,
        )

        content = response.choices[0].message.content.strip()

        # Try to parse JSON (handle potential markdown wrapping)
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        proposal = json.loads(content)

        # Validate required fields
        required = ["hypothesis", "target_file", "modification_type", "new_content"]
        if not all(k in proposal for k in required):
            logger.warning(f"Experiment proposal missing required fields: {proposal.keys()}")
            return None

        return proposal

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse experiment proposal: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to generate experiment proposal: {e}")
        return None


async def run_single_experiment(
    research_program: str,
    recent_experiments: list[dict],
    project_root: str,
) -> Optional[ExperimentResult]:
    """
    Run a single experiment iteration:
    baseline → propose → snapshot → modify → test → keep/discard
    """
    import uuid

    experiment_id = f"exp_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    logger.info(f"=== Starting experiment {experiment_id} ===")

    # Step 1: Run baseline tests
    logger.info("Running baseline self-tests...")
    baseline = await run_self_tests()
    baseline_score = baseline.get("aggregate_score", 0)
    logger.info(f"Baseline score: {baseline_score:.4f} ({baseline['tests_passed']}/{baseline['tests_total']} passed)")

    # Step 2: Propose an experiment
    logger.info("Generating experiment proposal...")
    proposal = await _propose_experiment(
        research_program=research_program,
        recent_experiments=recent_experiments,
        baseline_results=baseline,
        project_root=project_root,
    )

    if not proposal:
        return ExperimentResult(
            experiment_id=experiment_id,
            hypothesis="Failed to generate proposal",
            target_file="",
            modification_type="error",
            baseline_score=baseline_score,
            experiment_score=baseline_score,
            tests_passed=baseline["tests_passed"],
            tests_total=baseline["tests_total"],
            kept=False,
            duration_seconds=time.time() - start_time,
            error="LLM failed to generate a valid experiment proposal",
        )

    target_file = proposal["target_file"]
    hypothesis = proposal["hypothesis"]
    mod_type = proposal.get("modification_type", "unknown")
    new_content = proposal["new_content"]

    logger.info(f"Experiment: {hypothesis}")
    logger.info(f"Target: {target_file} ({mod_type})")

    # Step 3: Snapshot the file
    snapshot = FileSnapshot(project_root)
    try:
        full_path = Path(project_root) / target_file
        if not full_path.exists():
            return ExperimentResult(
                experiment_id=experiment_id,
                hypothesis=hypothesis,
                target_file=target_file,
                modification_type=mod_type,
                baseline_score=baseline_score,
                experiment_score=baseline_score,
                tests_passed=baseline["tests_passed"],
                tests_total=baseline["tests_total"],
                kept=False,
                duration_seconds=time.time() - start_time,
                error=f"Target file not found: {target_file}",
            )

        snapshot_id = snapshot.take_snapshot(target_file)
        logger.info(f"Snapshot taken: {snapshot_id}")
    except Exception as e:
        return ExperimentResult(
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            target_file=target_file,
            modification_type=mod_type,
            baseline_score=baseline_score,
            experiment_score=baseline_score,
            tests_passed=baseline["tests_passed"],
            tests_total=baseline["tests_total"],
            kept=False,
            duration_seconds=time.time() - start_time,
            error=f"Snapshot failed: {e}",
        )

    # Step 4: Apply the modification
    try:
        full_path.write_text(new_content, encoding="utf-8")
        logger.info(f"Modification applied to {target_file}")
    except Exception as e:
        snapshot.rollback(snapshot_id)
        return ExperimentResult(
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            target_file=target_file,
            modification_type=mod_type,
            baseline_score=baseline_score,
            experiment_score=baseline_score,
            tests_passed=baseline["tests_passed"],
            tests_total=baseline["tests_total"],
            kept=False,
            duration_seconds=time.time() - start_time,
            error=f"Write failed: {e}",
        )

    # Step 5: Run post-modification tests
    logger.info("Running post-modification self-tests...")
    try:
        # Small delay to let any module reloads settle
        await asyncio.sleep(1)
        experiment_results = await run_self_tests()
        experiment_score = experiment_results.get("aggregate_score", 0)
        tests_passed = experiment_results["tests_passed"]
        tests_total = experiment_results["tests_total"]
    except Exception as e:
        logger.error(f"Post-modification tests crashed: {e}")
        snapshot.rollback(snapshot_id)
        return ExperimentResult(
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            target_file=target_file,
            modification_type=mod_type,
            baseline_score=baseline_score,
            experiment_score=0,
            tests_passed=0,
            tests_total=baseline["tests_total"],
            kept=False,
            duration_seconds=time.time() - start_time,
            error=f"Post-modification tests crashed: {e}",
        )

    # Step 6: Keep or Discard decision
    # Karpathy's principle: improvement must justify complexity
    improvement = experiment_score - baseline_score
    keep = False

    if experiment_score > baseline_score and tests_passed >= baseline["tests_passed"]:
        # Clear improvement — keep it
        keep = True
        logger.info(f"✅ KEEPING: score improved {baseline_score:.4f} → {experiment_score:.4f} (+{improvement:.4f})")
    elif experiment_score == baseline_score and mod_type == "simplify":
        # Equal score but simpler code — also a win (Karpathy's simplification principle)
        keep = True
        logger.info(f"✅ KEEPING (simplification): score unchanged but code simplified")
    else:
        # Regression or no improvement — rollback
        keep = False
        snapshot.rollback(snapshot_id)
        logger.info(f"⏭️ DISCARDED: score {baseline_score:.4f} → {experiment_score:.4f} ({improvement:+.4f})")

    duration = time.time() - start_time

    return ExperimentResult(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        target_file=target_file,
        modification_type=mod_type,
        baseline_score=baseline_score,
        experiment_score=experiment_score,
        tests_passed=tests_passed,
        tests_total=tests_total,
        kept=keep,
        duration_seconds=duration,
        details=proposal.get("reasoning", ""),
    )


async def run_autonomous_loop(
    max_experiments: int = 100,
    max_hours: float = 8.0,
    progress_callback=None,
) -> dict:
    """
    Run the full autonomous research loop.

    Like Karpathy's autoresearch, this runs indefinitely (up to limits)
    and does NOT pause to ask the operator for permission.

    Args:
        max_experiments: Maximum number of experiments to run
        max_hours: Maximum runtime in hours
        progress_callback: Optional async callback for real-time updates

    Returns:
        Summary of all experiments run
    """
    logger.info("=" * 60)
    logger.info("CIPHER AUTONOMOUS RESEARCH LOOP STARTING")
    logger.info(f"Max experiments: {max_experiments}, Max hours: {max_hours}")
    logger.info("=" * 60)

    project_root = _get_project_root()
    research_program = _load_research_program()
    experiment_log = ExperimentLog()
    snapshot_mgr = FileSnapshot(project_root)

    start_time = time.time()
    max_runtime = max_hours * 3600

    # ── Phase 0: Model Evaluation (self-updating) ──
    # Run at the START of every research session to keep model routing optimal.
    logger.info("Phase 0: Running model evaluation for self-updating routing...")
    try:
        from app.services.self_research.model_evaluator import (
            compare_models, propose_routing_updates,
        )
        from app.services.llm_router import (
            MODEL_REGISTRY, save_model_benchmarks,
        )

        # Get all model IDs from registry
        all_models = [info["model_id"] for info in MODEL_REGISTRY.values()]

        if progress_callback:
            await progress_callback("Phase 0: Evaluating all LLM models...")

        comparison = await compare_models(all_models)
        proposals = await propose_routing_updates(comparison)

        if proposals.get("model_map_overrides") or proposals.get("agent_model_overrides"):
            logger.info(f"Model evaluation found {len(proposals.get('reasoning', []))} routing improvements:")
            for reason in proposals.get("reasoning", []):
                logger.info(f"  → {reason}")

            # Save updated benchmarks — will be loaded on next restart
            save_model_benchmarks({
                "comparison": comparison,
                "proposals": proposals,
                "model_map_overrides": proposals.get("model_map_overrides", {}),
                "agent_model_overrides": proposals.get("agent_model_overrides", {}),
            })
            logger.info("Saved model benchmark updates for next restart")
        else:
            logger.info("Model evaluation: current routing is optimal. No changes needed.")

    except Exception as e:
        logger.warning(f"Model evaluation failed (non-fatal, continuing): {e}")

    experiments_run = 0
    experiments_kept = 0
    experiments_discarded = 0
    experiments_errored = 0

    try:
        while experiments_run < max_experiments:
            # Check time limit
            elapsed = time.time() - start_time
            if elapsed >= max_runtime:
                logger.info(f"Time limit reached ({max_hours}h). Stopping.")
                break

            # Run one experiment
            experiments_run += 1
            recent = experiment_log.get_recent(15)

            if progress_callback:
                await progress_callback(
                    f"Experiment {experiments_run}/{max_experiments} "
                    f"(kept: {experiments_kept}, discarded: {experiments_discarded}, errors: {experiments_errored})"
                )

            result = await run_single_experiment(
                research_program=research_program,
                recent_experiments=recent,
                project_root=project_root,
            )

            if result:
                experiment_log.append(result)

                if result.error:
                    experiments_errored += 1
                elif result.kept:
                    experiments_kept += 1
                else:
                    experiments_discarded += 1

                logger.info(result.to_log_line())
            else:
                experiments_errored += 1
                logger.warning(f"Experiment {experiments_run} returned None")

            # Small cooldown between experiments
            await asyncio.sleep(5)

            # Periodically clean up old snapshots
            if experiments_run % 10 == 0:
                snapshot_mgr.cleanup_old(max_age_hours=24)

    except asyncio.CancelledError:
        logger.info("Autonomous loop cancelled by operator")
    except Exception as e:
        logger.error(f"Autonomous loop crashed: {e}")

    total_time = time.time() - start_time

    summary = {
        "total_experiments": experiments_run,
        "kept": experiments_kept,
        "discarded": experiments_discarded,
        "errors": experiments_errored,
        "keep_rate": round(experiments_kept / experiments_run, 3) if experiments_run > 0 else 0,
        "runtime_hours": round(total_time / 3600, 2),
        "stats": experiment_log.get_stats(),
        "best_experiments": experiment_log.get_best_experiments(5),
    }

    logger.info("=" * 60)
    logger.info("CIPHER AUTONOMOUS RESEARCH LOOP COMPLETE")
    logger.info(f"Experiments: {experiments_run} (kept: {experiments_kept}, discarded: {experiments_discarded})")
    logger.info(f"Keep rate: {summary['keep_rate']:.1%}")
    logger.info(f"Runtime: {summary['runtime_hours']:.1f}h")
    logger.info("=" * 60)

    return summary
