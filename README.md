# SUPERVAIZER

A Python toolkit for building, managing, and connecting AI agents with full [Agent-to-Agent (A2A)](https://google.github.io/A2A/#/) protocol support.

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![Package Version](https://img.shields.io/badge/Supervaizer-0.9.4-yellow.svg)](https://github.com/supervaize/supervaizer)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-orange.svg)](https://google.github.io/A2A/)
[![ACP Protocol](https://img.shields.io/badge/A2A-Protocol-purple.svg)](https://github.com/i-am-bee/ACP)
[![Test Coverage](https://img.shields.io/badge/Coverage-81%25-brightgreen.svg)](https://github.com/supervaize/supervaizer)

- [SUPERVAIZER](#supervaizer)
  - [Description](#description)
  - [Quick Start](#quick-start)
    - [Installation](#installation)
  - [Features](#features)
  - [Protocol Support](#protocol-support)
  - [Using the CLI](#using-the-cli)
  - [API Documentation \& User Interfaces](#api-documentation--user-interfaces)
    - [Admin Interface (`/admin`)](#admin-interface-admin)
      - [Quick Start](#quick-start-1)
- [Calculating costs](#calculating-costs)
  - [Documentation](#documentation)
  - [License](#license)

## Description

SUPERVAIZER is a toolkit built for the age of AI interoperability. At its core, it implements Google's Agent-to-Agent (A2A) protocol and IBM's Agent Communication Protocol (ACP), enabling seamless discovery and interaction between agents across different systems and platforms.

With comprehensive support for the A2A/ACP protocols, specification, SUPERVAIZER allows you to:

- Enhance the capabilities of your agents, making them automatically discoverable by other A2A/ACP compatible systems
- Expose standardized agent capabilities through agent cards
- Monitor agent health and status through dedicated endpoints
- Connect your agents to the growing ecosystem of A2A-compatible tools

Beyond A2A interoperability, SUPERVAIZER provides a robust API for agent registration, job control, event handling, telemetry, and more, making it a crucial component for building and managing AI agent systems.

## Quick Start

### Installation

```bash
pip install supervaizer
```

```python
# create supervaizer_control.py
from supervaizer import (
    Server,
    Agent,
    AgentMethod,
    Parameter,
    ParametersSetup,
    AgentMethods,
)
# Define at least one AgentMethod
agent_method = AgentMethod(
    name="start",
    method="example_agent.example_synchronous_job_start", #This is the function that is triggered when agent start - THIS MUST BE THE ABOLUTE PATH TO THE METHOD "module.submodule.method  - no parenthesis.
    is_async=False,
    params={"action": "start"},
    fields=[
        {
            "name": "Variable to start agent job",
            "type": str,
            "field_type": "CharField",
            "max_length": 100,
            "required": True,
        }]}

# Define agent parameters (optional)
agent_parameters = ParametersSetup.from_list([
    Parameter(
        name="OPEN_API_KEY",
        description="OpenAPI Key",
        is_environment=True,
    )]),

# Define at least one agent
agent = Agent(
    name="agent_name",
    id="agent_id",
    author="John Doe",
    developer="Developer",
    maintainer="Ive Maintained",
    editor="Yuri Editor",
    version="1.3",
    description="This is a test agent",
    urls={"dev": "http://host.docker.internal:8001", "prod": ""},
    active_environment="dev",
    tags=["testtag", "testtag2"],
    methods=AgentMethods(
        job_start=agent_method,
        job_stop=agent_method, #should be different methods
        job_status=agent_method, # should be different methods
        chat=None,
        custom=None}
    ),
    parameters_setup=agent_parameters,
)

# Initialize a connection to the SUPERVAIZE server
server = Server(
    agents=[agent],
    acp_endpoints=True,  # Enable ACP protocol support
    a2a_endpoints=True,  # Enable A2A protocol support
    admin_interface=True,  # Enable web admin interface (requires api_key)
    api_key="your-secure-api-key",  # Required for admin interface
    supervisor_account=None,
)

# Start the server
sv_server.launch(log_level="DEBUG")

```

For more comprehensive examples, check out the `examples/` directory:

- `examples/a2a-controller.py` - A complete A2A-compatible controller implementation

Run any example with:

```bash
python examples/a2a-controller.py
```

## Features

- **Agent Management**: Register, update, and control agents
- **Job Control**: Create, track, and manage jobs
- **Event Handling**: Process and respond to system events
- Protocol support
  - **A2A Protocol **: Integration with Google's Agent-to-Agent protocol for interoperability
  - **ACP Protocol **: Integration with IBM/BeeAI's Agent Communication Protocol for standardized agent discovery and interaction
- **Server Communication**: Interact with SUPERVAIZE servers (see [supervaize.com](https://www.supervaize.com) for more info)
- **Web Admin Interface**: Easy to use web-based admin dashboard for managing jobs, cases, and system monitoring

## Protocol Support

SUPERVAIZER provides comprehensive support for multiple agent communication protocols. See [Protocol Documentation](docs/PROTOCOLS.md) for complete details.

## Using the CLI

SUPERVAIZER includes a command-line interface to simplify setup and operation. See [CLI Documentation](docs/CLI.md) for complete details.

Also, check the list of [Environment variables](CLI.md#environment-variables).

## API Documentation & User Interfaces

SUPERVAIZER provides multiple ways to interact with and explore the API. See [REST API Documentation](docs/REST_API.md) for complete details.

### Admin Interface (`/admin`)

A comprehensive web-based admin interface for managing your SUPERVAIZER instance
See [Admin documentation](docs/ADMIN_README.md)

#### Quick Start

```python
from supervaizer import Server, Agent

# Create server with admin interface
server = Server(
    agents=[your_agents],
    api_key="your-secure-api-key",  # Required for admin interface
    admin_interface=True,  # Enable admin interface (default: True)
)

server.launch()
print(f"Admin Interface: http://localhost:8000/admin/")
```

# Calculating costs

Developers are free to define the cost of the transaction the way they want when updating the cases.
Here is a way to easily get an estimate of the cost of an LLM transaction (note that litellm also supports custom pricing. )

```python
from litellm import completion_cost
prompt = "Explain how transformers work."
output = "Transformers use attention mechanisms..."
model = "gpt-4"
cost = completion_cost(model=model, prompt=prompt, completion=output)
print(cost)
```

A list of costs is maintained here:
`https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json`

## Documentation

- [Persistence Layer](docs/PERSISTENCE.md) - TinyDB-based storage for Jobs, Cases, and workflow entities

- [API Reference](API_REFERENCE.md) - Complete documentation of classes and methods
- [Contributing Guide](CONTRIBUTING.md) - How to set up your development environment and contribute

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE.md) License.
