# Protocol Support

> **Created:** 2025-08-06
> **Updated:** 2026-09-25

SUPERVAIZER uses several protocol layers. They are related, but they do different jobs:

| Layer | Role in Supervaizer | Current status |
| --- | --- | --- |
| **A2A** | Transport and discovery: Agent Cards, controller URL, JSON-RPC method calls, and event streams. | Implemented for discovery, `supervaizer/action.invoke`, `supervaizer/surface.load`, and SSE observation. |
| **A2UI** | Surface payloads: declarative UI documents for Studio-rendered forms, dashboards, detail views, and mounted resource workflows. | Implemented as the payload format returned by `supervaizer/surface.load`. |
| **AG-UI** | Live agent-user runtime: bidirectional event flow for streaming messages, tool calls, state updates, and interactive agent sessions. | Not part of the MVP runtime; v2 registration only carries optional `ag_ui_version` metadata. |
| **Supervaizer v2** | Application semantics: Jobs, Cases, Steps, Resources, Datasets, Surfaces, Actions, Artifacts, and sync/offline policy. | Implemented as the Studio operation contract layered on A2A and A2UI. |

The detailed Supervaizer v2 model is documented in [2026_05_SUPERVAIZER_v2.md](2026_05_SUPERVAIZER_v2.md).

## Agent-to-Agent (A2A) Protocol

### Overview

SUPERVAIZER implements [A2A](https://a2a-protocol.org/)-style agent discovery and a JSON-RPC controller endpoint. The Agent Card is Supervaizer's own format (`schema_version: a2a_2023_v1`) and does not follow the upstream A2A AgentCard schema field for field.

### Implemented A2A Features

- **Agent Discovery**: `/.well-known/agents.json` lists every agent served by the controller
- **Agent Cards**: `/.well-known/agents/v{version}/{agent_slug}_agent.json`, plus the unversioned legacy route `/.well-known/agents/{agent_slug}_agent.json`
- **Health Monitoring**: system and agent health at `/.well-known/health`
- **JSON-RPC Controller Endpoint**: `POST /a2a` supports Supervaizer v2 methods including `supervaizer/action.invoke` and `supervaizer/surface.load`; requests require `X-API-Key` with write scope
- **Server-Sent Events**: `GET /a2a/events` streams Supervaizer v2 action effects for observers that need a live feed; requests require `X-API-Key` with read scope

### Supervaizer v2 Agent Card Extension

When an agent declares `supervaizer_v2_registration`, its A2A Agent Card includes a `supervaizer.v2` extension. Studio reads this extension to validate protocol compatibility and discover:

- pinned protocol versions: `supervaizer_contract_version`, `a2a_version`, `a2ui_version`, optional `ag_ui_version`, and agent-specific `a2ui_catalog_version`
- controller URLs and transport support
- supported surfaces and actions
- case lanes and artifact types
- resource, dataset, and dashboard contracts
- job policy, including `job.sync` support and offline behavior

This extension does **not** replace the existing Studio server-registration trust model. Studio registration still owns server identity, public key exchange, and encrypted payload handling. The A2A Agent Card advertises the v2 operational contract after the controller is known.

### Workspace Authorization

Workspace and tenant slugs are not enough to authorize shared-agent access. A Supervaizer v2 controller should treat them as display and routing hints only.

The shared-agent model uses a Studio-owned Workspace Agent Grant and a short-lived Studio-signed workspace authorization token. Studio sends the token with Studio-to-agent requests, and the Supervaizer SDK verifies it before dispatching handlers. This lets stateless agents safely serve multiple workspaces without storing grant state locally.

Studio sends the token in the `X-Supervaize-Workspace-Authorization: Bearer <token>` header. With `SUPERVAIZER_WORKSPACE_AUTH_REQUIRED` unset, every non-bootstrap `/a2a` call fails with JSON-RPC error `-32030 workspace_authorization_not_configured`; this includes local mode.

See [2026_05_WORKSPACE_AGENT_GRANTS.md](2026_05_WORKSPACE_AGENT_GRANTS.md).

### Supervaizer v2 JSON-RPC Methods

Supervaizer v2 currently exposes two A2A JSON-RPC methods:

| Method                      | Purpose                                                                                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `supervaizer/surface.load`  | Load an agent-owned A2UI document for a known surface such as `job.start`, `case.step.awaiting`, or `mission.analytics`.                             |
| `supervaizer/action.invoke` | Invoke a typed agent action such as `job.start`, `job.sync`, `step.awaiting.submit`, `resource.contacts.create`, or `dataset.session_metrics.query`. |

Both methods are scoped by `agent_slug`. In multi-agent controllers, handlers must be registered for the correct agent slug.

Every action and surface requires a Studio-signed workspace authorization token,
except the bootstrap set: the `workspace_binding.options` and
`workspace_binding.create` actions and the `workspace_binding.create` surface.
These calls are used before a Workspace Agent Grant exists, so they require
normal Studio-to-agent transport authentication but not a workspace
authorization token.

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

With a running controller, the A2A routes are listed under the `Protocol A2A` tag in the Swagger UI at `http://127.0.0.1:8000/docs`.

### Not Yet Implemented

- **A2A push notifications**: callback delivery instead of JSON-RPC polling or SSE observation. Not advertised until implemented.
- **AG-UI runtime**: optional bidirectional streaming runtime for live agent sessions. Registrations only carry `ag_ui_version` metadata.

## Enabling Protocol Support

A2A endpoints are enabled by default. `a2a_endpoints=False` is honoured only for a standalone server; when a `supervisor_account` is set or local mode is on, the server forces it back to `True`.

```python
server = Server(
    agents=[agent],
    a2a_endpoints=True,  # Enable A2A protocol support (default: True)
)
```

For the latest protocol specifications, see [a2a-protocol.org](https://a2a-protocol.org/), [a2ui.org](https://a2ui.org/), and [docs.ag-ui.com](https://docs.ag-ui.com/introduction).
