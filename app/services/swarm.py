"""
Prediction Swarm — Multi-agent debate & consensus engine.

Given a scenario (investment decision, market prediction, strategic question),
this service spawns perspective agents that argue different sides, then
synthesizes their outputs into a confidence-scored prediction.

Inspired by MiroFish's swarm intelligence approach — but adapted for Cipher's
existing 32-agent arsenal instead of building thousands of personality agents.

Architecture:
- Swarm Moderator: Orchestrates the debate, collects positions
- Perspective Agents: Each takes a stance (optimistic, conservative, adversarial, neutral)
- Evidence Phase: Agents gather real data via their tools
- Debate Phase: Agents respond to each other's positions
- Synthesis: Weighted consensus with confidence scoring
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.logging import logger


# ── Perspective Stances ─────────────────────────────────────────────

STANCES = {
    "optimistic": {
        "label": "Bull Case",
        "instruction": "Argue the STRONGEST case FOR this scenario succeeding. Find supporting evidence, upside potential, and positive indicators. Be genuinely enthusiastic but data-driven.",
        "weight": 0.25,
    },
    "conservative": {
        "label": "Bear Case",
        "instruction": "Argue the STRONGEST case AGAINST this scenario. Find risks, downsides, red flags, and reasons for caution. Be genuinely skeptical but fair.",
        "weight": 0.25,
    },
    "adversarial": {
        "label": "Devil's Advocate",
        "instruction": "Challenge ALL assumptions. What are the hidden risks nobody is talking about? What could go catastrophically wrong? What information is missing?",
        "weight": 0.2,
    },
    "neutral": {
        "label": "Balanced Analysis",
        "instruction": "Give a strictly balanced, objective analysis. Weigh pros and cons equally. Focus on what the data actually shows, not what anyone hopes.",
        "weight": 0.3,
    },
}


class SwarmPerspective:
    """A single perspective in a swarm debate."""

    def __init__(self, stance: str, agent_name: str):
        self.stance = stance
        self.agent_name = agent_name
        self.label = STANCES[stance]["label"]
        self.position: Optional[str] = None
        self.evidence: list[str] = []
        self.confidence: float = 0.0
        self.signal: Optional[dict] = None
        self.execution_time_ms: float = 0.0
        self.error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "stance": self.stance,
            "label": self.label,
            "agent_name": self.agent_name,
            "position": self.position,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


class SwarmResult:
    """Final output of a prediction swarm."""

    def __init__(
        self,
        scenario: str,
        perspectives: list[SwarmPerspective],
        consensus: str,
        confidence: float,
        risk_level: str,
        recommendation: str,
        dissent: list[str],
    ):
        self.scenario = scenario
        self.perspectives = perspectives
        self.consensus = consensus
        self.confidence = confidence
        self.risk_level = risk_level
        self.recommendation = recommendation
        self.dissent = dissent
        self.created_at = datetime.now(timezone.utc)
        self.total_time_ms = sum(p.execution_time_ms for p in perspectives)

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "consensus": self.consensus,
            "confidence": round(self.confidence, 2),
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
            "dissent": self.dissent,
            "perspectives": [p.to_dict() for p in self.perspectives],
            "total_time_ms": round(self.total_time_ms, 1),
            "created_at": self.created_at.isoformat(),
        }


class PredictionSwarm:
    """
    Orchestrates multi-agent prediction debates.

    Usage:
        swarm = PredictionSwarm()
        result = await swarm.predict(
            scenario="Should I invest in this property at 123 Main St for $280,000?",
            agents=["deal_flow_agent", "research_agent", "scout_agent"],
        )
    """

    def __init__(self):
        self._history: list[SwarmResult] = []

    async def predict(
        self,
        scenario: str,
        agents: Optional[list[str]] = None,
        stances: Optional[list[str]] = None,
        timeout: int = 120,
    ) -> SwarmResult:
        """
        Run a prediction swarm on a scenario.

        Args:
            scenario: The question/scenario to analyze
            agents: Agent names to use (defaults to research + synthesis)
            stances: Which stances to include (defaults to all 4)
            timeout: Max seconds for the entire swarm

        Returns:
            SwarmResult with consensus, confidence, and individual perspectives
        """
        start = time.time()
        stances = stances or list(STANCES.keys())
        agents = agents or ["research_agent", "synthesis_agent"]

        logger.info(f"[Swarm] Starting prediction swarm: {scenario[:80]}...")

        # Phase 1: Gather perspectives in parallel
        perspectives = []
        tasks = []
        for i, stance in enumerate(stances):
            agent_name = agents[i % len(agents)]
            perspective = SwarmPerspective(stance=stance, agent_name=agent_name)
            perspectives.append(perspective)
            tasks.append(self._gather_perspective(perspective, scenario, timeout))

        await asyncio.gather(*tasks, return_exceptions=True)

        # Phase 2: Synthesize consensus
        consensus_result = await self._synthesize(scenario, perspectives)

        result = SwarmResult(
            scenario=scenario,
            perspectives=perspectives,
            consensus=consensus_result.get("consensus", "Insufficient data for consensus"),
            confidence=consensus_result.get("confidence", 0.0),
            risk_level=consensus_result.get("risk_level", "MEDIUM"),
            recommendation=consensus_result.get("recommendation", "Gather more data"),
            dissent=consensus_result.get("dissent", []),
        )

        self._history.append(result)
        elapsed = (time.time() - start) * 1000
        logger.info(
            f"[Swarm] Complete: confidence={result.confidence:.0%}, "
            f"risk={result.risk_level}, {elapsed:.0f}ms"
        )
        return result

    async def _gather_perspective(
        self, perspective: SwarmPerspective, scenario: str, timeout: int
    ):
        """
        Gather a single perspective using direct LLM call with stance persona.
        MiroFish-style: each perspective is an LLM reasoning from a different stance,
        not a full agent execution (agents validate operations which limits flexibility).
        """
        import re
        start = time.time()
        stance_config = STANCES[perspective.stance]

        try:
            from app.services.llm_router import chat_completion

            prompt = (
                f"You are a {stance_config['label']} analyst (assigned agent: {perspective.agent_name}).\n\n"
                f"SCENARIO: {scenario}\n\n"
                f"INSTRUCTIONS: {stance_config['instruction']}\n\n"
                f"Provide your analysis with:\n"
                f"1. Your position (2-3 sentences)\n"
                f"2. Key evidence points (3-5 bullet points)\n"
                f"3. Your confidence level (state as X%)\n\n"
                f"Be specific and data-driven. Reference real market conditions, rates, and metrics where possible."
            )

            # Use reasoning model for neutral (highest weight), default for others
            model = "reasoning" if perspective.stance == "neutral" else "default"

            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0.4 if perspective.stance == "neutral" else 0.6,
                max_tokens=600,
            )

            content = response.get("content", "")
            if content:
                perspective.position = content[:1000]
                # Extract confidence from output
                conf_match = re.search(r'(\d{1,3})\s*%', content)
                if conf_match:
                    perspective.confidence = min(int(conf_match.group(1)) / 100.0, 1.0)
                else:
                    perspective.confidence = 0.5
            else:
                perspective.error = "LLM returned empty response"

        except Exception as e:
            perspective.error = str(e)
            logger.warning(f"[Swarm] {perspective.stance} perspective failed: {e}")
        finally:
            perspective.execution_time_ms = (time.time() - start) * 1000

    async def _synthesize(self, scenario: str, perspectives: list[SwarmPerspective]) -> dict:
        """Synthesize all perspectives into a consensus."""
        try:
            from app.services.llm_router import chat_completion

            # Build perspective summary
            summaries = []
            for p in perspectives:
                if p.position:
                    summaries.append(
                        f"[{p.label}] (confidence: {p.confidence:.0%})\n{p.position[:500]}"
                    )
                elif p.error:
                    summaries.append(f"[{p.label}] FAILED: {p.error}")

            if not summaries:
                return {
                    "consensus": "All perspectives failed — insufficient data.",
                    "confidence": 0.0,
                    "risk_level": "HIGH",
                    "recommendation": "Cannot make a recommendation without data.",
                    "dissent": [],
                }

            prompt = f"""You are a prediction synthesis engine. Analyze these perspectives on a scenario and produce a consensus.

SCENARIO: {scenario}

PERSPECTIVES:
{chr(10).join(summaries)}

Produce a JSON response:
{{
  "consensus": "2-3 sentence synthesis of the most likely outcome",
  "confidence": 0.0-1.0,
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "recommendation": "Clear actionable recommendation in 1-2 sentences",
  "dissent": ["any strongly disagreeing viewpoints that shouldn't be ignored"]
}}

Weight the neutral analyst highest. Flag any perspective that strongly disagrees with consensus."""

            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="reasoning",
                temperature=0.2,
                max_tokens=800,
            )

            content = response.get("content", "")
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])

        except Exception as e:
            logger.warning(f"[Swarm] Synthesis failed: {e}")

        # Fallback: weighted average of confidences
        total_weight = 0
        weighted_conf = 0
        for p in perspectives:
            if p.position:
                w = STANCES[p.stance]["weight"]
                weighted_conf += p.confidence * w
                total_weight += w

        avg_conf = weighted_conf / total_weight if total_weight > 0 else 0

        return {
            "consensus": "Mixed signals — see individual perspectives.",
            "confidence": round(avg_conf, 2),
            "risk_level": "HIGH" if avg_conf < 0.4 else "MEDIUM" if avg_conf < 0.7 else "LOW",
            "recommendation": "Exercise caution — perspectives are divided.",
            "dissent": [p.label for p in perspectives if p.error],
        }

    def get_history(self, limit: int = 10) -> list[dict]:
        """Get recent swarm predictions."""
        return [r.to_dict() for r in self._history[-limit:]]


# Singleton
_swarm_instance: Optional[PredictionSwarm] = None


def get_prediction_swarm() -> PredictionSwarm:
    global _swarm_instance
    if _swarm_instance is None:
        _swarm_instance = PredictionSwarm()
    return _swarm_instance
