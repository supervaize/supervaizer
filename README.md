# SUPERVAIZE Controller

A Python library for managing and controlling SUPERVAIZE agents and services.

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Package Version](https://img.shields.io/badge/version-0.1.5-green.svg)](https://github.com/supervaize/supervaize_control)

## Description

SUPERVAIZE Controller is a Python library designed to facilitate communication with and management of SUPERVAIZE agents. It provides a robust API for agent registration, job control, event handling, telemetry, and more.

## Features

- **Agent Management**: Register, update, and control agents
- **Job Control**: Create, track, and manage jobs
- **Event Handling**: Process and respond to system events
- **Telemetry**: Monitor and analyze system performance
- **Server Communication**: Interact with SUPERVAIZE servers
- **Account Management**: Manage user accounts and authentication

## Installation

```bash
pip install supervaize-control
```

Or with development dependencies:

```bash
pip install "supervaize-control[dev]"
```

## Quick Start

```python
from supervaize_control import Server, Agent, Account

# Initialize a connection to the SUPERVAIZE server
server = Server(api_url="https://api.example.com")

# Create an account
account = Account(server=server)
account.login(username="your_username", password="your_password")

# Register an agent
agent = Agent(server=server, account=account)
agent.register(name="my-agent", description="My awesome agent")

# Check agent status
status = agent.get_status()
print(f"Agent status: {status}")
```

## API Reference

### Core Components

#### Agent

The `Agent` class represents a SUPERVAIZE agent and provides methods for agent registration, status checks, and method execution.

```python
from supervaize_control import Agent, AgentMethod

agent = Agent(server=server, account=account)
agent.register(name="agent-name")
agent.set_method(AgentMethod.METHOD_NAME, handler_function)
```

#### Server

The `Server` class handles communication with the SUPERVAIZE backend services.

```python
from supervaize_control import Server

server = Server(api_url="https://api.example.com")
```

#### Account

The `Account` class manages authentication and user information.

```python
from supervaize_control import Account

account = Account(server=server)
account.login(username="username", password="password")
```

#### Events

The event system enables communication between components.

```python
from supervaize_control import Event, EventType

event = Event.create(EventType.AGENT_REGISTERED, payload={"agent_id": "123"})
```

#### Jobs

The job system handles the execution and tracking of agent tasks.

```python
from supervaize_control import Job, JobStatus

# Check job status
job = agent.get_job(job_id="job-123")
if job.status == JobStatus.COMPLETED:
    print("Job completed successfully!")
```

## Development

This project uses [just](https://github.com/casey/just) as a command runner. Here are the available commands:

`just -l`

### Setup Development Environment

1. Clone the repository
2. Set up a virtual environment: `python -m venv .venv`
3. Activate the environment:
   - Windows: `.venv\Scripts\activate`
   - Unix/MacOS: `source .venv/bin/activate`
4. Install development dependencies: `pip install -e ".[dev]"`

### Running Tests

```bash
pytest
```

Or for specific test categories:

```bash
pytest -m "not slow"  # Skip slow tests
pytest -m "current"   # Run tests under development
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE.md) License.
