# SUPERVAIZER

A Python toolkit for building, managing, and connecting AI agents with full [Agent-to-Agent (A2A)](https://google.github.io/A2A/#/) protocol support.

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Package Version](https://img.shields.io/badge/Supervaizer-0.6.0-yellow.svg)](https://github.com/supervaize/supervaizer)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-orange.svg)](https://google.github.io/A2A/)
[![Test Coverage](https://img.shields.io/badge/Coverage-80%25-brightgreen.svg)](https://github.com/supervaize/supervaizer)

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
  Note: the current version of the A2A protocol does not support yet multiple agents.
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

## ACP Protocol Support

SUPERVAIZER also implements the [Agent Communication Protocol (ACP)](https://docs.beeai.dev/acp/spec/concepts/discovery), providing standardized discovery and interaction with agents according to BeeAI's ACP specification.

### Implemented ACP Features

- **Agent Discovery**: `/agents` endpoint for listing all available agents
- **Agent Details**: Detailed agent information available at `/agents/{agent_slug}`
- **Health Monitoring**: Real-time system and agent health data at `/agents/health`
- **Agent Metadata**: Comprehensive metadata including documentation, language support, authors, and more
- **Status Metrics**: Performance metrics like success rate and average runtime

### Benefits of ACP Integration

- **Interoperability**: Your agents can be discovered and used by any ACP-compatible client
- **Standardized Interface**: Consistent API structure across all agents and platforms
- **Rich Metadata**: Automatically includes comprehensive metadata about agent capabilities
- **Health Insights**: Real-time monitoring of agent status and performance metrics
- **Multi-Protocol Support**: Works alongside A2A to provide maximum interoperability

### Example: Discovering Agents

To discover all agents on a SUPERVAIZER instance:

```bash
curl https://your-server/agents
```

### Example: Agent Detail

To access a specific agent's capabilities:

```bash
curl https://your-server/agents/myagent
```

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
server = Server(agents=[agent],
    acp_endpoints=True,
    a2a_endpoints=True,
    supervisor_account=None,)

# Start the server
sv_server.launch(log_level="DEBUG")

```

For more comprehensive examples, check out the `examples/` directory:

- `examples/a2a-controller.py` - A complete A2A-compatible controller implementation

Run any example with:

```bash
python examples/a2a-controller.py
```

## Using the CLI

SUPERVAIZER includes a command-line interface to simplify setup and operation:

```bash
# Install Supervaizer
pip install supervaizer

# Create a supervaizer_control.py file in your current directory
supervaizer install

# Start the server using the configuration file
supervaizer start
```

### CLI Commands

- **install**: Creates a starter configuration file (supervaizer_control.py)

  ```bash
  # Basic usage (creates supervaizer_control.py in current directory)
  supervaizer install

  # Specify a custom output path
  supervaizer install --output-path=my_config.py

  # Force overwrite if file already exists
  supervaizer install --force
  ```

- **start**: Starts the Supervaizer server

  ```bash
  # Basic usage (loads supervaizer_control.py from current directory)
  supervaizer start

  # Specify a custom configuration file
  supervaizer start my_config.py

  # Configure server options
  supervaizer start --host=0.0.0.0 --port=8080 --environment=production

  # Enable debug mode and auto-reload
  supervaizer start --debug --reload

  # Set log level
  supervaizer start --log-level=DEBUG
  ```

### Environment Variables

All CLI options can also be configured through environment variables:

| Environment Variable      | Description                     | Default Value          |
| ------------------------- | ------------------------------- | ---------------------- |
| SUPERVAIZER_HOST          | Host to bind the server to      | 0.0.0.0                |
| SUPERVAIZER_PORT          | Port to bind the server to      | 8000                   |
| SUPERVAIZER_ENVIRONMENT   | Environment name                | dev                    |
| SUPERVAIZER_LOG_LEVEL     | Log level (DEBUG, INFO, etc.)   | INFO                   |
| SUPERVAIZER_DEBUG         | Enable debug mode (true/false)  | false                  |
| SUPERVAIZER_RELOAD        | Enable auto-reload (true/false) | false                  |
| SUPERVAIZER_SCRIPT_PATH   | Path to configuration script    | -                      |
| SUPERVAIZER_OUTPUT_PATH   | Path for install command output | supervaizer_control.py |
| SUPERVAIZER_FORCE_INSTALL | Force overwrite existing file   | false                  |

## Agent API Documentation

The SUPERVAIZER API comes with comprehensive interactive documentation:

- **Swagger UI**: Available at `/docs` - Interactive API documentation with request builder and testing tools
- **ReDoc**: Available at `/redoc` - Responsive, searchable API reference documentation

These documentation endpoints provide a complete reference of all available API endpoints, request/response formats, and testing capabilities.

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

- [API Reference](API_REFERENCE.md) - Complete documentation of classes and methods
- [Contributing Guide](CONTRIBUTING.md) - How to set up your development environment and contribute

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE.md) License.
