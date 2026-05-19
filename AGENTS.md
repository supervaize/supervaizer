# Supervaizer Agent Instructions

This is the canonical agent guide for the Supervaizer controller repo. Supervaizer is public, packaged, and used by external agent developers, so preserve API compatibility unless the user explicitly asks for a breaking change.

## Working Rules

- Prefer simple, typed Python changes that match existing FastAPI/Pydantic patterns.
- **No guessing / no implicit fallbacks:** when protocol versions, workspace identity, action/resource contracts, authentication, or transport configuration are missing or inconsistent, fail with a clear error that names the missing configuration. Do not infer another context, broaden scope, or silently fall back.
- Use `just` recipes from this repo for local commands.
- Use `uv` for Python environment and package operations.
- Add or update targeted tests for changed behavior.
- Keep public payloads and generated docs compatible with Studio unless both repos are updated together.
- Use GitButler (`but`) for branch, commit, and push operations when available.

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

- When preparing a merge to `main` or a release, keep `docs/CHANGELOG.md` **Unreleased** accurate; on request, align listed dependency or tooling changes with the delta since the previous git tag (including `pyproject.toml`).

## Learned Workspace Facts

- `supervaizer start --reload` (or `SUPERVAIZER_RELOAD=true`) enables Uvicorn’s `reload` (file watching, dev-only; leave off in production).
- If agent data-resource routes are mounted twice (e.g. both inside `create_agents_routes` and again from `Server` startup), OpenAPI sees duplicate routes and `operationId` uniqueness tests fail.
- Compliance for this repo expects explicit type annotations, including return types, on functions in new or modified Python files (including tests), for mypy-clean CI.
- `ADMIN_ALLOWED_IPS` restricts `/admin` when set (comma-separated IPs/CIDR); unset or empty allows all client IPs.
- In `9agents/agent_interviewer`, empty `MANAGE_ALLOWED_IPS` still requires `MANAGE_AUTH_TOKEN` when that env is set; supervaizer’s admin IP middleware has no equivalent token fallback when the allowlist is empty.
- CI (`python-package` workflow): the pre-commit job checks **Ruff** formatting (`ruff format --check`) and **YAML** in `.github/workflows` via `yamllint` (not Black).
- In the matrix **build** job, `astral-sh/setup-uv` sets `cache-suffix: py-${{ matrix.python-version }}` so parallel Python versions do not race on the same GitHub Actions cache reservation.
- `@singleton` (from `supervaizer.common`) replaces the decorated class name with a function at import time; modules that annotate with that class in unions (e.g. `StorageManager | None` in `storage.py`) need `from __future__ import annotations` or class-body evaluation raises `TypeError`.
- `UTC` lives on the `datetime` module (`from datetime import UTC`), not on `datetime.datetime`; use `datetime.now(UTC)`, not `datetime.now(datetime.UTC)` (the latter raises `AttributeError` at runtime).

## Security and Supply-Chain Rules

These rules are mandatory. Violating them defeats the repo's security controls.

### Branch and commit rules
- Never push directly to `main`. Always work on a branch and open a PR.
- Never force-push to a shared branch.
- Never bypass branch protection or rulesets, even with admin access.
- Always check `git status` before committing — never include `.env`, `*.key`, or credential files.

### Dependency rules
- Never edit `uv.lock` by hand.
- To add a dependency: use `uv add <pkg>`, not direct edits to `pyproject.toml`.
- Never run `uv lock --upgrade` without explicit user approval. Upgrading all deps at once is the exact vector for supply-chain malware.
- To upgrade a single package: `uv lock --upgrade-package <name>`.

### Workflow file rules
- Never modify files in `.github/workflows/` without explicit user approval.
- Never change `permissions:` blocks in workflows.
- Never add `pull_request_target` triggers.
- Never replace a pinned action SHA with a tag. New actions must be pinned to a commit SHA with the version in a comment.

### Secret rules
- Never echo, log, or print environment variables.
- Never read `.env`, `~/.aws/credentials`, `~/.ssh/`, or `~/.pypirc`.

### Publishing rules
- Never run `hatch publish` or any publish command locally. Publishing happens through CI only.
- Never create or modify the `pypi` GitHub environment.

### When in doubt
Ask. Refusing to act is always safer than taking an action that bypasses these rules.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **supervaizer** (6117 symbols, 11434 relationships, 278 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/supervaizer/context` | Codebase overview, check index freshness |
| `gitnexus://repo/supervaizer/clusters` | All functional areas |
| `gitnexus://repo/supervaizer/processes` | All execution flows |
| `gitnexus://repo/supervaizer/process/{name}` | Step-by-step execution trace |

## Cross-Repo Groups

This repository is listed under GitNexus **group(s): runwaize** (see `~/.gitnexus/groups/`). For cross-repo analysis, use MCP tools `impact`, `query`, and `context` with `repo` set to `@<groupName>` or `@<groupName>/<memberPath>` (paths match keys in that group’s `group.yaml`). Use `group_list` / `group_sync` for membership and sync. From the terminal: `npx gitnexus group list`, `npx gitnexus group sync <name>`, `npx gitnexus group impact <name> --target <symbol> --repo <group-path>`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
