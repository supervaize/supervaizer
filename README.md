# SUPERVAIZER

[[Operate AI Agents with confidence]]

A Python toolkit for building, managing, and connecting AI agents with full [Agent-to-Agent (A2A)](https://google.github.io/A2A/#/) and [Agent Communication Protocol (ACP)](https://github.com/i-am-bee/ACP) support.

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![Package Version](https://img.shields.io/badge/Supervaizer-0.9.6-yellow.svg)](https://github.com/supervaize/supervaizer)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-orange.svg)](https://google.github.io/A2A/)
[![ACP Protocol](https://img.shields.io/badge/ACP-Protocol-purple.svg)](https://github.com/i-am-bee/ACP)
[![Test Coverage](https://img.shields.io/badge/Coverage-81%25-brightgreen.svg)](https://github.com/supervaize/supervaizer)

- [SUPERVAIZER](#supervaizer)
  - [Description](#description)
  - [Quick Start](#quick-start)
    - [What we'll do](#what-well-do)
    - [1. Install Supervaizer](#1-install-supervaizer)
    - [3. Scaffold the controller](#3-scaffold-the-controller)
    - [(Optional) 4. Configure your Supervaize account \& environment](#optional-4-configure-your-supervaize-account--environment)
    - [5. Start the server 🚀](#5-start-the-server-)
    - [What's next?](#whats-next)
  - [Features](#features)
  - [Protocol Support](#protocol-support)
  - [Using the CLI](#using-the-cli)
  - [API Documentation \& User Interfaces](#api-documentation--user-interfaces)
    - [Admin Interface (`/admin`)](#admin-interface-admin)
      - [Quick Start](#quick-start-1)
- [Calculating costs](#calculating-costs)
  - [Documentation](#documentation)
  - [Contributing](#contributing)
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

Kickstart a **Python** agent with the **Supervaizer Controller** so it's discoverable and operable by Supervaize.

### What we'll do

1. **Install Supervaizer** in that project
2. **Scaffold the controller** and map it to your agent
3. **Configure secrets & env**, then **start** the server 🚀

### 1. Install Supervaizer

First, navigate to your existing Python AI agent project. This could be built with any framework - LangChain, CrewAI, AutoGen, or your own custom implementation. Supervaizer works as a wrapper around your existing agent, regardless of the underlying framework you're using.

```bash
pip install supervaizer
```

### 3. Scaffold the controller

Generate a starter controller in your project:

```bash
supervaizer scaffold
# Success: Created an example file at supervaizer_control_example.py
```

This creates **`supervaizer_control_example.py`**. You'll customize it to:

- Define **agent parameters** (secrets, env, required inputs)
- Define **agent methods** (start/stop/status, etc.)
- Map those methods to **your agent's functions**

### (Optional) 4. Configure your Supervaize account & environment

Create your developer account on the [Supervaize platform](https://www.supervaize.com).

Create your API Key and collect your environment variables:

```bash
export SUPERVAIZE_API_KEY=...
export SUPERVAIZE_WORKSPACE_ID=team_1
export SUPERVAIZE_API_URL=https://app.supervaize.com
```

### 5. Start the server 🚀

```bash
# with the virtual environment active
supervaizer start
```

Or run directly:

```bash
python supervaizer_control.py
```

Once the server is running, you'll have:

- **API docs**: `http://127.0.0.1:8000/docs` (Swagger) and `/redoc`
- **A2A discovery**: `/.well-known/agents.json`
- **ACP discovery**: `/agents`

### What's next?

- Add more **custom methods** (`chat`, `custom`) to extend control
- Turn on **A2A / ACP** discovery for interoperability
- Hook your controller into Supervaize to **monitor, audit, and operate** the agent

For detailed instructions on customizing your controller, see the [Controller Setup Guide](https://doc.supervaize.com/docs/supervaizer-controller/controller-setup-guide).

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

For a full tutorial and example usage, go to [doc.supervaize.com](https://doc.supervaize.com)

## Contributing

We welcome contributions from the community! Whether you're fixing bugs, adding features, improving documentation, or sharing feedback, your contributions help make SUPERVAIZER better for everyone.

Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started, coding standards, and the contribution process.

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE.md) License.
