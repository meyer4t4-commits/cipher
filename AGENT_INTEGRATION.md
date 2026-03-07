# Agent Framework Integration Guide

## Integration into Cipher

The agent framework is fully integrated into Cipher and automatically initializes on startup.

### 1. API Registration

The agents router is registered in `app/main.py`:

```python
from app.api import agents

app.include_router(agents.router)
```

All endpoints are available at `/api/v1/agents/*`

### 2. Database Integration

Execution history is logged to the database in `TaskRecord` table:

```python
# Automatically logged on task completion
from app.db.models import TaskRecord

# Query execution history
db.query(TaskRecord).filter(
    TaskRecord.task_type.like('agent:%')
).order_by(TaskRecord.created_at.desc()).all()
```

### 3. Using in Code

```python
from app.agents import get_executor, get_registry, AgentTask

async def some_function():
    executor = get_executor()
    registry = get_registry()
    
    # Create task
    task = AgentTask(
        agent_name="shell_agent",
        instruction="Check disk",
        params={"command": "df -h"},
    )
    
    # Execute
    result = await executor.execute(task)
    
    # Use result
    if result.success and result.verified:
        print(f"Command output: {result.output}")
```

### 4. Using in API Endpoints

```python
from fastapi import APIRouter, Depends
from app.agents import get_executor, AgentTask
from app.db.database import get_db

router = APIRouter()

@router.post("/my-endpoint")
async def my_endpoint(db: Session = Depends(get_db)):
    executor = get_executor()
    
    task = AgentTask(
        agent_name="web_agent",
        instruction="Fetch data",
        params={"url": "https://api.example.com/data"}
    )
    
    result = await executor.execute(task, db)
    
    return {"success": result.success, "data": result.output}
```

## Configuration

### Shell Agent

Control which commands are blocked:

```python
from app.agents.skills import ShellAgent

agent = ShellAgent()

# Add custom denylist pattern
agent.DENIED_PATTERNS.append(r"^\s*format\s+")

# Set working directory
await agent.set_working_directory("/path/to/project")
```

### File Agent

Configure allowed directories:

```python
from app.agents.skills import FileAgent

agent = FileAgent(allowed_dirs=[
    "/path/to/project",
    "/path/to/data",
    "/tmp"
])
```

### Trading Agent

Use paper trading in development:

```python
from app.agents.skills import TradingAgent

# Paper trading (default)
agent = TradingAgent(paper_trading=True)

# Real trading (requires credentials)
agent = TradingAgent(paper_trading=False)
```

### Code Agent

Change sandbox directory:

```python
from app.agents.skills import CodeAgent

agent = CodeAgent(sandbox_dir="./data/code_sandbox")
```

### Web Agent

Configure timeout:

```python
from app.agents.skills import WebAgent

agent = WebAgent(timeout_seconds=60)
```

## Extending with Custom Agents

Create a new agent:

```python
# app/agents/skills/my_agent.py
from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="my_agent",
            description="My custom agent",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="do_something",
                    description="Does something useful",
                    category="data",
                    requires_approval=False,
                    timeout_seconds=30,
                ),
            ],
        )

    async def validate(self, task: AgentTask) -> bool:
        if not await super().validate(task):
            return False
        # Custom validation
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        try:
            # Do work
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
        # Verify output structure
        if not isinstance(result.output, dict):
            return False
        # Additional checks
        return True
```

Register it:

```python
# In app/api/agents.py startup

from app.agents.skills.my_agent import MyAgent

def _init_agents():
    # ... existing agents ...
    
    my_agent = MyAgent()
    registry.register(my_agent)
```

## Monitoring Agent Execution

### Via API

```bash
# Get all capabilities
curl http://localhost:8000/api/v1/agents/capabilities

# Get execution history
curl http://localhost:8000/api/v1/agents/history?limit=50

# Get pending approvals
curl http://localhost:8000/api/v1/agents/approvals

# Get executor status
curl http://localhost:8000/api/v1/agents/status
```

### In Code

```python
from app.agents import get_executor, get_registry

executor = get_executor()
registry = get_registry()

# Status
print(f"Agents: {registry.count()}")
print(f"Pending approvals: {len(executor._pending_approvals)}")
print(f"History entries: {len(executor._execution_history)}")

# List capabilities
for cap in registry.list_capabilities():
    print(f"{cap['agent']}.{cap['capability']}")

# Get execution history
history = executor.get_execution_history(limit=10)
for result in history:
    print(f"{result.task_id}: {result.agent_name} - {result.success}")
```

## Logging

Agents use the standard Cipher logger:

```python
from app.core.logging import logger

logger.info(f"[agent_name] Task started")
logger.warning(f"[agent_name] Task requires approval")
logger.error(f"[agent_name] Task failed: {error}")
```

View logs in real-time with Rich console output.

## Testing

### Unit Test Example

```python
import pytest
from app.agents.skills import ShellAgent
from app.agents.models import AgentTask

@pytest.mark.asyncio
async def test_shell_agent():
    agent = ShellAgent()
    
    task = AgentTask(
        agent_name="shell_agent",
        instruction="List files",
        params={"command": "ls /"},
    )
    
    result = await agent.run(task)
    
    assert result.success
    assert result.verified
    assert "bin" in result.output["stdout"]
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_executor():
    from app.agents import get_executor
    
    executor = get_executor()
    
    task = AgentTask(
        agent_name="shell_agent",
        params={"command": "echo hello"}
    )
    
    result = await executor.execute(task)
    
    assert result.success
    assert "hello" in result.output["stdout"]
```

## Performance Optimization

### Concurrent Execution

```python
executor = get_executor()

# Execute 10 tasks concurrently (default max)
tasks = [AgentTask(...) for _ in range(10)]
results = await executor.execute_many(tasks)
```

### Increase Concurrency

```python
from app.agents.executor import TaskExecutor

executor = TaskExecutor(max_concurrent_tasks=20)
```

### Clear History

```python
executor = get_executor()

# Clear execution history to free memory
count = executor.clear_history()
print(f"Cleared {count} entries")
```

## Approval Workflow Integration

```python
from app.agents import get_executor

executor = get_executor()

# 1. Get pending approvals
pending = executor.get_pending_approvals()
print(f"Pending: {len(pending)} tasks")

# 2. Review task details
for task in pending:
    print(f"Task: {task['instruction']}")

# 3. Approve or reject
if approved:
    executor.approve_task(task_id, approved_by="admin")
else:
    executor.reject_task(task_id, rejected_by="admin", reason="Too risky")
```

## Cost Tracking

Use the MonitorAgent to track LLM costs:

```python
executor = get_executor()

task = AgentTask(
    agent_name="monitor_agent",
    params={"operation": "track_costs", "period": "daily"}
)

result = await executor.execute(task)
costs = result.output["by_provider"]
```

## Deployment

### Development

```bash
# Run with hot reload
uvicorn app.main:app --reload

# Check agents endpoint
curl http://localhost:8000/api/v1/agents/agents
```

### Production

1. Ensure all environment variables are set
2. Initialize database: `python -c "from app.db.database import init_db; init_db()"`
3. Start server: `gunicorn app.main:app --workers 4`
4. Monitor `/api/v1/agents/status` endpoint

### Docker

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Troubleshooting Integration

### Agents Not Initializing

```python
# Check if initialized
from app.agents import get_registry
registry = get_registry()
print(f"Agents registered: {registry.count()}")

# Force initialization
from app.api.agents import _init_agents
_init_agents()
```

### Database Logging Failing

```python
# Check if TaskRecord table exists
from app.db.database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
print("tasks" in inspector.get_table_names())
```

### Agent Import Errors

```python
# Verify all dependencies installed
pip install httpx beautifulsoup4 pydantic fastapi sqlalchemy
```

## Next Steps

1. Read [AGENT_FRAMEWORK.md](./AGENT_FRAMEWORK.md) for comprehensive documentation
2. Check [AGENT_QUICK_REFERENCE.md](./AGENT_QUICK_REFERENCE.md) for common commands
3. Review individual agent files in `app/agents/skills/`
4. Test with curl or Postman to `/api/v1/agents/execute`
5. Create custom agents for your specific needs

---

Built by Elysian Protocol
