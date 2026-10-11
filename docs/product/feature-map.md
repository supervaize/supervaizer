# Product feature map

> **Updated:** 2026-10-11

Compact index of what a person is trying to do with Supervaizer. Each entry names the workflow, where it starts, who can use it, what should happen, and where the code and pytest evidence live.

This is not a screen catalog. Page filters, form fields, and click-by-click steps stay in the linked doc or test. There is no screenshot catalog and no browser end-to-end suite; verification links are pytest modules. When a workflow, route, or access rule changes, update the entry in the same change.

Protocol and model detail stays in [Supervaizer v2](../2026_05_SUPERVAIZER_v2.md) and [Protocols](../2026_05_PROTOCOLS.md). The admin page table stays in [Admin interface](../2025_08_ADMIN_README.md).

## Run the controller locally

- Purpose: See a v2 controller on this machine without Studio.
- Entry points:
  - `supervaizer start --local`
  - No control file: Hello World alone. With `supervaizer_control.py`: that server plus Hello World.
- Access: API key `local-dev` unless `SUPERVAIZER_API_KEY` is set. `--host 0.0.0.0`, `--host ::`, and an empty host bind `127.0.0.1`. Any other `--host` is kept and overrides the control script's `Server.host`.
- Preconditions: None. `SUPERVAIZER_DISABLE_HELLO_WORLD=true` skips the built-in agent.
- Main flow:
  1. Start in local mode.
  2. Open `/docs` on the bound host, or `POST /a2a` with `X-API-Key: local-dev`.
- Expected result: Studio registration is skipped. `/a2a` actions and surfaces run without a workspace token while the bypass below is on.
- Important states: The bypass is off when the server has a `supervisor_account`, when workspace auth is enabled, or when issuer, audience, public key, or JWKS URL is nonempty. `SUPERVAIZER_WORKSPACE_AUTH_LEEWAY_SECONDS` does not count. `SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=false` leaves the bypass on. With the verifier enabled, a missing token is JSON-RPC `-32030` and `error.data.code` `workspace_authorization_missing`. With no enabled verifier, `error.data.code` is `workspace_authorization_not_configured`.
- Source: `src/supervaizer/cli.py`, `src/supervaizer/examples/local_server.py`, `src/supervaizer/workspace_authorization.py`
- Verification: `tests/test_local_mode_a2a.py`, `tests/test_cli.py`
- Known caveats: The bypass covers `/a2a` actions and surfaces only. Data-resource routes never bypass. Do not expose the port: the key is well known, and a non-loopback `--host` publishes it. The public [supervaize_hello_world](https://github.com/supervaize/supervaize_hello_world) repo is still the v1 `AgentMethod` style; model new agents on the built-in agent.

## Scaffold a v2 control file

- Purpose: Generate a minimal controller you can edit.
- Entry points:
  - `supervaizer scaffold`
  - `supervaizer scaffold instructions`
  - `supervaizer scaffold refresh-instructions`
- Access: Local filesystem. No server auth.
- Preconditions: Write access to the output path. `--force` (or `SUPERVAIZER_FORCE_INSTALL=true`) overwrites.
- Main flow:
  1. Run `supervaizer scaffold`.
  2. Run `supervaizer start --local`.
  3. Invoke the scaffolded `job.start` action.
- Expected result: `supervaizer_control.py` declares one registration, one `job.start` surface, and one `job.start` action. `supervaize_instructions.html` is the instructions page.
- Important states: Existing files are left in place unless `--force` is set.
- Source: `src/supervaizer/cli.py`
- Verification: `tests/test_cli.py`
- Known caveats: The scaffold builds an `Account` from `SUPERVAIZE_*` environment variables. Local mode ignores that account. `agent_slug` must equal the slugified agent name.

## Discover agents

- Purpose: List the agents on a controller and read one Agent Card.
- Entry points:
  - `GET /.well-known/agents.json`
  - `GET /.well-known/agents/v{version}/{agent_slug}_agent.json`
  - Legacy card: `GET /.well-known/agents/{agent_slug}_agent.json`
  - `GET /.well-known/health`
- Access: Public. No API key.
- Preconditions: The server is running. Per-agent cards exist only for agents registered on that server.
- Main flow:
  1. Fetch `/.well-known/agents.json`.
  2. Fetch the card URL for one slug.
- Expected result: The list names every agent. A card for a v2 agent includes the `supervaizer.v2` extension. `api_endpoints[].url` points at `/api/supervaizer/agents/{agent_slug}`. `human_url` is that agent's instructions page.
- Important states: `version_info.changelog_url` is present only when the agent sets `release_notes_url`. There is no logo route and no `/changelog/{slug}` route.
- Source: `src/supervaizer/protocol/a2a/routes.py`, `src/supervaizer/protocol/a2a/model.py`
- Verification: `tests/test_a2a.py`, `tests/test_v2_only_agents.py`
- Known caveats: The card is Supervaizer's `schema_version: a2a_2023_v1` document, not the upstream A2A AgentCard schema. The instructions page is under `/api` and needs `X-API-Key`.

## Invoke a v2 action

- Purpose: Run a declared action such as `job.start` or `step.awaiting.submit`.
- Entry points:
  - Direct route: `POST /a2a`
  - JSON-RPC method: `supervaizer/action.invoke`
- Access: `X-API-Key` with write scope. Outside the local-mode bypass, also `X-Supervaize-Workspace-Authorization: Bearer <token>`.
- Preconditions: The agent declares the action and a handler is registered for that `agent_slug`. `POST /a2a` is mounted when `a2a_endpoints` is true, which is the default, including a standalone server with no Studio account and local mode off. `/api` is mounted only when a Studio account is set or local mode is on. Either of those forces `a2a_endpoints` back to true.
- Main flow:
  1. Send `supervaizer/action.invoke` with `agent_slug`, `action`, and `input`.
  2. Read `effects` and optional `job_state`.
- Expected result: The registered handler runs and the JSON-RPC result carries its effects.
- Important states: Unknown action `-32010`. Missing handler for a declared action fails the same way. Unknown agent is rejected. Workspace auth failures are JSON-RPC `-32030`. `error.data.code` is `workspace_authorization_missing` when the verifier is enabled and the header is absent, and `workspace_authorization_not_configured` when no verifier is enabled. `supervaizer/surface.load` uses the same auth codes. Bootstrap actions `workspace_binding.options` and `workspace_binding.create` do not need a workspace token.
- Source: `src/supervaizer/protocol/a2a/routes.py`, `src/supervaizer/protocol/a2a/controller.py`
- Verification: `tests/test_local_mode_a2a.py`, `tests/test_a2a.py`
- Known caveats: Pass `agent_slug` on every handler. Local mode adds Hello World, so a multi-agent server cannot infer the slug. A bare action id defaults to `mutating=True, scope="job"`.

## Load a surface

- Purpose: Fetch the A2UI document for a named surface such as `job.start` or `case.step.awaiting`.
- Entry points:
  - Direct route: `POST /a2a`
  - JSON-RPC method: `supervaizer/surface.load`
- Access: Same as invoking an action (write scope, plus a workspace token outside the local-mode bypass).
- Preconditions: The surface is declared and a handler is registered.
- Main flow:
  1. Send `supervaizer/surface.load` with `agent_slug` and the surface id.
  2. Render the returned A2UI document in Studio. Supervaizer does not render it.
- Expected result: The handler's document is returned for that surface.
- Important states: Missing surface handler answers `-32011`. The `workspace_binding.create` surface is in the bootstrap set and does not need a workspace token.
- Source: `src/supervaizer/protocol/a2a/controller.py`
- Verification: `tests/test_local_mode_a2a.py`
- Known caveats: A2UI version and `a2ui_catalog_version` are pinned on the registration. Incompatible versions should fail in Studio, not be best-effort rendered.

## Watch v2 effects

- Purpose: Follow action effects as they happen.
- Entry points:
  - Direct route: `GET /a2a/events`
- Access: `X-API-Key` with read scope. `write` implies `read`.
- Preconditions: A2A endpoints are on (default, and forced on when a Studio account or local mode is set).
- Main flow:
  1. Open the SSE stream.
  2. Invoke an action on `POST /a2a`.
  3. Read the effect events.
- Expected result: The stream emits Supervaizer v2 effects for observers.
- Important states: A key without read scope gets HTTP 403.
- Source: `src/supervaizer/protocol/a2a/routes.py`, `src/supervaizer/protocol/a2a/events.py`
- Verification: `tests/test_a2a.py`
- Known caveats: Push notifications are not implemented and are not advertised. AG-UI is metadata only (`ag_ui_version`); it is not a live runtime.

## Register the controller with Studio

- Purpose: Make Studio aware of this server and its agents.
- Entry points:
  - `supervaizer start` with `supervisor_account` set on `Server`
  - Admin: Server page → register, `POST /manage/api/server/register`
  - `POST /api/supervaizer/registration/refresh`
- Access: Launch uses the agent-to-Studio key (`SUPERVAIZE_API_KEY` on the `Account`). The admin register button is Tailscale-gated (loopback in local mode) and uses no API key.
- Preconditions: `SUPERVAIZE_WORKSPACE_ID`, `SUPERVAIZE_API_KEY`, and `SUPERVAIZE_API_URL` are passed into `Account` by the control script. `Server` does not read those variables. With A2A on, launch also requires `SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=true`, `SUPERVAIZER_WORKSPACE_AUTH_ISSUER`, and either `SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY` or `SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL`.
- Main flow:
  1. Build `Account` and pass it as `supervisor_account`.
  2. Start the server.
  3. Confirm registration on `/manage/server`.
- Expected result: Studio receives `server.register`. `details.server_id` is the stable server identity. `details.url` is `public_url`.
- Important states: Missing workspace-auth trust material aborts launch with `Studio-registered Supervaizer v2 A2A requires workspace authorization`. A workspace id that does not match the API key's workspace can make `SERVER_REGISTER` return HTTP 403. Local mode skips registration.
- Source: `src/supervaizer/account.py`, `src/supervaizer/server.py`, `src/supervaizer/studio_handshake.py`
- Verification: `tests/test_admin_routes.py`, `tests/test_routes.py`
- Known caveats: `--local` is exempt from the launch check and ignores `supervisor_account`. Set `SUPERVAIZER_SERVER_ID` and `SUPERVAIZER_PRIVATE_KEY` when more than one process must keep the same identity.

## Call a shared agent with a workspace grant

- Purpose: Let Studio authorize one workspace's use of an agent without the controller storing grants.
- Entry points:
  - Header: `X-Supervaize-Workspace-Authorization: Bearer <token>` on `POST /a2a` and on data-resource routes
- Access: Studio mints the token. The controller only verifies it.
- Preconditions: Issuer plus a public key or JWKS URL. `SUPERVAIZER_WORKSPACE_AUTH_REQUIRED` is what a Studio-registered launch demands; any single trust setting is enough to disable the local-mode bypass.
- Main flow:
  1. Studio sends the token with the controller call.
  2. The controller verifies issuer, signature, and claims before the handler runs.
- Expected result: The handler receives a verified workspace context. Bootstrap binding calls skip the token.
- Important states: Token missing or verifier not configured: `-32030`. A configured verifier still checks tokens in local mode, and those tokens need `agent.server_agent_id`, which exists only after Studio registration, so they cannot succeed in local mode.
- Source: `src/supervaizer/workspace_authorization.py`, `docs/2026_05_WORKSPACE_AGENT_GRANTS.md`
- Verification: `tests/test_local_mode_a2a.py`, `tests/test_routes.py`
- Known caveats: Workspace and tenant slugs are routing hints, not authorization.

## Expose records through a data resource

- Purpose: Let Studio list, read, and edit agent-owned records over REST.
- Entry points:
  - `GET /api/agents/{slug}/data/{name}/`
  - `GET /api/agents/{slug}/data/{name}/{item_id}`
  - `POST /api/agents/{slug}/data/{name}/`
  - `PUT /api/agents/{slug}/data/{name}/{item_id}`
  - `DELETE /api/agents/{slug}/data/{name}/{item_id}`
  - `POST /api/agents/{slug}/data/{name}/import/`
- Access: `X-API-Key`. Creates, updates, deletes, and imports also need write scope. Every call needs a workspace authorization token.
- Preconditions: The agent sets `data_resources`. A route exists only when that callback is set (`on_list`, `on_get`, `on_create`, `on_update`, `on_delete`, `on_import`). The `/api` router is mounted only with a Studio account or local mode. `name` must match `^[a-z0-9][a-z0-9_-]*$`.
- Main flow:
  1. Declare a `DataResource` on the agent.
  2. Studio calls the generated route with the API key and a workspace token.
  3. The callback receives a `DataResourceContext`.
- Expected result: The callback's records are returned. Registration info includes the resource.
- Important states: HTTP 403. No enabled verifier: the detail says workspace authorization is not configured. Verifier on and no token: the detail names the missing header. A callback `PermissionError` is also HTTP 403. Update or delete callbacks that report a missing item become HTTP 404. Create must return an id.
- Source: `src/supervaizer/data_resource.py`, `src/supervaizer/data_routes.py`, `src/supervaizer/routers/api.py`
- Verification: `tests/test_data_resource.py`, `tests/test_routes.py`, `tests/test_agent.py`
- Known caveats: This is not a v2 `resources=[...]` declaration. That path derives `resource.<id>.<operation>` actions invoked through `POST /a2a`. Data-resource routes are a separate CRUD surface, they are not under `/api/supervaizer`, and local mode does not bypass their workspace check. Names must be unique per agent.

## Declare a v2 resource

- Purpose: Publish agent-owned business objects that Studio operates through A2A actions.
- Entry points:
  - Registration field `resources=[...]` on `build_v2_agent_registration`
  - Invoke `resource.<id>.<operation>` via `POST /a2a`
- Access: Same as [Invoke a v2 action](#invoke-a-v2-action).
- Preconditions: Handlers are registered for the derived actions. Local mode requires an explicit `agent_slug` when Hello World is also loaded.
- Main flow:
  1. Declare the resource on the v2 registration.
  2. Register a handler per derived action.
  3. Studio invokes the action and renders the result.
- Expected result: The SDK adds `resource.<id>.<operation>` actions to the contract. Studio does not need a custom UI.
- Important states: A missing handler answers `-32010`.
- Source: `src/supervaizer/contracts.py`, `src/supervaizer/examples/hello_world_agent.py`
- Verification: `tests/test_contracts.py`, `tests/test_agent.py`
- Known caveats: Hello World exposes `resource.hello_messages.list` this way. Do not confuse it with [Expose records through a data resource](#expose-records-through-a-data-resource).

## Inspect jobs and cases

- Purpose: See what the controller has stored and update or delete a record.
- Entry points:
  - Admin home → Jobs or Cases
  - Direct routes: `/manage/`, `/manage/jobs`, `/manage/cases`, `/manage/agents`, `/manage/server`
- Access: Client IP in `100.64.0.0/10`, or loopback when `SUPERVAIZER_LOCAL_MODE=true`. No API key. `X-Forwarded-For` counts only when the peer is in `TRUSTED_PROXIES`.
- Preconditions: `admin_interface=True` (the default) and the server has an API key, which it always does (`SUPERVAIZER_API_KEY`, a generated key, or `local-dev`).
- Main flow:
  1. Open `/manage/`.
  2. Open Jobs or Cases and filter the list.
  3. Update a status or delete a row from the list.
- Expected result: The dashboard shows counts and the last five jobs and cases. Lists refresh on their own. Status updates and deletes hit `/manage/api/...`.
- Important states: HTTP 403 when the IP is not allowed. HTTP 404 when `admin_interface=False`. Empty lists after a restart when persistence is off.
- Source: `src/supervaizer/admin/routes.py`, `src/supervaizer/routers/private.py`
- Verification: `tests/test_admin_routes.py`
- Known caveats: Jobs are not created from the job list. `/admin` and `ADMIN_ALLOWED_IPS` are gone. The API key on the server is what allows the UI to be mounted; requests to `/manage` do not send it.

## Start a job from the workbench

- Purpose: Run a v1 agent from the admin UI without Studio.
- Entry points:
  - Agents → an agent → Workbench
  - Direct route: `/manage/agents/{slug}/workbench`
  - Start: `POST /manage/agents/{slug}/workbench/start`
  - Live updates: `GET /manage/agents/{slug}/workbench/jobs/{job_id}/ws`
- Access: Same Tailscale or local-loopback rule as the rest of `/manage`.
- Preconditions: The agent defines v1 `methods`, including `job_start`.
- Main flow:
  1. Open the workbench for the agent.
  2. Fill parameters and job fields.
  3. Start the job.
  4. Follow the job, answer a human-in-the-loop prompt, or execute, cancel, or schedule a step.
- Expected result: A v1 job is created and the job view updates over the WebSocket (`monitor`, `console`, `jobs`, `terminal`).
- Important states: An agent with no `methods` gets HTTP 400, `Agent has no methods defined: the workbench runs v1 jobs only`, and no job is stored. Missing `job_stop` or `job_status` disables those controls.
- Source: `src/supervaizer/admin/workbench_routes.py`
- Verification: `tests/test_workbench_routes.py`, `tests/test_v2_only_agents.py` (`test_workbench_start_rejects_v2_only_agent_without_creating_a_job`)
- Known caveats: v2-only agents are operated through `POST /a2a`, not this screen. The workbench does not talk to Studio when it starts a job.

## Watch server logs

- Purpose: Read the controller log while it runs.
- Entry points:
  - Admin → Console, `/manage/console`
  - Stream: `GET /manage/log-stream`
  - Per-agent console: `/manage/agents/{slug}/workbench/console`
- Access: Same as `/manage`.
- Preconditions: Admin interface is mounted.
- Main flow:
  1. Open `/manage/console`.
  2. Leave it open while traffic hits the server.
- Expected result: The page shows log lines from the SSE stream.
- Important states: `POST /manage/api/console/execute` runs a console command. `/manage/test-log`, `/manage/test-loguru`, and `/manage/debug-queue` are development helpers.
- Source: `src/supervaizer/admin/routes.py`
- Verification: `tests/test_admin_routes.py`
- Known caveats: The server-wide console is SSE. The per-job workbench channel is the WebSocket above. They are different streams.

## Persist jobs across restarts

- Purpose: Keep jobs, cases, and server info after the process exits.
- Entry points:
  - `supervaizer start --persist`
  - `SUPERVAIZER_PERSISTENCE=true` and `DATA_STORAGE_PATH` (default `./data`)
- Access: Local process. The file is `DATA_STORAGE_PATH/entities.json`.
- Preconditions: Set the variables before `supervaizer.storage` is imported. The CLI applies `--persist` before it loads the control script.
- Main flow:
  1. Start with persistence on.
  2. Create a job.
  3. Restart and open `/manage/jobs`.
- Expected result: Jobs and cases in `IN_PROGRESS`, `CANCELLING`, or `AWAITING` are loaded back. `ServerInfo` is written when the admin interface is on.
- Important states: Persistence off: lists are empty after restart. `StorageManager(db_path=...)` after import does nothing; the first singleton wins.
- Source: `src/supervaizer/storage.py`
- Verification: `tests/test_storage.py`
- Known caveats: Decrypted `agent_parameters` are not written. Old rows can still contain them because upsert merges. Locks are process-local. There is no caching middleware and no migration. Serverless disks should leave this off. Set `SUPERVAIZER_PRIVATE_KEY` and `SUPERVAIZER_SERVER_ID` separately; they are not in the file.

## Validate v1 inputs before job start

- Purpose: Check agent parameters and `job_start` fields before `POST .../jobs`.
- Entry points:
  - `POST /api/supervaizer/agents/{agent_slug}/validate-agent-parameters`
  - `POST /api/supervaizer/agents/{agent_slug}/validate-method-fields`
- Access: `X-API-Key` with write scope. Mounted only with a Studio account or local mode.
- Preconditions: v1 `Parameter` setup and `AgentMethod.fields`. v2 agents validate inside their own handlers instead.
- Main flow:
  1. Post the encrypted agent parameters or the job fields.
  2. Read `valid`, `errors`, and `invalid_parameters` or `invalid_fields`.
- Expected result: HTTP 200 either way. `valid` is false when a required value is missing or null, or a type does not match.
- Important states: Job start itself does not call these checks. An agent with no parameter setup returns `valid: true`. Unknown method names report `Agent has no methods defined` or `Method 'X' not found`.
- Source: `src/supervaizer/routes.py`, `docs/2025_08_PARAMETER_VALIDATION.md`
- Verification: `tests/test_validation_endpoints.py`
- Known caveats: v2-only agents keep these routes and the instructions page, and they do not get `/jobs`, `/stop`, or `/status`. String type labels such as `"str"` are not type-checked. `True` passes an `int` check.

## Smoke-test the container

- Purpose: Run the image that `deploy up` ships, on this machine.
- Entry points:
  - `supervaizer deploy local --name my-agent`
- Access: Docker Compose v2. The published port binds `127.0.0.1` only.
- Preconditions: The `deploy` extra, Docker, and a `pyproject.toml` in the current directory or up to three parents. `--name` is required or the CLI prompts.
- Main flow:
  1. Run `supervaizer deploy local --name my-agent --generate-api-key`.
  2. Hit the health URL the command prints.
- Expected result: The container comes up with the same environment shape as a cloud deploy.
- Important states: Day-to-day development stays on `supervaizer start --local`. This command is the image smoke test.
- Source: `src/supervaizer/deploy/commands/local.py`, `docs/2025_10_LOCAL_TESTING.md`
- Verification: `tests/test_deploy_local_testing.py`, `tests/test_deploy_wiring.py`
- Known caveats: Requires `docker compose`, not `supervaizer start`.

## Deploy to a cloud platform

- Purpose: Build the controller image, push it, and run it on Cloud Run, App Runner, or DigitalOcean App Platform.
- Entry points:
  - `supervaizer deploy plan`
  - `supervaizer deploy up`
  - `supervaizer deploy status`
  - `supervaizer deploy down`
  - `supervaizer deploy clean`
- Access: The platform CLI credentials (`gcloud`, AWS, or `doctl`). `--name` is required on every command except `clean`.
- Preconditions: `pip install "supervaizer[deploy]"`, Docker running, `pyproject.toml` nearby. Cloud Run also needs `--project-id`.
- Main flow:
  1. `deploy plan` to preview.
  2. `deploy up` to build, push, and create or update the service.
  3. `deploy status` to read the URL. `deploy down` tears the service down.
- Expected result: The image is pushed to the platform registry. With `--generate-api-key` and `--generate-rsa`, `SUPERVAIZER_API_KEY` and `SUPERVAIZER_PRIVATE_KEY` are stored as platform secrets under those names. `SUPERVAIZER_PUBLIC_URL` is set from the service URL once the revision is ready.
- Important states: `--image` accepts `name[:tag]` only; a `/` is rejected. Unsupported platforms and failed prerequisites print an error and return. `deploy up` prints failures and still exits `0`.
- Source: `src/supervaizer/deploy/commands/up.py`, `src/supervaizer/deploy/cli.py`, `docs/2025_08_CLI.md`
- Verification: `tests/test_deploy_commands.py`, `tests/test_deploy_driver_registry.py`, `tests/test_deploy_wiring.py`
- Known caveats: Cloud Run services start private, and the runtime service account needs `secretAccessor` on each secret. App Runner sets no ECR access role and no instance role; treat that platform as experimental. Without the generate flags, each instance makes its own key. The image holds no credentials, only `SUPERVAIZER_PORT`.

## Keeping this current

- Add or update an entry when a workflow, route, navigation label, or access rule changes. Link the pytest that fails if the behavior regresses.
- Prefer the path and the command or button name. Do not record CSS selectors.
- Leave request bodies and error matrices in the existing contract docs. This file should stay short enough to scan.
- If a browser suite is added later, link the spec from the entry. Do not generate a second inventory of DOM snapshots.
- Agents that change a workflow should report the route, the journey, the expected result, and the pytest they ran.
