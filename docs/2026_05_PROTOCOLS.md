# Protocol Support

> **Created:** 2025-08-06
> **Updated:** 2026-05-17

SUPERVAIZER uses several protocol layers. They are related, but they do different jobs:

| Layer              | Role in Supervaizer                                                                                           | Current status                                                                |
| ------------------ | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **A2A**            | Transport and discovery:                                                                                      | Implemented for discovery,                                                    |
|                    | Agent Cards, controller URL, JSON-RPC method calls, and event streams.                                        | `supervaizer/action.invoke`, `supervaizer/surface.load`, and SSE observation. |
| **A2UI**           | Surface payloads:                                                                                             | Implemented as the payload format                                             |
|                    | declarative UI documents for Studio-rendered forms, dashboards, detail views, and mounted resource workflows. | returned by `supervaizer/surface.load`.                                       |
| **AG-UI**          | Live agent-user runtime:                                                                                      | Not part of the MVP runtime;                                                  |
|                    | bidirectional event flow for streaming messages, tool calls, state updates, and interactive agent sessions.   | v2 registration only carries optional `ag_ui_version` metadata.               |
| **Supervaizer v2** | Application semantics:                                                                                        | Implemented as the Studio operation contract                                  |
|                    | Jobs, Cases, Steps, Resources, Datasets, Surfaces, Actions, Artifacts, and sync/offline policy.               | layered on A2A and A2UI.                                                      |

The detailed Supervaizer v2 model is documented in [2026_05_SUPERVAIZER_v2.md](2026_05_SUPERVAIZER_v2.md).

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
- **JSON-RPC Controller Endpoint**: `/a2a` supports Supervaizer v2 methods including `supervaizer/action.invoke` and `supervaizer/surface.load`
- **Server-Sent Events**: `/a2a/events` streams Supervaizer v2 action effects for observers that need a live feed

### Supervaizer v2 Agent Card Extension

When an agent declares `supervaizer_v2_registration`, its A2A Agent Card includes a `supervaizer.v2` extension. Studio reads this extension to validate protocol compatibility and discover:

- pinned protocol versions: `supervaizer_contract_version`, `a2a_version`, `a2ui_version`, optional `ag_ui_version`, and agent-specific `a2ui_catalog_version`
- controller URLs and transport support
- supported surfaces and actions
- case lanes and artifact types
- resource, dataset, and dashboard contracts
- job policy, including `job.sync` support and offline behavior

This extension does **not** replace the existing Studio server-registration trust model. Studio registration still owns server identity, public key exchange, and encrypted payload handling. The A2A Agent Card advertises the v2 operational contract after the controller is known.

### Supervaizer v2 JSON-RPC Methods

Supervaizer v2 currently exposes two A2A JSON-RPC methods:

| Method                      | Purpose                                                                                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `supervaizer/surface.load`  | Load an agent-owned A2UI document for a known surface such as `job.start`, `case.step.awaiting`, or `mission.analytics`.                             |
| `supervaizer/action.invoke` | Invoke a typed agent action such as `job.start`, `job.sync`, `step.awaiting.submit`, `resource.contacts.create`, or `dataset.session_metrics.query`. |

Both methods are scoped by `agent_slug`. In multi-agent controllers, handlers must be registered for the correct agent slug.

### Transport Status

The current MVP advertises:

- `json_rpc: true`
- `sse: true`
- `push_notifications: false`

A2A push notifications are intentionally not advertised until they are implemented. External A2A interop flags, such as inbound tasks and outbound delegation, default to `false` and should be enabled only when a controller actually implements those flows.

### A2UI Version Pinning

Supervaizer v2 registrations include a frozen A2UI protocol version and an agent-owned A2UI catalog version. This is separate from the Python package version:

- `SUPERVAIZER_V2_CONTRACT_VERSION` identifies the Supervaizer v2 semantic contract.
- `SUPERVAIZER_V2_A2A_VERSION` identifies the supported A2A protocol version.
- `SUPERVAIZER_V2_A2UI_VERSION` identifies the supported A2UI payload version.
- `a2ui_catalog_version` identifies the agent's own surface-document catalog.

Studio should reject incompatible protocol versions explicitly instead of attempting best-effort rendering.

## Agent-to-User Interface (A2UI) Protocol

SUPERVAIZER uses the [A2UI protocol](https://a2ui.org/) for agent-driven interface documents. A2UI is a declarative UI protocol: agents return structured component descriptions, and clients render those descriptions with their own native widgets instead of executing arbitrary agent-provided code.

Useful source links:

- [A2UI home](https://a2ui.org/)
- [What is A2UI?](https://a2ui.org/introduction/what-is-a2ui/)
- [A2UI v0.8 specification](https://a2ui.org/specification/v0.8-a2ui/)
- [A2UI v0.9 specification](https://a2ui.org/specification/v0.9-a2ui/)

In Supervaizer v2, A2UI is used for surface payloads:

- `job.start` forms
- `case.step.awaiting` HITL forms or review UIs
- `case.step.detail` rich step/artifact detail views
- `mission.analytics` dashboards
- `mission.agent.overview` pages
- mounted resource views such as prompt editors, scenario builders, or contact import flows

Mounted HITL surfaces can return specialized A2UI document types, such as `DocumentReview`, through the generic `V2SurfaceResult.document` payload. Supervaizer keeps this opaque and typed only as an A2UI document transport; the agent declares the surface/action and Studio renders the document.

Mounted resource import views can return `ResourceImport`. This document declares contextual fields, accepted file formats, row columns, and the submit action. Studio uses it to communicate and enforce the import structure, while the agent still owns validation and persistence.

Dashboard declarations live in the Supervaizer v2 registration contract. Widgets can point at datasets, typed actions, or inline data, and can declare `visualization: { type: "vega-lite", spec: ... }` using the [Vega-Lite](https://vega.github.io/vega-lite/) JSON grammar. This ports the useful chart declaration idea into the generic contract without reviving AnalyticsResource REST routes.

SUPERVAIZER does not render A2UI. The controller transports A2UI documents through `supervaizer/surface.load`; Studio validates the declared `a2ui_version` and renders the document.

## Agent-User Interaction (AG-UI) Protocol

AG-UI is the [Agent-User Interaction Protocol](https://docs.ag-ui.com/introduction). It is an event-based protocol for connecting agent backends to user-facing applications when the interaction is live, streaming, and bidirectional.

Useful source links:

- [AG-UI documentation](https://docs.ag-ui.com/introduction)
- [AG-UI core architecture](https://docs.ag-ui.com/concepts/architecture)
- [AG-UI agents concept](https://docs.ag-ui.com/concepts/agents)
- [AG-UI GitHub repository](https://github.com/ag-ui-protocol/ag-ui)

AG-UI is a good fit for:

- streaming assistant messages and partial outputs
- exposing tool calls and tool results while they happen
- synchronizing live agent state into a frontend
- collaborative chat-style workflows
- interrupt, approval, or live human-in-the-loop interactions

In the Supervaizer v2 MVP, AG-UI is **not** the runtime used for Studio job management. Studio currently operates agents through A2A JSON-RPC actions, A2UI surface documents, and `job.sync` snapshots. The v2 registration has an optional `ag_ui_version` field so an agent can later advertise a compatible AG-UI runtime without changing the rest of the v2 contract.

The intended division is:

| Need                                                             | Use            |
| ---------------------------------------------------------------- | -------------- |
| Discover an agent and call controller methods                    | A2A            |
| Render a stable Studio form, dashboard, detail view, or workflow | A2UI           |
| Run a live streaming agent-user session                          | AG-UI          |
| Persist and reconcile Studio operational state                   | Supervaizer v2 |

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
- **A2A Push Notifications**: push delivery for environments that need callback delivery instead of JSON-RPC polling/SSE observation
- **AG-UI Runtime Integration**: optional bidirectional streaming UI runtime for live agent interactions; current v2 registrations only carry `ag_ui_version` metadata

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
