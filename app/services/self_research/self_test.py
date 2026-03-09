"""
Self-Test Framework — Cipher validates its own capabilities.

This is the evaluation metric for CipherResearch (analogous to val_bpb in autoresearch).
Instead of measuring language model loss, we measure:
  1. Agent response quality (does the agent produce correct output?)
  2. Agent response time (latency)
  3. API health (are all services reachable?)
  4. System prompt coherence (does Cipher stay in character?)
  5. Tool execution success rate

Each test returns a score from 0.0 to 1.0.
The aggregate score is what experiments are optimized against.
"""

import asyncio
import json
import os
import time
from typing import Optional

from app.core.logging import logger


class TestCase:
    """A single self-test case."""

    def __init__(
        self,
        name: str,
        category: str,  # "agent", "api", "prompt", "tool", "integration"
        weight: float = 1.0,
        timeout: float = 30.0,
    ):
        self.name = name
        self.category = category
        self.weight = weight
        self.timeout = timeout
        self.score: float = 0.0
        self.passed: bool = False
        self.error: Optional[str] = None
        self.duration_ms: float = 0.0
        self.details: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "score": self.score,
            "passed": self.passed,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
            "details": self.details,
        }


class SelfTestSuite:
    """
    Cipher's self-test suite. Runs a battery of tests to produce
    a composite score that experiments are evaluated against.
    """

    def __init__(self):
        self.tests: list[TestCase] = []
        self.results: list[TestCase] = []

    async def run_all(self) -> dict:
        """Run all tests and return aggregate results."""
        self.results = []
        start = time.time()

        # Build the test battery
        test_coroutines = [
            self._test_api_health(),
            self._test_llm_routing(),
            self._test_agent_registry(),
            self._test_agent_execution(),
            self._test_memory_system(),
            self._test_tool_execution(),
            self._test_fact_checker(),
            self._test_system_prompt_coherence(),
            self._test_vision_service(),
            self._test_search_capability(),
        ]

        # Run all tests concurrently with individual timeouts
        completed = await asyncio.gather(*test_coroutines, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                tc = TestCase(name="unknown", category="error")
                tc.error = str(result)
                self.results.append(tc)
            elif isinstance(result, TestCase):
                self.results.append(result)

        total_duration = time.time() - start

        # Calculate aggregate score
        total_weight = sum(t.weight for t in self.results)
        weighted_score = sum(t.score * t.weight for t in self.results)
        aggregate_score = weighted_score / total_weight if total_weight > 0 else 0

        passed = [t for t in self.results if t.passed]
        failed = [t for t in self.results if not t.passed]

        return {
            "aggregate_score": round(aggregate_score, 4),
            "tests_passed": len(passed),
            "tests_total": len(self.results),
            "pass_rate": round(len(passed) / len(self.results), 3) if self.results else 0,
            "total_duration_ms": round(total_duration * 1000, 1),
            "by_category": self._aggregate_by_category(),
            "details": [t.to_dict() for t in self.results],
            "failures": [t.to_dict() for t in failed],
        }

    def _aggregate_by_category(self) -> dict:
        categories = {}
        for t in self.results:
            if t.category not in categories:
                categories[t.category] = {"total": 0, "passed": 0, "avg_score": 0}
            categories[t.category]["total"] += 1
            if t.passed:
                categories[t.category]["passed"] += 1
            categories[t.category]["avg_score"] += t.score

        for cat in categories:
            if categories[cat]["total"] > 0:
                categories[cat]["avg_score"] = round(
                    categories[cat]["avg_score"] / categories[cat]["total"], 3
                )
        return categories

    # ---------------------------------------------------------------
    # Individual Test Cases
    # ---------------------------------------------------------------

    async def _test_api_health(self) -> TestCase:
        """Test that the Cipher API is healthy and responsive."""
        tc = TestCase(name="api_health", category="api", weight=2.0)
        start = time.time()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                base = os.getenv("CIPHER_BASE_URL", "http://localhost:8000")
                resp = await client.get(f"{base}/api/v1/health")
                tc.duration_ms = (time.time() - start) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    tc.passed = data.get("status") in ("ok", "healthy")
                    tc.score = 1.0 if tc.passed else 0.3
                    tc.details = f"Status: {data.get('status')}"
                else:
                    tc.score = 0.0
                    tc.error = f"HTTP {resp.status_code}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_llm_routing(self) -> TestCase:
        """Test that LLM routing works (can reach at least one model)."""
        tc = TestCase(name="llm_routing", category="api", weight=3.0)
        start = time.time()
        try:
            import litellm
            # Try the fastest available model
            model = None
            if os.getenv("GROQ_API_KEY"):
                model = "groq/llama-3.1-8b-instant"
            elif os.getenv("ANTHROPIC_API_KEY"):
                model = "anthropic/claude-3-5-haiku-20241022"
            elif os.getenv("OPENAI_API_KEY"):
                model = "openai/gpt-4o-mini"

            if not model:
                tc.error = "No LLM API key configured"
                tc.score = 0.0
                return tc

            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": "Say 'CIPHER_ONLINE' and nothing else."}],
                max_tokens=20,
                temperature=0,
            )
            tc.duration_ms = (time.time() - start) * 1000

            content = response.choices[0].message.content.strip()
            tc.passed = "CIPHER_ONLINE" in content.upper()
            tc.score = 1.0 if tc.passed else 0.5
            tc.details = f"Model: {model}, Response: {content[:50]}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_agent_registry(self) -> TestCase:
        """Test that all expected agents are registered."""
        tc = TestCase(name="agent_registry", category="agent", weight=2.0)
        start = time.time()
        try:
            from app.agents.registry import get_registry
            registry = get_registry()
            agents = registry.list_agents()
            agent_names = [a.name for a in agents]
            tc.duration_ms = (time.time() - start) * 1000

            # Check for critical agents
            critical_agents = [
                "shell_agent", "code_agent", "research_agent",
                "brave_search_agent", "image_agent", "communication_agent",
            ]
            found = [a for a in critical_agents if a in agent_names]
            tc.passed = len(found) == len(critical_agents)
            tc.score = len(found) / len(critical_agents)
            tc.details = f"Registered: {len(agents)} agents, Critical: {len(found)}/{len(critical_agents)}"
            if len(found) < len(critical_agents):
                missing = set(critical_agents) - set(found)
                tc.details += f", Missing: {missing}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_agent_execution(self) -> TestCase:
        """Test that a basic agent can execute a simple task."""
        tc = TestCase(name="agent_execution", category="agent", weight=3.0, timeout=30)
        start = time.time()
        try:
            from app.agents.registry import get_registry
            from app.agents.executor import get_executor
            from app.agents.models import AgentTask

            registry = get_registry()
            executor = get_executor()

            # Use shell_agent for a simple test
            if not registry.is_registered("shell_agent"):
                tc.error = "shell_agent not registered"
                tc.score = 0.0
                return tc

            task = AgentTask(
                agent_name="shell_agent",
                instruction="echo 'CIPHER_SELF_TEST_OK'",
                params={"command": "echo 'CIPHER_SELF_TEST_OK'"},
            )

            result = await asyncio.wait_for(executor.execute(task), timeout=tc.timeout)
            tc.duration_ms = (time.time() - start) * 1000

            tc.passed = result.success and "CIPHER_SELF_TEST_OK" in str(result.output)
            tc.score = 1.0 if tc.passed else 0.3
            tc.details = f"Success: {result.success}, Time: {result.execution_time_ms}ms"
        except asyncio.TimeoutError:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = f"Timed out after {tc.timeout}s"
            tc.score = 0.1
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_memory_system(self) -> TestCase:
        """Test that ChromaDB memory store/recall works."""
        tc = TestCase(name="memory_system", category="integration", weight=1.5)
        start = time.time()
        try:
            from app.services.memory import store_memory, recall_memories

            # Store a test memory
            test_content = f"CIPHER_SELF_TEST_{uuid.uuid4().hex[:8]}"
            import uuid
            memory_id = store_memory(test_content, metadata={"test": True})

            # Recall it
            results = recall_memories(test_content, n_results=3)
            tc.duration_ms = (time.time() - start) * 1000

            found = any(test_content in r.get("content", "") for r in results)
            tc.passed = memory_id is not None and found
            tc.score = 1.0 if tc.passed else 0.3
            tc.details = f"Stored: {memory_id is not None}, Recalled: {found}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_tool_execution(self) -> TestCase:
        """Test that the tool calling system can execute basic tools."""
        tc = TestCase(name="tool_execution", category="tool", weight=2.0)
        start = time.time()
        try:
            from app.services.tool_calling import execute_tool

            result = await execute_tool("run_shell", {"command": "echo TOOL_TEST_OK"})
            tc.duration_ms = (time.time() - start) * 1000

            parsed = json.loads(result)
            tc.passed = parsed.get("success", False) and "TOOL_TEST_OK" in parsed.get("stdout", "")
            tc.score = 1.0 if tc.passed else 0.3
            tc.details = f"Exit: {parsed.get('exit_code')}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_fact_checker(self) -> TestCase:
        """Test that the fact-checking system works."""
        tc = TestCase(name="fact_checker", category="integration", weight=1.5)
        start = time.time()
        try:
            from app.services.fact_checker import validate_response

            # Test with a clearly factual claim
            result = await validate_response(
                response_text="The company was founded in 2015 and generated $500M in revenue.",
                user_query="Tell me about the company.",
            )
            tc.duration_ms = (time.time() - start) * 1000

            tc.passed = "confidence" in result and "warnings" in result
            tc.score = 1.0 if tc.passed and result.get("checked", False) else 0.5
            tc.details = f"Confidence: {result.get('confidence', 'N/A')}, Checked: {result.get('checked', False)}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_system_prompt_coherence(self) -> TestCase:
        """Test that the system prompt loads and contains critical sections."""
        tc = TestCase(name="system_prompt", category="prompt", weight=2.0)
        start = time.time()
        try:
            from app.core.system_prompt import get_cipher_system_prompt

            prompt = get_cipher_system_prompt()
            tc.duration_ms = (time.time() - start) * 1000

            # Check for critical sections
            checks = {
                "identity": "Cipher" in prompt,
                "agents": "agent" in prompt.lower(),
                "memory": "memory" in prompt.lower(),
                "hallucination": "hallucin" in prompt.lower() or "fact" in prompt.lower(),
                "routing": "route" in prompt.lower() or "routing" in prompt.lower(),
                "length": len(prompt) > 1000,
            }

            passed_checks = sum(1 for v in checks.values() if v)
            tc.passed = passed_checks == len(checks)
            tc.score = passed_checks / len(checks)
            tc.details = f"Checks: {passed_checks}/{len(checks)}, Length: {len(prompt)} chars"
            if not tc.passed:
                failed = [k for k, v in checks.items() if not v]
                tc.details += f", Failed: {failed}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_vision_service(self) -> TestCase:
        """Test that the vision service module is importable and functional."""
        tc = TestCase(name="vision_service", category="integration", weight=1.0)
        start = time.time()
        try:
            from app.services.vision_service import validate_image, detect_mime_type, build_vision_messages

            # Test with a minimal valid PNG header (base64)
            import base64
            # 1x1 transparent PNG
            tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

            valid, error = validate_image(tiny_png)
            mime = detect_mime_type(tiny_png)
            messages = build_vision_messages("test", [tiny_png])

            tc.duration_ms = (time.time() - start) * 1000
            tc.passed = valid and mime == "image/png" and len(messages) == 2
            tc.score = 1.0 if tc.passed else 0.3
            tc.details = f"Valid: {valid}, MIME: {mime}, Messages: {len(messages)}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc

    async def _test_search_capability(self) -> TestCase:
        """Test that web search is accessible (Brave Search API)."""
        tc = TestCase(name="search_capability", category="tool", weight=1.5)
        start = time.time()
        try:
            api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
            if not api_key:
                tc.score = 0.0
                tc.error = "No Brave Search API key"
                return tc

            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": "test", "count": 1},
                    headers={
                        "X-Subscription-Token": api_key,
                        "Accept": "application/json",
                    },
                )
                tc.duration_ms = (time.time() - start) * 1000

                tc.passed = resp.status_code == 200
                tc.score = 1.0 if tc.passed else 0.0
                tc.details = f"HTTP {resp.status_code}"
        except Exception as e:
            tc.duration_ms = (time.time() - start) * 1000
            tc.error = str(e)[:200]
            tc.score = 0.0
        return tc


# Convenience function
import uuid as _uuid  # noqa: avoid shadowing in test methods

async def run_self_tests() -> dict:
    """Run the full self-test suite and return results."""
    suite = SelfTestSuite()
    return await suite.run_all()
