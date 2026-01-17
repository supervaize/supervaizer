# SUPERVAIZER

[Operate AI Agents with confidence]

A Python toolkit for building, managing, and connecting AI agents with full [Agent-to-Agent (A2A)](https://a2a-protocol.org/) protocol support.

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-orange.svg)](https://a2a-protocol.org/)
[![Test Coverage](https://img.shields.io/badge/Coverage-81%25-brightgreen.svg)](https://github.com/supervaize/supervaizer)

> **⚠️ Beta Disclaimer**: SUPERVAIZER is currently in beta mode. Not everything works as expected yet. Please report any issues you encounter.

- [SUPERVAIZER](#supervaizer)
  - [Description](#description)
  - [Quick Start](#quick-start)
    - [What we'll do](#what-well-do)
    - [1. Install Supervaizer](#1-install-supervaizer)
    - [3. Scaffold the controller](#3-scaffold-the-controller)
    - [(Optional) 4. Configure your Supervaize account \& environment](#optional-4-configure-your-supervaize-account--environment)
    - [5. Start the server 🚀](#5-start-the-server-)
    - [6. Optional parameters](#6-optional-parameters)
    - [What's next?](#whats-next)
  - [Features](#features)
  - [Protocol Support](#protocol-support)
  - [Cloud Deployment](#cloud-deployment)
    - [Quick Start](#quick-start-1)
    - [Deployment Commands](#deployment-commands)
    - [Features](#features-1)
    - [Documentation](#documentation)
  - [Using the CLI](#using-the-cli)
  - [API Documentation \& User Interfaces](#api-documentation--user-interfaces)
    - [Admin Interface (`/admin`)](#admin-interface-admin)
      - [Quick Start](#quick-start-2)
- [Calculating costs](#calculating-costs)
  - [Documentation](#documentation-1)
  - [Contributing](#contributing)
  - [License](#license)

## Description

SUPERVAIZER is a toolkit built for the age of AI interoperability. At its core, it implements the Agent-to-Agent (A2A) protocol, enabling seamless discovery and interaction between agents across different systems and platforms.

With comprehensive support for the A2A protocol specification, SUPERVAIZER allows you to:

- Enhance the capabilities of your agents, making them automatically discoverable by other A2A compatible systems
- Expose standardized agent capabilities through agent cards
- Monitor agent health and status through dedicated endpoints
- Connect your agents to the growing ecosystem of A2A-compatible tools

Beyond A2A interoperability, SUPERVAIZER provides a robust API for agent registration, job control, event handling, telemetry, and more, making it a crucial component for building and managing AI agent systems.

SUPERVAIZER is the recommended controller to integrate AI Agents into the [supervaize](https://supervaize.com) plateform.

## Quick Start

Kickstart a **Python** agent with the **Supervaizer Controller** so it's discoverable and operable by Supervaize.

See full our full [documentation](https://doc.supervaize.com/docs/category/supervaizer-controller)

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

### 6. Optional parameters

Configure retry behavior for HTTP requests to the Supervaize API:

- **`SUPERVAIZE_HTTP_MAX_RETRIES`**: Number of retry attempts for failed HTTP requests (default: `2`). The client will automatically retry requests that fail with status codes 429, 500, 502, 503, or 504.

```bash
export SUPERVAIZE_MAX_HTTP_RETRIES=3  # Will attempt up to 4 times total (1 original + 3 retries)
```

### What's next?

- Add more **custom methods** (`chat`, `custom`) to extend control
- Turn on **A2A** discovery for interoperability
- Hook your controller into Supervaize to **monitor, audit, and operate** the agent

For detailed instructions on customizing your controller, see the [Controller Setup Guide](https://doc.supervaize.com/docs/supervaizer-controller/controller-setup)

## Features

- **Agent Management**: Register, update, and control agents
- **Job Control**: Create, track, and manage jobs
- **Event Handling**: Process and respond to system events
- **🚀 Cloud Deployment**: Automated deployment to GCP Cloud Run, AWS App Runner, and DigitalOcean App Platform
- **A2A Protocol Support**: Full integration with the Agent-to-Agent protocol for standardized agent discovery and interaction
- **Server Communication**: Interact with SUPERVAIZE servers (see [supervaize.com](https://www.supervaize.com) for more info)
- **Web Admin Interface**: Easy to use web-based admin dashboard for managing jobs, cases, and system monitoring

## Protocol Support

SUPERVAIZER provides comprehensive support for the A2A agent communication protocol. See [Protocol Documentation](docs/PROTOCOLS.md) for complete details.

## Cloud Deployment

SUPERVAIZER includes a powerful deployment CLI that automates the entire process of deploying your agents to production cloud platforms.

### Quick Start

```bash
# Install with deployment dependencies
pip install supervaizer[deploy]

# Test locally with Docker
supervaizer deploy local --generate-api-key --generate-rsa

# Deploy to Google Cloud Run
supervaizer deploy up --platform cloud-run --region us-central1

# Deploy to AWS App Runner
supervaizer deploy up --platform aws-app-runner --region us-east-1

# Deploy to DigitalOcean App Platform
supervaizer deploy up --platform do-app-platform --region nyc
```

### Deployment Commands

- **`supervaizer deploy plan`** - Preview deployment actions before applying
- **`supervaizer deploy up`** - Deploy to cloud platform with automated build, push, and verification
- **`supervaizer deploy down`** - Tear down deployment and clean up resources
- **`supervaizer deploy status`** - Check deployment status and health
- **`supervaizer deploy local`** - Local Docker testing with docker-compose
- **`supervaizer deploy clean`** - Clean up deployment artifacts and state

### Features

- ✅ **Automated Docker Workflow**: Build → Push → Deploy → Verify
- ✅ **Secret Management**: Secure handling of API keys and RSA keys
- ✅ **Health Verification**: Automatic health checks at `/.well-known/health`
- ✅ **Idempotent Deployments**: Safe create/update operations with rollback on failure
- ✅ **Local Testing**: Full Docker Compose environment for pre-deployment testing

### Documentation

- [RFC-001: Cloud Deployment CLI](docs/rfc/001-cloud-deployment-cli.md) - Complete specification
- [Local Testing Guide](docs/LOCAL_TESTING.md) - Docker testing documentation

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
