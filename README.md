# SUPERVAIZER

A Python toolkit for building, managing, and connecting AI agents with full [Agent-to-Agent (A2A)](https://google.github.io/A2A/#/) protocol support.

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Package Version](https://img.shields.io/badge/version-0.1.5-green.svg)](https://github.com/supervaize/supervaizer)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-orange.svg)](https://google.github.io/A2A/)

## Description

SUPERVAIZER is a toolkit built for the age of AI interoperability. At its core, it implements Google's Agent-to-Agent (A2A) protocol, enabling seamless discovery and interaction between agents across different systems and platforms.

With comprehensive support for the A2A specification, SUPERVAIZER allows you to:

- Enhance the capabilities of your agents, making them automatically discoverable by other A2A systems
- Expose standardized agent capabilities through agent cards
- Monitor agent health and status through dedicated endpoints
- Connect your agents to the growing ecosystem of A2A-compatible tools

Beyond A2A interoperability, SUPERVAIZER provides a robust API for agent registration, job control, event handling, telemetry, and more, making it a crucial component for building and managing AI agent systems.

## Features

- **Agent Management**: Register, update, and control agents
- **Job Control**: Create, track, and manage jobs
- **Event Handling**: Process and respond to system events
- **Telemetry**: Monitor and analyze system performance
- **Server Communication**: Interact with SUPERVAIZE servers
- **Account Management**: Manage user accounts and authentication
- **A2A Protocol Support**: Integration with Google's Agent-to-Agent protocol for interoperability

## A2A Protocol Support

SUPERVAIZER implements [Google's Agent-to-Agent (A2A) protocol](https://google.github.io/A2A/#/), providing standardized discovery and interaction with agents across different platforms and systems.

### Implemented A2A Features

- **Agent Discovery**: `/.well-known/agents.json` endpoint for listing all available agents
- **Agent Cards**: Detailed agent information available at `/.well-known/agents/v{version}/{agent_slug}_agent.json`
- **Health Monitoring**: Real-time system and agent health data at `/.well-known/health`
- **Versioned Endpoints**: Support for agent versioning with backward compatibility
- **OpenAPI Integration**: Direct links to OpenAPI specifications and documentation
- **Version Information**: Comprehensive version tracking with changelog access

### Benefits of A2A Integration

- **Interoperability**: Your agents can be discovered and used by any A2A-compatible client
- **Standardized Interface**: Consistent API structure across all agents and platforms
- **Self-Documentation**: Automatic generation of comprehensive agent cards with capabilities
- **Health Insights**: Real-time monitoring of agent status and performance metrics
- **Future-Proofing**: Join the emerging standard for agent interoperability

### Example: Discovering Agents

To discover all agents on a SUPERVAIZER instance:

```bash
curl https://your-server/.well-known/agents.json
```

### Example: Agent Card

To access a specific agent's capabilities:

```bash
curl https://your-server/.well-known/agents/v1.0.0/myagent_agent.json
```

### Future A2A Enhancements

- **Webhooks**: Event subscription for real-time updates
- **Rich Authentication**: OAuth2 and API key options with scope control
- **Tool Streaming**: Support for streaming responses in long-running operations
- **Extended Metadata**: Licensing, pricing, and usage limit information
- **Localization**: Multi-language support for agent interfaces

## Installation

```bash
pip install supervaizer
```

Or with development dependencies:

```bash
pip install "supervaizer[dev]"
```

## Quick Start

```python
from supervaizer import Server, Agent, Account

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
```

For more comprehensive examples, check out the `examples/` directory:

- `examples/a2a-controller.py` - A complete A2A-compatible controller implementation

Run any example with:

```bash
python examples/a2a-controller.py
```

## Documentation

- [API Reference](API_REFERENCE.md) - Complete documentation of classes and methods
- [Contributing Guide](CONTRIBUTING.md) - How to set up your development environment and contribute

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE.md) License.
