# Supervaizer v2


> **Created:** 2026-05-16
> **Updated:** 2026-05-17

Supervaizer v2 is the new operation contract between an agent controller and Supervaize Studio.

The goal is simple: Studio should be able to operate many different agents through one generic UI, while each agent keeps ownership of its own business vocabulary and business logic.

## Layering

Supervaizer v2 is layered, not monolithic:

| Layer | Owned by | Role |
| --- | --- | --- |
| A2A | protocol/runtime | discovery, Agent Card, JSON-RPC controller endpoint, SSE events |
| A2UI | protocol/surface payload | UI document shape for forms, dashboards, tables, details, and custom surfaces |
| Supervaizer v2 | Supervaizer SDK + agent | Jobs, Cases, Steps, Resources, Datasets, Artifacts, Surfaces, Actions, and sync semantics |
| Studio | Supervaize Studio | authentication, permissions, rendering, persistence, polling, offline policy, and operator workflow |
| Agent | agent author | business objects, action handlers, validation, resource mutations, artifact content, and state snapshots |

The key rule is: **the universal protocol owns the shape; the agent owns the vocabulary.**

For example, Supervaizer v2 defines that a Case has a `lane`, but the agent decides which lanes exist. Studio knows how to render `setup`, `work`, and `deliverable`, but custom lanes can also be declared and rendered generically.

## Versioning

Supervaizer v2 protocol versions are independent from the Python package version.

| Constant | Meaning |
| --- | --- |
| `SUPERVAIZER_V2_CONTRACT_VERSION` | The semantic contract version for Supervaizer v2. |
| `SUPERVAIZER_V2_A2A_VERSION` | The A2A protocol version the controller advertises. |
| `SUPERVAIZER_V2_A2UI_VERSION` | The A2UI document version the controller emits. |

Every registration also declares `a2ui_catalog_version`, which is the agent-owned version for its own surface documents. Studio can use this to detect when an agent changed its UI catalog even if the shared A2UI version did not change.

Because A2UI is pre-1.0, agents should pin the supported A2UI version in registration. Studio should reject incompatible versions explicitly instead of guessing.

## Registration

An agent declares v2 support through `supervaizer_v2_registration` on the `Agent`.

The recommended path is `build_v2_agent_registration()`:

```python
from supervaizer import Agent
from supervaizer.contracts import (
    V2ResourceDefinition,
    build_v2_agent_registration,
)

registration = build_v2_agent_registration(
    agent_id="research-agent",
    agent_slug="research-agent",
    display_name="Research Agent",
    agent_card_url="/.well-known/agents/v1.0.0/research-agent_agent.json",
    controller_url="/a2a",
    a2ui_catalog_version="research-agent.2026-05-16",
    surfaces=[
        "job.start",
        "case.step.awaiting",
        "case.step.detail",
        "mission.analytics",
    ],
    actions=[
        "job.start",
        "job.stop",
        "step.awaiting.submit",
    ],
    case_lanes=[
        {"id": "setup", "label": "Setup"},
        {"id": "work", "label": "Work", "default": True},
        {"id": "deliverable", "label": "Deliverables"},
    ],
    artifact_types=[
        {"type": "transcript", "label": "Transcript"},
        {"type": "synthesis", "label": "Synthesis"},
    ],
    job_policy={"sync": {"action": "job.sync"}},
    resources=[
        V2ResourceDefinition(
            id="contacts",
            label="Contacts",
            auto_surface=True,
            operations=["list", "create", "update", "import"],
        )
    ],
)

agent = Agent(
    name="Research Agent",
    version="1.0.0",
    supervaizer_v2_registration=registration,
    # v1 fields may still exist during transition in older agents,
    # but new v2 agents should model Studio operation through v2.
)
```

The v2 registration is exposed in the A2A Agent Card under `supervaizer.v2`.

This does not replace the existing Studio server registration process. Server identity, public key exchange, and encrypted payload handling still belong to the normal Studio registration path. The v2 extension tells Studio how to operate the already-registered controller.

## Runtime Handlers

Agents register action and surface handlers on the `Server`.

```python
from supervaizer import Server
from supervaizer.contracts import V2ActionRequest, V2ActionResult, V2SurfaceRequest

server = Server(agents=[agent])


@server.v2_surface("job.start", agent_slug="research-agent")
def load_job_start(request: V2SurfaceRequest) -> dict:
    return {
        "surface": request.surface,
        "document": {
            "type": "Form",
            "fields": [
                {"id": "topic_id", "label": "Topic", "type": "string"},
            ],
            "submit": {"label": "Start research", "action": "job.start"},
        },
    }


@server.v2_action("job.start", agent_slug="research-agent")
def start_job(request: V2ActionRequest) -> V2ActionResult:
    topic_id = request.input["topic_id"]
    return V2ActionResult(
        status="ok",
        effects=[{"type": "job.started", "data": {"topic_id": topic_id}}],
    )
```

Surface handlers return A2UI documents. Action handlers perform business logic and return typed effects, optionally with a full `job_state` snapshot for sync convergence.

## Core Model

### Job

A Job is committed work Studio tracks for an agent.

Studio may load `job.start` before a Job exists. In that case the request can include `draft_session_id`. Agents should treat this as transient UI context. Persistent business state should be created on `job.start`, not on surface load.

Status convergence happens through `job.sync`. `job.sync` does not need to be strictly idempotent in the sense of byte-for-byte identical responses. It should be **convergent**: repeated calls for the same external state should lead Studio to the same Job/Case/Step projection.

### Case

A Case is a unit of work inside a Job. Cases declare a `lane`, which is a rendering hint.

The default lane is `work`. Agents can declare standard or custom lanes:

- `setup`: preparation and pre-flight review
- `work`: primary execution
- `deliverable`: final outputs and reviews
- custom lanes such as `extract`, `transform`, `load`, `verify`

Studio renders unknown lanes generically.

### Step

A Step is an observable activity inside a Case.

In the current SDK model:

- `activity` is `operation` or `delegation`
- `status` carries lifecycle state such as pending, active, awaiting, completed, failed, or cancelled
- `awaiting` carries HITL state when Studio must collect operator input
- `outputs` carries produced artifacts

HITL is therefore not a Step kind. It is represented by `status="awaiting"` plus an `awaiting` object with a surface, action, and fields.

The awaiting `surface` can return any valid A2UI document through `V2SurfaceResult.document`. For mounted review workflows, agents can return a generic `DocumentReview` document that contains document content, submit metadata, and typed fields. Supervaizer does not interpret document-review semantics; Studio renders the A2UI document and invokes the declared action, usually `step.awaiting.submit`.

Example:

```python
V2SurfaceResult(
    surface="case.step.awaiting",
    a2ui_version="v0.8",
    document={
        "type": "DocumentReview",
        "document": {
            "title": "Review",
            "field": "review_text",
            "language": "markdown",
            "value": "# Draft\n\nReview this content.",
            "validation": [
                {"id": "readiness", "label": "Ready for approval", "status": "review"}
            ],
        },
        "submit": {"action": "step.awaiting.submit", "label": "Approve"},
        "fields": [
            {
                "id": "review_text",
                "label": "Review text",
                "type": "text",
                "multiline": True,
                "required": True,
            },
            {
                "id": "approve_review",
                "label": "Approve review",
                "type": "boolean",
                "required": True,
            }
        ],
    },
)
```

### Artifact

Artifacts are agent-owned outputs. The protocol only defines the reference shape:

- `id`
- `type`
- `title`
- optional external id and media type

Artifact types such as `transcript`, `synthesis`, `report`, `metric`, or `decision` belong to the agent registration. Studio can render known artifact types richly and fall back to generic previews for unknown types.

## Resources

Resources are agent-owned business objects Studio can manage generically.

Examples:

- projects
- contacts
- prompts
- scenarios
- project_contacts

A resource declaration can include:

- operations such as `list`, `get`, `create`, `update`, `delete`, `import`
- display metadata for title, columns, and search fields
- simple form fields
- typed resource-backed option sources
- mounted custom views for cases where generic CRUD is not enough

Dynamic behavior should not be implemented as opaque Python callbacks. It should reduce to:

- A2UI-local declarative behavior inside the surface document, or
- typed action calls such as `resource.contacts.list`, `resource.contacts.create`, or an agent-specific validation action.

This avoids repeating the v1 dynamic-choice callback model.

## Datasets

Datasets are read-oriented tables or metric streams that Studio can query through typed actions.

An auto-surfaced dataset declares:

- `id`
- `label`
- display columns
- `auto_surface=True`

The SDK derives the action id `dataset.<id>.query`. Studio can render the result in generic tables and dashboards, including `mission.analytics` surfaces.

## Dashboards

Dashboards are declarative registration metadata for Studio-rendered views. They do not create AnalyticsResource routes and they do not imply agent-specific analytics business logic.

A dashboard declares:

- `id`
- `label`
- `surface`, defaulting to `mission.analytics`
- `widgets`

Each widget can reference data from a dataset, typed action, or inline sample data. Widgets carry a `visualization` object whose `type` is `table`, `metric`, `vega-lite`, or `custom`. For Vega-Lite charts, use `visualization.type = "vega-lite"` and place the Vega-Lite JSON spec in `visualization.spec`. Studio is responsible for rendering and validating the visualization; Supervaizer only transports the typed contract.

Example:

```python
registration = build_v2_agent_registration(
    # ...
    datasets=[
        {
            "id": "progress_metrics",
            "label": "Progress Metrics",
            "auto_surface": True,
            "display": {"columns": ["label", "value"]},
        }
    ],
    dashboards=[
        {
            "id": "mission_overview",
            "label": "Mission Overview",
            "widgets": [
                {
                    "id": "progress_chart",
                    "title": "Progress",
                    "data": {"mode": "ref", "datasetId": "progress_metrics"},
                    "visualization": {
                        "type": "vega-lite",
                        "spec": {
                            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                            "mark": "bar",
                            "encoding": {
                                "x": {"field": "label", "type": "nominal"},
                                "y": {"field": "value", "type": "quantitative"},
                            },
                        },
                    },
                }
            ],
        }
    ],
)
```

## Surfaces

Surfaces are named UI entry points. A surface handler returns an A2UI document.

Common surface IDs:

| Surface | Purpose |
| --- | --- |
| `job.start` | Form used before `job.start`. |
| `case.step.awaiting` | HITL form or review UI for an awaiting step. |
| `case.step.detail` | Rich detail view for a step or artifact. |
| `mission.analytics` | Mission-scoped dashboard over agent datasets. |
| `mission.agent.overview` | Optional agent overview and quick links. |
| `mission.agent.resource.<resource_id>` | Studio-generated resource CRUD surface. |
| `mission.agent.dataset.<dataset_id>` | Studio-generated dataset surface. |

Mounted resource views use a resource-shaped URL in Studio but let the agent replace a whole view, such as `edit` or `import`, with a custom A2UI surface.

For imports, agents should use the `ResourceImport` A2UI document shape. The document declares:

- `resource`, such as `campaign_contacts`
- `accepted_formats`, currently `csv` and optionally `xlsx`
- contextual `fields`, such as a required campaign picker
- row `columns`, such as `email` and `phone_number`
- `submit.action`, such as `resource.campaign_contacts.import`

Studio reads this document to show the required format, validate CSV rows before submit, and route the typed action. The agent remains responsible for tenant checks, business validation, persistence, and returning typed effects. If an import changes an existing Job, the action can return a top-level `job_state`; Studio treats that like `job.sync` and upserts the returned cases and steps.

## Actions

Actions are typed commands invoked through A2A JSON-RPC.

Common action IDs:

| Action | Purpose |
| --- | --- |
| `job.start` | Commit a new Job and start agent work. |
| `job.stop` | Stop or cancel agent work. |
| `job.sync` | Return a convergent state snapshot for Studio. |
| `step.awaiting.submit` | Submit operator input for a HITL step. |
| `resource.<id>.<operation>` | Run a resource operation. |
| `dataset.<id>.query` | Query an agent-owned dataset. |
| `artifact.get` | Load artifact content by reference. |

Action requests include `actor`, `workspace`, `mission_id`, `agent_slug`, `surface`, `action`, `input`, and optional correlation fields such as `job_id`, `case_id`, `step_id`, `draft_session_id`, and `idempotency_key`.

## Sync and Offline Semantics

Studio owns operator-facing job lifecycle, but the agent owns actual business state. `job.sync` is the reconciliation point between the two.

Recommended behavior:

- new starts go through `job.start`
- already-started external work can be loaded by creating a Studio Job and calling `job.sync`
- repeated sync calls should be convergent
- offline agents block new starts
- if Studio marks a running Job failed because the agent is offline, resuming later should use a new Job plus `job.sync`

## A2A, A2UI, and AG-UI

Supervaizer v2 currently uses:

- A2A for Agent Card discovery, `/a2a` JSON-RPC calls, and `/a2a/events` SSE observation
- A2UI for Studio-rendered surface documents such as `job.start`, `case.step.awaiting`, `case.step.detail`, and `mission.analytics`
- Supervaizer v2 semantics for Jobs, Cases, Steps, Resources, Datasets, Actions, Artifacts, and sync/offline policy

The current transport advertises JSON-RPC and SSE, not A2A push notifications.

AG-UI is not required for the MVP. It is the right layer for future live streaming agent-user sessions where Studio needs bidirectional events, streaming messages, tool-call visualization, live state synchronization, or interrupt/approval flows. Registrations can include `ag_ui_version` metadata for that future runtime, but the implemented v2 flow works through A2UI surface documents and typed actions.

## Migration From v1

The v2 model intentionally replaces v1 field/dynamic-choice/job-poll behavior.

| v1 concept | v2 replacement |
| --- | --- |
| `AgentMethodField` for Studio job start | A2UI `job.start` surface |
| `dynamic_choices_callback` | typed resource option sources or typed actions |
| `job_poll` | `job.sync` |
| controller-specific HITL payloads | `case.step.awaiting` surface plus `step.awaiting.submit` |
| fixed Studio assumptions about agent outputs | agent-declared artifact types and `case.step.detail` surfaces |

New agents should model Studio integration through v2 from the start.

## Minimal Checklist For A v2 Agent

- Declare `supervaizer_v2_registration`.
- Pin `a2ui_version`, `a2a_version`, and `a2ui_catalog_version`.
- Declare at least one surface, usually `job.start`.
- Register `job.start`.
- Register `job.sync` if Studio needs status convergence or catch-up.
- Declare resources and datasets that Studio should manage generically.
- Register handlers for every declared action.
- Use `awaiting` state for HITL.
- Return stable external ids in Job/Case/Step/Artifact snapshots.
- Keep business validation inside agent actions, not inside Studio-specific code paths.
