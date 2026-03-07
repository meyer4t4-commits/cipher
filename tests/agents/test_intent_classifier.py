"""
Tests for the Intent Classifier — the bridge between chat and agentic execution.
Ensures that natural language messages are correctly routed to the right agent.
"""

import pytest
from app.agents.intent_classifier import AgentIntent, classify_intent


class TestNonAgenticMessages:
    """Messages that should NOT trigger agent execution."""

    @pytest.mark.parametrize("message", [
        "Hello Cipher",
        "What's the weather like?",
        "Tell me about quantum computing",
        "How are you doing today?",
        "What do you think about AI?",
        "Good morning",
        "Thanks for the help",
        "Can you explain machine learning?",
        "",
    ])
    def test_non_agentic_messages(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is False
        assert intent.agent_name is None


class TestShellAgent:
    """Messages that should route to the shell agent."""

    @pytest.mark.parametrize("message", [
        "run the command ls -la",
        "execute the script deploy.sh",
        "install pip install pandas",
        "restart the server",
        "kill the process on port 8000",
    ])
    def test_shell_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "shell"


class TestWebAgent:
    """Messages that should route to the web agent."""

    @pytest.mark.parametrize("message", [
        "fetch the page at example.com",
        "scrape the website for data",
        "call the API endpoint",
        "check the status of the server",
    ])
    def test_web_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "web"


class TestCodeAgent:
    """Messages that should route to the code agent."""

    @pytest.mark.parametrize("message", [
        "run this python script",
        "execute the code below",
        "test this function for me",
    ])
    def test_code_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "code"


class TestDeployAgent:
    """Messages that should route to the deploy agent."""

    @pytest.mark.parametrize("message", [
        "deploy this to Railway",
        "push to production",
        "ship this to the cloud",
    ])
    def test_deploy_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "deploy"
        assert intent.requires_approval is True


class TestTradingAgent:
    """Messages that should route to the trading agent."""

    @pytest.mark.parametrize("message", [
        "buy $AAPL",
        "sell $TSLA",
        "trade $NVDA",
        "check my portfolio",
    ])
    def test_trading_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "trading"


class TestResearchAgent:
    """Messages that should route to the research agent."""

    @pytest.mark.parametrize("message", [
        "research the latest AI trends",
        "search the web for FastAPI tutorials",
        "find news about Tesla",
        "look up information on quantum computing",
    ])
    def test_research_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "research"


class TestFileAgent:
    """Messages that should route to the file agent."""

    @pytest.mark.parametrize("message", [
        "read the file config.py",
        "write to the log file",
        "create a new file called notes.txt",
        "delete the temp files",
    ])
    def test_file_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "file"


class TestDataAgent:
    """Messages that should route to the data agent."""

    @pytest.mark.parametrize("message", [
        "analyze the CSV data",
        "create a chart of the sales data",
        "query the database for users",
        "generate a report on revenue",
    ])
    def test_data_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "data"


class TestCommunicationAgent:
    """Messages that should route to the communication agent."""

    @pytest.mark.parametrize("message", [
        "send an email to mark@elysianprotocol.io",
        "post a message to Slack",
        "send a Telegram message",
    ])
    def test_comms_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "communication"


class TestSchedulerAgent:
    """Messages that should route to the scheduler agent."""

    @pytest.mark.parametrize("message", [
        "schedule a task for every morning",
        "set up a cron job to check health",
        "create a recurring daily backup",
    ])
    def test_scheduler_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "scheduler"


class TestMonitorAgent:
    """Messages that should route to the monitor agent."""

    @pytest.mark.parametrize("message", [
        "monitor the CPU usage",
        "check system health",
        "watch for anomalies in the logs",
    ])
    def test_monitor_intent_detected(self, message):
        intent = classify_intent(message)
        assert intent.is_agentic is True
        assert intent.agent_name == "monitor"


class TestApprovalFlags:
    """Ensure dangerous operations require approval."""

    def test_deploy_requires_approval(self):
        intent = classify_intent("deploy this to Railway")
        assert intent.requires_approval is True

    def test_trading_requires_approval(self):
        intent = classify_intent("buy $AAPL")
        assert intent.requires_approval is True

    def test_shell_requires_approval(self):
        intent = classify_intent("run the command rm -rf /tmp")
        assert intent.requires_approval is True


class TestIntentMetadata:
    """Verify intent metadata is populated correctly."""

    def test_original_message_preserved(self):
        msg = "deploy this to Railway right now"
        intent = classify_intent(msg)
        assert intent.original_message == msg

    def test_confidence_is_reasonable(self):
        intent = classify_intent("deploy this to Railway")
        assert 0.0 < intent.confidence <= 1.0

    def test_action_is_set(self):
        intent = classify_intent("deploy this to Railway")
        assert intent.action is not None
