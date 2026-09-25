# Supervaizer Agent Instructions

This is the canonical agent guide for the Supervaizer controller repo. Supervaizer is public, packaged, and used by external agent developers, so preserve API compatibility unless the user explicitly asks for a breaking change.

## Working Rules

- Use the shared [RUNWAIZE domain glossary](../glossary.md) as the canonical terminology reference.
- Prefer simple, typed Python changes that match existing FastAPI/Pydantic patterns.
- Do not import from inside functions, methods, or local scopes unless it is absolutely required to avoid a concrete circular import, optional dependency, or startup-cost problem. Prefer module-level imports by default, and document the reason when a local import is unavoidable.
- **No guessing / no implicit fallbacks:** when protocol versions, workspace identity, action/resource contracts, authentication, or transport configuration are missing or inconsistent, fail with a clear error that names the missing configuration. Do not infer another context, broaden scope, or silently fall back.
- Use `just` recipes from this repo for local commands.
- Use `uv` for Python environment and package operations.
- Add or update targeted tests for changed behavior.
- Keep public payloads and generated docs compatible with Studio unless both repos are updated together.
- Use GitButler (`but`) for branch, commit, and push operations when available.
- Personas (`backend-developer`, `tech-lead`, ...) are defined in `../.agent/personas/`; name one when requesting work.

## Documentation Map

| Need | Read |
| --- | --- |
| User-facing overview and quick start | `README.md` |
| Supervaizer v2 contract (Jobs, Cases, Steps, Resources, Surfaces, Actions) | `docs/2026_05_SUPERVAIZER_v2.md` |
| Protocol layering (A2A, A2UI, AG-UI) | `docs/2026_05_PROTOCOLS.md` |
| Workspace authorization (grants, signed tokens) | `docs/2026_05_WORKSPACE_AGENT_GRANTS.md` |
| CLI, deployment, local Docker testing | `docs/2025_08_CLI.md`, `docs/rfc/2025_10_001-cloud-deployment-cli.md`, `docs/2025_10_LOCAL_TESTING.md` |
| API surfaces and auth, admin UI, persistence, v1 parameter validation | `docs/2025_08_REST_API.md`, `docs/2025_08_ADMIN_README.md`, `docs/2025_08_PERSISTENCE.md`, `docs/2025_08_PARAMETER_VALIDATION.md` |
| Generated model and OpenAPI reference (`just generate-docs`) | `docs/model_reference/`, `docs/api/openapi.json` |
| Release history | `docs/CHANGELOG.md` |

Docs are prefixed `YYYY_MM_` with their creation month; `2025_*` files document v1-era subsystems that still exist, `2026_05_*` files define the v2 contract.

## Cross-Repo Compatibility (supervaizer <-> Studio)

- `server.register` is consumed by `supervaize-studio`; preserve backward compatibility for the payload structure unless both repos are updated together.
- `server.register.details.server_id` is the stable identity used by Studio for server upsert.
- `server.register.details.url` is expected to represent the controller `public_url` (reachable URL), not necessarily the local bind address.
- Agent registration payloads currently expose the controller agent identifier as `id`; coordinate with Studio if renaming/removing this field (Studio may also support legacy `agent_id`).
- If changing registration/event payload fields, update `supervaizer` tests and validate compatibility against Studio’s controller-event processing.

## Learned User Preferences

- When preparing a merge to `main` or a release, keep `docs/CHANGELOG.md` **Unreleased** accurate; on request, align listed dependency or tooling changes with the delta since the previous git tag (including `pyproject.toml`).
- Prefer `docs/CHANGELOG.md` `Unreleased` entries grouped into `Added` / `Changed` / `Fixed` (instead of custom feature headings).
- Dependabot PRs target `develop`, not `main` (`target-branch` in `.github/dependabot.yml`); feature branches and PRs target `develop` too. `main` only receives release PRs from `just ship`.

## Learned Workspace Facts

- `supervaizer start --reload` / `--debug` only set `SUPERVAIZER_RELOAD` / `SUPERVAIZER_DEBUG`; `Server` never reads them, and the CLI only overrides host, port, and public URL on the control script's `Server`. Uvicorn also rejects `reload=True` with an app object. Treat both flags as non-functional until fixed.
- Local mode cannot invoke v2 actions or surfaces over `/a2a`: without `SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=true` the controller answers `-32030 workspace_authorization_not_configured`, and token checks need `agent.server_agent_id`, which only Studio registration sets.
- `just install-hooks` sets `core.hooksPath=.githooks`, so the hooks that `pre-commit install` writes to `.git/hooks` never run; `just precommit` and CI are the real gates.
- A Studio-registered controller with A2A enabled fails at launch unless `SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=true`, `SUPERVAIZER_WORKSPACE_AUTH_ISSUER`, and `SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY` or `_JWKS_URL` are set (`studio_handshake.validate_studio_a2a_workspace_authorization`). `--local` is exempt.
- If agent data-resource routes are mounted twice (e.g. both inside `create_agents_routes` and again from `Server` startup), OpenAPI sees duplicate routes and `operationId` uniqueness tests fail.
- Compliance for this repo expects explicit type annotations, including return types, on functions in new or modified Python files (including tests), for mypy-clean CI.
- Route surfaces since 0.15.0: `/api/*` requires `X-API-Key`; `/a2a` needs write scope and `/a2a/events` read scope; `/manage/*` (admin UI + workbench) is gated by `require_tailscale` (client IP in `100.64.0.0/10`, or loopback when `SUPERVAIZER_LOCAL_MODE=true`) with no API key. `X-Forwarded-For` is honoured only when the peer is in `TRUSTED_PROXIES`. `ADMIN_ALLOWED_IPS` and `/admin` no longer exist.
- CI (`python-package` workflow): the pre-commit job checks **Ruff** formatting (`ruff format --check`) and **YAML** in `.github/workflows` via `yamllint` (not Black).
- In the matrix **build** job, `astral-sh/setup-uv` sets `cache-suffix: py-${{ matrix.python-version }}` so parallel Python versions do not race on the same GitHub Actions cache reservation.
- `@singleton` (from `supervaizer.common`) replaces the decorated class name with a function at import time; modules that annotate with that class in unions (e.g. `StorageManager | None` in `storage.py`) need `from __future__ import annotations` or class-body evaluation raises `TypeError`.
- `UTC` lives on the `datetime` module (`from datetime import UTC`), not on `datetime.datetime`; use `datetime.now(UTC)`, not `datetime.now(datetime.UTC)` (the latter raises `AttributeError` at runtime).
- `just ship` bumps version in CI after merge to `main`, not in the ship PR itself; the publish job waits on GitHub Environment `pypi` approval; bump lands as `chore(release): vX.Y.Z`. After that, `just ship-reconcile` merges `main` back into `develop`.
- Do not re-run a failed `publish-pypi` workflow after the bump commit is already on `main` — it would bump again. Pushing other commits to `main` also retriggers publish with the default minor bump.
- hatchling ≥1.32 emits Metadata-Version 2.5; `pypa/gh-action-pypi-publish` must be ≥v1.14.2, pinned to the peeled tag commit SHA (not the annotated-tag object SHA).

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

This project is indexed by GitNexus as **supervaizer** (4857 symbols, 9137 relationships, 286 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/supervaizer/context` | Codebase overview, check index freshness |
| `gitnexus://repo/supervaizer/clusters` | All functional areas |
| `gitnexus://repo/supervaizer/processes` | All execution flows |
| `gitnexus://repo/supervaizer/process/{name}` | Step-by-step execution trace |

## Cross-Repo Groups

This repository is listed under GitNexus **group(s): runwaize** (see `~/.gitnexus/groups/`). For cross-repo analysis, use MCP tools `impact`, `query`, and `context` with `repo` set to `@<groupName>` or `@<groupName>/<memberPath>` (paths match keys in that group’s `group.yaml`). Use `group_list` / `group_sync` for membership and sync. From the project root: `node .gitnexus/run.cjs group list`, `node .gitnexus/run.cjs group sync <name>`, `node .gitnexus/run.cjs group impact <name> --target <symbol> --repo <group-path>` (the `.gitnexus/run.cjs` path is repo-root-relative).

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
