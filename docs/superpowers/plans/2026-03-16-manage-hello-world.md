# Manage Hello World in Local Mode — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `supervaizer start --local` run user agents alongside the Hello World agent, with the ability to disable Hello World via env var.

**Architecture:** Unify the `--local` and normal CLI code paths. The CLI sets `SUPERVAIZER_LOCAL_MODE=true` and falls through to the normal subprocess flow. `Server.__init__` detects local mode, forces `supervisor_account=None`, injects Hello World, and defaults `api_key` to `"local-dev"`. Also deploy agent routes in local mode (currently only deployed when `supervisor_account` is set).

**Tech Stack:** Python, Typer (CLI), FastAPI (Server), pytest

**Spec:** `docs/superpowers/specs/2026-03-16-manage-hello-world-design.md`

---

## Chunk 1: Server local mode support

### Task 1: Server injects Hello World agent in local mode

**Files:**
- Modify: `src/supervaizer/server.py:306-460` (Server.__init__)
- Test: `tests/test_server.py`

- [ ] **Step 1: Write failing tests for local mode Hello World injection**

In `tests/test_server.py`, add:

```python
class TestServerLocalMode:
    """Tests for SUPERVAIZER_LOCAL_MODE behavior in Server.__init__."""

    def test_local_mode_injects_hello_world_agent(self, agent_fixture: Agent) -> None:
        """When SUPERVAIZER_LOCAL_MODE=true, Hello World agent is prepended."""
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        try:
            server = Server(
                agents=[agent_fixture],
                host="localhost",
                port=8002,
                environment="test",
                api_key="test-key",
            )
            assert len(server.agents) == 2
            assert server.agents[0].name == "Hello World AI Agent"
            assert server.agents[1].name == agent_fixture.name
        finally:
            del os.environ["SUPERVAIZER_LOCAL_MODE"]

    def test_local_mode_skips_hello_world_when_disabled(self, agent_fixture: Agent) -> None:
        """When SUPERVAIZER_DISABLE_HELLO_WORLD=true, Hello World is not injected."""
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        os.environ["SUPERVAIZER_DISABLE_HELLO_WORLD"] = "true"
        try:
            server = Server(
                agents=[agent_fixture],
                host="localhost",
                port=8002,
                environment="test",
                api_key="test-key",
            )
            assert len(server.agents) == 1
            assert server.agents[0].name == agent_fixture.name
        finally:
            del os.environ["SUPERVAIZER_LOCAL_MODE"]
            del os.environ["SUPERVAIZER_DISABLE_HELLO_WORLD"]

    def test_local_mode_skips_duplicate_hello_world(self) -> None:
        """If user already has an agent with Hello World slug, skip injection."""
        from supervaizer.examples.local_server import get_default_local_agent
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        try:
            hw_agent = get_default_local_agent()
            server = Server(
                agents=[hw_agent],
                host="localhost",
                port=8002,
                environment="test",
                api_key="test-key",
            )
            assert len(server.agents) == 1
        finally:
            del os.environ["SUPERVAIZER_LOCAL_MODE"]

    def test_local_mode_forces_supervisor_account_none(
        self, agent_fixture: Agent, account_fixture: Any
    ) -> None:
        """When local mode is on, supervisor_account is forced to None."""
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        try:
            server = Server(
                agents=[agent_fixture],
                supervisor_account=account_fixture,
                host="localhost",
                port=8002,
                environment="test",
                api_key="test-key",
            )
            assert server.supervisor_account is None
        finally:
            del os.environ["SUPERVAIZER_LOCAL_MODE"]

    def test_local_mode_defaults_api_key_to_local_dev(self, agent_fixture: Agent) -> None:
        """In local mode without explicit api_key, default to 'local-dev'."""
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        # Clear any existing API key env var
        old_key = os.environ.pop("SUPERVAIZER_API_KEY", None)
        try:
            server = Server(
                agents=[agent_fixture],
                host="localhost",
                port=8002,
                environment="test",
                api_key=None,
            )
            assert server.api_key == "local-dev"
        finally:
            del os.environ["SUPERVAIZER_LOCAL_MODE"]
            if old_key is not None:
                os.environ["SUPERVAIZER_API_KEY"] = old_key

    def test_local_mode_deploys_agent_routes(self, agent_fixture: Agent) -> None:
        """In local mode, agent routes are deployed even without supervisor_account."""
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        try:
            server = Server(
                agents=[agent_fixture],
                host="localhost",
                port=8002,
                environment="test",
                api_key="test-key",
            )
            # Verify agent endpoints are reachable via TestClient
            client = TestClient(server.app)
            response = client.get(f"/supervaizer{agent_fixture.path}/")
            assert response.status_code != 404
        finally:
            del os.environ["SUPERVAIZER_LOCAL_MODE"]

    def test_local_mode_empty_server_still_starts(self) -> None:
        """Local mode with Hello World disabled and no agents starts an empty server."""
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        os.environ["SUPERVAIZER_DISABLE_HELLO_WORLD"] = "true"
        try:
            server = Server(
                agents=[],
                host="localhost",
                port=8002,
                environment="test",
                api_key="test-key",
            )
            assert len(server.agents) == 0
            # Admin UI should still be accessible
            client = TestClient(server.app)
            response = client.get("/admin/", headers={"X-API-Key": "test-key"})
            assert response.status_code != 404
        finally:
            del os.environ["SUPERVAIZER_LOCAL_MODE"]
            del os.environ["SUPERVAIZER_DISABLE_HELLO_WORLD"]

    def test_non_local_mode_unchanged(self, agent_fixture: Agent) -> None:
        """Without local mode, Server behaves as before (no Hello World injection)."""
        os.environ.pop("SUPERVAIZER_LOCAL_MODE", None)
        server = Server(
            agents=[agent_fixture],
            host="localhost",
            port=8002,
            environment="test",
            api_key="test-key",
        )
        assert len(server.agents) == 1
        assert server.agents[0].name == agent_fixture.name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_server.py::TestServerLocalMode -v`
Expected: FAIL (class doesn't exist yet, tests reference new behavior)

- [ ] **Step 3: Implement local mode in Server.__init__**

In `src/supervaizer/server.py`, at the top of `Server.__init__` (after the method signature, before mac_addr logic), add:

```python
# Local mode: skip Studio, inject Hello World, default api_key
local_mode = os.environ.get("SUPERVAIZER_LOCAL_MODE", "").lower() == "true"
if local_mode:
    if supervisor_account is not None:
        log.warning(
            "[Server] Local mode active — ignoring supervisor_account (no Studio registration)"
        )
    supervisor_account = None
    a2a_endpoints = True
    admin_interface = True
    if api_key is None:
        api_key = "local-dev"

    # Inject Hello World agent unless disabled or duplicate
    if os.environ.get("SUPERVAIZER_DISABLE_HELLO_WORLD", "").lower() != "true":
        from supervaizer.examples.local_server import get_default_local_agent
        hw_agent = get_default_local_agent()
        existing_slugs = {a.slug for a in agents}
        if hw_agent.slug not in existing_slugs:
            agents = [hw_agent] + list(agents)
    elif not agents:
        log.warning(
            "[Server] Local mode with Hello World disabled and no agents — server will be empty"
        )
```

Then in the route setup section (around line 440), change:

```python
# Before:
if self.supervisor_account:
    log.info(...)
    self.app.include_router(create_default_routes(self))
    self.app.include_router(create_utils_routes(self))
    self.app.include_router(create_agents_routes(self))
    self.a2a_endpoints = True

# After:
if self.supervisor_account or local_mode:
    log.info(
        "[Server launch] 🚀 Deploy Supervaizer routes"
        + (" (local mode)" if local_mode else " - also activates A2A routes")
    )
    self.app.include_router(create_default_routes(self))
    self.app.include_router(create_utils_routes(self))
    self.app.include_router(create_agents_routes(self))
    self.a2a_endpoints = True
```

Note: `local_mode` needs to be accessible in the route setup section. Since it's defined at the top of `__init__`, it's already in scope.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_server.py::TestServerLocalMode -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_server.py -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
but commit -m "feat: add local mode support to Server (Hello World injection, skip registration)"
```

---

## Chunk 2: CLI unification

### Task 2: Unify CLI --local with normal subprocess path

**Files:**
- Modify: `src/supervaizer/cli.py:108-217`
- Modify: `src/supervaizer/examples/local_server.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for unified CLI --local**

In `tests/test_cli.py`, add to `TestCLIStart`:

```python
def test_start_local_sets_env_and_runs_script(
    self, runner: CliRunner, temp_script: str
) -> None:
    """--local sets SUPERVAIZER_LOCAL_MODE and runs the script normally."""
    with patch("subprocess.Popen") as mock_popen:
        mock_process = Mock()
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        result = runner.invoke(app, ["start", "--local", temp_script])
        assert "local test mode" in result.stdout
        mock_popen.assert_called_once()
        # The env var should be set for the subprocess
        assert os.environ.get("SUPERVAIZER_LOCAL_MODE") == "true"

def test_start_local_without_script_uses_fallback(self, runner: CliRunner) -> None:
    """--local without script_path and no supervaizer_control.py uses fallback."""
    with patch("subprocess.Popen") as mock_popen:
        mock_process = Mock()
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        # Run from a temp dir where no supervaizer_control.py exists
        with patch("supervaizer.cli.os.path.exists", return_value=False):
            result = runner.invoke(app, ["start", "--local"])
            assert "local test mode" in result.stdout
            mock_popen.assert_called_once()
            # Should use the fallback script path
            call_args = mock_popen.call_args[0][0]
            assert "local_server.py" in call_args[1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_cli.py::TestCLIStart::test_start_local_sets_env_and_runs_script tests/test_cli.py::TestCLIStart::test_start_local_without_script_uses_fallback -v`
Expected: FAIL

- [ ] **Step 3: Simplify local_server.py to a runnable fallback script**

Rewrite `src/supervaizer/examples/local_server.py`:

```python
"""Local test server fallback: used by `supervaizer start --local` when no supervaizer_control.py exists.

Also exports get_default_local_agent() for Server to import when injecting Hello World.
"""

import os
import shortuuid
from typing import Optional

from supervaizer import (
    Agent,
    AgentMethod,
    AgentMethods,
    ParametersSetup,
    Parameter,
    Server,
)
from supervaizer.agent import AgentMethodField


def get_default_local_agent() -> Agent:
    """Default Hello World agent for local test mode (mirrors supervaize_hello_world)."""
    # ... keep existing implementation exactly as-is ...


if __name__ == "__main__":
    """Fallback entry point: starts a server with no user agents.
    Hello World is injected by Server.__init__ when SUPERVAIZER_LOCAL_MODE=true.
    """
    server = Server(
        agents=[],
        supervisor_account=None,
        a2a_endpoints=True,
        admin_interface=True,
        host=os.environ.get("SUPERVAIZER_HOST") or "0.0.0.0",
        port=int(os.environ.get("SUPERVAIZER_PORT") or "8000"),
        public_url=os.environ.get("SUPERVAIZER_PUBLIC_URL"),
        debug=os.environ.get("SUPERVAIZER_DEBUG", "False").lower() == "true",
        reload=os.environ.get("SUPERVAIZER_RELOAD", "False").lower() == "true",
        environment=os.environ.get("SUPERVAIZER_ENVIRONMENT", "dev"),
        # api_key defaults to "local-dev" in Server.__init__ when SUPERVAIZER_LOCAL_MODE=true
    )
    log_level = os.environ.get("SUPERVAIZER_LOG_LEVEL", "INFO")
    server.launch(log_level=log_level)
```

Remove `create_local_server()` — it's no longer needed.

- [ ] **Step 4: Rewrite the CLI start command**

In `src/supervaizer/cli.py`, replace lines 164-217 (the `if local:` branch and the normal branch) with a unified flow:

```python
    if local:
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        console.print(
            f"[bold green]Starting Supervaizer Controller v{VERSION}[/] (local test mode)"
        )
        console.print(
            "[dim]No Studio registration — agents run locally[/]"
        )
        api_key = os.environ.get("SUPERVAIZER_API_KEY") or "local-dev"
        base = public_url or f"http://{host}:{port}"
        console.print(
            f"[bold]API:[/] {base}/docs  [bold]Admin/Workbench:[/] {base}/admin/"
        )
        console.print(
            f"[dim]API key for /admin: {api_key}[/]"
        )

    if script_path is None:
        script_path = (
            os.environ.get("SUPERVAIZER_SCRIPT_PATH") or "supervaizer_control.py"
        )

    if not os.path.exists(script_path):
        if local:
            # Use fallback script (Hello World only)
            import supervaizer.examples.local_server as fallback_module
            script_path = fallback_module.__file__
        else:
            console.print(f"[bold red]Error:[/] {script_path} not found")
            console.print("Run [bold]supervaizer scaffold[/] to create a default script")
            sys.exit(1)

    if not local:
        console.print(f"[bold green]Starting Supervaizer Controller v{VERSION}[/]")
    console.print(f"Loading configuration from [bold]{script_path}[/]")

    # Execute the script in a new Python process with proper signal handling
    def signal_handler(signum: int, frame: Any) -> None:
        if "process" in globals():
            globals()["process"].terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    process = subprocess.Popen([sys.executable, script_path])
    globals()["process"] = process
    process.wait()
```

Also update the `script_path` help text:
```python
    script_path: Optional[str] = typer.Argument(
        None,
        help="Path to the supervaizer_control.py script",
    ),
```

And update `--local` help text:
```python
    local: bool = typer.Option(
        False,
        "--local",
        help="Local test mode: run without Studio credentials, with built-in Hello World agent",
    ),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest tests/test_cli.py -v`
Expected: All tests PASS (new and existing)

- [ ] **Step 6: Run full test suite**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Run pre-commit checks**

Run: `cd /Volumes/SSDext1TB/Documents/GitRepo/RUNWAIZE/supervaizer && just precommit`
Expected: All checks pass (ruff, mypy, etc.)

- [ ] **Step 8: Commit**

```bash
but commit -m "feat: unify --local CLI path with normal subprocess flow"
```

---

## Chunk 3: Verification

### Task 3: Manual smoke test

- [ ] **Step 1: Test --local without supervaizer_control.py**

Run from a directory without `supervaizer_control.py`:
```bash
cd /tmp && uv run supervaizer start --local
```
Expected: Server starts with Hello World agent. Admin at `/admin/` shows Hello World.

- [ ] **Step 2: Test --local with supervaizer_control.py**

Run from the supervaize_hello_world example directory (or any dir with a `supervaizer_control.py`):
```bash
supervaizer start --local
```
Expected: Server starts with user agents + Hello World. Both visible in admin.

- [ ] **Step 3: Test SUPERVAIZER_DISABLE_HELLO_WORLD**

```bash
SUPERVAIZER_DISABLE_HELLO_WORLD=true supervaizer start --local
```
Expected: Server starts with user agents only, no Hello World.

- [ ] **Step 4: Test normal mode (no --local) is unchanged**

```bash
supervaizer start
```
Expected: Behaves exactly as before (subprocess, Studio registration, no Hello World injection).
