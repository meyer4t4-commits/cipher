# Agent Framework - Quick Reference Guide

## Quick Start

### 1. Initialize Framework
```python
from app.agents import get_registry, get_executor

# Framework auto-initializes on first API call
registry = get_registry()
executor = get_executor()
```

### 2. Create and Execute Task
```python
from app.agents import AgentTask

task = AgentTask(
    agent_name="shell_agent",
    instruction="Check disk usage",
    params={"command": "df -h"},
    timeout_seconds=30,
)

result = await executor.execute(task)
print(result.output)
```

### 3. Check Task Status
```python
status = executor.get_task_status(task.task_id)
print(f"Success: {status.success}")
print(f"Verified: {status.verified}")
```

## Agent Quick Commands

### Shell Agent
```python
# List files
{"agent_name": "shell_agent", "params": {"command": "ls -la"}}

# Get system info
{"agent_name": "shell_agent", "params": {"command": "uname -a"}}

# Check disk
{"agent_name": "shell_agent", "params": {"command": "df -h"}}
```

### Web Agent
```python
# GET request
{"agent_name": "web_agent", "params": {
    "url": "https://api.example.com/data",
    "method": "GET"
}}

# POST with JSON
{"agent_name": "web_agent", "params": {
    "url": "https://api.example.com/create",
    "method": "POST",
    "json": {"key": "value"}
}}
```

### Code Agent
```python
# Python code
{"agent_name": "code_agent", "params": {
    "code": "print(2 + 2)",
    "language": "python"
}}

# JavaScript
{"agent_name": "code_agent", "params": {
    "code": "console.log('Hello');",
    "language": "javascript"
}}

# Install package
{"agent_name": "code_agent", "params": {
    "operation": "install_package",
    "package": "requests"
}}
```

### File Agent
```python
# Read file
{"agent_name": "file_agent", "params": {
    "operation": "read",
    "path": "/path/to/file.txt"
}}

# Write file
{"agent_name": "file_agent", "params": {
    "operation": "write",
    "path": "/path/to/file.txt",
    "content": "Hello World"
}}

# List directory
{"agent_name": "file_agent", "params": {
    "operation": "list",
    "path": "/path/to/dir"
}}

# Search files
{"agent_name": "file_agent", "params": {
    "operation": "search",
    "path": "/path/to/dir",
    "pattern": "*.txt"
}}
```

### Trading Agent
```python
# Get quote
{"agent_name": "trading_agent", "params": {
    "operation": "get_quote",
    "symbol": "AAPL"
}}

# Get portfolio
{"agent_name": "trading_agent", "params": {
    "operation": "get_portfolio"
}}

# Place order (requires approval)
{"agent_name": "trading_agent", "params": {
    "operation": "place_order",
    "symbol": "AAPL",
    "side": "buy",
    "quantity": 10,
    "type": "market"
}}

# Technical analysis
{"agent_name": "trading_agent", "params": {
    "operation": "analyze_technical",
    "symbol": "TSLA"
}}
```

### Deploy Agent
```python
# Git status
{"agent_name": "deploy_agent", "params": {
    "operation": "git_status"
}}

# Git commit
{"agent_name": "deploy_agent", "params": {
    "operation": "git_commit",
    "message": "Auto-commit"
}}

# Docker build
{"agent_name": "deploy_agent", "params": {
    "operation": "docker_build",
    "tag": "myapp:latest"
}}

# Health check
{"agent_name": "deploy_agent", "params": {
    "operation": "health_check",
    "url": "https://myapp.com/health"
}}
```

### Research Agent
```python
# Web search
{"agent_name": "research_agent", "params": {
    "operation": "web_search",
    "query": "artificial intelligence trends"
}}

# News search
{"agent_name": "research_agent", "params": {
    "operation": "news_search",
    "query": "tech stocks"
}}

# Competitor analysis
{"agent_name": "research_agent", "params": {
    "operation": "competitor_analysis",
    "company": "MyCompany"
}}
```

### Communication Agent
```python
# Send email (requires approval)
{"agent_name": "communication_agent", "params": {
    "operation": "send_email",
    "to": "user@example.com",
    "subject": "Hello",
    "body": "Message"
}}

# Send Slack (requires approval)
{"agent_name": "communication_agent", "params": {
    "operation": "send_slack",
    "channel": "#general",
    "message": "Hello team"
}}

# Send Telegram (requires approval)
{"agent_name": "communication_agent", "params": {
    "operation": "send_telegram",
    "chat_id": "123456789",
    "message": "Hello"
}}

# Read emails
{"agent_name": "communication_agent", "params": {
    "operation": "read_email",
    "folder": "INBOX"
}}
```

### Scheduler Agent
```python
# Schedule for later
{"agent_name": "scheduler_agent", "params": {
    "operation": "schedule_delay",
    "delay_seconds": 3600,
    "task": {"agent_name": "shell_agent", "params": {...}}
}}

# Schedule recurring (cron)
{"agent_name": "scheduler_agent", "params": {
    "operation": "schedule_recurring",
    "cron": "0 9 * * *",  # Daily at 9am
    "task": {...}
}}

# List scheduled tasks
{"agent_name": "scheduler_agent", "params": {
    "operation": "list_scheduled"
}}
```

### Data Agent
```python
# SQL query
{"agent_name": "data_agent", "params": {
    "operation": "sql_query",
    "query": "SELECT * FROM users WHERE active=1"
}}

# Load CSV
{"agent_name": "data_agent", "params": {
    "operation": "load_csv",
    "path": "/path/to/data.csv"
}}

# Generate chart
{"agent_name": "data_agent", "params": {
    "operation": "generate_chart",
    "chart_type": "line",
    "data_source": "sales_data",
    "x_axis": "date",
    "y_axis": "revenue"
}}

# Generate report
{"agent_name": "data_agent", "params": {
    "operation": "generate_report",
    "title": "Monthly Report",
    "data_sources": ["sales", "costs"]
}}
```

### Monitor Agent
```python
# Health check
{"agent_name": "monitor_agent", "params": {
    "operation": "health_check",
    "url": "https://api.example.com/health"
}}

# Get metrics
{"agent_name": "monitor_agent", "params": {
    "operation": "get_metrics",
    "service": "api"
}}

# Detect anomalies
{"agent_name": "monitor_agent", "params": {
    "operation": "detect_anomaly",
    "metric_name": "cpu_usage"
}}

# Track uptime
{"agent_name": "monitor_agent", "params": {
    "operation": "track_uptime",
    "service": "api",
    "hours": 24
}}

# Track costs
{"agent_name": "monitor_agent", "params": {
    "operation": "track_costs",
    "period": "monthly"
}}

# System resources
{"agent_name": "monitor_agent", "params": {
    "operation": "system_resources"
}}
```

## API Endpoints Cheat Sheet

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/agents/execute` | POST | Execute a task |
| `/api/v1/agents/capabilities` | GET | List all capabilities |
| `/api/v1/agents/agents` | GET | List all agents |
| `/api/v1/agents/status/{task_id}` | GET | Get task status |
| `/api/v1/agents/history` | GET | Get execution history |
| `/api/v1/agents/approvals` | GET | List pending approvals |
| `/api/v1/agents/approve/{task_id}` | POST | Approve a task |
| `/api/v1/agents/reject/{task_id}` | POST | Reject a task |
| `/api/v1/agents/status` | GET | Get executor status |
| `/api/v1/agents/batch` | POST | Execute multiple tasks |
| `/api/v1/agents/history` | DELETE | Clear history |

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 404 | Agent not found | Check agent name exists |
| 422 | Invalid parameters | Validate task parameters |
| 400 | Validation failed | Check required fields |
| 408 | Task timeout | Increase timeout_seconds |
| 500 | Execution error | Check logs for details |

## Approval Workflow

```
1. Submit task with risky operation
2. Task goes to AWAITING_APPROVAL
3. Operator calls /api/v1/agents/approvals
4. Review the pending task
5. Call /api/v1/agents/approve/{task_id}
6. Task executes and returns to client
```

## Common Patterns

### Execute and Wait
```python
# Create task
result = await executor.execute(task)

# Immediately have result
if result.success and result.verified:
    print("Task succeeded and was verified")
```

### Handle Approval
```python
# Create risky task
result = await executor.execute(task)

if result.error == "Task requires operator approval":
    # Wait for approval via API endpoint
    # Re-approve and re-execute
    executor.approve_task(task.task_id, "admin")
```

### Batch Operations
```python
tasks = [
    AgentTask(...),
    AgentTask(...),
    AgentTask(...),
]
results = await executor.execute_many(tasks)
```

### Monitor Costs
```python
result = await executor.execute(AgentTask(
    agent_name="monitor_agent",
    params={"operation": "track_costs"}
))
```

## Troubleshooting

### Task Returns Failed
1. Check `result.error` for error message
2. Verify `result.verified = False` (verification failed)
3. Check agent logs for details
4. Increase `timeout_seconds` if timing out

### Agent Not Found
1. Verify agent name is correct
2. Check `/api/v1/agents/agents` for list
3. Ensure agent is registered on startup

### Approval Required
1. Check if operation needs approval
2. Call `/api/v1/agents/approvals` to see pending
3. Call `/api/v1/agents/approve/{task_id}` to approve
4. Resubmit the task

### Timeout
1. Increase `timeout_seconds` in task
2. Check if agent is hanging
3. Verify no deadlocks in code
4. Check system resources (CPU, memory)

## Performance Tips

- Use batch execution for multiple tasks
- Set appropriate timeout_seconds (don't too low)
- Clear history periodically for memory
- Monitor costs to optimize provider usage
- Use paper trading in development

---

Quick links: [Full Documentation](./AGENT_FRAMEWORK.md) | [API Docs](/docs)
