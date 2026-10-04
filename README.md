# Supervaizer

> **Created:** 2024-12-28
> **Updated:** 2026-10-05

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
- [API surfaces and authentication](docs/2025_08_REST_API.md)
- [Admin interface and workbench](docs/2025_08_ADMIN_README.md)
- [Hello World example repository](https://github.com/supervaize/supervaize_hello_world)
- [Built-in local Hello World agent](src/supervaizer/examples/hello_world_agent.py)

## Quick Start

### 1. Install

```bash
pip install supervaizer
```

For local development from this repository:

```bash
just install-dev   # uv sync --extra dev
```

### 2. Run The Built-In V2 Hello World Agent

The fastest way to see the v2 controller is local mode:

```bash
supervaizer start --local
```

Local mode runs the agents from your `supervaizer_control.py` plus the built-in Hello World agent (disable it with `SUPERVAIZER_DISABLE_HELLO_WORLD=true`); with no control file it starts Hello World alone. Hello World declares:

- a v2 Agent Card
- `job.start` and `case.step.awaiting` A2UI surfaces
- `job.start`, `job.start.preview`, `job.sync`, and `step.awaiting.submit` actions
- one generated resource action, `resource.hello_messages.list`
- a minimal HITL review step when human review is enabled

Local mode binds to `127.0.0.1`, skips Studio registration, and uses the API key `local-dev`. It also bypasses Studio workspace authorization for `/a2a` actions and surfaces, so `X-API-Key` alone is enough:

```bash
curl -s http://127.0.0.1:8000/a2a \
  -H "X-API-Key: local-dev" -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "supervaizer/action.invoke",
       "params": {"request_id": "r1", "actor": {"user_id": "me"},
                  "workspace": {"id": "local"}, "mission_id": "m1",
                  "agent_slug": "hello-world-ai-agent", "surface": "job.start",
                  "action": "job.start", "input": {"count": 1}, "job_id": "job-1"}}'
```

Handlers receive an unverified `workspace_authorization` whose `grant_id` is `local-mode`, and the server logs a startup warning. The bypass applies only while the server has no Studio account and none of `SUPERVAIZER_WORKSPACE_AUTH_REQUIRED`, `_ISSUER`, `_AUDIENCE`, `_PUBLIC_KEY`, or `_JWKS_URL` is set. Otherwise every call needs a real Studio token, and a partial setup answers `workspace_authorization_not_configured`. Never expose a local-mode port: anyone who reaches it can run your agents with the well-known key.

Open these endpoints:

| URL | Purpose | Access |
| --- | --- | --- |
| `http://127.0.0.1:8000/docs` | FastAPI Swagger docs | public |
| `http://127.0.0.1:8000/.well-known/agents.json` | A2A discovery | public |
| `http://127.0.0.1:8000/.well-known/health` | Controller health | public |
| `POST http://127.0.0.1:8000/a2a` | A2A JSON-RPC controller endpoint | `X-API-Key` (write scope); workspace token outside local mode |
| `GET http://127.0.0.1:8000/a2a/events` | SSE stream for v2 effects | `X-API-Key` (read scope) |
| `http://127.0.0.1:8000/manage` | Admin interface and agent workbench | Tailscale IP, or loopback in local mode |

### 3. Inspect The Hello World Example

The built-in agent is the v2 reference implementation:

- Local built-in implementation: [src/supervaizer/examples/hello_world_agent.py](src/supervaizer/examples/hello_world_agent.py)
- Local server registration: [src/supervaizer/examples/local_server.py](src/supervaizer/examples/local_server.py)
- Public repository: [supervaize/supervaize_hello_world](https://github.com/supervaize/supervaize_hello_world). It shows the standalone project layout but still uses the v1 `AgentMethodField` style; model new agents on the built-in v2 agent instead.

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

Run `supervaizer scaffold` to create `supervaizer_control.py`, or write the file yourself. It is a complete v2 agent: one registration, one surface, and one action. The scaffolded file also builds a Studio `Account` from the environment; local mode ignores it.

```python
from typing import Any

from supervaizer import (
    Agent,
    Server,
    V2ActionRequest,
    V2SurfaceRequest,
    build_v2_agent_registration,
)

agent = Agent(
    name="My Agent",
    version="0.1.0",
    description="My Supervaizer v2 agent.",
    supervaizer_v2_registration=build_v2_agent_registration(
        agent_slug="my-agent",  # must equal Agent.slug, the slugified name
        display_name="My Agent",
        a2ui_catalog_version="my-agent-ui.1",  # bump when your surfaces change
        surfaces=["job.start"],
        actions=["job.start"],
    ),
)

server = Server(agents=[agent])


@server.v2_surface("job.start", agent_slug=agent.slug)
def job_start_form(request: V2SurfaceRequest) -> dict[str, Any]:
    return {
        "surface": request.surface,
        "document": {
            "type": "Form",
            "title": "Start job",
            "fields": [
                {"id": "goal", "label": "Goal", "type": "string", "required": True}
            ],
            "submit": {"action": "job.start", "label": "Start"},
        },
    }


@server.v2_action("job.start", agent_slug=agent.slug)
def start_job(request: V2ActionRequest) -> dict[str, Any]:
    job_id = request.job_id or "local-job"
    return {
        "status": "ok",
        "effects": [{"type": "job.started", "job_id": job_id, "status": "completed"}],
        "job_state": {
            "job": {
                "id": job_id,
                "mission_id": request.mission_id,
                "agent_slug": request.agent_slug,
                "status": "completed",
                "source": {"type": "fresh_start"},
            },
            "cases": [
                {
                    "id": "case-1",
                    "title": request.input["goal"],
                    "status": "completed",
                    "steps": [
                        {"id": "step-1", "activity": "operation", "status": "completed"}
                    ],
                }
            ],
        },
    }
```

Start it in local mode. The CLI loads `supervaizer_control.py`, finds the `Server`, and launches it:

```bash
supervaizer start --local
```

Load the surface:

```bash
curl -s http://127.0.0.1:8000/a2a \
  -H "X-API-Key: local-dev" -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "supervaizer/surface.load",
       "params": {"request_id": "r1", "actor": {"user_id": "me"},
                  "workspace": {"id": "local"}, "mission_id": "m1",
                  "agent_slug": "my-agent", "surface": "job.start"}}'
```

| Part | Role |
| --- | --- |
| `build_v2_agent_registration` | Declares the `surfaces` Studio can show and the `actions` Studio can call. |
| `@server.v2_surface` | Returns the A2UI document for one declared surface. |
| `@server.v2_action` | Runs one declared action. Returns `effects` and an optional `job_state` snapshot. |

Rules that prevent the usual first errors:

- `agent_slug` in the registration must equal `Agent.slug` (the slugified `name`). A mismatch fails at `Agent` creation.
- Register one handler for each declared action and each surface you serve. A missing action handler answers JSON-RPC error `-32010`; a missing surface handler answers `-32011`.
- Pass `agent_slug` to each handler decorator. Local mode adds the built-in Hello World agent, so the server holds two agents and cannot infer the slug.
- A bare action id defaults to `mutating=True, scope="job"`. Declare a read-only action with `V2ActionDefinition(id=..., mutating=False, scope=...)`.

Add these when you need them:

- Status convergence: declare `job_policy={"sync": {"action": "job.sync"}}` and register a `job.sync` handler.
- Human review: return a step with `status="awaiting"` and an `awaiting` object. Declare the `case.step.awaiting` surface and the `step.awaiting.submit` action.
- Business objects: declare `resources=[...]`. The SDK derives the `resource.<id>.<operation>` actions; you register their handlers.

The built-in [Hello World agent](src/supervaizer/examples/hello_world_agent.py) shows all three. [Supervaizer v2 concepts](docs/2026_05_SUPERVAIZER_v2.md) holds the full model.

### 5. Connect To Studio

Studio-managed operation needs a `supervisor_account` on the `Server`, the controller's own API key, and workspace authorization trust material. The scaffold template (`supervaizer scaffold`) reads these variables:

```bash
export SUPERVAIZE_API_KEY=...            # agent -> Studio calls
export SUPERVAIZE_WORKSPACE_ID=...
export SUPERVAIZE_API_URL=https://app.supervaize.com
export SUPERVAIZER_API_KEY=...           # Studio -> controller calls (X-API-Key); generated if unset
export SUPERVAIZER_PUBLIC_URL=https://your-controller.example.com

# Workspace authorization: required when A2A is enabled and the controller registers with Studio
export SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=true
export SUPERVAIZER_WORKSPACE_AUTH_ISSUER=https://studio.supervaize.com
export SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL=https://app.supervaize.com/w/your-workspace-slug/api/v1/workspace-agent-grants/jwks/  # or SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY=<PEM>
```

Copy the generated workspace values from Studio's **Developer → Environment variables** section. `SUPERVAIZE_WORKSPACE_ID` must be the workspace slug shown there; the API key's user must belong to that workspace and retain Developer access. A mismatch can make `SERVER_REGISTER` return HTTP 403. The issuer must match Studio's token issuer. The JWKS URL is public and supplies the signing key. Workspace authorization is separate from `SUPERVAIZE_API_KEY` and `SUPERVAIZER_API_KEY`.

In your own control file, build the account explicitly; `Server` does not read the `SUPERVAIZE_*` variables itself:

```python
import os

from supervaizer import Account, Server

account = Account(
    workspace_id=os.environ["SUPERVAIZE_WORKSPACE_ID"],
    api_key=os.environ["SUPERVAIZE_API_KEY"],
    api_url=os.environ.get("SUPERVAIZE_API_URL", "https://app.supervaize.com"),
)
server = Server(agents=[agent], supervisor_account=account)
```

Without the three `SUPERVAIZER_WORKSPACE_AUTH_*` variables, a Studio-registered controller refuses to launch (`Studio-registered Supervaizer v2 A2A requires workspace authorization`). Local mode does not need them. See [docs/2026_05_WORKSPACE_AGENT_GRANTS.md](docs/2026_05_WORKSPACE_AGENT_GRANTS.md).

Then start the controller:

```bash
supervaizer start
```

Studio registration remains the trust bootstrap. It owns server identity, public key exchange, and encrypted payload handling. The A2A Agent Card advertises the v2 operational contract after Studio knows the controller.

## V2 Concepts

| Concept | Meaning |
| --- | --- |
| Job | Committed work that Studio tracks for an agent. |
| Case | A unit of work inside a Job, grouped by `lane` (default `work`). |
| Step | An observable activity inside a Case: `activity`, `status`, optional `awaiting`, and `outputs`. |
| Surface | A named UI entry point. Its handler returns an A2UI document. |
| Action | A typed command invoked through A2A JSON-RPC. Its handler returns `effects` and an optional `job_state`. |
| Resource, Dataset | Agent-owned business objects and queryable data that Studio renders generically. |
| Artifact | An agent-owned output, referenced from Step `outputs`. |

Failure is a status, not a step kind. Human review is `status="awaiting"` plus an `awaiting` object. Dynamic UI behavior is A2UI local logic or a typed action call, never a callback.

The full model, the standard surface and action ids, and the protocol split are in [docs/2026_05_SUPERVAIZER_v2.md](docs/2026_05_SUPERVAIZER_v2.md) and [docs/2026_05_PROTOCOLS.md](docs/2026_05_PROTOCOLS.md).

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

Preview, smoke-test in Docker, and deploy:

```bash
supervaizer deploy plan --platform cloud-run --name my-agent --project-id my-gcp-project
supervaizer deploy local --name my-agent --generate-api-key
supervaizer deploy up --platform cloud-run --name my-agent --project-id my-gcp-project --region us-central1
```

Targets: Google Cloud Run, AWS App Runner, and DigitalOcean App Platform.

> **Experimental:** `deploy up` builds the image locally but does not push it to a registry, and generated secrets are not injected under the variable names the server reads. Use `plan` and `local` today; finish cloud deployment with your provider's CLI.

See:

- [Cloud deployment RFC](docs/rfc/2025_10_001-cloud-deployment-cli.md)
- [Local Docker testing guide](docs/2025_10_LOCAL_TESTING.md)

## Admin Interface

The admin interface and agent workbench are mounted at `/manage` (`admin_interface=True`, the default). Access is restricted to Tailscale addresses (`100.64.0.0/10`), plus loopback in local mode; no API key is used. See [docs/2025_08_ADMIN_README.md](docs/2025_08_ADMIN_README.md).

## Development

Run tests and checks:

```bash
just test        # pytest, no coverage
just precommit   # ruff check, ruff format, mypy, hooks
```

## Contributing

Supervaizer is public SDK infrastructure. Keep public contracts typed, generic, and free of agent-specific business logic. If a protocol field changes, update the producer and consumer documentation together.

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution details.

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE.md).
