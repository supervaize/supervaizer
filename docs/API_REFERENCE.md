# SUPERVAIZER API Reference

This document provides details about the core components and APIs of SUPERVAIZER.

## Core Components

### Agent

The `Agent` class represents a SUPERVAIZE agent and provides methods for agent registration, status checks, and method execution.

```python
from supervaizer import Agent, AgentMethod

agent = Agent(server=server, account=account)
agent.register(name="agent-name")
agent.set_method(AgentMethod.METHOD_NAME, handler_function)
```

### Server

The `Server` class handles communication with the SUPERVAIZE backend services.

```python
from supervaizer import Server

server = Server(api_url="https://api.example.com")
```

### Account

The `Account` class manages authentication and user information.

```python
from supervaizer import Account

account = Account(server=server)
account.login(username="username", password="password")
```

### Events

The event system enables communication between components.

```python
from supervaizer import Event, EventType

event = Event.create(EventType.AGENT_REGISTERED, payload={"agent_id": "123"})
```

### Jobs

The job system handles the execution and tracking of agent tasks.

```python
from supervaizer import Job
from supervaizer import EntityStatus

# Check job status
job = agent.get_job(job_id="job-123")
if job.status == EntityStatus.COMPLETED:
    print("Job completed successfully!")
```

## A2A Protocol API

### Agent Discovery

Retrieve a list of all available agents:

```python
import requests

response = requests.get("https://your-server/.well-known/agents.json")
agents = response.json()
```

### Agent Cards

Retrieve detailed information about a specific agent:

```python
import requests

response = requests.get(f"https://your-server/.well-known/agents/v1.0.0/myagent_agent.json")
agent_card = response.json()
```

### Health Status

Check the health status of all agents:

```python
import requests

response = requests.get("https://your-server/.well-known/health")
health_data = response.json()
```

## Additional Components

### Parameters

The parameter system manages agent-specific configuration:

```python
from supervaizer import Parameter, Parameters

params = Parameters.from_list([
    Parameter(name="api_key", value="your-api-key", is_secret=True),
    Parameter(name="endpoint", value="https://api.example.com")
])
```

### Telemetry

The telemetry system provides monitoring and logging capabilities:

```python
from supervaizer import Telemetry, TelemetryType, TelemetryCategory, TelemetrySeverity

telemetry = Telemetry(
    agent_id="agent-123",
    type=TelemetryType.LOGS,
    category=TelemetryCategory.PERFORMANCE,
    severity=TelemetrySeverity.INFO,
    details={"message": "Processing complete", "duration_ms": 250}
)
```

## Advanced Usage

### Creating Custom Agents

Example of creating a custom agent with specialized methods:

```python
from supervaizer import Agent, AgentMethod, AgentMethods

def process_data(data):
    # Process data
    return {"result": "processed"}

# Define agent methods
methods = AgentMethods(
    job_start=AgentMethod(
        name="start_processing",
        method="process_data",
        description="Start processing data"
    ),
    job_stop=AgentMethod(
        name="stop_processing",
        method="stop_process",
        description="Stop processing data"
    ),
    job_status=AgentMethod(
        name="check_status",
        method="get_status",
        description="Check processing status"
    )
)

# Create agent
agent = Agent(
    name="data-processor",
    version="1.0.0",
    description="Agent for processing data",
    methods=methods
)
```
