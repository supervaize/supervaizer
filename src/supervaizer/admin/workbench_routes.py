import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import shortuuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from supervaizer.__version__ import API_VERSION
from supervaizer.agent import Agent
from supervaizer.case import CaseNodeUpdate
from supervaizer.common import log
from supervaizer.job import Job, JobContext, JobResponse
from supervaizer.lifecycle import EntityStatus

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Module-level log buffer — avoids race conditions with SSE consumer
_workbench_log_buffer: list[dict[str, str]] = []
_WORKBENCH_LOG_BUFFER_MAX = 500
_patch_applied = False


def _apply_log_patch() -> None:
    global _patch_applied
    if _patch_applied:
        return
    from supervaizer.admin import routes as _admin_routes
    _original_add_log = _admin_routes.add_log_to_queue

    def _patched_add_log(timestamp: str, level: str, message: str) -> None:
        _original_add_log(timestamp, level, message)
        _workbench_log_buffer.append({"timestamp": timestamp, "level": level, "message": message})
        if len(_workbench_log_buffer) > _WORKBENCH_LOG_BUFFER_MAX:
            del _workbench_log_buffer[:len(_workbench_log_buffer) - _WORKBENCH_LOG_BUFFER_MAX]

    _admin_routes.add_log_to_queue = _patched_add_log
    _patch_applied = True


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


def get_agent_by_slug(request: Request, slug: str) -> Agent:
    """Look up a live Agent instance by its URL slug."""
    server = request.app.state.server
    for agent in server.agents:
        if agent.slug == slug:
            return agent
    raise HTTPException(status_code=404, detail=f"Agent '{slug}' not found")


def get_job_cases(job: Job) -> List[Any]:
    """Get all cases for a job from the Cases singleton."""
    from supervaizer.case import Cases
    cases_registry = Cases()
    job_cases = cases_registry.get_job_cases(job.id)  # returns dict[str, Case]
    return list(job_cases.values())


def get_agent_parameters_from_env(agent: Agent) -> Dict[str, str]:
    """Pre-fill parameter values from environment variables."""
    values = {}
    if agent.parameters_setup:
        for name, param in agent.parameters_setup.definitions.items():
            env_val = os.environ.get(name, "")
            if env_val:
                values[name] = env_val
            elif param.value:
                values[name] = param.value
    return values


class WorkbenchStartRequest(BaseModel):
    parameters: Dict[str, str] = {}
    fields: Dict[str, Any] = {}


class WorkbenchAnswerRequest(BaseModel):
    answer: Dict[str, Any] = {}


def create_workbench_routes() -> APIRouter:
    """Create workbench sub-router."""
    _apply_log_patch()

    router = APIRouter(tags=["workbench"])

    @router.get("/agents/{slug}/workbench", response_class=HTMLResponse)
    async def workbench_page(request: Request, slug: str):
        """Render the main workbench page."""
        agent = get_agent_by_slug(request, slug)

        # Gather agent info for the template
        parameters = []
        if agent.parameters_setup:
            env_values = get_agent_parameters_from_env(agent)
            for name, param in agent.parameters_setup.definitions.items():
                parameters.append({
                    "name": param.name,
                    "description": param.description,
                    "is_required": param.is_required,
                    "is_secret": param.is_secret,
                    "value": env_values.get(name, ""),
                })

        job_fields = []
        if agent.methods and agent.methods.job_start and agent.methods.job_start.fields:
            for field in agent.methods.job_start.fields:
                job_fields.append({
                    "name": field.name,
                    "field_type": field.field_type.value if hasattr(field.field_type, "value") else str(field.field_type),
                    "description": field.description,
                    "choices": field.choices,
                    "default": field.default,
                    "required": field.required,
                    "widget": field.widget,
                })

        # Check for active job
        from supervaizer.job import Jobs
        jobs_registry = Jobs()
        active_job = None
        agent_jobs = jobs_registry.get_agent_jobs(agent.name)  # returns dict[str, Job]
        for job in agent_jobs.values():
            if hasattr(job, "status") and job.status == EntityStatus.IN_PROGRESS:
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
                "has_human_answer": agent.methods and agent.methods.human_answer is not None,
                "agents": [{"slug": a.slug, "name": a.name} for a in request.app.state.server.agents],
            },
        )

    @router.post("/agents/{slug}/workbench/start")
    async def workbench_start_job(request: Request, slug: str):
        """Start a job from the workbench — no Studio communication."""
        agent = get_agent_by_slug(request, slug)

        body = await request.json()
        parameters = body.get("parameters", {})
        fields = body.get("fields", {})

        # Set parameters via os.environ (matching agent convention)
        if agent.parameters_setup:
            for name, value in parameters.items():
                if name in agent.parameters_setup.definitions:
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
        agent_params_list = [
            {"name": k, "value": v} for k, v in parameters.items()
        ] if parameters else None

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
        params = method_params | {"fields": fields, "context": context, "agent_parameters": agent_params_list or []}

        # Run in background thread to not block the response
        loop = asyncio.get_running_loop()

        async def run_job():
            try:
                job.add_response(JobResponse(
                    job_id=job.id,
                    status=EntityStatus.IN_PROGRESS,
                    message="Starting job execution",
                    payload=None,
                ))
                result = await loop.run_in_executor(None, lambda: agent._execute(action_method, params))
                job.add_response(result)
            except Exception as e:
                log.error(f"[Workbench] Job {job.id} failed: {e}")
                job.add_response(JobResponse(
                    job_id=job.id,
                    status=EntityStatus.FAILED,
                    message=f"Job failed: {str(e)}",
                    error=e,
                ))

        asyncio.create_task(run_job())

        return JSONResponse({
            "id": job.id,
            "status": "STARTING",
            "message": "Job started from workbench",
        })

    @router.get("/agents/{slug}/workbench/jobs/{job_id}", response_class=HTMLResponse)
    async def workbench_job_monitor(request: Request, slug: str, job_id: str):
        """HTMX partial — returns execution monitor HTML for polling."""
        agent = get_agent_by_slug(request, slug)

        from supervaizer.job import Jobs
        jobs_registry = Jobs()
        job = jobs_registry.get_job(job_id, agent_name=agent.name)

        if job and job.agent_name != agent.name:
            job = None  # Don't leak cross-agent data

        if not job:
            return HTMLResponse("<div class='text-gray-500 text-sm'>Job not found</div>")

        cases = get_job_cases(job)

        # For each case, check if it's awaiting and extract HITL form data
        cases_data = []
        for case in cases:
            case_info = {
                "case": case,
                "hitl_form": None,
            }
            if hasattr(case, "status") and case.status == EntityStatus.AWAITING:
                # Find the HITL update in case.updates
                for update in reversed(case.updates):
                    if hasattr(update, "payload") and update.payload:
                        payload = update.payload
                        if isinstance(payload, dict) and "supervaizer_form" in payload:
                            case_info["hitl_form"] = payload["supervaizer_form"]
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
                "has_human_answer": agent.methods and agent.methods.human_answer is not None,
            },
        )

    @router.post("/agents/{slug}/workbench/jobs/{job_id}/stop")
    async def workbench_stop_job(request: Request, slug: str, job_id: str):
        """Stop a running job."""
        agent = get_agent_by_slug(request, slug)

        if not agent.methods or not agent.methods.job_stop:
            raise HTTPException(status_code=400, detail="Agent has no job_stop method")

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent._execute(agent.methods.job_stop.method, {"job_id": job_id}),
            )
            return JSONResponse({"status": "stopped", "message": str(result.message)})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop job: {e}")

    @router.get("/agents/{slug}/workbench/jobs/{job_id}/status")
    async def workbench_job_status(request: Request, slug: str, job_id: str):
        """Get job status via agent's job_status method."""
        agent = get_agent_by_slug(request, slug)

        if not agent.methods or not agent.methods.job_status:
            # Fall back to reading job state directly
            from supervaizer.job import Jobs
            jobs_registry = Jobs()
            job = jobs_registry.get_job(job_id, agent_name=agent.name)

            if job and job.agent_name != agent.name:
                job = None  # Don't leak cross-agent data

            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            return JSONResponse({
                "job_id": job.id,
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            })

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: agent._execute(agent.methods.job_status.method, {"job_id": job_id}),
            )
            return JSONResponse({"status": result.status.value, "message": result.message})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")

    @router.post("/agents/{slug}/workbench/jobs/{job_id}/cases/{case_id}/answer")
    async def workbench_answer_hitl(request: Request, slug: str, job_id: str, case_id: str):
        """Submit HITL answer — two-step dispatch (receive + invoke human_answer)."""
        agent = get_agent_by_slug(request, slug)

        body = await request.json()
        answer_data = body.get("answer", {})

        # Find the case
        from supervaizer.case import Cases
        cases_registry = Cases()
        case = cases_registry.get_case(case_id, job_id=job_id)

        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

        if case.status != EntityStatus.AWAITING:
            raise HTTPException(
                status_code=409,
                detail=f"Case '{case_id}' is not awaiting input (current status: {case.status})",
            )

        # Step 1: Transition case state AWAITING -> IN_PROGRESS
        update = CaseNodeUpdate(name="HITL Answer", payload=answer_data)
        case.receive_human_input(update)

        # Step 2: Invoke agent's human_answer method if defined
        if agent.methods and agent.methods.human_answer:
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
                    lambda: agent._execute(agent.methods.human_answer.method, params),
                )
            except Exception as e:
                log.error(f"[Workbench] human_answer failed for case {case_id}: {e}")
                return JSONResponse(
                    {"status": "error", "message": f"human_answer failed: {e}"},
                    status_code=500,
                )

        return JSONResponse({
            "status": "answered",
            "case_id": case_id,
            "message": "HITL answer submitted and dispatched",
        })

    @router.get("/agents/{slug}/workbench/console", response_class=HTMLResponse)
    async def workbench_console(request: Request, slug: str):
        """HTMX partial — returns recent console log entries."""
        try:
            last_index = int(request.query_params.get("last_index", 0))
        except (ValueError, TypeError):
            last_index = 0

        entries_to_send = _workbench_log_buffer[last_index:]

        return templates.TemplateResponse(
            request,
            "workbench_console.html",
            {
                "request": request,
                "entries": entries_to_send,
                "next_index": len(_workbench_log_buffer),
                "agent_slug": slug,
            },
        )

    return router
