# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Helper for integrating an existing Python agent with the Supervaizer controller."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer

DEFAULT_TIMEOUT = 30
SUPERVAIZE_ENV_VARS = (
    "SUPERVAIZE_API_KEY",
    "SUPERVAIZE_WORKSPACE_ID",
    "SUPERVAIZE_API_URL",
)
WORKSPACE_AUTH_ENV_VARS = (
    "SUPERVAIZER_WORKSPACE_AUTH_REQUIRED",
    "SUPERVAIZER_WORKSPACE_AUTH_ISSUER",
    "SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL",
    "SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY",
)
URL_ENV_HOSTNAMES = (
    "SUPERVAIZE_API_URL",
    "SUPERVAIZER_WORKSPACE_AUTH_ISSUER",
    "SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL",
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Integration helper for wiring an existing Python agent into the Supervaizer controller.",
)


def _print_json(data: dict[str, Any] | list[Any], pretty: bool = False) -> None:
    if pretty:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(json.dumps(data, separators=(",", ":"), sort_keys=True))


def _normalize_controller_url(url: str) -> str:
    return url.rstrip("/")


def _env_url_hostname(var_name: str) -> str | None:
    """Hostname from a URL env var, or None when unset. Never returns the full URL."""
    raw = os.getenv(var_name)
    if not raw or not str(raw).strip():
        return None
    parsed = urlparse(str(raw).strip())
    return parsed.hostname or "<unparsed>"


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


_URL_FIELD_NAMES = frozenset({"url", "request_url", "uri", "href"})


def _redact_url_string(value: str) -> str:
    host = urlparse(value).hostname
    return host or "<redacted>"


def _redact_urls_in_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key in _URL_FIELD_NAMES and isinstance(item, str):
                redacted[key] = _redact_url_string(item)
            elif key == "raw_text":
                redacted[key] = "<omitted>"
            else:
                redacted[key] = _redact_urls_in_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_urls_in_value(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("http://", "https://")):
            return _redact_url_string(stripped)
        if "://" in value:
            return "<omitted>"
    return value


def _redact_url_in_error_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize HTTP error payloads so probe output never echoes secrets from URLs."""
    sanitized = _redact_urls_in_value(payload)
    if not isinstance(sanitized, dict):
        return {"error": "<redacted>"}
    return sanitized


def _resolve_supervaizer_argv(project_dir: Path) -> list[str]:
    """Command prefix to run the SDK CLI from the agent project directory."""
    cli = shutil.which("supervaizer")
    if cli is not None:
        return [cli]
    for name in (".venv", ".venv-sv", "venv"):
        for base in (project_dir, Path.cwd()):
            candidate = base / name / "bin" / "supervaizer"
            if candidate.is_file():
                return [str(candidate)]
    uv = shutil.which("uv")
    if uv is not None:
        probe = subprocess.run(
            [uv, "run", "supervaizer", "--version"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            return [uv, "run", "supervaizer"]
    raise RuntimeError(
        "The `supervaizer` command was not found. Install the SDK in the project "
        "environment (activate the venv, set UV_PROJECT_ENVIRONMENT, or use `uv run "
        "supervaizer` from the project root), then retry scaffold-integration."
    )


def _read_json_file(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_text(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise ValueError(f"Refusing to overwrite existing file without --force: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_params(params_json: str | None, params_file: str | None) -> dict[str, Any]:
    if params_file:
        payload = _read_json_file(params_file)
    elif params_json:
        payload = json.loads(params_json)
    else:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("params payload must be a JSON object")
    return payload


def _controller_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def _http_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, Any]:
    raw = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url=url, data=raw, method=method.upper())
    for key, value in (headers or {}).items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            if not text.strip():
                return response.status, None
            try:
                return response.status, json.loads(text)
            except json.JSONDecodeError:
                return response.status, {"raw_text": text}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(text) if text else None
        except json.JSONDecodeError:
            payload = {"raw_text": text}
        raise RuntimeError(
            json.dumps({"status": exc.code, "url": url, "error": payload})
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(json.dumps({"url": url, "error": str(exc.reason)})) from exc


def _print_rpc_result(
    operation: str,
    endpoint: str,
    status: int,
    payload: dict[str, Any],
    response: Any,
    pretty: bool,
) -> None:
    """Print the call. A JSON-RPC error fails the command: the controller sends it with HTTP 200."""
    report = {
        "operation": operation,
        "endpoint": endpoint,
        "status_code": status,
        "json_rpc": payload,
        "response": response,
    }
    if isinstance(response, dict) and response.get("error") is not None:
        raise RuntimeError(json.dumps(report))
    _print_json({"ok": True, **report}, pretty=pretty)


def _handle(output_pretty: bool, fn: Any, *args: Any, **kwargs: Any) -> None:
    try:
        fn(*args, **kwargs)
    except json.JSONDecodeError as exc:
        _print_json(
            {
                "ok": False,
                "error": f"Invalid JSON input: {exc.msg}",
                "position": exc.pos,
            },
            pretty=output_pretty,
        )
        raise typer.Exit(code=2)
    except ValueError as exc:
        _print_json({"ok": False, "error": str(exc)}, pretty=output_pretty)
        raise typer.Exit(code=2)
    except RuntimeError as exc:
        try:
            payload = json.loads(str(exc))
        except json.JSONDecodeError:
            payload = {"error": str(exc)}
        _print_json({"ok": False, **payload}, pretty=output_pretty)
        raise typer.Exit(code=1)
    except Exception as exc:
        _print_json(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"}, pretty=output_pretty
        )
        raise typer.Exit(code=1)


def _spec_template() -> dict[str, Any]:
    """A blank design record. Each section holds the decisions of one interview topic."""
    return {
        "project": {
            "name": "my_agent_project",
            "output_dir": ".",
            "controller_filename": "supervaizer_control.py",
        },
        "agent": {
            "slug": "my-agent",
            "display_name": "My Agent",
            "description": "What the agent does, for Studio users.",
            "version": "0.1.0",
        },
        "mission": "The business goal that several jobs serve together.",
        "job": {
            "definition": "What one click starts, and what is finished when it is finished.",
            "started_by": ["person"],
            "continues_after_start": False,
            "needs_setup": False,
            "entrypoint": "my_agent.main.run_workflow",
        },
        "case": {
            "definition": "The item an operator counts: a contact, a document, a ticket.",
            "known_at_start": True,
            "independent": True,
            "title": "What names a case on one line.",
        },
        "steps": [
            {
                "id": "execute",
                "title": "The step name, in the operator's words",
                "can_fail": True,
                "costs_money": False,
                "output": None,
                "outside_effect": False,
                "needs_person": False,
            }
        ],
        "start_fields": [
            {"id": "goal", "label": "Goal", "type": "text", "required": True}
        ],
        "parameters": [],
        "cost": {"counted": [], "estimate_before_start": False},
        "human_in_the_loop": [],
        "guardrail_checkpoints": [],
        "resources": [],
        "configure": {"sections": [], "primary_action": None},
        "analytics": {"job": [], "mission": []},
        "artifact_types": [],
        "scheduled_start": False,
        "notes": {},
    }


def _load_and_validate_spec(spec_file: str | Path) -> dict[str, Any]:
    spec = _read_json_file(spec_file)
    if not isinstance(spec, dict):
        raise ValueError("Spec file must be a JSON object")
    for key in ["project", "agent", "job", "case", "steps"]:
        if key not in spec:
            raise ValueError(f"Spec file missing required top-level key: {key}")
    return spec


HELLO_WORLD = "https://github.com/runwaize/supervaize_hello_world/blob/main"
DOCS = "https://docs.runwaize.com/docs/supervaizer-controller"


def _spec_checklist(spec: dict[str, Any]) -> list[dict[str, str]]:
    """What to build for this spec, in build order, with the guide and the pattern of each part.

    This helper holds no code templates: the guides, the SDK scaffold and the
    Hello World example are the only sources of implementation patterns.
    """
    steps = spec.get("steps") or []
    cost = spec.get("cost") or {}
    configure = spec.get("configure") or {}
    analytics = spec.get("analytics") or {}
    topics = [
        (
            True,
            (
                f"Register {spec['agent'].get('slug')!r}, describe the start form, wire job.start to "
                f"{spec['job'].get('entrypoint')}, and return the job state for: {spec['job'].get('definition', '')}"
            ),
            "controller-setup",
            "agent_v2.py",
        ),
        (
            spec.get("parameters"),
            "Declare the parameters and secrets.",
            "parameters",
            "supervaizer_control.py",
        ),
        (
            cost.get("counted")
            or cost.get("estimate_before_start")
            or any(s.get("costs_money") for s in steps),
            "Report the cost of each step and the job total.",
            "cost-reporting",
            "agent_v2.py",
        ),
        (
            spec.get("human_in_the_loop") or any(s.get("needs_person") for s in steps),
            "Add the waiting steps, their form and the submit action.",
            "human-in-the-loop",
            "tests/test_hitl.py",
        ),
        (
            spec.get("guardrail_checkpoints")
            or any(s.get("outside_effect") for s in steps),
            "Add a rule checkpoint to each step with an outside effect.",
            "rule-checkpoints",
            "agent_rules.py",
        ),
        (
            spec.get("resources"),
            "Declare the shared resources and their operations.",
            "resources",
            "agent_data_resource.py",
        ),
        (
            configure.get("sections") or spec["job"].get("needs_setup"),
            "Build the Configure screen.",
            "job-configurator",
            "agent_configurator.py",
        ),
        (
            analytics.get("job") or analytics.get("mission"),
            "Build the analytics dashboards.",
            "job-analytics",
            "agent_dashboard.py",
        ),
    ]
    return [
        {"task": task, "guide": f"{DOCS}/{page}", "pattern": f"{HELLO_WORLD}/{pattern}"}
        for wanted, task, page, pattern in topics
        if wanted
    ]


def _scaffold_integration_impl(
    *,
    spec_file: str,
    output_dir: str | None,
    controller_filename: str | None,
    force: bool,
    pretty: bool,
) -> None:
    spec = _load_and_validate_spec(spec_file)
    project = spec.setdefault("project", {})
    controller_file = controller_filename or str(
        project.get("controller_filename") or "supervaizer_control.py"
    )
    out_dir = (
        Path(output_dir or str(project.get("output_dir") or ".")).expanduser().resolve()
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    controller_path = out_dir / controller_file
    scaffolded_by = "supervaizer scaffold"
    if controller_path.exists() and not force:
        scaffolded_by = "skipped (controller already exists; extend in place)"
    else:
        command = [
            *_resolve_supervaizer_argv(out_dir),
            "scaffold",
            "--output-path",
            controller_file,
            *(["--force"] if force else []),
        ]
        run = subprocess.run(
            command, cwd=out_dir, capture_output=True, text=True, check=False
        )
        if run.returncode != 0:
            raise RuntimeError(
                f"`supervaizer scaffold` failed: {(run.stdout + run.stderr).strip()}"
            )
    _print_json(
        {
            "ok": True,
            "operation": "scaffold-integration",
            "spec_file": str(Path(spec_file).resolve()),
            "output_dir": str(out_dir),
            "files": {"controller": str(controller_path)},
            "scaffolded_by": scaffolded_by,
            "checklist": _spec_checklist(spec),
        },
        pretty=pretty,
    )


def _function_score(name: str, has_loop: bool, returns_dict_like: bool) -> int:
    score = 0
    lname = name.lower()
    for token in ["main", "run", "process", "workflow", "start", "handle"]:
        if token in lname:
            score += 2
    if has_loop:
        score += 2
    if returns_dict_like:
        score += 1
    return score


def _analyze_file(path: Path, project_root: Path) -> list[dict[str, Any]]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    results: list[dict[str, Any]] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._record(node, is_async=False)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._record(node, is_async=True)
            self.generic_visit(node)

        def _record(
            self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
        ) -> None:
            params = [arg.arg for arg in node.args.args]
            if node.args.vararg:
                params.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                params.append(f"**{node.args.kwarg.arg}")
            loops = []
            has_loop = False
            returns_dict_like = False
            for child in ast.walk(node):
                if isinstance(child, ast.For):
                    has_loop = True
                    target = (
                        ast.unparse(child.target)
                        if hasattr(ast, "unparse")
                        else "<target>"
                    )
                    iter_expr = (
                        ast.unparse(child.iter)
                        if hasattr(ast, "unparse")
                        else "<iterable>"
                    )
                    loops.append({"target": target, "iter": iter_expr})
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                    returns_dict_like = True
            results.append({
                "file": str(path.relative_to(project_root)),
                "line": node.lineno,
                "function": node.name,
                "is_async": is_async,
                "params": params,
                "has_loop": has_loop,
                "loops": loops[:5],
                "returns_dict_like": returns_dict_like,
                "score": _function_score(node.name, has_loop, returns_dict_like),
                "doc": (ast.get_docstring(node) or "")[:240],
            })

    Visitor().visit(tree)
    return results


def _analyze_agent_impl(
    project_root: str, entry_file: str | None, max_files: int, pretty: bool
) -> None:
    root = Path(project_root).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"Project root does not exist: {root}")

    candidates: list[dict[str, Any]] = []
    scanned_files = 0
    excluded_dirs = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
    }

    if entry_file:
        entry_path = (
            (root / entry_file).resolve()
            if not Path(entry_file).is_absolute()
            else Path(entry_file)
        )
        if not entry_path.exists():
            raise ValueError(f"Entry file not found: {entry_path}")
        candidates.extend(_analyze_file(entry_path, root))
        scanned_files = 1
    else:
        for path in root.rglob("*.py"):
            if any(part in excluded_dirs for part in path.parts):
                continue
            candidates.extend(_analyze_file(path, root))
            scanned_files += 1
            if scanned_files >= max_files:
                break

    candidates.sort(
        key=lambda item: (
            -int(item.get("score", 0)),
            str(item.get("file")),
            int(item.get("line", 0)),
        )
    )

    top = candidates[:30]
    _print_json(
        {
            "ok": True,
            "operation": "analyze-agent",
            "project_root": str(root),
            "scanned_files": scanned_files,
            "candidate_functions": top,
            "analysis_hints": [
                "Pick the function that represents one business run (the Job).",
                "If that function loops over items, those items are strong Case candidates.",
                "The loop body stages usually become per-case Steps.",
            ],
        },
        pretty=pretty,
    )


def _discover_controller_impl(
    controller_url: str,
    controller_api_key: str | None,
    timeout_seconds: int,
    pretty: bool,
) -> None:
    base_url = _normalize_controller_url(controller_url)
    api_key = controller_api_key or os.getenv("CONTROLLER_AUTH_KEY")
    status, openapi = _http_json(
        "GET",
        f"{base_url}/openapi.json",
        headers=_controller_headers(api_key),
        timeout=timeout_seconds,
    )
    paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
    job_routes: list[dict[str, Any]] = []
    for path, methods in sorted(paths.items()):
        if not isinstance(methods, dict):
            continue
        for method, spec in sorted(methods.items()):
            if not isinstance(spec, dict):
                continue
            fingerprint = " ".join([
                path,
                method,
                str(spec.get("summary") or ""),
                str(spec.get("operationId") or ""),
                " ".join(spec.get("tags", []) or []),
            ]).lower()
            if "job" in fingerprint:
                job_routes.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": spec.get("summary"),
                    "operation_id": spec.get("operationId"),
                    "tags": spec.get("tags", []),
                })
    has_a2a = any(path == "/a2a" for path in paths)
    has_events = any(path == "/a2a/events" for path in paths)

    _print_json(
        {
            "ok": True,
            "operation": "discover-controller",
            "controller_url": base_url,
            "status_code": status,
            "a2a_json_rpc": has_a2a,
            "a2a_events": has_events,
            "job_routes": job_routes,
            "recommended_controller_endpoint": "/a2a" if has_a2a else None,
        },
        pretty=pretty,
    )


def _probe_jwks_url(timeout: int) -> dict[str, Any]:
    jwks_url = os.getenv("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL")
    if not jwks_url or not str(jwks_url).strip():
        return {"probed": False, "reason": "SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL unset"}
    url = str(jwks_url).strip()
    try:
        status, _ = _http_json("GET", url, timeout=timeout)
        return {
            "probed": True,
            "status_code": status,
            "ok": status == 200,
            "jwks_hostname": _env_url_hostname("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL"),
        }
    except RuntimeError as exc:
        try:
            payload = _redact_url_in_error_payload(json.loads(str(exc)))
        except json.JSONDecodeError:
            payload = {"error": "JWKS request failed"}
        return {
            "probed": True,
            "ok": False,
            "jwks_hostname": _env_url_hostname("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL"),
            **payload,
        }


def _env_status_impl(
    shell_template: bool, pretty: bool, probe_jwks: bool, jwks_timeout: int
) -> None:
    if shell_template:
        sys.stdout.write(
            'export SUPERVAIZE_API_KEY="..."\nexport SUPERVAIZE_WORKSPACE_ID="team_1"\nexport SUPERVAIZE_API_URL="https://app.supervaize.com"\n'
            'export SUPERVAIZER_WORKSPACE_AUTH_REQUIRED="true"\n'
            'export SUPERVAIZER_WORKSPACE_AUTH_ISSUER="https://studio.supervaize.com"\n'
            'export SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL="https://app.supervaize.com/w/team_1/api/v1/workspace-agent-grants/jwks/"\n\n'
            "# Optional local controller protection\n"
            'export CONTROLLER_AUTH_KEY="..."' + "\n"
        )
        return

    # Names only: no value of an environment variable is ever printed, in full or in part.
    missing = [name for name in SUPERVAIZE_ENV_VARS if not os.getenv(name)]
    auth_missing = [name for name in WORKSPACE_AUTH_ENV_VARS if not os.getenv(name)]
    has_public_key = bool(os.getenv("SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY"))
    workspace_auth_required = _env_bool("SUPERVAIZER_WORKSPACE_AUTH_REQUIRED")
    workspace_auth_ok = (
        workspace_auth_required
        and bool(os.getenv("SUPERVAIZER_WORKSPACE_AUTH_ISSUER"))
        and (has_public_key or bool(os.getenv("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL")))
    )
    report: dict[str, Any] = {
        "ok": len(missing) == 0 and workspace_auth_ok,
        "operation": "env-status",
        "required_env_vars": list(SUPERVAIZE_ENV_VARS),
        "present": [name for name in SUPERVAIZE_ENV_VARS if name not in missing],
        "missing": missing,
        "workspace_auth_env_vars": list(WORKSPACE_AUTH_ENV_VARS),
        "workspace_auth_present": [
            name for name in WORKSPACE_AUTH_ENV_VARS if name not in auth_missing
        ],
        "workspace_auth_missing": auth_missing,
        "workspace_auth_required_enabled": workspace_auth_required,
        "workspace_auth_configured": workspace_auth_ok,
        "url_hostnames": {
            name: _env_url_hostname(name)
            for name in URL_ENV_HOSTNAMES
            if _env_url_hostname(name)
        },
        "controller_auth_key_present": bool(
            os.getenv("CONTROLLER_AUTH_KEY")
            or os.getenv("SUPERVAIZE_CONTROLLER_AUTH_KEY")
            or os.getenv("SUPERVAIZER_CONTROLLER_AUTH_KEY")
        ),
    }
    if probe_jwks:
        if has_public_key and not os.getenv("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL"):
            report["jwks_probe"] = {
                "probed": False,
                "ok": True,
                "reason": "SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY configured",
            }
        else:
            jwks = _probe_jwks_url(jwks_timeout)
            report["jwks_probe"] = jwks
            if jwks.get("probed") and not jwks.get("ok", False):
                report["ok"] = False
    _print_json(report, pretty=pretty)


def _invoke_action_impl(
    controller_url: str,
    controller_api_key: str | None,
    agent_slug: str,
    action: str,
    surface: str,
    workspace_slug: str,
    mission_id: str,
    actor_id: str,
    correlation: dict[str, str | None],
    params_json: str | None,
    params_file: str | None,
    timeout_seconds: int,
    dry_run: bool,
    pretty: bool,
) -> None:
    base_url = _normalize_controller_url(controller_url)
    endpoint = f"{base_url}/a2a"
    api_key = (
        controller_api_key
        or os.getenv("CONTROLLER_AUTH_KEY")
        or os.getenv("SUPERVAIZE_CONTROLLER_AUTH_KEY")
        or os.getenv("SUPERVAIZER_CONTROLLER_AUTH_KEY")
    )
    params = _load_params(params_json=params_json, params_file=params_file)
    request_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "supervaizer/action.invoke",
        "params": {
            "request_id": request_id,
            "actor": {"user_id": actor_id},
            "workspace": {"id": workspace_slug, "slug": workspace_slug},
            "mission_id": mission_id,
            "agent_slug": agent_slug,
            "surface": surface,
            "action": action,
            "input": params,
            "idempotency_key": request_id,
            # An id that the caller did not give stays absent: a made-up job id
            # would test a mission-scoped action in the wrong context.
            **{key: value for key, value in correlation.items() if value},
        },
    }

    if dry_run:
        _print_json(
            {
                "ok": True,
                "operation": "invoke-action",
                "dry_run": True,
                "endpoint": endpoint,
                "headers": {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-API-Key": "***" if api_key else None,
                },
                "json_rpc": payload,
            },
            pretty=pretty,
        )
        return

    status, response = _http_json(
        "POST",
        endpoint,
        body=payload,
        headers=_controller_headers(api_key),
        timeout=timeout_seconds,
    )
    _print_rpc_result("invoke-action", endpoint, status, payload, response, pretty)


def _load_surface_impl(
    controller_url: str,
    controller_api_key: str | None,
    agent_slug: str,
    surface: str,
    workspace_slug: str,
    mission_id: str,
    actor_id: str,
    correlation: dict[str, str | None],
    input_json: str | None,
    input_file: str | None,
    timeout_seconds: int,
    pretty: bool,
) -> None:
    base_url = _normalize_controller_url(controller_url)
    endpoint = f"{base_url}/a2a"
    api_key = (
        controller_api_key
        or os.getenv("CONTROLLER_AUTH_KEY")
        or os.getenv("SUPERVAIZE_CONTROLLER_AUTH_KEY")
        or os.getenv("SUPERVAIZER_CONTROLLER_AUTH_KEY")
    )
    action_input = _load_params(params_json=input_json, params_file=input_file)
    request_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "supervaizer/surface.load",
        "params": {
            "request_id": request_id,
            "actor": {"user_id": actor_id},
            "workspace": {"id": workspace_slug, "slug": workspace_slug},
            "mission_id": mission_id,
            "agent_slug": agent_slug,
            "surface": surface,
            "input": action_input,
            **{key: value for key, value in correlation.items() if value},
        },
    }
    status, response = _http_json(
        "POST",
        endpoint,
        body=payload,
        headers=_controller_headers(api_key),
        timeout=timeout_seconds,
    )
    _print_rpc_result("load-surface", endpoint, status, payload, response, pretty)


@app.command("spec-template")
def spec_template(
    output_file: str | None = typer.Option(
        None, "--output-file", help="Write the template JSON to a file."
    ),
    force: bool = typer.Option(
        False, "--force", help="Replace an existing file. A filled spec is lost."
    ),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Print or write an integration spec template used for scaffolding."""

    def run() -> None:
        template = _spec_template()
        if output_file:
            _write_text(
                Path(output_file), json.dumps(template, indent=2) + "\n", force=force
            )
        _print_json(
            {
                "ok": True,
                "operation": "spec-template",
                "template": template,
                "output_file": output_file,
            },
            pretty=pretty,
        )

    _handle(pretty, run)


@app.command("analyze-agent")
def analyze_agent(
    project_root: str = typer.Option(
        ..., "--project-root", help="Path to the user's Python agent project."
    ),
    entry_file: str | None = typer.Option(
        None, "--entry-file", help="Optional file to analyze first/only."
    ),
    max_files: int = typer.Option(
        200, "--max-files", help="Max number of Python files to scan."
    ),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Heuristically scan a Python agent project to find likely Job entrypoints and Case loops."""
    _handle(
        pretty,
        _analyze_agent_impl,
        project_root=project_root,
        entry_file=entry_file,
        max_files=max_files,
        pretty=pretty,
    )


@app.command("scaffold-integration")
def scaffold_integration(
    spec_file: str = typer.Option(
        ..., "--spec-file", help="Path to integration spec JSON."
    ),
    output_dir: str | None = typer.Option(
        None, "--output-dir", help="Override output directory for generated files."
    ),
    controller_filename: str | None = typer.Option(
        None,
        "--controller-filename",
        help="Controller file name (default from spec, usually supervaizer_control.py).",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Run the SDK's `supervaizer scaffold`, then list what to build for the spec and where to copy it from."""
    _handle(
        pretty,
        _scaffold_integration_impl,
        spec_file=spec_file,
        output_dir=output_dir,
        controller_filename=controller_filename,
        force=force,
        pretty=pretty,
    )


@app.command("env-status")
def env_status(
    shell_template: bool = typer.Option(
        False,
        "--shell-template",
        help="Print shell export statements for required env vars.",
    ),
    probe_jwks: bool = typer.Option(
        False,
        "--probe-jwks",
        help="GET the JWKS URL from the environment (hostnames only in output; no secrets).",
    ),
    jwks_timeout: int = typer.Option(
        10, "--jwks-timeout", help="Seconds to wait for the JWKS probe."
    ),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Check SUPERVAIZE_* and workspace-auth env vars; optional JWKS reachability."""
    _handle(
        pretty,
        _env_status_impl,
        shell_template=shell_template,
        pretty=pretty,
        probe_jwks=probe_jwks,
        jwks_timeout=jwks_timeout,
    )


@app.command("discover-controller")
def discover_controller(
    controller_url: str = typer.Option(
        ..., "--controller-url", help="Base URL, e.g. http://127.0.0.1:8000"
    ),
    controller_api_key: str | None = typer.Option(
        None, "--controller-api-key", help="Optional controller auth key."
    ),
    timeout_seconds: int = typer.Option(
        DEFAULT_TIMEOUT, "--timeout-seconds", help="HTTP timeout in seconds."
    ),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Inspect a controller OpenAPI spec and report v2 A2A endpoints."""
    _handle(
        pretty,
        _discover_controller_impl,
        controller_url,
        controller_api_key,
        timeout_seconds,
        pretty,
    )


@app.command("load-surface")
def load_surface(
    controller_url: str = typer.Option(
        ..., "--controller-url", help="Base URL, e.g. http://127.0.0.1:8000"
    ),
    controller_api_key: str | None = typer.Option(
        None, "--controller-api-key", help="Controller auth key (optional)"
    ),
    agent_slug: str = typer.Option(
        ..., "--agent-slug", help="Agent slug in the v2 registration."
    ),
    surface: str = typer.Option(..., "--surface", help="Surface id, e.g. job.start."),
    workspace_slug: str = typer.Option(
        ..., "--workspace-slug", help="Studio workspace slug."
    ),
    mission_id: str = typer.Option(
        "local-mission", "--mission-id", help="Mission id for the surface context."
    ),
    actor_id: str = typer.Option(
        "local-user", "--actor-id", help="Actor id for the surface context."
    ),
    job_id: str | None = typer.Option(
        None, "--job-id", help="Job id, for a job-scoped surface such as job.analytics."
    ),
    case_id: str | None = typer.Option(None, "--case-id", help="Optional case id."),
    step_id: str | None = typer.Option(None, "--step-id", help="Optional step id."),
    draft_session_id: str | None = typer.Option(
        None, "--draft-session-id", help="Optional draft session id."
    ),
    input_json: str | None = typer.Option(
        None, "--input-json", help="JSON object string for surface input."
    ),
    input_file: str | None = typer.Option(
        None, "--input-file", help="Path to JSON file for surface input."
    ),
    timeout_seconds: int = typer.Option(
        DEFAULT_TIMEOUT, "--timeout-seconds", help="HTTP timeout in seconds."
    ),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Load a Supervaizer v2 A2UI surface through A2A JSON-RPC."""
    _handle(
        pretty,
        _load_surface_impl,
        controller_url,
        controller_api_key,
        agent_slug,
        surface,
        workspace_slug,
        mission_id,
        actor_id,
        {
            "job_id": job_id,
            "case_id": case_id,
            "step_id": step_id,
            "draft_session_id": draft_session_id,
        },
        input_json,
        input_file,
        timeout_seconds,
        pretty,
    )


@app.command("invoke-action")
def invoke_action(
    controller_url: str = typer.Option(
        ..., "--controller-url", help="Base URL, e.g. http://127.0.0.1:8000"
    ),
    controller_api_key: str | None = typer.Option(
        None, "--controller-api-key", help="Controller auth key (optional)"
    ),
    agent_slug: str = typer.Option(
        ..., "--agent-slug", help="Agent slug in the v2 registration."
    ),
    action: str = typer.Option(
        ..., "--action", help="V2 action id, e.g. job.start or resource.contacts.list."
    ),
    surface: str = typer.Option(
        "job.start",
        "--surface",
        help="Surface that owns the action (required in JSON-RPC params for action.invoke).",
    ),
    workspace_slug: str = typer.Option(
        ..., "--workspace-slug", help="Studio workspace slug."
    ),
    mission_id: str = typer.Option(
        "local-mission", "--mission-id", help="Mission id for the action context."
    ),
    actor_id: str = typer.Option(
        "local-user", "--actor-id", help="Actor id for the action context."
    ),
    job_id: str | None = typer.Option(None, "--job-id", help="Optional job id."),
    case_id: str | None = typer.Option(None, "--case-id", help="Optional case id."),
    step_id: str | None = typer.Option(None, "--step-id", help="Optional step id."),
    draft_session_id: str | None = typer.Option(
        None, "--draft-session-id", help="Optional draft session id."
    ),
    params_json: str | None = typer.Option(
        None, "--params-json", help="JSON object string for action input."
    ),
    params_file: str | None = typer.Option(
        None, "--params-file", help="Path to JSON file for action input."
    ),
    timeout_seconds: int = typer.Option(
        DEFAULT_TIMEOUT, "--timeout-seconds", help="HTTP timeout in seconds."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print JSON-RPC payload without sending."
    ),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Invoke a Supervaizer v2 action through A2A JSON-RPC."""
    _handle(
        pretty,
        _invoke_action_impl,
        controller_url,
        controller_api_key,
        agent_slug,
        action,
        surface,
        workspace_slug,
        mission_id,
        actor_id,
        {
            "job_id": job_id,
            "case_id": case_id,
            "step_id": step_id,
            "draft_session_id": draft_session_id,
        },
        params_json,
        params_file,
        timeout_seconds,
        dry_run,
        pretty,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
