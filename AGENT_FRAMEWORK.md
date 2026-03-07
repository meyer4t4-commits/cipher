# Cipher Agent Framework

Comprehensive agentic execution framework for the Cipher sovereign AI intelligence daemon.

## Architecture Overview

The agent framework consists of:

1. **Base Components**
   - `BaseAgent`: Abstract base class all agents inherit from
   - `AgentTask`: Task definition model
   - `AgentResult`: Execution result model
   - `AgentStatus`: Execution status enum

2. **Core Infrastructure**
   - `AgentRegistry`: Agent discovery and routing
   - `TaskExecutor`: Task execution lifecycle management
   - `ExecutionHistoryDB`: Result persistence

3. **Skill Agents** (11 specialized agents)
   - `ShellAgent`: Execute shell commands safely
   - `WebAgent`: HTTP requests, web scraping, API interaction
   - `CodeAgent`: Python and JavaScript execution
   - `FileAgent`: File system operations
   - `TradingAgent`: Stock trading and portfolio management
   - `DeployAgent`: Git, Docker, Railway deployments
   - `ResearchAgent`: Web search, news, market research
   - `CommunicationAgent`: Email, Slack, Telegram, SMS
   - `SchedulerAgent`: Task scheduling and cron jobs
   - `DataAgent`: Data analysis, SQL, visualization
   - `MonitorAgent`: Monitoring, metrics, alerting

4. **API Layer**
   - FastAPI router with RESTful endpoints
   - Task submission, status tracking, approval management

## Key Design Principles

### 1. Verification is Mandatory
Every agent's `verify()` method MUST validate its output is real:
- Checks for expected data structures
- Validates exit codes match success flags
- Ensures response fields are present
- Detects partial/corrupted output

```python
async def verify(self, result: AgentResult) -> bool:
    """Must be implemented by every agent."""
    if not isinstance(result.output, dict):
        return False
    # ... additional validation
    return True
```

### 2. Approval Gates for Dangerous Operations
High-risk operations require operator approval:
- All trade orders
- Git pushes to main branch
- Environment variable changes
- Shell commands with sudo/rm
- Message sending
- File deletion

```python
def requires_approval_for(self, instruction: str) -> bool:
    """Check if instruction requires approval."""
    return "delete" in instruction or "rm -rf" in instruction
```

### 3. Sandboxing and Security
- Shell agent blocks dangerous commands by default
- File agent limited to allowed directories
- Code agent runs in isolated subprocess
- Web agent validates URLs, rate limits requests
- Trading agent operates in paper mode by default

### 4. Comprehensive Logging
All operations logged with context:
- Task ID and agent name
- Execution time
- Success/failure status
- Verification results

## Agent Implementation Template

```python
from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="my_agent",
            description="What this agent does",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="my_capability",
                    description="What it does",
                    category="data",
                    requires_approval=False,
                    timeout_seconds=30,
                ),
            ],
        )

    async def validate(self, task: AgentTask) -> bool:
        """Validate task before execution."""
        if not await super().validate(task):
            return False
        # Custom validation
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute the task."""
        try:
            # Do work here
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={"result": "data"},
            )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def verify(self, result: AgentResult) -> bool:
        """Verify output is real and valid."""
        if not isinstance(result.output, dict):
            return False
        # Verify structure, values, etc
        return True
```

## API Endpoints

### Execute Task
```
POST /api/v1/agents/execute

Request:
{
  "agent_name": "shell_agent",
  "instruction": "List files in current directory",
  "params": {
    "command": "ls -la"
  },
  "timeout_seconds": 30,
  "priority": 0
}

Response:
{
  "task_id": "abc123...",
  "agent_name": "shell_agent",
  "success": true,
  "output": {
    "stdout": "file1.txt\nfile2.txt\n",
    "stderr": "",
    "exit_code": 0,
    "command": "ls -la"
  },
  "error": null,
  "execution_time_ms": 125.5,
  "verified": true
}
```

### List All Capabilities
```
GET /api/v1/agents/capabilities

Response:
{
  "agents": 11,
  "capabilities": [
    {
      "agent": "shell_agent",
      "capability": "execute_shell",
      "description": "Execute shell commands",
      "category": "execution",
      "requires_approval": false,
      "timeout_seconds": 30
    },
    ...
  ]
}
```

### Get Task Status
```
GET /api/v1/agents/status/{task_id}

Response: AgentResult object
```

### Get Execution History
```
GET /api/v1/agents/history?limit=100

Response:
{
  "total": 100,
  "entries": [AgentResult, ...]
}
```

### List Pending Approvals
```
GET /api/v1/agents/approvals

Response:
{
  "pending": 2,
  "tasks": [
    {
      "task_id": "xyz789",
      "agent_name": "trading_agent",
      "instruction": "Buy 100 shares of AAPL",
      "requested_at": "2024-02-27T10:30:00",
      "priority": 1
    }
  ]
}
```

### Approve Task
```
POST /api/v1/agents/approve/{task_id}

Request:
{
  "approved_by": "operator@example.com",
  "notes": "Approved after review"
}

Response:
{
  "task_id": "xyz789",
  "approved": true,
  "approved_by": "operator@example.com"
}
```

### Reject Task
```
POST /api/v1/agents/reject/{task_id}?approved_by=operator&reason=Too+risky

Response:
{
  "task_id": "xyz789",
  "rejected": true,
  "rejected_by": "operator",
  "reason": "Too risky"
}
```

### Execute Batch
```
POST /api/v1/agents/batch

Request:
[
  {
    "agent_name": "shell_agent",
    "instruction": "Check disk space",
    "params": {"command": "df -h"}
  },
  {
    "agent_name": "shell_agent",
    "instruction": "Check memory",
    "params": {"command": "free -h"}
  }
]

Response:
{
  "total": 2,
  "results": [AgentResult, AgentResult]
}
```

## Agent-Specific Details

### ShellAgent
- **Denylist**: `rm -rf`, `sudo`, `mkfs`, `reboot`, `halt`, `shutdown`
- **Approval Required For**: Commands with `sudo`, `rm`, system modifications
- **Sandboxing**: Configurable working directory
- **Verification**: Checks exit code matches success flag

### WebAgent
- **Safety**: URL validation (no localhost), HTTPS preferred
- **Rate Limiting**: Per-domain tracking
- **Scraping**: HTML parsing with BeautifulSoup
- **APIs**: JSON support with proper error handling
- **Verification**: Status code 200-299 for success

### CodeAgent
- **Languages**: Python, JavaScript (via Node.js)
- **Sandboxing**: Temp files in sandbox directory
- **Timeouts**: 60s default, configurable
- **Package Install**: pip support with stderr capture
- **Verification**: Exit code validation

### FileAgent
- **Allowed Dirs**: Configurable allowlist
- **Operations**: read, write, create, delete, list, search
- **Size Limits**: Configurable max file size (100KB default)
- **Search**: Glob patterns and content search
- **Approval**: Required for delete operations

### TradingAgent
- **Mode**: Paper trading by default (no real money)
- **Operations**: Quotes, portfolio, orders, analysis, watchlists
- **Technical Analysis**: RSI, MACD, SMA, EMA, VWAP
- **Risk Management**: Position size and daily loss limits
- **Approval**: All trades require approval

### DeployAgent
- **Git**: Status, commit, push (push requires approval)
- **Docker**: Build and run containers
- **Railway**: Deployment integration
- **Environment**: Variable management (approval required)
- **Monitoring**: Health checks and log retrieval

### ResearchAgent
- **Search**: Web, news, academic papers
- **Analysis**: Competitor, market, sentiment analysis
- **Fact-Checking**: Source verification
- **Intelligence**: Market trends and insights

### CommunicationAgent
- **Channels**: Email, Slack, Telegram, SMS
- **Reading**: Email retrieval from IMAP
- **Templates**: Reusable message templates
- **Approval**: All sends require approval

### SchedulerAgent
- **Types**: One-time, recurring (cron), delayed
- **Chains**: Task dependency chains
- **Queue**: Priority-based task queue
- **Recovery**: Missed task recovery with lookback

### DataAgent
- **Loading**: CSV, JSON, Excel files
- **Analysis**: Statistical analysis, correlation
- **Transformation**: Data cleaning, normalization
- **Output**: Charts (PNG), reports (PDF)
- **Database**: SQL query execution

### MonitorAgent
- **Health**: Endpoint health checks
- **Metrics**: CPU, memory, disk, latency
- **Anomalies**: Detection with configurable sensitivity
- **Alerts**: Threshold-based alerting
- **Costs**: LLM provider cost tracking

## Task Status Lifecycle

```
PENDING
  ↓
(Requires Approval?) → AWAITING_APPROVAL → (Approved/Rejected)
  ↓                                          ↓
RUNNING                                   FAILED
  ↓
VERIFYING
  ↓
COMPLETED or FAILED
```

## Error Handling

All agents handle errors gracefully:

1. **Validation Errors**: Return failed result with validation error
2. **Execution Errors**: Catch exceptions, return error result
3. **Verification Failures**: Log warning, mark verified=false
4. **Timeouts**: Return timeout error after deadline

Example:
```python
return AgentResult(
    task_id=task.task_id,
    agent_name=self.name,
    success=False,
    error="Descriptive error message",
    execution_time_ms=elapsed,
    verified=False,
)
```

## Configuration

### Shell Agent
```python
agent = ShellAgent()
agent.DENIED_PATTERNS  # Extend for custom blocks
agent.working_directory  # Set working dir
```

### File Agent
```python
agent = FileAgent(allowed_dirs=[
    "/path/to/project",
    "/path/to/data",
])
```

### Code Agent
```python
agent = CodeAgent(sandbox_dir="./data/sandbox")
```

### Trading Agent
```python
agent = TradingAgent(paper_trading=True)  # Use paper mode
agent.position_size_limit = 0.05  # 5% per position
agent.daily_loss_limit = -1000.0  # Stop at -$1000
```

### Web Agent
```python
agent = WebAgent(timeout_seconds=30)
agent.rate_limits["example.com"]  # Per-domain tracking
```

## Testing

Example usage:
```python
from app.agents import get_registry, get_executor, AgentTask

# Initialize
registry = get_registry()
executor = get_executor()

# Create task
task = AgentTask(
    agent_name="shell_agent",
    instruction="List files",
    params={"command": "ls -la"},
    timeout_seconds=30,
)

# Execute
result = await executor.execute(task)
print(f"Success: {result.success}")
print(f"Verified: {result.verified}")
print(f"Output: {result.output}")
```

## Performance Considerations

- **Concurrent Execution**: Default 10 max concurrent tasks
- **Timeouts**: Per-task timeouts prevent hangs
- **History**: In-memory history (can be cleared)
- **Verification**: Quick validity checks in verify()
- **Logging**: Minimal overhead with structured logging

## Security Best Practices

1. **Never disable verification** - it catches bad data
2. **Use approval gates** for risky operations
3. **Keep denylist updated** for shell agent
4. **Validate user input** before creating tasks
5. **Monitor costs** with MonitorAgent
6. **Review logs** regularly for anomalies
7. **Test approval flow** before production
8. **Limit shell command capabilities** as needed

## Future Enhancements

- [ ] Distributed execution across multiple servers
- [ ] Real-time WebSocket status updates
- [ ] More sophisticated anomaly detection
- [ ] Agent chaining (task output → next task input)
- [ ] Cost optimization with cascade routing
- [ ] Advanced rate limiting per API key
- [ ] Persistent execution history to database
- [ ] Agent performance metrics and analytics
- [ ] Custom agent template generator
- [ ] Integration with external LLM reasoning engines

## File Structure

```
app/agents/
├── __init__.py                 # Framework exports
├── base.py                     # BaseAgent abstract class
├── models.py                   # Pydantic models
├── registry.py                 # Agent registry
├── executor.py                 # Task executor
└── skills/
    ├── __init__.py
    ├── shell_agent.py
    ├── web_agent.py
    ├── code_agent.py
    ├── file_agent.py
    ├── trading_agent.py
    ├── deploy_agent.py
    ├── research_agent.py
    ├── communication_agent.py
    ├── scheduler_agent.py
    ├── data_agent.py
    └── monitor_agent.py

app/api/
└── agents.py                   # FastAPI router
```

## Version History

- **v1.0.0** (2024-02-27)
  - Initial framework release
  - 11 skill agents
  - Full API endpoints
  - Approval workflow
  - Execution history
  - Comprehensive logging

---

Built with ❤️ by Elysian Protocol for Cipher
