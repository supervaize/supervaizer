# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import collections
import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import shortuuid
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from supervaizer.agent import Agent
from supervaizer.case import Case, CaseNodeUpdate, Cases
from supervaizer.common import log
from supervaizer.contracts import API_VERSION
from supervaizer.job import Job, JobContext, JobResponse, Jobs
from supervaizer.lifecycle import EntityStatus
from supervaizer.scheduled_steps import _execute_scheduled_method

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Shared log buffer — populated via log listener registered in routes.py
_WORKBENCH_LOG_BUFFER_MAX = 500
_workbench_log_buffer: collections.deque[dict[str, str]] = collections.deque(
    maxlen=_WORKBENCH_LOG_BUFFER_MAX
)


# Counter incremented only for non-admin log entries (avoids WS feedback loop)
_workbench_log_version = 0


def workbench_log_listener(timestamp: str, level: str, message: str) -> None:
    """Log listener callback — appends to workbench buffer."""
    global _workbench_log_version
    _workbench_log_buffer.append({
        "timestamp": timestamp,
        "level": level,
        "message": message,
    })
    # Only bump version for meaningful logs (not HTTP access logs from admin endpoints)
    if "/manage/" not in message and "HTTP/1.1" not in message:
        _workbench_log_version += 1


def _is_workbench_local_mode(request: Request) -> bool:
    """True when server has no Studio registration."""
    live = getattr(request.app.state, "server", None)
    return live is not None and getattr(live, "supervisor_account", None) is None


def get_agent_by_slug(request: Request | WebSocket, slug: str) -> Agent:
    """Look up a live Agent instance by its URL slug."""
    server = request.app.state.server
    for agent in server.agents:
        if agent.slug == slug:
            return agent
    raise HTTPException(status_code=404, detail=f"Agent '{slug}' not found")


def get_job_cases(job: Job) -> list[Any]:
    """Get all cases for a job from the Cases singleton."""
    return list(Cases().get_job_cases(job.id).values())


def get_agent_parameters_from_env(agent: Agent) -> dict[str, dict[str, str | bool]]:
    """Pre-fill parameter values from environment variables.

    Returns dict of {name: {"value": str, "from_env": bool}}.
    """
    values: dict[str, dict[str, str | bool]] = {}
    if agent.parameters_setup:
        for name, param in agent.parameters_setup.definitions.items():
            env_val = os.environ.get(name, "")
            if env_val:
                values[name] = {"value": env_val, "from_env": True}
            elif param.value:
                values[name] = {"value": param.value, "from_env": False}
    return values


_FIELD_TYPE_MAP = {
    "BooleanField": "checkbox",
    "CharField": "text",
    "TextField": "textarea",
    "IntegerField": "number",
    "ChoiceField": "select",
}


def _answer_fields(form_data: dict) -> list | None:
    """The field list of a `supervaizer_form` payload, or None when it has none."""
    answer = form_data.get("answer")
    fields = answer.get("fields") if isinstance(answer, dict) else None
    return fields if isinstance(fields, list) else None


def _field_definition(field: dict) -> dict[str, Any]:
    """One form field as the template wants it: input type, label, required, options."""
    field_type = field.get("field_type", "CharField")
    definition: dict[str, Any] = {
        "type": _FIELD_TYPE_MAP.get(field_type, "text"),
        "label": field.get("description") or field["name"],
        "required": field.get("required", False),
    }
    if field_type == "ChoiceField" and "choices" in field:
        definition["options"] = field["choices"]
    return definition


def _normalize_hitl_form(form_data: dict) -> dict:
    """Convert supervaizer_form payload to {field_name: {type, label, required, ...}} for the template."""
    if not isinstance(form_data, dict):
        return {}
    fields = _answer_fields(form_data)
    if fields is None:
        return form_data  # already in flat {name: def} format
    return {
        field["name"]: _field_definition(field)
        for field in fields
        if isinstance(field, dict) and "name" in field
    }


def _compute_job_state_hash(job: "Job") -> str:
    """Compute a hash of the job's observable state (status, cases, updates).

    Used by the WebSocket endpoint to detect changes without sending full HTML.
    """
    parts: list[str] = [job.status.value]
    cases = get_job_cases(job)
    for case in cases:
        parts.append(f"{case.id}:{case.status.value}:{len(case.updates)}")
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def _parameter_rows(agent: Agent) -> list[dict[str, Any]]:
    """The agent's parameters with the value to pre-fill and where it came from."""
    if not agent.parameters_setup:
        return []
    env_values = get_agent_parameters_from_env(agent)
    return [
        {
            "name": param.name,
            "description": param.description,
            "is_required": param.is_required,
            "is_secret": param.is_secret,
            "value": env_values.get(name, {}).get("value", ""),
            "from_env": env_values.get(name, {}).get("from_env", False),
        }
        for name, param in agent.parameters_setup.definitions.items()
    ]


def _job_field_rows(agent: Agent) -> list[dict[str, Any]]:
    """The input fields of the agent's job_start method, as the form needs them."""
    if not (
        agent.methods and agent.methods.job_start and agent.methods.job_start.fields
    ):
        return []
    return [
        {
            "name": field.name,
            "field_type": field.field_type.value
            if hasattr(field.field_type, "value")
            else str(field.field_type),
            "description": field.description,
            "choices": field.choices,
            "default": field.default,
            "required": field.required,
            "widget": field.widget,
        }
        for field in agent.methods.job_start.fields
    ]


def _active_job(agent: Agent) -> Job | None:
    """The first job of the agent that is still in progress."""
    return next(
        (
            job
            for job in Jobs().get_agent_jobs(agent.name).values()
            if job.status == EntityStatus.IN_PROGRESS
        ),
        None,
    )


async def workbench_page(request: Request, slug: str) -> Response:
    """Render the main workbench page."""
    agent = get_agent_by_slug(request, slug)

    return templates.TemplateResponse(
        request,
        "workbench.html",
        {
            "request": request,
            "agent": agent,
            "agent_slug": slug,
            "parameters": _parameter_rows(agent),
            "job_fields": _job_field_rows(agent),
            "active_job": _active_job(agent),
            "api_version": API_VERSION,
            "local_mode": _is_workbench_local_mode(request),
            "has_human_answer": agent.methods
            and getattr(agent.methods, "human_answer", None) is not None,
            "agents": [
                {"slug": a.slug, "name": a.name}
                for a in request.app.state.server.agents
            ],
        },
    )


async def _execute_in_thread(agent: Agent, method: str, params: dict[str, Any]) -> Any:
    """Run an agent method in a worker thread so the event loop stays free."""
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: agent._execute(method, params)
    )


def _resolve_parameters(agent: Agent, submitted: dict[str, Any]) -> dict[str, Any]:
    """Typed values win; empty ones fall back to the environment, then the default.

    Typed values for names the agent does not declare are kept.
    """
    resolved: dict[str, Any] = {}
    if agent.parameters_setup:
        env_values = get_agent_parameters_from_env(agent)
        for name in agent.parameters_setup.definitions:
            value = submitted.get(name, "") or env_values.get(name, {}).get("value", "")
            if value:
                resolved[name] = value
    resolved.update({k: v for k, v in submitted.items() if v and k not in resolved})
    return resolved


def _store_parameters(agent: Agent, resolved: dict[str, Any]) -> None:
    """Set the resolved values on the agent's declared parameters."""
    if agent.parameters_setup:
        for name, definition in agent.parameters_setup.definitions.items():
            if name in resolved:
                definition.set_value(resolved[name])


async def _run_job(job: Job, agent: Agent, method: str, params: dict[str, Any]) -> None:
    """Execute the job's start method and record the outcome on the job."""
    try:
        job.add_response(
            JobResponse(
                job_id=job.id,
                status=EntityStatus.IN_PROGRESS,
                message="Starting job execution",
                payload=None,
            )
        )
        job.add_response(await _execute_in_thread(agent, method, params))
    except Exception as e:
        log.error(f"[Workbench] Job {job.id} failed: {e}")
        job.add_response(
            JobResponse(
                job_id=job.id,
                status=EntityStatus.FAILED,
                message=f"Job failed: {e!s}",
                error=e,
            )
        )


async def workbench_start_job(request: Request, slug: str) -> Response:
    """Start a job from the workbench — no Studio communication."""
    agent = get_agent_by_slug(request, slug)
    # Check before any side effect: a rejected start must not leave a Job.
    if not agent.methods:
        raise HTTPException(
            status_code=400,
            detail="Agent has no methods defined: the workbench runs v1 jobs only",
        )

    body = await request.json()
    resolved = _resolve_parameters(agent, body.get("parameters", {}))
    # Set parameters via os.environ (matching agent convention).
    _store_parameters(agent, resolved)
    agent_params_list = [{"name": k, "value": v} for k, v in resolved.items()] or None

    # Job.__init__ auto-registers the job in the Jobs() singleton
    job_id = shortuuid.uuid()
    context = JobContext(
        workspace_id="workbench",
        job_id=job_id,
        started_by="workbench-admin",
        started_at=datetime.now(),
        mission_id="local",
        mission_name="Workbench Test",
    )
    job = Job(
        id=job_id,
        name="Workbench Test",
        agent_name=agent.name,
        status=EntityStatus.STOPPED,
        job_context=context,
        agent_parameters=agent_params_list,
    )

    # Execute job_start directly, bypassing agent.job_start() which sends Studio events
    job_start = agent.methods.job_start
    params = (job_start.params or {}) | {
        "fields": body.get("fields", {}),
        "context": context,
        "agent_parameters": agent_params_list or [],
    }
    asyncio.create_task(_run_job(job, agent, job_start.method, params))

    return JSONResponse({
        "id": job.id,
        "status": "STARTING",
        "message": "Job started from workbench",
    })


_NO_HITL: dict[str, Any] = {"hitl_form": None, "hitl_dialog": None}


def _latest_hitl(case: Case) -> dict[str, Any]:
    """The newest dialog or form an awaiting case asks the human for."""
    for update in reversed(case.updates):
        payload = update.payload
        if payload and "supervaizer_dialog" in payload:
            return {"hitl_form": None, "hitl_dialog": payload["supervaizer_dialog"]}
        if payload and "supervaizer_form" in payload:
            form = _normalize_hitl_form(payload["supervaizer_form"])
            return {"hitl_form": form, "hitl_dialog": None}
    return _NO_HITL


async def workbench_job_monitor(request: Request, slug: str, job_id: str) -> Response:
    """HTMX partial — returns execution monitor HTML for polling."""
    agent = get_agent_by_slug(request, slug)

    job = Jobs().get_job(job_id, agent_name=agent.name)
    if not job:
        return HTMLResponse("<div class='text-gray-500 text-sm'>Job not found</div>")

    cases_data = [
        {
            "case": case,
            **(
                _latest_hitl(case) if case.status == EntityStatus.AWAITING else _NO_HITL
            ),
        }
        for case in get_job_cases(job)
    ]

    return templates.TemplateResponse(
        request,
        "workbench_monitor.html",
        {
            "request": request,
            "agent_slug": slug,
            "job": job,
            "cases_data": cases_data,
            "has_human_answer": agent.methods
            and getattr(agent.methods, "human_answer", None) is not None,
        },
    )


async def workbench_stop_job(request: Request, slug: str, job_id: str) -> Response:
    """Stop a running job."""
    agent = get_agent_by_slug(request, slug)

    if not agent.methods or not agent.methods.job_stop:
        raise HTTPException(status_code=400, detail="Agent has no job_stop method")

    # Update job status in registry so the running loop can detect it
    job = Jobs().get_job(job_id, agent_name=agent.name)
    if job:
        job.add_response(
            JobResponse(
                job_id=job_id,
                status=EntityStatus.STOPPED,
                message="Stopped by user",
            )
        )

    try:
        result = await _execute_in_thread(
            agent, agent.methods.job_stop.method, {"job_id": job_id}
        )
        return JSONResponse({"status": "stopped", "message": str(result.message)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop job: {e}")


async def workbench_job_status(request: Request, slug: str, job_id: str) -> Response:
    """Get job status via agent's job_status method."""
    agent = get_agent_by_slug(request, slug)

    if not agent.methods or not agent.methods.job_status:
        # Fall back to reading job state directly
        job = Jobs().get_job(job_id, agent_name=agent.name)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JSONResponse({
            "job_id": job.id,
            "status": job.status.value,
        })

    try:
        result = await _execute_in_thread(
            agent, agent.methods.job_status.method, {"job_id": job_id}
        )
        return JSONResponse({
            "status": result.status.value,
            "message": result.message,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


def _hitl_label(case: Case) -> str:
    """The name of the newest step that asked a human for input."""
    for update in reversed(case.updates):
        payload = update.payload
        if payload and (
            "supervaizer_form" in payload or "supervaizer_dialog" in payload
        ):
            return update.name or "User response"
    return "User response"


async def _run_human_answer(
    agent: Agent, method: str, answer: Any, job_id: str, case_id: str
) -> JSONResponse | None:
    """Hand the answer to the agent's human_answer method; a 500 response if it fails."""
    params = {
        "fields": answer,
        "context": {"job_id": job_id, "case_id": case_id},
        "payload": answer,
        "case_id": case_id,
        "job_id": job_id,
    }
    try:
        await _execute_in_thread(agent, method, params)
    except Exception as e:
        log.error(f"[Workbench] human_answer failed for case {case_id}: {e}")
        return JSONResponse(
            {"status": "error", "message": f"human_answer failed: {e}"},
            status_code=500,
        )
    return None


async def workbench_answer_hitl(
    request: Request, slug: str, job_id: str, case_id: str
) -> Response:
    """Submit HITL answer — two-step dispatch (receive + invoke human_answer)."""
    agent = get_agent_by_slug(request, slug)
    answer_data = (await request.json()).get("answer", {})

    case = _find_case(job_id, case_id)
    if case.status != EntityStatus.AWAITING:
        raise HTTPException(
            status_code=409,
            detail=f"Case '{case_id}' is not awaiting input (current status: {case.status})",
        )

    # Step 1: Transition case state AWAITING -> IN_PROGRESS
    payload = (
        {**answer_data, "_hitl_label": _hitl_label(case)}
        if isinstance(answer_data, dict)
        else answer_data
    )
    await case.receive_human_input(CaseNodeUpdate(name="HITL Answer", payload=payload))

    # Step 2: Invoke agent's human_answer method if defined
    human_answer = agent.methods.human_answer if agent.methods else None
    if human_answer is not None:
        failure = await _run_human_answer(
            agent, human_answer.method, answer_data, job_id, case_id
        )
        if failure:
            return failure

    return JSONResponse({
        "status": "answered",
        "case_id": case_id,
        "message": "HITL answer submitted and dispatched",
    })


def _find_case(job_id: str, case_id: str) -> Case:
    """The case of a job, or a 404."""
    case = Cases().get_case(case_id, job_id=job_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return case


def _pending_step(case: Case, step_index: int) -> CaseNodeUpdate:
    """The scheduled step at `step_index` that has not started, or the matching error."""
    if step_index < 0 or step_index >= len(case.updates):
        raise HTTPException(status_code=404, detail="Step not found")
    update = case.updates[step_index]
    if update.scheduled_at is None:
        raise HTTPException(status_code=400, detail="Step is not a scheduled step")
    if update.scheduled_status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Step is not pending (current: {update.scheduled_status})",
        )
    return update


def _run_step(update: CaseNodeUpdate, agent: Agent) -> JSONResponse:
    """Run the step's method now and record whether it completed or failed."""
    object.__setattr__(update, "scheduled_status", "executing")
    try:
        if update.scheduled_method:
            _execute_scheduled_method(
                update.scheduled_method,
                update.scheduled_params or {},
                allowed_methods=agent._declared_method_paths(),
            )
        object.__setattr__(update, "scheduled_status", "completed")
        return JSONResponse({
            "status": "completed",
            "message": "Step executed successfully",
        })
    except Exception as e:
        object.__setattr__(update, "scheduled_status", "failed")
        log.error(f"[Workbench] Scheduled step execute failed: {e}")
        return JSONResponse(
            {"status": "failed", "message": f"Execution failed: {e}"},
            status_code=500,
        )


def _parse_scheduled_at(body: dict[str, Any]) -> datetime:
    """The `scheduled_at` field of a request body as a datetime, or a 400."""
    raw = body.get("scheduled_at")
    if not raw:
        raise HTTPException(status_code=400, detail="scheduled_at is required")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid datetime format")


async def workbench_execute_step(
    request: Request, slug: str, job_id: str, case_id: str, step_index: int
) -> Response:
    """Execute a scheduled step immediately."""
    agent = get_agent_by_slug(request, slug)

    # Verify the job and case are both owned by this agent before using
    # the agent's method allow-list.
    job = Jobs().get_job(job_id, agent_name=agent.name)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found for agent '{slug}'",
        )

    case = _find_case(job_id, case_id)
    if case.id not in job.case_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Case '{case_id}' not found for agent '{slug}'",
        )

    return _run_step(_pending_step(case, step_index), agent)


async def workbench_cancel_step(
    request: Request, slug: str, job_id: str, case_id: str, step_index: int
) -> Response:
    """Cancel a pending scheduled step."""
    get_agent_by_slug(request, slug)

    update = _pending_step(_find_case(job_id, case_id), step_index)
    object.__setattr__(update, "scheduled_status", "cancelled")
    return JSONResponse({"status": "cancelled", "message": "Step cancelled"})


async def workbench_reschedule_step(
    request: Request, slug: str, job_id: str, case_id: str, step_index: int
) -> Response:
    """Reschedule a pending scheduled step."""
    get_agent_by_slug(request, slug)

    update = _pending_step(_find_case(job_id, case_id), step_index)
    new_dt = _parse_scheduled_at(await request.json())
    object.__setattr__(update, "scheduled_at", new_dt)
    return JSONResponse({
        "status": "rescheduled",
        "message": f"Step rescheduled to {new_dt.isoformat()}",
    })


async def workbench_console(request: Request, slug: str) -> Response:
    """HTMX partial — returns recent console log entries."""
    try:
        last_index = int(request.query_params.get("last_index", 0))
    except (ValueError, TypeError):
        last_index = 0

    buf = list(_workbench_log_buffer)
    entries_to_send = buf[last_index:]

    return templates.TemplateResponse(
        request,
        "workbench_console.html",
        {
            "request": request,
            "entries": entries_to_send,
            "next_index": len(buf),
            "agent_slug": slug,
        },
    )


async def workbench_jobs_list(request: Request, slug: str) -> Response:
    """HTMX partial — returns job history list."""
    agent = get_agent_by_slug(request, slug)
    agent_jobs = Jobs().get_agent_jobs(agent.name)

    # Sort by created_at descending (most recent first)
    jobs_list = sorted(
        agent_jobs.values(),
        key=lambda j: getattr(j, "created_at", None) or datetime.min,
        reverse=True,
    )

    return templates.TemplateResponse(
        request,
        "workbench_jobs_list.html",
        {
            "request": request,
            "agent_slug": slug,
            "jobs": jobs_list,
        },
    )


# (HTTP method, path, handler, extra add_api_route options).
_WORKBENCH_ROUTES: list[tuple[str, str, Callable[..., Any], dict[str, Any]]] = [
    (
        "GET",
        "/agents/{slug}/workbench",
        workbench_page,
        {"response_class": HTMLResponse},
    ),
    ("POST", "/agents/{slug}/workbench/start", workbench_start_job, {}),
    (
        "GET",
        "/agents/{slug}/workbench/jobs/{job_id}",
        workbench_job_monitor,
        {"response_class": HTMLResponse},
    ),
    ("POST", "/agents/{slug}/workbench/jobs/{job_id}/stop", workbench_stop_job, {}),
    ("GET", "/agents/{slug}/workbench/jobs/{job_id}/status", workbench_job_status, {}),
    (
        "POST",
        "/agents/{slug}/workbench/jobs/{job_id}/cases/{case_id}/answer",
        workbench_answer_hitl,
        {},
    ),
    (
        "POST",
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/execute",
        workbench_execute_step,
        {},
    ),
    (
        "POST",
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/cancel",
        workbench_cancel_step,
        {},
    ),
    (
        "PATCH",
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/schedule",
        workbench_reschedule_step,
        {},
    ),
    (
        "GET",
        "/agents/{slug}/workbench/console",
        workbench_console,
        {"response_class": HTMLResponse},
    ),
    (
        "GET",
        "/agents/{slug}/workbench/jobs",
        workbench_jobs_list,
        {"response_class": HTMLResponse},
    ),
]


def create_workbench_routes() -> APIRouter:
    """Create workbench sub-router."""
    from supervaizer.admin.routes import register_log_listener

    register_log_listener(workbench_log_listener)

    router = APIRouter(tags=["workbench"])
    for method, route_path, handler, options in _WORKBENCH_ROUTES:
        router.add_api_route(route_path, handler, methods=[method], **options)
    return router


_TERMINAL_STATUSES = ("completed", "failed", "stopped", "cancelled")


@dataclass
class _SignalState:
    """What one WebSocket client has already been told."""

    monitor_hash: str = ""
    log_version: int = field(default_factory=lambda: _workbench_log_version)
    jobs_count: int = -1

    def changes(self, job: Job, agent_name: str) -> list[str]:
        """Refresh signals for what changed since the last call; updates the state."""
        signals: list[str] = []
        current_hash = _compute_job_state_hash(job)
        if current_hash != self.monitor_hash:
            self.monitor_hash = current_hash
            signals.append("monitor")
        # Only meaningful log entries bump the version (no admin HTTP noise).
        if _workbench_log_version != self.log_version:
            self.log_version = _workbench_log_version
            signals.append("console")
        jobs_count = len(Jobs().get_agent_jobs(agent_name))
        if jobs_count != self.jobs_count:
            self.jobs_count = jobs_count
            signals.append("jobs")
        return signals


def _find_job(job_id: str, agent_name: str) -> Job | None:
    try:
        return Jobs().get_job(job_id, agent_name=agent_name)
    except Exception:
        return None


async def _idle_until_disconnect(websocket: WebSocket) -> None:
    """Keep the connection open but idle, so the client does not reconnect in a loop."""
    try:
        while True:
            await asyncio.wait_for(websocket.receive_text(), timeout=60)
    except (TimeoutError, WebSocketDisconnect):
        pass


async def _answer_ping(websocket: WebSocket) -> None:
    """Wait up to two seconds for a client message; answer a ping with a pong."""
    try:
        data = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
    except TimeoutError:
        return
    if data == "ping":
        await websocket.send_text("pong")


async def workbench_job_ws(websocket: WebSocket, slug: str, job_id: str) -> None:
    """WebSocket that pushes typed refresh signals when state changes.

    Sends: "monitor" (job/case state changed), "console" (new log entries),
           "jobs" (job list changed). Client fetches the relevant partial.
    """
    await websocket.accept()
    # Cache agent outside the loop — it doesn't change during a WS session
    try:
        agent = get_agent_by_slug(websocket, slug)
    except Exception:
        await websocket.close()
        return
    state = _SignalState()
    try:
        while True:
            job = _find_job(job_id, agent.name)
            if not job:
                await websocket.send_text("monitor")
                break
            signals = state.changes(job, agent.name)
            finished = job.status.value in _TERMINAL_STATUSES
            if finished:
                signals += ["console", "jobs", "terminal"]
            for signal in signals:
                await websocket.send_text(signal)
            if finished:
                await _idle_until_disconnect(websocket)
                break
            await _answer_ping(websocket)
    except WebSocketDisconnect:
        pass


def create_workbench_ws_routes() -> APIRouter:
    """Create WebSocket routes for workbench (no auth dependency — WS can't use APIKeyHeader)."""
    ws_router = APIRouter(tags=["workbench-ws"])
    ws_router.add_api_websocket_route(
        "/agents/{slug}/workbench/jobs/{job_id}/ws", workbench_job_ws
    )
    return ws_router
