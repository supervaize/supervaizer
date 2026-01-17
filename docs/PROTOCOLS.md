# Protocol Support

SUPERVAIZER provides comprehensive support for the Agent-to-Agent (A2A) protocol, enabling seamless interoperability between different AI agent systems.

## Agent-to-Agent (A2A) Protocol

### Overview

SUPERVAIZER implements the [Agent-to-Agent (A2A) protocol](https://a2a-protocol.org/) for standardized agent discovery and interaction.

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

## Enabling Protocol Support

A2A endpoints are enabled by default. You can control protocol support when creating your server:

```python
server = Server(
    agents=[agent],
    a2a_endpoints=True,  # Enable A2A protocol support (default: True)
)
```

## Protocol Evolution

The A2A protocol has evolved to incorporate features from multiple agent communication standards, including the former Agent Communication Protocol (ACP). This unified approach provides a comprehensive standard for agent interoperability across different systems and platforms.

For the latest protocol specifications and updates, visit [a2a-protocol.org](https://a2a-protocol.org/).
