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
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import typer

DEFAULT_TIMEOUT = 30
SUPERVAIZE_ENV_VARS = (
    "SUPERVAIZE_API_KEY",
    "SUPERVAIZE_WORKSPACE_ID",
    "SUPERVAIZE_API_URL",
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


def _mask_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _normalize_controller_url(url: str) -> str:
    return url.rstrip("/")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "value"


def _v2_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "agent"


def _module_from_filename(filename: str) -> str:
    return Path(filename).stem


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


def _questions_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "operation": "questions",
        "goal": "Design the Supervaizer v2 Job, Case, Step, Resource, Surface, and Action contract before writing controller code.",
        "questions": [
            {
                "id": "agent_entrypoint",
                "category": "Target Function",
                "question": "What Python function should the v2 `job.start` action call (module path + function)?",
                "why": "This becomes the target call inside the generated `agent_impl.py` action handler.",
            },
            {
                "id": "job_definition",
                "category": "Job Mapping",
                "question": "What does one invocation represent in business terms (the Job)?",
                "why": "The Job should match a committed user-visible unit of work in Studio.",
            },
            {
                "id": "case_definition",
                "category": "Case Mapping",
                "question": "Does one job process multiple items? If yes, what is the per-item unit (email, phone number, document, lead, etc.)?",
                "why": "Each repeated item is usually one Case.",
            },
            {
                "id": "case_source_field",
                "category": "Case Mapping",
                "question": "Which input field contains the case items (e.g., `emails`, `phone_numbers`) and how is it encoded (CSV/list/single)?",
                "why": "Used to build the case loop in `agent_impl.py`.",
            },
            {
                "id": "lane_list",
                "category": "Case Mapping",
                "question": "Which lanes should Studio render for these Cases? Use `work` by default; add `setup` or `deliverable` only when useful.",
                "why": "Case.lane is a rendering hint, not an ontology.",
            },
            {
                "id": "step_list",
                "category": "Flow Mapping",
                "question": "What are the ordered steps inside each case (fetch, parse, classify, generate, send, review, etc.)?",
                "why": "These become v2 Step snapshots with activity/status/awaiting/outputs.",
            },
            {
                "id": "human_in_the_loop",
                "category": "Flow Mapping",
                "question": "Where do humans approve/review/answer? Which steps are HITL?",
                "why": "HITL is represented as a Step with `status=awaiting` and an `awaiting` form submitted through `step.awaiting.submit`.",
            },
            {
                "id": "start_fields",
                "category": "A2UI Surface",
                "question": "Which user-provided inputs should appear in the `job.start` A2UI form?",
                "why": "These become the document returned by `supervaizer/surface.load` for `job.start`.",
            },
            {
                "id": "agent_parameters",
                "category": "Secrets / Env",
                "question": "Which environment variables/secrets should be requested as agent parameters (API keys, credentials, endpoints)?",
                "why": "These become explicit controller requirements or optional Agent parameters; missing required values should fail clearly.",
            },
            {
                "id": "resources",
                "category": "Resources",
                "question": "What agent-owned resources should Studio manage, and which operations are allowed?",
                "why": "Resources become v2 declarations plus `resource.<id>.<operation>` typed actions.",
            },
            {
                "id": "datasets_artifacts",
                "category": "Outputs",
                "question": "Which datasets, Vega-Lite dashboards, and artifacts should Studio render?",
                "why": "Agent-owned vocabulary belongs in dataset and artifact declarations, not protocol enums.",
            },
            {
                "id": "sync_source",
                "category": "Sync",
                "question": "How should `job.sync` converge Studio state with the agent when status has drifted or a job was created for an existing external run?",
                "why": "`job.sync` is the v2 status convergence mechanism.",
            },
        ],
    }


def _spec_template() -> dict[str, Any]:
    return {
        "project": {
            "name": "my_agent_project",
            "output_dir": ".",
            "controller_filename": "supervaizer_control.py",
            "workflow_filename": "agent_impl.py",
        },
        "integration": {
            "agent_slug": "my-agent",
            "agent_display_name": "My Agent",
            "agent_description": "Describe the agent's purpose for Supervaize users.",
            "agent_version": "0.1.0",
            "a2ui_catalog_version": "my-agent-ui.1",
            "workflow_wrapper_function": "process_my_agent_workflow",
            "job_start_title": "Start My Agent",
        },
        "target_agent": {
            "module": "my_agent.main",
            "function": "run_workflow",
            "kwargs_from_fields": ["input_text"],
            "case_item_param": None,
        },
        "job_mapping": {
            "job_definition": "One execution processes a user request end-to-end.",
            "case_strategy": "single_case",
            "case_collection_field": None,
            "case_items_format": "single",
            "case_item_label": "item",
            "case_name_prefix": "Case",
            "case_description_template": "Process one case item",
        },
        "lanes": [{"id": "work", "label": "Work", "default": True}],
        "steps": [
            {
                "id": "prepare",
                "name": "Prepare Inputs",
                "description": "Validate and normalize inputs.",
                "activity": "operation",
                "status": "completed",
            },
            {
                "id": "execute",
                "name": "Run Agent Logic",
                "description": "Call the existing Python agent function.",
                "activity": "operation",
                "status": "completed",
            },
            {
                "id": "finalize",
                "name": "Finalize Result",
                "description": "Prepare final payload and close the case.",
                "activity": "operation",
                "status": "completed",
                "outputs": [{"id": "result", "type": "result", "title": "Result"}],
            },
        ],
        "start_fields": [
            {
                "id": "input_text",
                "label": "Input text",
                "type": "string",
                "required": True,
                "description": "Primary user input",
            }
        ],
        "resources": [
            {
                "id": "items",
                "label": "Items",
                "auto_surface": True,
                "scope": "workspace",
                "requires_context": ["workspace.slug"],
                "operations": ["list"],
                "fields": [
                    {"id": "id", "label": "ID", "type": "string", "required": True},
                    {"id": "name", "label": "Name", "type": "string", "required": True},
                ],
            }
        ],
        "datasets": [],
        "artifact_types": [{"type": "result", "label": "Result"}],
        "agent_parameters": [
            {
                "name": "EXAMPLE_API_KEY",
                "description": "API key used by the agent",
                "is_environment": True,
                "is_secret": True,
            }
        ],
        "supervaize_env": {
            "workspace_id_env": "SUPERVAIZE_WORKSPACE_ID",
            "api_key_env": "SUPERVAIZE_API_KEY",
            "api_url_env": "SUPERVAIZE_API_URL",
        },
        "notes": {
            "job_case_step_mapping": "Replace with your concrete v2 mapping before scaffolding.",
            "hitl_steps": [],
        },
    }


def _parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _wizard_impl(output_file: str, pretty: bool) -> None:
    typer.echo(
        "Supervaizer v2 Integration Wizard (existing Python agent -> A2A/A2UI controller)"
    )
    project_name = typer.prompt("Project name", default="my_agent_project")
    agent_slug = _v2_slug(
        typer.prompt("Agent slug (Studio/A2A slug)", default="my-agent")
    )
    agent_display_name = typer.prompt(
        "Agent display name", default=agent_slug.replace("_", " ").title()
    )
    agent_description = typer.prompt(
        "Agent description", default="Existing Python agent integrated with Supervaizer"
    )
    agent_version = typer.prompt("Agent version", default="0.1.0")
    a2ui_catalog_version = typer.prompt(
        "A2UI catalog version", default=f"{agent_slug}-ui.1"
    )

    target_module = typer.prompt(
        "Target agent module (dotted path)", default=f"{agent_slug}.main"
    )
    target_function = typer.prompt("Target agent function name", default="run_workflow")
    kwargs_from_fields_csv = typer.prompt(
        "Target function kwargs sourced from job fields (comma-separated)",
        default="input_text",
    )

    job_definition = typer.prompt(
        "What is one Job (business meaning)?",
        default="One end-to-end agent execution",
    )
    case_strategy = typer.prompt(
        "Case strategy (single_case/per_item)",
        default="single_case",
    ).strip()
    case_collection_field = None
    case_items_format = "single"
    case_item_label = "item"
    case_item_param = None
    if case_strategy == "per_item":
        case_collection_field = typer.prompt(
            "Field containing case items", default="items"
        )
        case_items_format = typer.prompt(
            "Case items format (csv/list/single)", default="csv"
        )
        case_item_label = typer.prompt("Per-case item label", default="item")
        case_item_param = (
            typer.prompt(
                "Target function kwarg name for the current case item (blank to skip)",
                default=case_item_label,
            ).strip()
            or None
        )

    steps_csv = typer.prompt(
        "Ordered per-case steps (comma-separated)",
        default="prepare,execute,finalize",
    )
    start_fields_csv = typer.prompt(
        "Job start form fields (comma-separated, default all string required)",
        default=kwargs_from_fields_csv,
    )
    agent_params_csv = typer.prompt(
        "Agent parameter env vars/secrets (comma-separated, blank if none)",
        default="",
        show_default=False,
    )

    steps: list[dict[str, Any]] = []
    step_names = _parse_csv_list(steps_csv)
    for idx, step in enumerate(step_names):
        step_id = _slug(step)
        steps.append({
            "id": step_id,
            "name": step.replace("_", " ").title(),
            "description": f"{step.replace('_', ' ').title()} step",
            "activity": "operation",
            "status": "completed",
            "outputs": [
                {"id": f"{step_id}_output", "type": "result", "title": "Result"}
            ]
            if idx == len(step_names) - 1
            else [],
        })

    start_fields = [
        {
            "id": field,
            "label": field.replace("_", " ").title(),
            "type": "string",
            "required": True,
            "description": f"Input field: {field}",
        }
        for field in _parse_csv_list(start_fields_csv)
    ]

    agent_parameters = [
        {
            "name": name,
            "description": f"{name} environment variable",
            "is_environment": True,
            "is_secret": bool(name.endswith("KEY") or "PASSWORD" in name),
        }
        for name in _parse_csv_list(agent_params_csv)
    ]

    spec = _spec_template()
    spec["project"]["name"] = project_name
    spec["integration"].update({
        "agent_slug": agent_slug,
        "agent_display_name": agent_display_name,
        "agent_description": agent_description,
        "agent_version": agent_version,
        "a2ui_catalog_version": a2ui_catalog_version,
        "workflow_wrapper_function": f"process_{_slug(agent_slug)}_workflow",
        "job_start_title": f"Start {agent_display_name}",
    })
    spec["target_agent"].update({
        "module": target_module,
        "function": target_function,
        "kwargs_from_fields": _parse_csv_list(kwargs_from_fields_csv),
        "case_item_param": case_item_param,
    })
    spec["job_mapping"].update({
        "job_definition": job_definition,
        "case_strategy": case_strategy,
        "case_collection_field": case_collection_field,
        "case_items_format": case_items_format,
        "case_item_label": case_item_label,
        "case_name_prefix": case_item_label.replace("_", " ").title(),
        "case_description_template": f"Process one {case_item_label}",
    })
    spec["steps"] = steps
    spec["start_fields"] = start_fields
    spec["agent_parameters"] = agent_parameters
    spec["notes"]["job_case_step_mapping"] = (
        "Review this mapping carefully. Confirm the Job, each Case boundary, and the exact ordered Steps before scaffolding."
    )

    out_path = Path(output_file)
    _write_text(out_path, json.dumps(spec, indent=2) + "\n", force=True)
    _print_json(
        {
            "ok": True,
            "operation": "wizard",
            "spec_file": str(out_path),
            "next_steps": [
                "Review and edit the generated spec (especially job_mapping, steps, start_fields, and agent_parameters).",
                "Run analyze-agent on the target project if you need help choosing the target function.",
                "Run scaffold-integration with this spec to generate a v2 supervaizer_control.py and agent_impl.py.",
            ],
            "spec": spec if pretty else None,
        },
        pretty=pretty,
    )


def _load_and_validate_spec(spec_file: str | Path) -> dict[str, Any]:
    spec = _read_json_file(spec_file)
    if not isinstance(spec, dict):
        raise ValueError("Spec file must be a JSON object")
    for key in ["project", "integration", "target_agent", "job_mapping"]:
        if key not in spec:
            raise ValueError(f"Spec file missing required top-level key: {key}")
    return spec


V2_GUIDE = (
    "https://github.com/supervaize/supervaizer/blob/main/docs/2026_05_SUPERVAIZER_v2.md"
)
HELLO_WORLD = "https://github.com/runwaize/supervaize_hello_world/blob/main"
DOCS = "https://docs.runwaize.com/docs/supervaizer-controller"


def _spec_checklist(spec: dict[str, Any]) -> list[dict[str, str]]:
    """What to build for this spec, and the reference to copy each part from.

    This helper holds no code templates: the SDK scaffold, the SDK docs and the
    Hello World example are the only sources of implementation patterns.
    """
    integration = spec["integration"]
    target = spec["target_agent"]
    items = [
        {
            "task": f"Set the registration: slug {integration.get('agent_slug')!r}, display name, catalog version, lanes.",
            "reference": f"{V2_GUIDE}#registration",
        },
        {
            "task": f"Wire job.start to {target.get('module')}.{target.get('function')} and return the job state "
            f"for this mapping: {spec['job_mapping'].get('job_definition', '')}",
            "reference": f"{HELLO_WORLD}/agent_v2.py",
        },
        {
            "task": "Implement job.sync and job.stop; make job.start safe to retry.",
            "reference": f"{V2_GUIDE}#idempotency",
        },
        {
            "task": "Declare action metadata (read-only actions, scopes).",
            "reference": f"{V2_GUIDE}#action-metadata",
        },
    ]
    optional = [
        (
            spec.get("notes", {}).get("hitl_steps")
            or any(s.get("status") == "awaiting" for s in spec.get("steps", [])),
            "Add the awaiting steps, their surface and the submit action.",
            f"{HELLO_WORLD}/tests/test_hitl.py",
        ),
        (
            spec.get("resources"),
            "Declare the resources and implement their operations.",
            f"{HELLO_WORLD}/agent_data_resource.py",
        ),
        (
            spec.get("datasets"),
            "Declare the datasets and build the dashboards.",
            f"{DOCS}/job-analytics",
        ),
        (
            spec.get("artifact_types"),
            "Declare the artifact types and the step outputs.",
            f"{HELLO_WORLD}/agent_deliverable.py",
        ),
        (
            integration.get("scheduled_start"),
            "Opt in to scheduled start.",
            f"{V2_GUIDE}#scheduled-start",
        ),
        (
            integration.get("job_configurator"),
            "Build the Configure screen.",
            f"{DOCS}/job-configurator",
        ),
        (
            spec.get("agent_parameters"),
            "Declare the agent parameters and secrets.",
            "https://github.com/supervaize/supervaizer/blob/main/README.md",
        ),
    ]
    items.extend(
        {"task": task, "reference": reference}
        for wanted, task, reference in optional
        if wanted
    )
    return items


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
    cli = shutil.which("supervaizer")
    if cli is None:
        raise RuntimeError(
            "The `supervaizer` command was not found. Install the SDK in this environment first."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    # The SDK owns the controller template, so the scaffold always matches the installed version.
    command = [
        cli,
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
            "files": {"controller": str(out_dir / controller_file)},
            "scaffolded_by": "supervaizer scaffold",
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


def _env_status_impl(shell_template: bool, pretty: bool) -> None:
    if shell_template:
        sys.stdout.write(
            'export SUPERVAIZE_API_KEY="..."\nexport SUPERVAIZE_WORKSPACE_ID="team_1"\nexport SUPERVAIZE_API_URL="https://app.supervaize.com"\n\n# Optional local controller protection\nexport CONTROLLER_AUTH_KEY="..."'
            + "\n"
        )
        return

    values = {name: os.getenv(name) for name in SUPERVAIZE_ENV_VARS}
    missing = [name for name, value in values.items() if not value]
    _print_json(
        {
            "ok": len(missing) == 0,
            "operation": "env-status",
            "required_env_vars": list(SUPERVAIZE_ENV_VARS),
            "present": [name for name, value in values.items() if value],
            "missing": missing,
            "values_masked": {
                k: (_mask_secret(v) if "KEY" in k else v) for k, v in values.items()
            },
            "controller_auth_key_present": bool(
                os.getenv("CONTROLLER_AUTH_KEY")
                or os.getenv("SUPERVAIZE_CONTROLLER_AUTH_KEY")
                or os.getenv("SUPERVAIZER_CONTROLLER_AUTH_KEY")
            ),
        },
        pretty=pretty,
    )


def _invoke_action_impl(
    controller_url: str,
    controller_api_key: str | None,
    agent_slug: str,
    action: str,
    surface: str,
    workspace_slug: str,
    mission_id: str,
    actor_id: str,
    job_id: str | None,
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
            "job_id": job_id or f"local-{request_id}",
            "idempotency_key": request_id,
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
    _print_json(
        {
            "ok": True,
            "operation": "invoke-action",
            "endpoint": endpoint,
            "status_code": status,
            "json_rpc": payload,
            "response": response,
        },
        pretty=pretty,
    )


def _load_surface_impl(
    controller_url: str,
    controller_api_key: str | None,
    agent_slug: str,
    surface: str,
    workspace_slug: str,
    mission_id: str,
    actor_id: str,
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
        },
    }
    status, response = _http_json(
        "POST",
        endpoint,
        body=payload,
        headers=_controller_headers(api_key),
        timeout=timeout_seconds,
    )
    _print_json(
        {
            "ok": True,
            "operation": "load-surface",
            "endpoint": endpoint,
            "status_code": status,
            "json_rpc": payload,
            "response": response,
        },
        pretty=pretty,
    )


@app.command("questions")
def questions(
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Print the integration discovery questions (Job/Case/Step mapping first)."""
    _print_json(_questions_payload(), pretty=pretty)


@app.command("spec-template")
def spec_template(
    output_file: str | None = typer.Option(
        None, "--output-file", help="Write the template JSON to a file."
    ),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Print or write an integration spec template used for scaffolding."""
    template = _spec_template()
    if output_file:
        _write_text(
            Path(output_file), json.dumps(template, indent=2) + "\n", force=True
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


@app.command("wizard")
def wizard(
    output_file: str = typer.Option(
        "integration_spec.json",
        "--output-file",
        help="Where to write the generated integration spec JSON.",
    ),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Interactive wizard to collect Job/Case/Step mapping and create an integration spec."""
    _handle(pretty, _wizard_impl, output_file=output_file, pretty=pretty)


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
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Check required SUPERVAIZE_* env vars or print export template."""
    _handle(pretty, _env_status_impl, shell_template=shell_template, pretty=pretty)


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
        "job.start", "--surface", help="Surface context for the action."
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
        job_id,
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
