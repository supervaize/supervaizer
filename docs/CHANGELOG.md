# Supervaizer Changelog

All notable changes to this project will be documented in this file.

> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## TODO

- Fix CICD
- Review and test feature/data-persistance
- Complete feature/smartinstall implementation
- Fix receive_human_input
- Test and fix deploy
- When AgentMethodField returns its value (in the kwargs of job_start), the value should be casted in the appropriate type :
  - example: here the 'How many times to say hello' is supposed to be an 'int'.
  - agent_simple:job_start:74 - AGENT ExampleAgent: Received kwargs: {'action': 'start', 'fields': {'How many times to say hello': '3'}, 'context': JobContext(workspace_id='odm', job_id='01KGM75NQ76AWBAXHXERW8FKHW', started_by='alp', started_at=datetime.datetime(2026, 2, 4, 11, 39, 0, 712598, tzinfo=TzInfo(0)), mission_id='01KGG50ZMFYMHG9N5FGCACF0XA', mission_name='Operate Agent Hello World AI Agent', mission_context=None, job_instructions=JobInstructions(max_cases=None, max_duration=None, max_cost=None, stop_on_warning=False, stop_on_error=True, job_start_time=None)), 'agent_parameters': [{'name': 'SIMPLE AGENT PARAMETER', 'team_id': 2, 'description': 'Setup agent parameter in this workspace', 'is_environment': True, 'value': '123456', 'is_secret': False, 'is_required': False}, {'name': 'SIMPLE AGENT SECRET', 'team_id': 2, 'description': 'Setup agent secret in this workspace', 'is_environment': True, 'value': '123456', 'is_secret': True, 'is_required': False}]}

## [Unreleased]

### Changed

- **`publish-pypi.yml` — post-publish release automation** — After PyPI publish, CI now runs the same GitHub release flow as `just gh-release` (`tools/gh-release-latest-tag.sh`) to create/update and mark the latest release from the newest `origin/main` tag.
- **`publish-pypi.yml` — branch reconciliation in CI** — Added an automatic `main -> develop` merge-back step after publish/release so long-lived branch history stays synchronized without manual follow-up.

### Fixed

- **GitHub Actions Node 20 deprecation warnings** — Upgraded workflow action majors across CI/release/publish pipelines: `actions/checkout@v5`, `actions/setup-python@v6`, and `astral-sh/setup-uv@v7` to avoid Node 20 runtime deprecation warnings and align with Node 24 transition.

## [0.17.1] - 2026-04-26

### Fixed

- **`server.py` — startup lifespan migration** — Replaced deprecated `@app.on_event("startup")` with a proper `asynccontextmanager` lifespan passed to `FastAPI(lifespan=...)`. Eliminates `DeprecationWarning` from FastAPI 0.100+.
- **`account_service.py` — atexit robustness** — `close_httpx_client_sync` now guards the `aclose()` call with `getattr(_httpx_client, "aclose", None)` to prevent `AttributeError` when the module-level client is a sync `httpx.Client` in older-installed environments.

### Tests

`just test`

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 559   |
| 🤔 Skipped | 0     |
| 🔴 Failed  | 0     |
| ⏱️ in      | 74s   |

## [0.17.0] - 2026-04-26

### Changed

- **Async control-event HTTP client** — `account_service.send_event`, `Account` event helpers, and case event-reporting methods now use `httpx.AsyncClient` and must be awaited in async agents. Explicit `_sync` shims remain for CLI, startup, and synchronous controller methods. See [RFC: async-control-event-http-client](/docs/rfc/async-control-event-http-client.md) for details.

### Tests

`just test`

| Status      | Count |
| ----------- | ----- |
| ✅ Passed   | 559   |
| 🤔 Skipped  | 0     |
| 🔴 Failed   | 0     |
| ⏱️ in       |       |
| ⏱️ with cov | 102s  |

### Coverage

| Name                                              | Stmts | Miss | Cover |
| ------------------------------------------------- | ----- | ---- | ----- |
| src/supervaizer/**init**.py                       | 23    | 3    | 87%   |
| src/supervaizer/**version**.py                    | 3     | 0    | 100%  |
| src/supervaizer/access/**init**.py                | 4     | 0    | 100%  |
| src/supervaizer/access/api_auth.py                | 38    | 1    | 97%   |
| src/supervaizer/access/client_ip.py               | 37    | 7    | 81%   |
| src/supervaizer/access/tailscale.py               | 23    | 2    | 91%   |
| src/supervaizer/account.py                        | 122   | 15   | 88%   |
| src/supervaizer/account_service.py                | 80    | 2    | 98%   |
| src/supervaizer/admin/routes.py                   | 549   | 190  | 65%   |
| src/supervaizer/admin/workbench_routes.py         | 380   | 256  | 33%   |
| src/supervaizer/agent.py                          | 354   | 80   | 77%   |
| src/supervaizer/case.py                           | 267   | 64   | 76%   |
| src/supervaizer/cli.py                            | 210   | 75   | 64%   |
| src/supervaizer/common.py                         | 142   | 4    | 97%   |
| src/supervaizer/contracts.py                      | 168   | 3    | 98%   |
| src/supervaizer/data_resource.py                  | 70    | 0    | 100%  |
| src/supervaizer/data_routes.py                    | 98    | 21   | 79%   |
| src/supervaizer/deploy/**init**.py                | 2     | 0    | 100%  |
| src/supervaizer/deploy/cli.py                     | 104   | 46   | 56%   |
| src/supervaizer/deploy/commands/**init**.py       | 2     | 0    | 100%  |
| src/supervaizer/deploy/commands/clean.py          | 158   | 17   | 89%   |
| src/supervaizer/deploy/commands/down.py           | 61    | 12   | 80%   |
| src/supervaizer/deploy/commands/local.py          | 214   | 15   | 93%   |
| src/supervaizer/deploy/commands/plan.py           | 75    | 7    | 91%   |
| src/supervaizer/deploy/commands/status.py         | 100   | 41   | 59%   |
| src/supervaizer/deploy/commands/up.py             | 113   | 8    | 93%   |
| src/supervaizer/deploy/docker.py                  | 186   | 23   | 88%   |
| src/supervaizer/deploy/driver_factory.py          | 20    | 0    | 100%  |
| src/supervaizer/deploy/drivers/**init**.py        | 13    | 4    | 69%   |
| src/supervaizer/deploy/drivers/aws_app_runner.py  | 221   | 157  | 29%   |
| src/supervaizer/deploy/drivers/base.py            | 82    | 8    | 90%   |
| src/supervaizer/deploy/drivers/cloud_run.py       | 205   | 125  | 39%   |
| src/supervaizer/deploy/drivers/do_app_platform.py | 164   | 125  | 24%   |
| src/supervaizer/deploy/health.py                  | 161   | 12   | 93%   |
| src/supervaizer/deploy/state.py                   | 115   | 9    | 92%   |
| src/supervaizer/deploy/utils.py                   | 24    | 0    | 100%  |
| src/supervaizer/event.py                          | 40    | 1    | 98%   |
| src/supervaizer/examples/local_server.py          | 17    | 3    | 82%   |
| src/supervaizer/instructions.py                   | 56    | 1    | 98%   |
| src/supervaizer/job.py                            | 166   | 28   | 83%   |
| src/supervaizer/job_service.py                    | 34    | 0    | 100%  |
| src/supervaizer/lifecycle.py                      | 153   | 3    | 98%   |
| src/supervaizer/parameter.py                      | 79    | 7    | 91%   |
| src/supervaizer/protocol/**init**.py              | 2     | 0    | 100%  |
| src/supervaizer/protocol/a2a/**init**.py          | 3     | 0    | 100%  |
| src/supervaizer/protocol/a2a/model.py             | 37    | 5    | 86%   |
| src/supervaizer/protocol/a2a/routes.py            | 35    | 3    | 91%   |
| src/supervaizer/routers/**init**.py               | 4     | 0    | 100%  |
| src/supervaizer/routers/api.py                    | 18    | 1    | 94%   |
| src/supervaizer/routers/private.py                | 10    | 0    | 100%  |
| src/supervaizer/routers/public.py                 | 22    | 5    | 77%   |
| src/supervaizer/routes.py                         | 333   | 60   | 82%   |
| src/supervaizer/server.py                         | 282   | 84   | 70%   |
| src/supervaizer/server_utils.py                   | 25    | 0    | 100%  |
| src/supervaizer/storage.py                        | 160   | 12   | 92%   |
| src/supervaizer/telemetry.py                      | 40    | 0    | 100%  |
| src/supervaizer/utils/**init**.py                 | 2     | 0    | 100%  |
| src/supervaizer/utils/version_check.py            | 27    | 6    | 78%   |
| ------------------------------------------------- | ----- | ---- | ----- |
| TOTAL                                             | 6133  | 1551 | 75%   |

## [0.16.0] - 2026-04-25

### Added

- **Controller contract metadata for Studio** — `server.register` now advertises `controller_contract_version`, `/api` base path, and canonical endpoint templates so Studio can route without hardcoded Supervaizer paths. The same contract is available at `GET /api/supervaizer/contract`.
- **DataResource request context** — DataResource callbacks can opt into a `context` keyword with workspace, mission, agent, and request identifiers while legacy callbacks continue to work unchanged.
- **CaseNodes update helpers** — `CaseNodes.node_index()` and `CaseNodes.make_update()` derive step indexes from the declared node set instead of requiring consumers to maintain a separate index map.

### Changed

- **DataResource fields can be marked sensitive** — `DataResourceField.sensitive` is included in registration payloads for Studio masking.

### Tests

- New: `tests/test_contracts.py` for contract endpoint templates, schema export, import safety, resolver behavior, and DataResource context headers.
- New: `tests/test_case.py` coverage for `CaseNodes.node_index()` and `CaseNodes.make_update()`.
- Updated: `tests/test_routes.py` to verify DataResource callbacks receive `DataResourceContext` from forwarded `X-Supervaize-*` headers.
- Updated: `tests/test_server.py` to assert registration info and `/api/supervaizer/contract` expose matching `/api` contract metadata.
- Deleted: none.

`just test`

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 514   |
| 🤔 Skipped | 0     |
| 🔴 Failed  | 0     |
| ⏱️ in      | 01:03 |

## [0.15.1] - 2026-04-20

### Fixed

- **`TemplateResponse` Starlette 0.50 compatibility** — Updated `routers/public.py` and `routes.py` to use the new `TemplateResponse(request, name, context)` API. The old two-argument form `TemplateResponse(name, context)` was removed in Starlette 0.50.0, causing a `TypeError: unhashable type: 'dict'` crash on every `GET /` request.

## [0.15.0] - 2026-04-20

### Added

- **`supervaizer.access` module** — New package with three focused sub-modules for centralized access control:
  - `client_ip.py` — `_extract_client_ip(scope)` extracts the real client IP from ASGI scope, honoring `TRUSTED_PROXIES` (env var, comma-separated CIDRs) to safely parse `X-Forwarded-For`; returns `""` on any parse error (fail-closed).
  - `tailscale.py` — `require_tailscale` FastAPI dependency enforces that requests originate from the Tailscale CGNAT range `100.64.0.0/10`; raises HTTP 403 or `WebSocketException(1008)` on denial; logs via `log_access_denied_tailscale`.
  - `api_auth.py` — `require_api_key` / `require_scope` FastAPI dependencies for machine-to-machine auth with a hierarchical scope model (`write` implies `read`). `API_KEYS` registry is empty by default; `SUPERVAIZER_API_KEY` env var is pre-loaded as a `write`-scope entry at import time.

- **`supervaizer.routers` module** — Three router factories that replace scattered per-route `Security(...)` calls:
  - `public_router` — unauthenticated surface for home page (`/`) and A2A discovery (`/.well-known/*`).
  - `private_router` (prefix `/manage`) — admin UI and workbench WebSocket, gated by `require_tailscale` at router level.
  - `api_router` (prefix `/api`) — machine-to-machine surface (`/api/supervaizer/…`, `/api/agents/{slug}/…`), gated by `require_api_key`; write-mutating endpoints additionally enforce `require_scope("write")`.

- **`log_access_denied_tailscale` and `log_access_denied_api` helpers** in `supervaizer.common` — structured `WARNING` log entries for every denied request, including IP, path, reason, and a truncated key preview (never the raw key value).

### Changed

- **Admin UI moved from `/admin` to `/manage`** — All admin routes, workbench, and HTML template links updated. `private_router` (prefix `/manage`) gates the surface with Tailscale-only access instead of the previous `AdminIPAllowlistMiddleware` + API-key combo.

- **API routes moved from `/supervaizer/…` to `/api/supervaizer/…`** — All machine-to-machine endpoints now live under the `/api` prefix provided by `api_router`. Clients must update base paths accordingly.

- **`AdminIPAllowlistMiddleware` removed** — Replaced by `require_tailscale` at router level. The `admin/ip_allowlist.py` module is deleted.

- **Per-route `Security(server.verify_api_key)` removed** from `routes.py` and `data_routes.py` — Authentication is now enforced once at the `api_router` level.

- **Admin auth simplified to Tailscale-only** — `verify_admin_access`, `?key=` query-param handling, and console-token generation/validation are removed from `admin/routes.py` and `admin/workbench_routes.py`.

### Security

- **Removed hard-coded default API keys** — `API_KEYS` is now empty at startup; no credentials ship with the package. Only `SUPERVAIZER_API_KEY` (operator-supplied env var) populates the registry.

### Tests

- New: `tests/test_access_client_ip.py`, `tests/test_access_tailscale.py`, `tests/test_access_api_auth.py` covering the new access layer.
- Updated: `test_routes.py`, `test_routes_case_update.py`, `test_data_resource.py` — paths prefixed with `/api`.
- Updated: `test_admin_routes.py`, `test_workbench_routes.py` — prefix `/admin` → `/manage`; Tailscale gate bypassed via `dependency_overrides`.
- Deleted: `test_admin_ip_allowlist.py` — coverage moved to new access tests.

`just test`

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 505   |
| 🤔 Skipped | 0     |
| 🔴 Failed  | 0     |
| ⏱️ in      | 01:07 |

## [0.14.2] - 2026-04-16

### Added

- **Automatic data resource route mounting at startup** — `Server` now mounts generated CRUD routers for any agent that declares `data_resources`, so endpoints are available immediately after server boot without extra manual wiring.

### Fixed

- **`DataResource.registration_info` now includes computed `display_label` per field** — Resource field payloads sent to Studio now expose resolved labels (`display_label`) instead of only raw model dumps, ensuring proper field naming in the UI.

- **`JobStartConfirmationEvent` is emitted after `job_start` execution metadata is available** — The confirmation event is now sent after `job.metadata` is populated from the `job_start` response payload, so Studio receives complete metadata in the start confirmation event.

### Unit Tests Results

`just test`

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 500   |
| 🤔 Skipped | 0     |
| 🔴 Failed  | 0     |
| ⏱️ in      | ~70s  |

## [0.14.1] - 2026-04-15

## [0.14.0] - 2026-04-14

### Added

- **`DataResource` class** — Declares agent-owned CRUD endpoints exposed to Studio with `name`, `entity_type`, `description`, `operations` (list of CRUD operations), `importable` (bulk import support), and `deletable` flags.

- **`DataResourceField` class** — Describes field schema with `name`, `type`, `description`, `editable`, and `visible` attributes for validated rendering in Studio forms.

- **`FieldType` enum** — Validated field types: `STRING`, `INTEGER`, `BOOLEAN`, `DATE`, `DATETIME`, `TEXT`, `EMAIL`, `URL` for consistent data handling across agents and Studio.

- **`Editable` enum** — Controls Studio form behaviour per field: `ALWAYS` (edit in all forms), `CREATE_ONLY` (edit only on creation), `NEVER` (read-only display).

- **`metadata: dict` on `AbstractJob` and `CaseAbstractModel`** — Arbitrary metadata flows through `registration_info` to Studio, enabling agents to attach custom context and tracking data to jobs and cases.

- **`data_resources: list[DataResource]` on `Agent`** — Included in `registration_info` for Studio to discover and render CRUD interfaces for agent-managed data.

- **Auto-generated FastAPI CRUD routes** — For each declared `DataResource` operation, Supervaizer auto-mounts routes (GET, POST, PATCH, DELETE) at `/agents/{slug}/data/{resource}/...`.

- **Bulk import route** — When `importable=True` on a `DataResource`, a `POST /data/{resource}/import/` route accepts CSV or JSON for batch creation, enabling Studio to load data in bulk.

### Unit Tests Results

`just test`

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 492   |
| 🤔 Skipped | 0     |
| 🔴 Failed  | 0     |
| ⏱️ in      | ~70s  |

## [0.13.3] 2026-04-14

### Added

- **`CaseNodeUpdate.upsert` and `Case.patch_step`** — Optional step update path for Studio: when `upsert` is true, the existing case step at the same index is updated instead of appending. `Case.patch_step(index, update)` sets `index` and `upsert` on the update, sends `send_update_case`, and replaces the matching entry in `Case.updates`. Serialized in `CaseNodeUpdate.registration_info` for the controller payload.

- **Human answer with `casestep_index`** — `POST /jobs/{job_id}/cases/{case_id}/update`: if `request.answer` includes `casestep_index`, the controller calls `case.patch_step(int(casestep_index), update)` and runs `PersistentEntityLifecycle.handle_event(..., INPUT_RECEIVED)` instead of `receive_human_input`. Omit `casestep_index` for the previous append/receive-human-input behavior.

- **Tests** — `tests/test_routes_case_update.py` covers job 404, workbench-style `human_answer` params (including `casestep_index` stripped from `fields`), single owning agent vs multiple agents, and skip when `job.agent_name` is not on the server.

### Changed

- **Dynamic choices request context** — `POST .../start/dynamic_choices` now passes `workspace_slug` through to `dynamic_choices_callback` alongside `workspace_id` and `mission_id` (Supervaize Studio sends it in the JSON body).

- **`POST /jobs/{job_id}/cases/{case_id}/update` (human_answer)** — Resolves the job with in-memory `Jobs().get_job` first, then persisted (`include_persisted=True`) if missing. Returns **404** when the job does not exist. Dispatches `human_answer` only for the job owner via `server.get_agent_by_name(job.agent_name)` and `agent._execute(...)`, using the same parameter shape as the workbench HITL route (`fields`, `context`, `payload`, `job_id`, `case_id`, optional `message`). Strips `casestep_index` from `fields` for the hook. Runs the hook in a thread pool executor to avoid blocking the event loop.

### Unit Tests Results

`just test`

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 473   |
| 🤔 Skipped | 0     |
| 🔴 Failed  | 0     |
| ⏱️ in      | ~70s  |

## [0.13.1]

### Added

- **`ADMIN_ALLOWED_IPS` for admin UI** — When set, only matching client IPs may access `/admin` (HTML, APIs, static files, WebSocket). Comma-separated IPs and optional CIDR notation; empty or unset allows all. Uses the first address in `X-Forwarded-For` when present.
- **Dynamic choices for `AgentMethodField`** — Fields can now use `dynamic_choices` instead of static `choices` to resolve options at runtime via a callback. Add a `dynamic_choices_callback` callable (signature: `(method_name: str, context: dict) -> dict[str, list[tuple[str, str]]]`) to the `Agent` constructor and a `dynamic_choices` key to your `AgentMethodField`. Supervaize Studio fetches choices from the new `POST /supervaizer/agents/{slug}/start/dynamic_choices` endpoint (with `workspace_id`, `workspace_slug`, and `mission_id` in the request body) when rendering the job start form. Static `choices` and `dynamic_choices` are mutually exclusive on a field. See [Dynamic Choices guide](https://docs.runwaize.com/docs/supervaizer-controller/dynamic-choices).

### Unit Tests Results

`just test`

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 464   |
| 🤔 Skipped | 0     |
| 🔴 Failed  | 0     |
| ⏱️ in      | 65s   |

## [0.12.0]

### Added

- **Custom routes** — Agents can mount their own FastAPI `APIRouter` via the new `custom_routes` field on `Agent`. Supervaizer mounts them under the API router at `/api/agents/{slug}/...` (paths defined on the nested router append after that prefix) without inspecting or managing the routes. Enables agents to expose tool endpoints, webhooks, or any HTTP API alongside the workbench.

- **Scheduled steps** — `CaseNodeUpdate` gains `scheduled_at`, `scheduled_method`, `scheduled_params`, `scheduled_status` fields. Steps with `scheduled_at` are deferred until the scheduled time. A background executor polls every 60 seconds and calls the agent method automatically. The workbench shows countdown, "Execute now", and "Cancel" controls on pending scheduled steps. Enables time-based orchestration (call scheduling, retries with backoff, follow-up actions).
  - Model: `CaseNodeUpdate.scheduled_at / scheduled_method / scheduled_params / scheduled_status`
  - Property: `CaseNodeUpdate.is_scheduled` returns `True` when `scheduled_at` is set
  - Executor: `_run_scheduled_step_loop` — background asyncio task, polls every 60s
  - Routes: `POST .../execute`, `POST .../cancel`, `PATCH .../schedule` for step management
  - UI: status badges (pending/executing/completed/failed/cancelled), execute now / cancel buttons
  - `Case.cancel_scheduled_steps()` — cancels all pending steps on job stop
  - `Cases.get_due_scheduled_steps()` — returns steps where `scheduled_at <= now()` and status is `pending`

- **`AgentResponse` export** — `AgentResponse` is now exported from `supervaizer.__init__` for use as a typed response model in custom routes and agent endpoints.

### Fixed

- **OpenAPI / JSON Schema (Pydantic 2.12+)** — Building the full FastAPI schema (`GET /openapi.json`, Swagger UI) could raise `PydanticInvalidForJsonSchema: … CallableSchema`. Three root causes fixed:
  - `AgentMethodAbstract.model_config["example_dict"]` used `"type": str` (Python builtin) — changed to string `"str"`
  - `AgentResponse` nested schemas not rebuilt after dependent models — added `AgentResponse.model_rebuild()` after `Case.model_rebuild()` in `supervaizer/__init__.py`
  - `CaseNode.factory` typed as `Callable` which cannot appear in JSON Schema — changed to `Any` (behaviour unchanged)

## [0.11.0]

- **Job Poll mechanism** — New optional `job_poll` method in `AgentMethods` for manual external service polling. When defined, the workbench shows a "Check for updates" button on active jobs. Clicking it calls the agent's poll handler, which checks external services (email inboxes, call status APIs, etc.) and updates cases accordingly. Enables local development without webhooks — production uses real-time webhooks, local mode uses the poll button.
  - `AgentMethods`: new `job_poll: AgentMethod | None` field
  - Route: `POST /workbench/jobs/{job_id}/poll` triggers the agent's poll handler
  - UI: "Check for updates" button with loading state, conditionally rendered via `has_poll` template variable
  - JS: `pollJob()` in `workbench-form.js` with disable-during-request pattern

- **HITL double-click guard** — All HITL buttons are disabled during submission via `_postAnswer()`. Buttons get `opacity-50 cursor-not-allowed` while in flight and re-enable on error. Dialog HITL `submitMessage`/`confirmDialog` are now async, properly awaiting the form submission before resetting state.

- **Monitor reply display** — Step payloads with a `reply` key render as a blue blockquote below the step row. Step payloads with `approved_content` render as a green confirmed card.

- **Monitor duration display** — `step_duration` format now handles both numeric and string values, preventing Jinja2 `TypeError` when duration comes from HITL form input.

- **WebSocket terminal signal** — Terminal job state sends a `terminal` WS signal that keeps the connection idle, preventing reconnect loops.

- **`is_local_mode()` helper** — Centralized in `supervaizer.common`, replacing inline `os.environ.get("SUPERVAIZER_LOCAL_MODE")` checks across `account_service.py`, `server.py`.

- **`deque` for log buffer** — `_workbench_log_buffer` changed from `list` to `collections.deque(maxlen=500)`, removing manual trim logic.

- **Dialog HITL** — New HITL type for interactive content review via chat interface. When a `CaseNodeUpdate` payload contains `supervaizer_dialog`, the workbench renders a conversation UI instead of a fixed form. Supports iterative refinement through LLM-powered feedback loops. Fields: `content` (JSON string or plain text), `content_type` (email/text/code), `objective`, `instructions`, `messages` (conversation history), `confirm_label`.
  - Template: `dialog_renderer.html` with `render_hitl_dialog` and `render_dialog_confirmed` macros
  - JS: `submitDialogMessage(caseId, message)` and `confirmDialog(caseId)` in `workbench-form.js`
  - Route: `workbench_routes.py` detects `supervaizer_dialog` in AWAITING case payloads

- **Local mode URL fixes** — `supervaizer start --local --port N` now correctly shows localhost URLs everywhere: CLI output, admin interface logs, storage, and uvicorn. Fixed by resolving `Server.__init__` defaults from env vars at call time (not class definition time) and ensuring CLI-provided values take precedence over `.env` file values.

- **Local mode event skipping** — `account_service.send_event()` returns a no-op `ApiSuccess` when `SUPERVAIZER_LOCAL_MODE=true`, preventing HTTP errors against the SaaS API during local development.

- **Agent parameter env pre-fill** — In local mode, the workbench auto-loads `.env` values into agent parameter fields with green `.env` badge indicators. Secret fields show a masked placeholder; non-secret fields display the value. Backend falls back to env values for empty fields on job submission.

- **HTMX polling guard** — Monitor template suppresses `hx-trigger` polling when a HITL dialog or form is active, preventing DOM overwrites while users interact with forms.

### v0.10.27

- **Agent Workbench** — Full-featured testing interface for agents directly from the admin panel. Four-zone layout with agent parameters, job control, execution monitor, and live console log. Supports starting/stopping jobs, real-time case and step tracking via HTMX polling, and Human-in-the-Loop (HITL) form rendering and submission. Job history panel lists all past executions with status badges.
  - Backend: `workbench_routes.py` with 8 FastAPI endpoints (page, start, stop, status, monitor, console, HITL answer, job history)
  - Frontend: `workbench.html`, `workbench_monitor.html`, `workbench_console.html`, `workbench_jobs_list.html`, `workbench-form.js`
  - Shared field renderer macros: `field_renderer.html`

- **Local test mode (`--local`)** — Run the supervaizer server without Supervaize Studio credentials for local development and workbench testing. Includes built-in Hello World agent with configurable case count, optional HITL steps, and `JobInstructions.check()` support for graceful stop. Default API key `local-dev`, amber banner in admin UI.
  - CLI: `supervaizer start --local` / `just local`
  - Agent: `examples/hello_world_agent.py` with `_LocalAccount` (no-op Studio stub)
  - Server factory: `examples/local_server.py`

### Changed

- **Admin navigation** — Workbench access moved from nav dropdown to per-agent cards with direct green "Workbench" button. Removed "New Agent" button from agents list.
- **Admin auth** — Refactored API key resolution to support local server instance (`_get_admin_api_key`, `_is_local_mode`), with fallback chain: server state → env var → default.

### Fixed

- **CaseNode.factory now optional** — `CaseNode.factory` field changed from required to `Optional[Callable] = None`. Previously, `factory` was `exclude=True` (correctly omitted from serialization), but still required by Pydantic validation. This caused `AgentResponse(**agent.registration_info)` to fail with `Field required` errors on the `GET /supervaizer/agents` route, because the round-tripped dict never contained `factory`. Agents with CaseNode-based workflows were unable to register. ([#6](https://github.com/supervaize/supervaizer/issues/6))

### Changed

- **CI** – Python package workflow: dependency install now uses `uv sync --extra dev --extra deploy` (adds deploy extras for CI).

### Unit Tests Results

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 433   |
| 🤔 Skipped | 0     |
| 🔴 Failed  | 0     |
| ⏱️ in      | 50s   |

## [0.10.19]

### Added

- **Server: optional local index.html** – If a local `index.html` exists, the server serves it for the home page response.

### Changed

- **Dependencies** – Bumped `boto3`/`botocore` to 1.42.41 (lock file). Updated `ruff` to 0.15.0 and pre-commit config.
- **Admin index** – Simplified displayed information in the admin index template.
- **CI** – PyPI publish workflow: added concurrency settings to cancel in-progress runs.

## [0.10.18]

### Added

- **SUPERVAIZER_PRIVATE_KEY** – `_get_or_create_private_key` reads key from env or generates and sets it. Admin dashboard shows a development-only warning (not for production exposure).

### Changed

- **Refactor** – Code formatting and trailing whitespace cleanup (admin routes, server, examples, tests, templates).

## [0.10.17]

### Added

- **SUPERVAIZER_PRIVATE_KEY** from env if set; else create key and set env.

- **Admin: live server and data when no persistence** – When there is no persistent storage (e.g. Vercel, serverless), the admin dashboard and agents page no longer fail. Server status, server config, and agents use the live server instance (`app.state.server`) when storage has no ServerInfo. Dashboard stats, jobs list, cases list, and recent activity use live Jobs/Cases registries when storage is in-memory and empty.

### Changed

- **Register with supervisor (no frontend API key)** – The "Register with supervisor" button now calls the backend without any API key. The backend sends the SERVER_REGISTER event to SUPERVAIZE_API_URL; no authentication is required from the frontend for this action.
- **Admin server/agents fallback** – Server info and agents are read from storage first, then from the live server when storage has no ServerInfo (e.g. persistence disabled). `get_server_status` and `get_server_configuration` accept an optional `request` for the live fallback.

### Fixed

- **Admin: API key "None" in URLs** – When `SUPERVAIZER_API_KEY` is unset, the template no longer renders the literal string `"None"` (e.g. in `data-admin-key`). SessionStorage no longer stores `"None"` from `?key=None`, and the frontend treats the string `"None"` as no key where applicable.

### Unit Tests Results

| Status     | Count  |
| ---------- | ------ |
| ✅ Passed  | 419    |
| 🤔 Skipped | 6      |
| 🔴 Failed  | 0      |
| ⏱️ in      | 53.16s |

## [0.10.11]

### Added

- **Optional data persistence (default off)** – Data is no longer persisted to file by default, so the server runs correctly on Vercel and other serverless platforms where the filesystem is ephemeral.

### Changed

- **Controller unreachable** – When the Supervaize controller server is not available (connection refused or timeout), event send now fails gracefully with a short, clear error message instead of dumping the full payload and traceback. Logs: `Supervaize controller is not available at {url}. Connection refused or timed out. Is the controller server running?` and the event type/exception.
  - Set `SUPERVAIZER_PERSISTENCE=true` (or `1`/`yes`) to enable file persistence.
  - CLI: `supervaizer start --persist` enables persistence for that run.
  - Explicit `StorageManager(db_path=...)` in code still uses file storage (e.g. tests).
  - See [PERSISTENCE.md](PERSISTENCE.md) for configuration.

### Unit Tests Results

| Status     | Count  |
| ---------- | ------ |
| ✅ Passed  | 419    |
| 🤔 Skipped | 6      |
| 🔴 Failed  | 0      |
| ⏱️ in      | 55.28s |

## [0.10.4]

- Relax some dependencies requirements

## [0.10.2]

### Changed

- **🐍 Python 3.13 Support** - Added Python 3.13 compatibility
  - Updated package classifiers to include Python 3.13
  - Build process now uses Python 3.13 for wheel generation
  - CI test matrix includes Python 3.13
  - Wheels built with Python 3.13 are compatible with both Python 3.12 and 3.13

## [0.10.0]

### Added

- **🚀 Cloud Deployment CLI** - Complete automated deployment system for Supervaizer agents
  - Full implementation of [RFC-001: Cloud Deployment CLI](docs/rfc/001-cloud-deployment-cli.md)
  - Support for three major cloud platforms:
    - **Google Cloud Run** with Artifact Registry and Secret Manager
    - **AWS App Runner** with ECR and Secrets Manager
    - **DigitalOcean App Platform**
  - New deployment commands:
    - `supervaizer deploy plan` - Preview deployment actions before applying
    - `supervaizer deploy up` - Deploy to cloud platform with automated build, push, and verification
    - `supervaizer deploy down` - Tear down deployment and clean up resources
    - `supervaizer deploy status` - Check deployment status and health
    - `supervaizer deploy local` - Local Docker testing with docker-compose
    - `supervaizer deploy clean` - Clean up deployment artifacts and state
  - **Automated Docker Workflow**: Build → Push → Deploy → Verify
  - **Secret Management**: Secure handling of API keys and RSA keys via cloud provider secret stores
  - **Health Verification**: Automatic health checks at `/.well-known/health` endpoint
  - **Idempotent Deployments**: Safe create/update operations with rollback on failure
  - **Local Testing**: Full Docker Compose environment for pre-deployment testing
  - See [Local Testing Documentation](docs/LOCAL_TESTING.md) for details

- **Agent Instructions Template** - New HTML page served by FastAPI for Supervaize integration instructions
  - Accessible at `/admin/supervaize-instructions`
  - Provides step-by-step setup guide for agents

- **Version Check Utility** - Automatic check for latest Supervaizer version
  - Helps users stay up-to-date with latest features and fixes
  - Located in `supervaizer.utils.version_check`

- **Enhanced Admin Interface**
  - New agents listing page with grid view
  - Improved agent detail views
  - Better navigation and UI consistency

### Changed

- **🔄 Protocol Unification** - Removed ACP protocol in favor of unified A2A protocol
  - Removed `src/supervaizer/protocol/acp/` directory and all ACP-specific code
  - Removed `acp_endpoints` parameter from Server class
  - Removed ACP route registration and test files
  - Updated all documentation to reflect A2A-only support
  - The A2A protocol has evolved to incorporate features from multiple agent communication standards, including the former ACP
  - All A2A protocol links updated to [https://a2a-protocol.org/](https://a2a-protocol.org/)
  - **Breaking Change**: `acp_endpoints` parameter no longer accepted in Server initialization

- **📦 Dependency Optimization** - Cloud SDKs moved to optional dependencies
  - Base package size significantly reduced
  - Cloud deployment dependencies now optional: `pip install supervaizer[deploy]`
  - Optional `deploy` group includes: boto3, docker, google-cloud-artifact-registry, google-cloud-run, google-cloud-secret-manager, psutil
  - Removed unused `pymongo` dependency
  - Updated dependency versions for better compatibility

- **Improved Error Handling** - Enhanced API error responses with better context

- **Documentation Updates**
  - Added comprehensive deployment documentation
  - Updated model reference documentation
  - Improved README with deployment examples
  - Updated PROTOCOLS.md to focus on unified A2A protocol
  - Added Protocol Evolution section explaining ACP merger

### Fixed

- API documentation errors corrected
- Improved type hints for `agent_parameters` and `case_ids` in job.py
- Health logging optimized in A2A routes

### Unit Tests Results

| Status     | Count  |
| ---------- | ------ |
| ✅ Passed  | 415    |
| 🤔 Skipped | 6      |
| 🔴 Failed  | 0      |
| ⏱️ in      | 50.56s |

### Migration Notes

- **ACP Protocol Removal**: If your code uses `acp_endpoints=True` parameter, remove it from Server initialization. The A2A protocol now provides unified agent communication.
- If you need deployment features, install with: `pip install supervaizer[deploy]`
- For development, install with: `pip install supervaizer[dev,deploy]`
- No other breaking changes to existing APIs or functionality

## [0.9.8]

### Added

- **Parameter Validation System**: Added comprehensive parameter validation for job creation with clean error messages
  - New `validate_parameters()` method in `ParametersSetup` class for agent parameter validation
  - New `validate_method_fields()` method in `AgentMethod` class for job field validation
  - Two separate validation endpoints for different validation needs:
    - `/validate-agent-parameters` - Validate agent configuration parameters (secrets, API keys, etc.)
    - `/validate-method-fields` - Validate job input fields against method definitions
  - Support for validating both job fields and encrypted agent parameters
  - Clean error messages with specific details about invalid parameter types and missing required parameters

### Fixed

- Execution of `supervaizer start` was not maintaining the _main_ namespace so the fastapi server was never starting. Replaced execution by sub-process.
- Type of agent.choice. #TODO: test and decide which to keep (list[str] or list [tuple[str,str]])
- When supervisor_account is provided, A2A endpoints are automatically activated, because Supervaize needs to be able to trigger the healthchecks. -`export_openapi.py` tool to generate openapi.json (for docusaurus documentation) - automation in docusaurus to do.

### Changed

- **Parameter Validation System**: Refactored to provide separate validation endpoints for different concerns
  - **Agent Parameters**: Now validated separately through `/validate-agent-parameters` endpoint
  - **Method Fields**: Now validated separately through `/validate-method-fields` endpoint
  - **Clean Architecture**: Removed legacy endpoint for cleaner, more focused API design
  - **Code Deduplication**: Eliminated redundant validation code in job start endpoints
  - **Clearer Separation**: Agent configuration validation vs. job input validation are now distinct operations

- pytest does not run with coverage by default (change in pyproject.toml)

### Unit tests results

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 308   |
| 🤔 Skipped | 6     |

## [0.9.6]

- Public release to Pypi
- Fixed the gihut workflows
- Improve README.md

## [0.9.5]

### Fixed

- Setup : missing `py.typed` in pyproject
- clarified public_url (replaced registration_host by public_url)
- changed "supervaizer install" to "supervaizer scaffold"

### Added

- `gen_model_docs.py`: tool for documentation generation - see disclaimer

### Unit tests results

| Status     | Count |
| ---------- | ----- |
| ✅ Passed  | 277   |
| 🤔 Skipped | 6     |

## [0.9.4]

### Added

- CICD : release, deploy
- `gen_model_docs.py` : to generate the documentation of the models.

### Changed

- Moved "example" to `src/supervaizer`
- Improved and Moved some documentation to `docs`
- Added `python-package.yml` github action, triggered on push / PR of "develop" branch

## [0.9.3]

### Added

- Data persistence with tinyDB
- Admin UI with fastAdmin
- Dynamic content on:
  - Server page
  - Agent
  - Jobs
  - Cases
- Add persisted data to job status check.

### Changed

- Paramater.to_dict : override to avoid storing secrets.
- Removed Case Nodes
- Improved test coverage : accounts, admin/routes,

### Unit tests results

| Status     | Count |
| ---------- | ----- |
| 🤔 Skipped | 6     |
| ⚠️ Failed  | 0     |
| ✅ Passed  | 281   |

Test Coverage : [![Test Coverage](https://img.shields.io/badge/Coverage-81%25-brightgreen.svg)](https://github.com/supervaize/supervaizer)

> | Emoji Legend |                        |               |
> | ------------ | ---------------------- | ------------- |
> | 🌅 Template  | 🏹 Service             | 👔 Models     |
> | 🐛 Bug       | 🛣️ Infrastructure/CICD | 🔌 API        |
> | 💼 Admin     | 📖 Documentation       | 📰 Events     |
> | 🧪 Tests     | 🧑‍🎨 UI/Style            | 🎼 Controller |
