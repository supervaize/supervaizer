# Supervaizer Changelog

All notable changes to this project will be documented in this file.

> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## TODO

- Fix CICD
  - Version bump : rebuild documentation after version bump in CI-CD
  - Update Released / Package / Tag
- Review and test feature/data-persistance
- Complete feature/smartinstall implementation
- Fix receive_human_input
- Test and fix deploy
- When AgentMethodField returns its value (in the kwargs of job_start), the value should be casted in the appropriate type :
  - example: here the 'How many times to say hello' is supposed to be an 'int'.
  - agent_simple:job_start:74 - AGENT ExampleAgent: Received kwargs: {'action': 'start', 'fields': {'How many times to say hello': '3'}, 'context': JobContext(workspace_id='odm', job_id='01KGM75NQ76AWBAXHXERW8FKHW', started_by='alp', started_at=datetime.datetime(2026, 2, 4, 11, 39, 0, 712598, tzinfo=TzInfo(0)), mission_id='01KGG50ZMFYMHG9N5FGCACF0XA', mission_name='Operate Agent Hello World AI Agent', mission_context=None, job_instructions=JobInstructions(max_cases=None, max_duration=None, max_cost=None, stop_on_warning=False, stop_on_error=True, job_start_time=None)), 'agent_parameters': [{'name': 'SIMPLE AGENT PARAMETER', 'team_id': 2, 'description': 'Setup agent parameter in this workspace', 'is_environment': True, 'value': '123456', 'is_secret': False, 'is_required': False}, {'name': 'SIMPLE AGENT SECRET', 'team_id': 2, 'description': 'Setup agent secret in this workspace', 'is_environment': True, 'value': '123456', 'is_secret': True, 'is_required': False}]}

## Unreleased

## v0.12.0

### Added

- **Custom routes** — Agents can mount their own FastAPI `APIRouter` via the new `custom_routes` field on `Agent`. Supervaizer mounts them at `/agents/{slug}/api/` without inspecting or managing the routes. Enables agents to expose tool endpoints, webhooks, or any HTTP API alongside the workbench.

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

## v0.11.0

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

## v0.10.19

### Added

- **Server: optional local index.html** – If a local `index.html` exists, the server serves it for the home page response.

### Changed

- **Dependencies** – Bumped `boto3`/`botocore` to 1.42.41 (lock file). Updated `ruff` to 0.15.0 and pre-commit config.
- **Admin index** – Simplified displayed information in the admin index template.
- **CI** – PyPI publish workflow: added concurrency settings to cancel in-progress runs.

## v0.10.18

### Added

- **SUPERVAIZER_PRIVATE_KEY** – `_get_or_create_private_key` reads key from env or generates and sets it. Admin dashboard shows a development-only warning (not for production exposure).

### Changed

- **Refactor** – Code formatting and trailing whitespace cleanup (admin routes, server, examples, tests, templates).

## v0.10.17

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

## v0.10.11

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
