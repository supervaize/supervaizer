# Protocol Support

SUPERVAIZER provides comprehensive support for multiple agent communication protocols, enabling seamless interoperability between different AI agent systems.

## Google's Agent-to-Agent (A2A) Protocol

### Overview

SUPERVAIZER implements Google's [Agent-to-Agent (A2A) protocol](https://google.github.io/A2A/#/) for standardized agent discovery and interaction.

### Implemented A2A Features

- **Agent Discovery**: `/.well-known/agents.json` endpoint for listing all available agents
  Note: the current version of the A2A protocol does not support yet multiple agents.
- **Agent Cards**: Detailed agent information available at `/.well-known/agents/v{version}/{agent_slug}_agent.json`
- **Health Monitoring**: Real-time system and agent health data at `/.well-known/health`
- **Versioned Endpoints**: Support for agent versioning with backward compatibility
- **OpenAPI Integration**: Direct links to OpenAPI specifications and documentation
- **Version Information**: Comprehensive version tracking with changelog access

### A2A Examples

```bash
# Discovering Agents
curl https://your-server/.well-known/agents.json

# Agent card
curl https://your-server/.well-known/agents/v1.0.0/myagent_agent.json
```

Full documentation of A2A endpoints can be found at [local A2A](http://127.0.0.1:8001/docs#/Protocol%20A2A)

### Future A2A Enhancements

- **Webhooks**: Event subscription for real-time updates
- **Rich Authentication**: OAuth2 and API key options with scope control
- **Tool Streaming**: Support for streaming responses in long-running operations
- **Extended Metadata**: Licensing, pricing, and usage limit information
- **Localization**: Multi-language support for agent interfaces

## Agent Communication Protocol (ACP)

### Overview

SUPERVAIZER implements IBM/BeeAI's [Agent Communication Protocol (ACP)](https://docs.beeai.dev/acp/spec/concepts/discovery) for standardized agent discovery and interaction.

### Implemented ACP Features

- **Agent Discovery**: `/agents` endpoint for listing all available agents
- **Agent Details**: Detailed agent information available at `/agents/{agent_slug}`
- **Health Monitoring**: Real-time system and agent health data at `/agents/health`
- **Agent Metadata**: Comprehensive metadata including documentation, language support, authors, and more
- **Status Metrics**: Performance metrics like success rate and average runtime
- **Rich Interfaces**: Standardized input/output interfaces with chat capabilities
- **Comprehensive Metadata**: Includes licensing, programming language, framework, use cases, and examples
- **Performance Tracking**: Real-time statistics on job completion rates and average runtime
- **Health Status**: Agent status monitoring (available, busy, degraded)

### Example: Discovering Agents

To discover all agents on a SUPERVAIZER instance:

```bash
# Agent discovery
curl https://your-server/agents

# Agent details
curl https://your-server/agents/myagent

# Health monitoring
curl https://your-server/agents/health
```

Full documentation of ACP endpoints can be found at [local ACP](http://127.0.0.1:8001/docs#/Protocol%20ACP)

## Enabling Protocol Support

ACP endpoints are enabled by default. You can control protocol support when creating your server:

```python
server = Server(
    agents=[agent],
    acp_endpoints=True,  # Enable ACP protocol support (default: True)
    a2a_endpoints=True,  # Enable A2A protocol support
)
```
