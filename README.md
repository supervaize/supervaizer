# Supervaizer

> **Created:** 2024-12-28
> **Updated:** 2026-05-17

Supervaizer is the Python controller SDK for exposing AI agents to Supervaize Studio through the Supervaizer v2 operation contract.

Supervaizer v2 is layered on:

- [A2A](https://a2a-protocol.org/) for discovery, Agent Cards, JSON-RPC controller calls, and SSE events
- [A2UI](https://a2ui.org/) for agent-authored UI surface documents rendered by Studio
- Supervaizer v2 semantics for Jobs, Cases, Steps, Resources, Datasets, Surfaces, Actions, Artifacts, and `job.sync` convergence

Supervaizer does not contain agent business logic. Agents declare their resources, surfaces, actions, and artifacts; Studio consumes that declaration as a generic operations UI.

> **Beta:** Supervaizer v2 is under active development. Protocol versions are pinned in the registration contract and incompatible versions should fail explicitly.

## Start Here

- [Supervaizer v2 concepts](docs/2026_05_SUPERVAIZER_v2.md)
- [Protocols: A2A, A2UI, AG-UI, and Supervaizer v2](docs/2026_05_PROTOCOLS.md)
- [CLI reference](docs/2025_08_CLI.md)
- [REST and admin API reference](docs/2025_08_REST_API.md)
- [Hello World example repository](https://github.com/supervaize/supervaize_hello_world)
- [Built-in local Hello World agent](src/supervaizer/examples/hello_world_agent.py)

## Quick Start

### 1. Install

```bash
pip install supervaizer
```

For local development from this repository:

```bash
uv sync
```

### 2. Run The Built-In V2 Hello World Agent

The fastest way to see the v2 controller is local mode:

```bash
supervaizer start --local
```

If your project does not define `supervaizer_control.py`, local mode starts the built-in Hello World agent. It exposes:

- a v2 Agent Card
- a `job.start` A2UI form surface
- `job.start`, `job.sync`, and `step.awaiting.submit` actions
- one generated resource action, `resource.hello_messages.list`
- a minimal HITL review step when human review is enabled

Open these endpoints:

| URL | Purpose |
| --- | --- |
| `http://127.0.0.1:8000/docs` | FastAPI Swagger docs |
| `http://127.0.0.1:8000/.well-known/agents.json` | A2A discovery |
| `http://127.0.0.1:8000/.well-known/health` | Controller health |
| `http://127.0.0.1:8000/a2a` | A2A JSON-RPC controller endpoint |
| `http://127.0.0.1:8000/a2a/events` | SSE stream for v2 effects |
| `http://127.0.0.1:8000/admin` | Local admin interface |

### 3. Inspect The Hello World Example

Use the public example as the reference project layout:

- Repository: [supervaize/supervaize_hello_world](https://github.com/supervaize/supervaize_hello_world)
- Local built-in implementation: [src/supervaizer/examples/hello_world_agent.py](src/supervaizer/examples/hello_world_agent.py)
- Local server registration: [src/supervaizer/examples/local_server.py](src/supervaizer/examples/local_server.py)

Run the standalone example:

```bash
git clone https://github.com/supervaize/supervaize_hello_world.git
cd supervaize_hello_world
uv venv
source .venv/bin/activate
uv pip install -e .
supervaizer start
```

### 4. Add A V2 Controller To Your Agent

Create `supervaizer_control.py` in your agent project.

```python
from typing import Any

from supervaizer import (
    Agent,
    Server,
    V2ResourceDefinition,
    build_v2_agent_registration,
)


AGENT_NAME = "My Agent"
AGENT_SLUG = "my-agent"
AGENT_VERSION = "0.1.0"
A2UI_CATALOG_VERSION = "my-agent-ui.1"


registration = build_v2_agent_registration(
    agent_id=AGENT_SLUG,
    agent_slug=AGENT_SLUG,
    display_name=AGENT_NAME,
    agent_card_url=f"/.well-known/agents/v{AGENT_VERSION}/{AGENT_SLUG}_agent.json",
    controller_url="/a2a",
    a2ui_catalog_version=A2UI_CATALOG_VERSION,
    surfaces=["job.start"],
    actions=["job.start"],
    case_lanes=[{"id": "work", "label": "Work", "default": True}],
    job_policy={"sync": {"action": "job.sync"}},
    resources=[
        V2ResourceDefinition(
            id="contacts",
            label="Contacts",
            auto_surface=True,
            operations=["list"],
            scope="workspace",
            requires_context=["workspace.slug"],
        )
    ],
)

agent = Agent(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    description="My Supervaizer v2 agent.",
    supervaizer_v2_registration=registration,
)

server = Server(
    agents=[agent],
    a2a_endpoints=True,
    admin_interface=True,
)


@server.v2_surface("job.start", agent_slug=agent.slug)
def load_job_start_surface(request: Any) -> dict[str, Any]:
    return {
        "surface": "job.start",
        "a2ui_version": registration.versions.a2ui_version,
        "a2ui_catalog_version": A2UI_CATALOG_VERSION,
        "document": {
            "type": "Form",
            "id": "my-agent.job.start",
            "title": "Start job",
            "fields": [
                {
                    "id": "goal",
                    "label": "Goal",
                    "type": "string",
                    "required": True,
                }
            ],
            "submit": {"action": "job.start", "label": "Start"},
        },
    }


@server.v2_action("job.start", agent_slug=agent.slug)
def start_job(request: Any) -> dict[str, Any]:
    job_id = getattr(request, "job_id", None) or "local-job"
    return {
        "status": "ok",
        "effects": [
            {
                "type": "job.started",
                "job_id": job_id,
                "status": "completed",
            }
        ],
        "job_state": {
            "job": {
                "id": job_id,
                "agent_slug": agent.slug,
                "status": "completed",
                "source": {"type": "fresh_start"},
            },
            "cases": [
                {
                    "id": "case-1",
                    "lane": "work",
                    "title": "First case",
                    "status": "completed",
                    "steps": [
                        {
                            "id": "step-1",
                            "activity": "operation",
                            "status": "completed",
                            "title": "Run operation",
                            "outputs": [],
                        }
                    ],
                }
            ],
        },
    }


@server.v2_action("job.sync", agent_slug=agent.slug)
def sync_job(request: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "effects": [
            {
                "type": "job.synced",
                "job_id": getattr(request, "job_id", None),
                "status": "completed",
            }
        ],
    }


@server.v2_action("resource.contacts.list", agent_slug=agent.slug)
def list_contacts(request: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "effects": [
            {
                "type": "resource.listed",
                "resource": "contacts",
                "items": [],
            }
        ],
    }


server.launch()
```

Run it:

```bash
python supervaizer_control.py
```

### 5. Connect To Studio

For Studio-managed operation, configure the controller with your Studio credentials and public controller URL:

```bash
export SUPERVAIZE_API_KEY=...
export SUPERVAIZE_WORKSPACE_ID=...
export SUPERVAIZE_API_URL=https://app.supervaize.com
export SUPERVAIZER_PUBLIC_URL=https://your-controller.example.com
```

Then start the controller:

```bash
supervaizer start
```

Studio registration remains the trust bootstrap. It owns server identity, public key exchange, and encrypted payload handling. The A2A Agent Card advertises the v2 operational contract after Studio knows the controller.

## V2 Concepts

### Jobs, Cases, And Steps

Studio starts and tracks Jobs. Agents return convergent state through action effects and optional `job_state` snapshots.

A `job_state` contains:

- one Job record
- Cases grouped by `lane`; default lane is `work`
- Steps with `activity`, `status`, optional `awaiting`, and `outputs`
- Artifact references for agent-owned deliverables

Failure is a status, not a step kind. Agent-specific deliverables are artifacts, not universal protocol enum values.

### Resources And Datasets

Resources are agent-owned business objects that Studio can render generically when `auto_surface=True`.

Datasets are agent-owned queryable data products for dashboards and analytics. Dashboard widgets can point at datasets, typed actions, or inline data and may use Vega-Lite chart specs.

### Surfaces And Actions

Surfaces are named UI entry points. A surface handler returns an A2UI document.

Common surfaces:

- `job.start`
- `case.step.awaiting`
- `case.step.detail`
- `mission.analytics`
- `mission.agent.overview`
- `mission.agent.resource.<resource_id>`
- `mission.agent.surface.<surface_id>`

Actions are typed commands invoked through A2A JSON-RPC:

- `job.start`
- `job.stop`
- `job.sync`
- `step.awaiting.submit`
- `resource.<id>.<operation>`
- `dataset.<id>.query`
- `artifact.get`

Dynamic UI behavior must be either A2UI local logic or typed action calls. Supervaizer v2 does not reintroduce callback-shaped dynamic field logic.

## Protocols

Supervaizer v2 uses each protocol for a specific job:

| Layer | Role |
| --- | --- |
| A2A | Discovery, Agent Cards, JSON-RPC controller calls, and SSE event observation |
| A2UI | Declarative Studio-rendered documents for forms, tables, dashboards, detail views, and custom workflows |
| AG-UI | Future optional runtime for live bidirectional agent-user sessions |
| Supervaizer v2 | Application semantics: Jobs, Cases, Steps, Resources, Datasets, Surfaces, Actions, Artifacts, and sync/offline policy |

Read [docs/2026_05_PROTOCOLS.md](docs/2026_05_PROTOCOLS.md) for the protocol split and links to upstream A2A, A2UI, AG-UI, and Vega-Lite references.

## CLI

Common commands:

```bash
supervaizer start
supervaizer start --local
supervaizer start --host 0.0.0.0 --port 8000
```

See [docs/2025_08_CLI.md](docs/2025_08_CLI.md) for the full CLI reference and environment variables.

## Deployment

Install deployment extras:

```bash
pip install "supervaizer[deploy]"
```

Preview and deploy:

```bash
supervaizer deploy plan
supervaizer deploy local --generate-api-key --generate-rsa
supervaizer deploy up --platform cloud-run --region us-central1
```

Supported targets include Google Cloud Run, AWS App Runner, and DigitalOcean App Platform.

See:

- [Cloud deployment RFC](docs/rfc/2025_10_001-cloud-deployment-cli.md)
- [Local Docker testing guide](docs/2025_10_LOCAL_TESTING.md)

## Admin Interface

The optional admin interface is available at `/admin` when `admin_interface=True`.

```python
from supervaizer import Agent, Server

server = Server(
    agents=[Agent(name="My Agent")],
    api_key="local-dev",
    admin_interface=True,
)
server.launch()
```

## Development

Run tests:

```bash
uv run pytest
```

Run focused checks:

```bash
uv run ruff check .
uv run ruff format --check .
git diff --check
```

## Contributing

Supervaizer is public SDK infrastructure. Keep public contracts typed, generic, and free of agent-specific business logic. If a protocol field changes, update the producer and consumer documentation together.

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution details.

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE.md).
