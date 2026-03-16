# Design: `--local` Mode with User Agents + Hello World

## Problem

`supervaizer start --local` currently ignores `supervaizer_control.py` entirely and runs a separate code path with only the built-in Hello World agent. Users with existing agent setups cannot see their agents alongside Hello World in local mode.

## Goal

Make `--local` behave like normal mode (same script loading, same server startup) with two differences:

1. Skip Studio registration (no `supervisor_account` needed)
2. Inject the Hello World agent alongside user agents (controllable via env var)

## Design

### 1. `cli.py` — Unify the code paths

Remove the separate `if local:` branch. When `--local` is set:

- Set `SUPERVAIZER_LOCAL_MODE=true` as an environment variable
- Update `script_path` help text (remove "ignored when --local")
- If `script_path` is provided or `supervaizer_control.py` exists in CWD, fall through to the normal subprocess path
- If no script exists, use the fallback script from `local_server.py` instead
- Print local mode banner (no Studio registration message, API key info)

### 2. `Server` — Handle local mode during init/launch

In `Server.__init__`, check `SUPERVAIZER_LOCAL_MODE`:

- If `true`, force `supervisor_account=None` regardless of what was passed (log a warning if a non-None value was overridden)
- If `true` and `SUPERVAIZER_DISABLE_HELLO_WORLD` is not `true`, prepend the Hello World agent to the agents list (inside `__init__`, before route setup). Skip injection if an agent with the same slug already exists.
- Enable `admin_interface` and `a2a_endpoints` automatically in local mode
- Default `api_key` to `"local-dev"` in local mode (if not explicitly set or via `SUPERVAIZER_API_KEY`)

### 3. `local_server.py` — Becomes a fallback script

Repurpose `local_server.py` as a minimal runnable script that `cli.py` invokes when `--local` is used but no `supervaizer_control.py` exists. It creates a `Server` with an empty agents list and calls `launch()`. Hello World is injected by `Server.__init__`.

Keep `get_default_local_agent()` as the canonical factory for the Hello World agent — `Server` imports it from here.

### Edge Cases

| Scenario                                                       | Result                                                                     |
| -------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `--local`, no `supervaizer_control.py`                         | Hello World only (like today)                                              |
| `--local` + `supervaizer_control.py`                           | User agents + Hello World                                                  |
| `--local` + `SUPERVAIZER_DISABLE_HELLO_WORLD=true` + script    | User agents only                                                           |
| `--local` + `SUPERVAIZER_DISABLE_HELLO_WORLD=true` + no script | Warn and start empty server (admin UI still accessible)                    |
| `--local` + script with real `supervisor_account`              | Override to `None`, log warning that credentials are skipped in local mode |
| `--local` + user agent named "Hello World AI Agent"            | Skip Hello World injection (no duplicate)                                  |

### Files to Modify

1. `src/supervaizer/cli.py` — Remove separate local branch, set env var, unify paths, update help text
2. `src/supervaizer/server.py` — Add local mode detection, Hello World injection, skip registration, api_key default
3. `src/supervaizer/examples/local_server.py` — Simplify to fallback-only script, keep `get_default_local_agent()`

### What Doesn't Change

- `supervaizer_control.py` structure — works as-is
- Agent loading mechanism
- Route registration
- Admin workbench UI
