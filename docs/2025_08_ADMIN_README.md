# Supervaizer Admin Interface

> **Created:** 2025-08-05
> **Updated:** 2026-09-25

A web UI mounted at `/manage` for inspecting Jobs and Cases, watching server and agent status, and exercising agents through a per-agent workbench. Built with FastAPI, Jinja templates, TinyDB, and HTMX/Alpine/Tailwind loaded from CDNs.

## Enabling

```python
from supervaizer import Agent, Server

server = Server(agents=[my_agent], admin_interface=True)  # default: True
server.launch()
```

At launch the server logs `Deploy admin interface @ <public_url>/manage`. The mount also requires an API key, which is always present: `SUPERVAIZER_API_KEY`, an auto-generated key, or `local-dev` in local mode.

## Access Model

The whole `/manage` router (HTTP and WebSocket) is gated by `require_tailscale`. No API key is involved.

- The client IP must be in the Tailscale CGNAT range `100.64.0.0/10`.
- In local mode (`supervaizer start --local`, which sets `SUPERVAIZER_LOCAL_MODE=true`) loopback addresses are also allowed.
- Behind a reverse proxy, `X-Forwarded-For` is trusted only when the direct peer is listed in `TRUSTED_PROXIES` (comma-separated CIDRs). Otherwise the peer address is used, so an untrusted proxy is denied.
- Denied requests return HTTP 403 and are logged at `WARNING` with IP, path, and reason.

`SUPERVAIZER_API_KEY` protects `/api/*` and `/a2a`, not `/manage`. `ADMIN_ALLOWED_IPS` and the old `/admin` prefix were removed in 0.15.0. See [2025_08_REST_API.md](2025_08_REST_API.md) for the full surface table.

## Pages

| URL | Purpose |
| --- | --- |
| `/manage/` | Dashboard: job and case counts by status, storage info, recent activity (last 5 jobs and cases) |
| `/manage/jobs` | Job list with filters (`status`, `agent_name`, `search`, `sort`, `limit`, `skip`), details modal, status update, delete |
| `/manage/cases` | Case list with filters (`status`, `job_id`, `search`, `sort`), cost per case, link to parent job |
| `/manage/server` | Server identity, registration state, public URL |
| `/manage/agents` | Registered agents and their methods |
| `/manage/agents/{slug}/workbench` | Workbench: start a job, follow cases and steps, answer HITL prompts, execute, cancel, or schedule steps, live console over WebSocket |
| `/manage/job-start-test` | Manual job-start form for testing |
| `/manage/console` | Live log console fed by `/manage/log-stream` (server-sent events) |

Job and case lists auto-refresh every 30 seconds. Jobs are created through the workbench or the API, not from the job list.

## Endpoints Under `/manage/api`

JSON:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/manage/api/stats` | Dashboard counters |
| GET | `/manage/api/server/status` | Server and registration status |
| POST | `/manage/api/server/register` | Trigger Studio registration |
| GET | `/manage/api/agents`, `/manage/api/agents/{slug}` | Agent details |
| POST | `/manage/api/jobs/{job_id}/status`, `/manage/api/cases/{case_id}/status` | Body `{"status": "<EntityStatus>"}` |
| DELETE | `/manage/api/jobs/{job_id}` | Delete a job and its cases |
| DELETE | `/manage/api/cases/{case_id}` | Delete a case |
| POST | `/manage/api/console/execute` | Run a console command |

HTML fragments for HTMX (not JSON): `GET /manage/api/jobs`, `/manage/api/jobs/{job_id}`, `/manage/api/cases`, `/manage/api/cases/{case_id}`, `/manage/api/recent-activity`.

Workbench routes live under `/manage/agents/{slug}/workbench/...` (start, stop, status, answer, execute, cancel, schedule, jobs, console). `/manage/test-log`, `/manage/test-loguru`, and `/manage/debug-queue` are development helpers.

## Storage

Jobs and Cases are `WorkflowEntity` objects stored through `StorageManager` in TinyDB tables `Job` and `Case`. Storage is in-memory unless `SUPERVAIZER_PERSISTENCE=true` (or `supervaizer start --persist`), in which case data is written under `DATA_STORAGE_PATH` (default `./data`). See [2025_08_PERSISTENCE.md](2025_08_PERSISTENCE.md).

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| 403 on `/manage` from your laptop | Client IP is not a Tailscale address and local mode is off |
| 403 behind a proxy | The proxy is not listed in `TRUSTED_PROXIES`, so the forwarded IP is ignored |
| 404 on `/manage` | `admin_interface=False` |
| Empty lists after restart | Persistence is off; set `SUPERVAIZER_PERSISTENCE=true` |

Quick local check: `supervaizer start --local`, then open `http://127.0.0.1:8000/manage/`.
