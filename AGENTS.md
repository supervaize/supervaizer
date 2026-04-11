# Agent Instructions

> CRITICAL: Read AGENTS.md first.

This project follows the organization's agentic toolkit standards.

## Usage

Reference specific personas when requesting work:
- "As a **backend-developer**, implement feature X"
- "As a **frontend-developer**, implement feature Y"
- "As a **tech-lead**, review my changes"

## Cross-Repo Compatibility (supervaizer <-> Studio)

- `server.register` is consumed by `supervaize-studio`; preserve backward compatibility for the payload structure unless both repos are updated together.
- `server.register.details.server_id` is the stable identity used by Studio for server upsert.
- `server.register.details.url` is expected to represent the controller `public_url` (reachable URL), not necessarily the local bind address.
- Agent registration payloads currently expose the controller agent identifier as `id`; coordinate with Studio if renaming/removing this field (Studio may also support legacy `agent_id`).
- If changing registration/event payload fields, update `supervaizer` tests and validate compatibility against Studio’s controller-event processing.

## Learned User Preferences

## Learned Workspace Facts

- `ADMIN_ALLOWED_IPS` restricts `/admin` when set (comma-separated IPs/CIDR); unset or empty allows all client IPs.
- In `9agents/agent_interviewer`, empty `MANAGE_ALLOWED_IPS` still requires `MANAGE_AUTH_TOKEN` when that env is set; supervaizer’s admin IP middleware has no equivalent token fallback when the allowlist is empty.
