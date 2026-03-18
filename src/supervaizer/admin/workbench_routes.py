# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import collections
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import shortuuid
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from supervaizer.__version__ import API_VERSION
from supervaizer.agent import Agent
from supervaizer.case import Cases, CaseNodeUpdate
from supervaizer.common import log
from supervaizer.job import Job, JobContext, JobResponse, Jobs
from supervaizer.lifecycle import EntityStatus

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
    global _workbench_log_version  # noqa: PLW0603
    _workbench_log_buffer.append({
        "timestamp": timestamp,
        "level": level,
        "message": message,
    })
    # Only bump version for meaningful logs (not HTTP access logs from admin endpoints)
    if "/admin/" not in message and "HTTP/1.1" not in message:
        _workbench_log_version += 1


def _get_workbench_api_key(request: Request) -> str:
    """API key for workbench requests (live server or env)."""
    live = getattr(request.app.state, "server", None)
    if live is not None and getattr(live, "api_key", None):
        return live.api_key
    return os.getenv("SUPERVAIZER_API_KEY") or ""


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


def get_job_cases(job: Job) -> List[Any]:
    """Get all cases for a job from the Cases singleton."""
    return list(Cases().get_job_cases(job.id).values())


def get_agent_parameters_from_env(agent: Agent) -> Dict[str, Dict[str, str | bool]]:
    """Pre-fill parameter values from environment variables.

    Returns dict of {name: {"value": str, "from_env": bool}}.
    """
    values: Dict[str, Dict[str, str | bool]] = {}
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


def _normalize_hitl_form(form_data: dict) -> dict:
    """Convert supervaizer_form payload to {field_name: {type, label, required, ...}} for the template."""
    if not isinstance(form_data, dict):
        return {}
    # Already in flat {name: def} format
    answer = form_data.get("answer")
    if not isinstance(answer, dict):
        return form_data
    fields = answer.get("fields")
    if not isinstance(fields, list):
        return form_data
    result = {}
    for field in fields:
        if not isinstance(field, dict) or "name" not in field:
            continue
        name = field["name"]
        field_type = field.get("field_type", "CharField")
        result[name] = {
            "type": _FIELD_TYPE_MAP.get(field_type, "text"),
            "label": field.get("description") or name,
            "required": field.get("required", False),
        }
        if field_type == "ChoiceField" and "choices" in field:
            result[name]["options"] = field["choices"]
    return result


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


def create_workbench_routes() -> APIRouter:
    """Create workbench sub-router."""
    from supervaizer.admin.routes import register_log_listener

    register_log_listener(workbench_log_listener)

    router = APIRouter(tags=["workbench"])

    @router.get("/agents/{slug}/workbench", response_class=HTMLResponse)
    async def workbench_page(request: Request, slug: str) -> Response:
        """Render the main workbench page."""
        agent = get_agent_by_slug(request, slug)

        # Gather agent info for the template
        parameters = []
        if agent.parameters_setup:
            env_values = get_agent_parameters_from_env(agent)
            for name, param in agent.parameters_setup.definitions.items():
                env_info = env_values.get(name, {})
                parameters.append({
                    "name": param.name,
                    "description": param.description,
                    "is_required": param.is_required,
                    "is_secret": param.is_secret,
                    "value": env_info.get("value", ""),
                    "from_env": env_info.get("from_env", False),
                })

        job_fields = []
        if agent.methods and agent.methods.job_start and agent.methods.job_start.fields:
            for field in agent.methods.job_start.fields:
                job_fields.append({
                    "name": field.name,
                    "field_type": field.field_type.value
                    if hasattr(field.field_type, "value")
                    else str(field.field_type),
                    "description": field.description,
                    "choices": field.choices,
                    "default": field.default,
                    "required": field.required,
                    "widget": field.widget,
                })

        # Check for active job
        active_job = None
        agent_jobs = Jobs().get_agent_jobs(agent.name)
        for job in agent_jobs.values():
            if job.status == EntityStatus.IN_PROGRESS:
                active_job = job
                break

        return templates.TemplateResponse(
            request,
            "workbench.html",
            {
                "request": request,
                "agent": agent,
                "agent_slug": slug,
                "parameters": parameters,
                "job_fields": job_fields,
                "active_job": active_job,
                "api_version": API_VERSION,
                "api_key": _get_workbench_api_key(request),
                "local_mode": _is_workbench_local_mode(request),
                "has_human_answer": agent.methods
                and getattr(agent.methods, "human_answer", None) is not None,
                "has_poll": agent.methods
                and getattr(agent.methods, "job_poll", None) is not None,
                "agents": [
                    {"slug": a.slug, "name": a.name}
                    for a in request.app.state.server.agents
                ],
            },
        )

    @router.post("/agents/{slug}/workbench/start")
    async def workbench_start_job(request: Request, slug: str) -> Response:
        """Start a job from the workbench — no Studio communication."""
        agent = get_agent_by_slug(request, slug)

        body = await request.json()
        parameters = body.get("parameters", {})
        fields = body.get("fields", {})

        # Set parameters via os.environ (matching agent convention).
        # Fall back to env values for empty fields (local mode pre-fill).
        if agent.parameters_setup:
            env_values = get_agent_parameters_from_env(agent)
            for name in agent.parameters_setup.definitions:
                value = parameters.get(name, "")
                if not value:
                    env_info = env_values.get(name, {})
                    value = env_info.get("value", "")
                if value:
                    agent.parameters_setup.definitions[name].set_value(value)

        # Create job context and job (Job.__init__ auto-registers in Jobs() singleton)
        job_id = shortuuid.uuid()

        context = JobContext(
            workspace_id="workbench",
            job_id=job_id,
            started_by="workbench-admin",
            started_at=datetime.now(),
            mission_id="local",
            mission_name="Workbench Test",
        )

        # Build agent_parameters as list of dicts (matching AbstractJob.agent_parameters type)
        # Merge submitted values with env fallbacks
        merged_params = {}
        if agent.parameters_setup:
            for name in agent.parameters_setup.definitions:
                value = parameters.get(name, "")
                if not value:
                    env_info = env_values.get(name, {})
                    value = env_info.get("value", "")
                if value:
                    merged_params[name] = value
        # Also include any extra params not in definitions
        for k, v in parameters.items():
            if v and k not in merged_params:
                merged_params[k] = v
        agent_params_list = (
            [{"name": k, "value": v} for k, v in merged_params.items()]
            if merged_params
            else None
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
        if not agent.methods:
            raise HTTPException(status_code=400, detail="Agent has no methods defined")

        action_method = agent.methods.job_start.method
        method_params = agent.methods.job_start.params or {}
        params = method_params | {
            "fields": fields,
            "context": context,
            "agent_parameters": agent_params_list or [],
        }

        # Run in background thread to not block the response
        loop = asyncio.get_running_loop()

        async def run_job() -> None:
            try:
                job.add_response(
                    JobResponse(
                        job_id=job.id,
                        status=EntityStatus.IN_PROGRESS,
                        message="Starting job execution",
                        payload=None,
                    )
                )
                result = await loop.run_in_executor(
                    None, lambda: agent._execute(action_method, params)
                )
                job.add_response(result)
            except Exception as e:
                log.error(f"[Workbench] Job {job.id} failed: {e}")
                job.add_response(
                    JobResponse(
                        job_id=job.id,
                        status=EntityStatus.FAILED,
                        message=f"Job failed: {str(e)}",
                        error=e,
                    )
                )

        asyncio.create_task(run_job())

        return JSONResponse({
            "id": job.id,
            "status": "STARTING",
            "message": "Job started from workbench",
        })

    @router.get("/agents/{slug}/workbench/jobs/{job_id}", response_class=HTMLResponse)
    async def workbench_job_monitor(
        request: Request, slug: str, job_id: str
    ) -> Response:
        """HTMX partial — returns execution monitor HTML for polling."""
        agent = get_agent_by_slug(request, slug)

        job = Jobs().get_job(job_id, agent_name=agent.name)

        if not job:
            return HTMLResponse(
                "<div class='text-gray-500 text-sm'>Job not found</div>"
            )

        cases = get_job_cases(job)

        # For each case, check if it's awaiting and extract HITL form data
        cases_data = []
        for case in cases:
            case_info = {
                "case": case,
                "hitl_form": None,
                "hitl_dialog": None,
            }
            if case.status == EntityStatus.AWAITING:
                # Find the HITL update in case.updates
                for update in reversed(case.updates):
                    if hasattr(update, "payload") and update.payload:
                        payload = update.payload
                        if isinstance(payload, dict):
                            if "supervaizer_dialog" in payload:
                                case_info["hitl_dialog"] = payload["supervaizer_dialog"]
                                break
                            elif "supervaizer_form" in payload:
                                case_info["hitl_form"] = _normalize_hitl_form(
                                    payload["supervaizer_form"]
                                )
                                break
            cases_data.append(case_info)

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

    @router.post("/agents/{slug}/workbench/jobs/{job_id}/stop")
    async def workbench_stop_job(request: Request, slug: str, job_id: str) -> Response:
        """Stop a running job."""
        agent = get_agent_by_slug(request, slug)

        if not agent.methods or not agent.methods.job_stop:
            raise HTTPException(status_code=400, detail="Agent has no job_stop method")

        job_stop_method = agent.methods.job_stop.method

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
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent._execute(job_stop_method, {"job_id": job_id}),
            )
            return JSONResponse({"status": "stopped", "message": str(result.message)})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop job: {e}")

    @router.post("/agents/{slug}/workbench/jobs/{job_id}/poll")
    async def workbench_poll_job(request: Request, slug: str, job_id: str) -> Response:
        """Trigger manual poll for external updates on a job."""
        agent = get_agent_by_slug(request, slug)

        if not agent.methods or not agent.methods.job_poll:
            raise HTTPException(status_code=404, detail="Agent has no poll method")

        job_poll_method = agent.methods.job_poll.method

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent._execute(job_poll_method, {"job_id": job_id}),
            )
            return JSONResponse({
                "status": result.status.value if result.status else "unknown",
                "message": result.message or "Poll completed",
                "payload": result.payload,
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to poll job: {e}")

    @router.get("/agents/{slug}/workbench/jobs/{job_id}/status")
    async def workbench_job_status(
        request: Request, slug: str, job_id: str
    ) -> Response:
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

        job_status_method = agent.methods.job_status.method
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent._execute(job_status_method, {"job_id": job_id}),
            )
            return JSONResponse({
                "status": result.status.value,
                "message": result.message,
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")

    @router.post("/agents/{slug}/workbench/jobs/{job_id}/cases/{case_id}/answer")
    async def workbench_answer_hitl(
        request: Request, slug: str, job_id: str, case_id: str
    ) -> Response:
        """Submit HITL answer — two-step dispatch (receive + invoke human_answer)."""
        agent = get_agent_by_slug(request, slug)

        body = await request.json()
        answer_data = body.get("answer", {})

        # Find the case
        case = Cases().get_case(case_id, job_id=job_id)

        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

        if case.status != EntityStatus.AWAITING:
            raise HTTPException(
                status_code=409,
                detail=f"Case '{case_id}' is not awaiting input (current status: {case.status})",
            )

        # Derive a human-readable label from the HITL step that prompted this answer
        hitl_label = "User response"
        for prev_update in reversed(case.updates):
            if hasattr(prev_update, "payload") and prev_update.payload:
                p = prev_update.payload
                if isinstance(p, dict) and (
                    "supervaizer_form" in p or "supervaizer_dialog" in p
                ):
                    hitl_label = prev_update.name or hitl_label
                    break

        # Step 1: Transition case state AWAITING -> IN_PROGRESS
        answer_with_label = (
            dict(answer_data) if isinstance(answer_data, dict) else answer_data
        )
        if isinstance(answer_with_label, dict):
            answer_with_label["_hitl_label"] = hitl_label
        update = CaseNodeUpdate(name="HITL Answer", payload=answer_with_label)
        case.receive_human_input(update)

        # Step 2: Invoke agent's human_answer method if defined
        if agent.methods:
            human_answer_def = getattr(agent.methods, "human_answer", None)
            if human_answer_def is not None:
                human_answer_method = human_answer_def.method
                try:
                    params = {
                        "fields": answer_data,
                        "context": {"job_id": job_id, "case_id": case_id},
                        "payload": answer_data,
                        "case_id": case_id,
                        "job_id": job_id,
                    }
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: agent._execute(human_answer_method, params),
                    )
                except Exception as e:
                    log.error(
                        f"[Workbench] human_answer failed for case {case_id}: {e}"
                    )
                    return JSONResponse(
                        {"status": "error", "message": f"human_answer failed: {e}"},
                        status_code=500,
                    )

        return JSONResponse({
            "status": "answered",
            "case_id": case_id,
            "message": "HITL answer submitted and dispatched",
        })

    @router.post(
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/execute"
    )
    async def workbench_execute_step(
        request: Request, slug: str, job_id: str, case_id: str, step_index: int
    ) -> Response:
        """Execute a scheduled step immediately."""
        from supervaizer.server import _execute_scheduled_method

        get_agent_by_slug(request, slug)

        case = Cases().get_case(case_id, job_id=job_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

        if step_index < 0 or step_index >= len(case.updates):
            raise HTTPException(status_code=404, detail="Step not found")

        update = case.updates[step_index]
        if getattr(update, "scheduled_at", None) is None:
            raise HTTPException(status_code=400, detail="Step is not a scheduled step")
        if getattr(update, "scheduled_status", None) != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Step is not pending (current: {getattr(update, 'scheduled_status', 'unknown')})",
            )

        object.__setattr__(update, "scheduled_status", "executing")
        try:
            if update.scheduled_method:
                _execute_scheduled_method(
                    update.scheduled_method,
                    update.scheduled_params or {},
                )
            object.__setattr__(update, "scheduled_status", "completed")
            return JSONResponse({"status": "completed", "message": "Step executed successfully"})
        except Exception as e:
            object.__setattr__(update, "scheduled_status", "failed")
            log.error(f"[Workbench] Scheduled step execute failed: {e}")
            return JSONResponse(
                {"status": "failed", "message": f"Execution failed: {e}"},
                status_code=500,
            )

    @router.post(
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/cancel"
    )
    async def workbench_cancel_step(
        request: Request, slug: str, job_id: str, case_id: str, step_index: int
    ) -> Response:
        """Cancel a pending scheduled step."""
        get_agent_by_slug(request, slug)

        case = Cases().get_case(case_id, job_id=job_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

        if step_index < 0 or step_index >= len(case.updates):
            raise HTTPException(status_code=404, detail="Step not found")

        update = case.updates[step_index]
        if getattr(update, "scheduled_at", None) is None:
            raise HTTPException(status_code=400, detail="Step is not a scheduled step")
        if getattr(update, "scheduled_status", None) != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Step is not pending (current: {getattr(update, 'scheduled_status', 'unknown')})",
            )

        object.__setattr__(update, "scheduled_status", "cancelled")
        return JSONResponse({"status": "cancelled", "message": "Step cancelled"})

    @router.patch(
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/schedule"
    )
    async def workbench_reschedule_step(
        request: Request, slug: str, job_id: str, case_id: str, step_index: int
    ) -> Response:
        """Reschedule a pending scheduled step."""
        get_agent_by_slug(request, slug)

        case = Cases().get_case(case_id, job_id=job_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

        if step_index < 0 or step_index >= len(case.updates):
            raise HTTPException(status_code=404, detail="Step not found")

        update = case.updates[step_index]
        if getattr(update, "scheduled_at", None) is None:
            raise HTTPException(status_code=400, detail="Step is not a scheduled step")
        if getattr(update, "scheduled_status", None) != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Step is not pending (current: {getattr(update, 'scheduled_status', 'unknown')})",
            )

        body = await request.json()
        new_scheduled_at = body.get("scheduled_at")
        if not new_scheduled_at:
            raise HTTPException(status_code=400, detail="scheduled_at is required")

        try:
            new_dt = datetime.fromisoformat(new_scheduled_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid datetime format")

        object.__setattr__(update, "scheduled_at", new_dt)
        return JSONResponse({
            "status": "rescheduled",
            "message": f"Step rescheduled to {new_dt.isoformat()}",
        })

    @router.get("/agents/{slug}/workbench/console", response_class=HTMLResponse)
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

    @router.get("/agents/{slug}/workbench/jobs", response_class=HTMLResponse)
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

    return router


def create_workbench_ws_routes() -> APIRouter:
    """Create WebSocket routes for workbench (no auth dependency — WS can't use APIKeyHeader)."""
    ws_router = APIRouter(tags=["workbench-ws"])

    @ws_router.websocket("/agents/{slug}/workbench/jobs/{job_id}/ws")
    async def workbench_job_ws(websocket: WebSocket, slug: str, job_id: str) -> None:
        """WebSocket that pushes typed refresh signals when state changes.

        Sends: "monitor" (job/case state changed), "console" (new log entries),
               "jobs" (job list changed). Client fetches the relevant partial.
        """
        await websocket.accept()
        last_monitor_hash = ""
        last_log_version = _workbench_log_version
        last_jobs_count = -1
        # Cache agent outside the loop — it doesn't change during a WS session
        try:
            agent = get_agent_by_slug(websocket, slug)
        except Exception:
            await websocket.close()
            return
        try:
            while True:
                try:
                    job = Jobs().get_job(job_id, agent_name=agent.name)
                except Exception:
                    job = None

                if not job:
                    await websocket.send_text("monitor")
                    break

                # Monitor: job/case state changes
                current_hash = _compute_job_state_hash(job)
                if current_hash != last_monitor_hash:
                    last_monitor_hash = current_hash
                    await websocket.send_text("monitor")

                # Console: only meaningful log entries (filtered, no admin HTTP noise)
                if _workbench_log_version != last_log_version:
                    last_log_version = _workbench_log_version
                    await websocket.send_text("console")

                # Jobs: job count changed
                agent_jobs = Jobs().get_agent_jobs(agent.name)
                if len(agent_jobs) != last_jobs_count:
                    last_jobs_count = len(agent_jobs)
                    await websocket.send_text("jobs")

                is_terminal = job.status.value in (
                    "completed",
                    "failed",
                    "stopped",
                    "cancelled",
                )
                if is_terminal:
                    await websocket.send_text("console")
                    await websocket.send_text("jobs")
                    await websocket.send_text("terminal")
                    # Keep connection open but idle — prevents client reconnect loop
                    try:
                        while True:
                            await asyncio.wait_for(websocket.receive_text(), timeout=60)
                    except (asyncio.TimeoutError, WebSocketDisconnect):
                        pass
                    break

                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=2.0,
                    )
                    if data == "ping":
                        await websocket.send_text("pong")
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            pass

    return ws_router
