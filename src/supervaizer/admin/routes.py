# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from supervaizer.__version__ import VERSION
from supervaizer.common import ApiError, ApiSuccess, log
from supervaizer.contracts import API_VERSION
from supervaizer.lifecycle import EntityStatus
from supervaizer.routes import get_server
from supervaizer.storage import (
    StorageManager,
)

# Global log queue for streaming
log_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()

# Log listeners — callables notified on every log entry
_log_listeners: list[Any] = []


def register_log_listener(listener: Any) -> None:
    """Register a callback(timestamp, level, message) to receive log entries."""
    if listener not in _log_listeners:
        _log_listeners.append(listener)


def add_log_to_queue(timestamp: str, level: str, message: str) -> None:
    """Add a log message to the streaming queue and notify listeners."""
    log_data = {"timestamp": timestamp, "level": level, "message": message}
    try:
        log_queue.put_nowait(log_data)
    except asyncio.QueueFull:
        pass  # Skip if queue is full
    for listener in _log_listeners:
        listener(timestamp, level, message)


# Initialize templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class AdminStats(BaseModel):
    """Statistics for admin dashboard."""

    jobs: dict[str, int]
    cases: dict[str, int]
    collections: int


class ServerStatus(BaseModel):
    """Server status and metrics."""

    status: str
    uptime: str
    uptime_seconds: int
    memory_usage: str
    memory_usage_mb: float
    memory_percent: float
    cpu_percent: float
    active_connections: int
    agents_count: int
    host: str
    port: int
    environment: str
    database_type: str
    storage_path: str


class ServerConfiguration(BaseModel):
    """Server configuration details."""

    host: str
    port: int
    api_version: str
    environment: str
    database_type: str
    storage_path: str
    agents: list[dict[str, str]]


def _is_local_mode(request: Request) -> bool:
    """True when server has no Studio registration (supervisor_account is None)."""
    live = getattr(request.app.state, "server", None)
    if live is None:
        return False
    return getattr(live, "supervisor_account", None) is None


def format_uptime(seconds: int) -> str:
    """Format uptime seconds into human readable string."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def _get_server_info(request: Request | None) -> Any | None:
    """Get server info from storage, or from live server (app.state.server) when no persistence."""
    from supervaizer.server import (
        get_server_info_from_live,
        get_server_info_from_storage,
    )

    server_info = get_server_info_from_storage()
    if server_info is not None:
        return server_info
    if request is not None:
        live = getattr(request.app.state, "server", None)
        if live is not None:
            return get_server_info_from_live(live)
    return None


def get_server_status(request: Request | None = None) -> ServerStatus:
    """Get current server status and metrics."""
    server_info = _get_server_info(request)
    if not server_info:
        raise HTTPException(
            status_code=503,
            detail="Server information not available in storage. Server may not be properly initialized.",
        )

    # Calculate uptime from stored start time
    uptime_seconds = int(time.time() - server_info.start_time)
    uptime_str = format_uptime(uptime_seconds)

    # Get memory usage
    memory = psutil.virtual_memory()
    process = psutil.Process()
    process_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Get CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # Get network connections (approximate active connections)
    try:
        connections = len(psutil.net_connections(kind="inet"))
    except (psutil.AccessDenied, OSError):
        # This is a system limitation, not a missing data issue
        connections = 0

    return ServerStatus(
        status="online",
        uptime=uptime_str,
        uptime_seconds=uptime_seconds,
        memory_usage=f"{process_memory:.1f} MB",
        memory_usage_mb=process_memory,
        memory_percent=memory.percent,
        cpu_percent=cpu_percent,
        active_connections=connections,
        agents_count=len(server_info.agents),
        host=server_info.host,
        port=server_info.port,
        environment=server_info.environment,
        database_type="TinyDB",
        storage_path=os.getenv("DATA_STORAGE_PATH", "./data"),
    )


def get_server_configuration(
    storage: StorageManager, request: Request | None = None
) -> ServerConfiguration:
    """Get server configuration details."""
    server_info = _get_server_info(request)
    if not server_info:
        raise HTTPException(
            status_code=503,
            detail="Server configuration not available in storage. Server may not be properly initialized.",
        )

    return ServerConfiguration(
        host=server_info.host,
        port=server_info.port,
        api_version=server_info.api_version,
        environment=server_info.environment,
        database_type="TinyDB",
        storage_path=str(storage.db_path.absolute()),
        agents=server_info.agents,
    )


# Sort keys each list endpoint supports, with the value used when a row lacks the key.
_JOB_SORT_DEFAULTS: dict[str, Any] = {"created_at": "", "name": "", "status": ""}
_CASE_SORT_DEFAULTS: dict[str, Any] = {**_JOB_SORT_DEFAULTS, "total_cost": 0}
_AGENT_SORT_DEFAULTS: dict[str, Any] = {"name": ""}


def _contains_text(record: dict[str, Any], term: str, fields: tuple[str, ...]) -> bool:
    """True when `term` appears, ignoring case, in any of the record's `fields`."""
    needle = term.lower()
    return any(needle in record.get(field, "").lower() for field in fields)


def _sort_rows(rows: list[dict[str, Any]], sort: str, defaults: dict[str, Any]) -> None:
    """Sort in place by `sort` ("-key" for descending); unknown keys keep the order."""
    reverse = sort.startswith("-")
    key = sort[1:] if reverse else sort
    if key in defaults:
        rows.sort(key=lambda row: row.get(key, defaults[key]), reverse=reverse)


def _paginate(
    rows: list[dict[str, Any]], skip: int, limit: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the requested page and the paging fields the table templates use."""
    total = len(rows)
    paging = {
        "total": total,
        "limit": limit,
        "skip": skip,
        "has_next": skip + limit < total,
        "has_prev": skip > 0,
    }
    return rows[skip : skip + limit], paging


def _job_matches(
    job: dict[str, Any], status: str | None, agent_name: str | None, search: str | None
) -> bool:
    if status and job.get("status") != status:
        return False
    if agent_name and agent_name.lower() not in job.get("agent_name", "").lower():
        return False
    return not search or _contains_text(job, search, ("name", "id"))


def _case_matches(
    case: dict[str, Any], status: str | None, job_id: str | None, search: str | None
) -> bool:
    if status and case.get("status") != status:
        return False
    if job_id and case.get("job_id") != job_id:
        return False
    return not search or _contains_text(case, search, ("name", "id", "description"))


def _agent_matches(
    agent: dict[str, Any],
    status: str | None,
    agent_type: str | None,
    search: str | None,
) -> bool:
    # Agents carry no status yet: every agent counts as active.
    if status and status not in ("all", "active"):
        return False
    # An agent without a type counts as "conversational".
    if agent_type and agent_type.lower() != agent.get("type", "conversational").lower():
        return False
    return not search or _contains_text(agent, search, ("name", "description"))


def _job_row(job: dict[str, Any]) -> dict[str, Any]:
    """The fields of a job the jobs table shows."""
    return {
        "id": job.get("id", ""),
        "name": job.get("name", ""),
        "agent_name": job.get("agent_name", ""),
        "status": job.get("status", ""),
        "created_at": job.get("created_at", ""),
        "finished_at": job.get("finished_at"),
        "case_count": len(job.get("case_ids", [])),
    }


def _case_row(case: dict[str, Any]) -> dict[str, Any]:
    """The fields of a case the cases table shows."""
    return {
        "id": case.get("id", ""),
        "name": case.get("name", ""),
        "description": case.get("description", ""),
        "status": case.get("status", ""),
        "job_id": case.get("job_id", ""),
        "created_at": case.get("created_at", ""),
        "finished_at": case.get("finished_at"),
        "total_cost": case.get("total_cost", 0.0),
    }


def _sse_event(entry: dict[str, str]) -> str:
    return f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"


def _system_entry(level: str, message: str) -> dict[str, str]:
    return {"timestamp": datetime.now().isoformat(), "level": level, "message": message}


def _log_entry(item: Any) -> dict[str, str]:
    """A queued item as a log entry; anything that is not a dict becomes an INFO message."""
    return item if isinstance(item, dict) else _system_entry("INFO", str(item))


async def _log_events() -> AsyncGenerator[str, None]:
    """Server-Sent Events: a hello, the queued backlog, then live entries and keep-alives."""
    try:
        yield _sse_event(_system_entry("INFO", "Log stream connected"))

        # Send any existing messages in the queue
        while not log_queue.empty():
            try:
                event = _sse_event(_log_entry(log_queue.get_nowait()))
            except Exception:  # QueueEmpty or an entry that cannot be serialized
                break
            yield event

        # Keep alive and wait for new messages
        while True:
            try:
                item = await asyncio.wait_for(log_queue.get(), timeout=30.0)
                yield _sse_event(_log_entry(item))
            except TimeoutError:
                yield _sse_event(_system_entry("SYSTEM", "keepalive"))

    except asyncio.CancelledError:
        pass  # Client disconnected
    except Exception as e:
        yield _sse_event(_system_entry("ERROR", f"Log stream error: {e!s}"))


@contextmanager
def _http_errors(label: str, *, keep_http: bool = True) -> Iterator[None]:
    """Log an unexpected error and answer 500 with its message.

    An HTTPException passes through unchanged when `keep_http` is true.
    """
    try:
        yield
    except Exception as e:
        if keep_http and isinstance(e, HTTPException):
            raise
        log.error(f"{label} error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _resolve_server(request: Request) -> Any | None:
    """The live server: `app.state.server` (set at launch), else the dependency override."""
    server = getattr(request.app.state, "server", None)
    if server is not None:
        return server
    get_current = request.app.dependency_overrides.get(get_server)
    if get_current is None:
        return None
    try:
        return await get_current()
    except (NotImplementedError, TypeError):
        return None


def _registration_response(result: ApiSuccess | ApiError) -> JSONResponse:
    """200 when Studio accepted the registration, 502 when it refused it."""
    if isinstance(result, ApiSuccess):
        status_code, success = 200, True
    else:
        status_code, success = 502, False
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,
            "message": result.message,
            "detail": getattr(result, "detail", None),
        },
    )


def _list_page(request: Request, template: str) -> Response:
    """A list page shell; the rows load through the /api endpoints."""
    return templates.TemplateResponse(
        request,
        template,
        {
            "request": request,
            "api_version": API_VERSION,
            "local_mode": _is_local_mode(request),
        },
    )


_FINISHED_STATUSES = ("completed", "failed", "cancelled")


def _set_status(
    storage: StorageManager, kind: str, entity_id: str, status_data: dict[str, str]
) -> dict[str, str]:
    """Set the status of a stored Job or Case; a final status also stamps finished_at."""
    new_status = status_data.get("status")
    if not new_status or new_status not in [s.value for s in EntityStatus]:
        raise HTTPException(status_code=400, detail="Invalid status")

    entity = storage.get_object_by_id(kind, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"{kind} not found")

    entity["status"] = new_status
    if new_status in _FINISHED_STATUSES:
        entity["finished_at"] = datetime.now().isoformat()
    storage.save_object(kind, entity)
    return {"message": f"{kind} status updated successfully"}


class AdminHandlers:
    """Request handlers of the admin router, bound to one storage manager."""

    def __init__(self, storage: StorageManager) -> None:
        self.storage = storage
        self.static_dir = Path(__file__).parent / "static"

    async def admin_dashboard(self, request: Request) -> Response:
        """Admin dashboard page."""
        with _http_errors("Admin dashboard", keep_http=False):
            # Get stats
            stats = get_dashboard_stats(self.storage)

            return templates.TemplateResponse(
                request,
                "dashboard.html",
                {
                    "request": request,
                    "api_version": VERSION,
                    "stats": stats,
                    "system_status": "Online",
                    "db_name": "TinyDB",
                    "data_storage_path": str(self.storage.db_path.absolute()),
                    "local_mode": _is_local_mode(request),
                    "server_id": os.getenv("SUPERVAIZER_SERVER_ID"),
                },
            )

    async def admin_jobs_page(self, request: Request) -> Response:
        """Jobs management page."""
        return _list_page(request, "jobs_list.html")

    async def admin_cases_page(self, request: Request) -> Response:
        """Cases management page."""
        return _list_page(request, "cases_list.html")

    async def admin_server_page(self, request: Request) -> Response:
        """Server status and configuration page."""
        with _http_errors("Admin server page", keep_http=False):
            # Get initial server data (from storage or live when no persistence)
            server_status = get_server_status(request)
            server_config = get_server_configuration(self.storage, request)

            return templates.TemplateResponse(
                request,
                "server.html",
                {
                    "request": request,
                    "api_version": VERSION,
                    "server_status": server_status,
                    "server_config": server_config,
                    "local_mode": _is_local_mode(request),
                },
            )

    async def admin_agents_page(self, request: Request) -> Response:
        """Agents management page."""
        try:
            server_info = _get_server_info(request)
            if not server_info:
                raise HTTPException(
                    status_code=503, detail="Server information not available"
                )

            return templates.TemplateResponse(
                request,
                "agents.html",
                {
                    "request": request,
                    "api_version": VERSION,
                    "agents": server_info.agents,
                    "local_mode": _is_local_mode(request),
                },
            )
        except Exception as e:
            log.error(f"Admin agents page error: {e}")
            raise HTTPException(
                status_code=503, detail="Server information unavailable"
            ) from e

    async def serve_static(self, file_path: str) -> Response:
        """Serve static files from the admin static directory."""
        full_path = self.static_dir / file_path
        if not full_path.is_file() or not full_path.resolve().is_relative_to(
            self.static_dir.resolve()
        ):
            raise HTTPException(status_code=404, detail="File not found")
        suffix = full_path.suffix.lower()
        media_types = {
            ".js": "application/javascript",
            ".css": "text/css",
            ".html": "text/html",
        }
        return Response(
            content=full_path.read_bytes(),
            media_type=media_types.get(suffix, "application/octet-stream"),
        )

    async def admin_console_page(self, request: Request) -> Response:
        """Interactive console page — access enforced by Tailscale at router level."""
        return templates.TemplateResponse(
            request,
            "console.html",
            {"request": request},
        )

    async def get_stats(self) -> AdminStats:
        """Get system statistics."""
        return get_dashboard_stats(self.storage)

    async def get_server_status_api(self, request: Request) -> Response:
        """Get current server status for HTMX refresh."""
        with _http_errors("Get server status API", keep_http=False):
            server_status = get_server_status(request)

            return templates.TemplateResponse(
                request,
                "server_status_cards.html",
                {
                    "request": request,
                    "server_status": server_status,
                },
            )

    async def register_server_with_supervisor(self, request: Request) -> JSONResponse:
        """Trigger SERVER_REGISTER to the supervaizer supervisor (no frontend API key; backend sends to SUPERVAIZE_API_URL)."""
        with _http_errors("Server register API"):
            server = await _resolve_server(request)
            if server is None:
                raise HTTPException(
                    status_code=503,
                    detail="Server instance not available (admin not running with live server)",
                )
            if not getattr(server, "supervisor_account", None):
                raise HTTPException(
                    status_code=503,
                    detail="No supervisor account configured",
                )
            result = await server.supervisor_account.register_server(server=server)
            return _registration_response(result)

    async def get_agents_api(
        self,
        request: Request,
        status: str | None = Query(None),
        agent_type: str | None = Query(None),
        search: str | None = Query(None),
        sort: str = Query("-created_at"),
    ) -> Response:
        """Get agents with filtering for HTMX refresh."""
        with _http_errors("Get agents API", keep_http=False):
            server_info = _get_server_info(request)
            if not server_info:
                raise HTTPException(
                    status_code=503, detail="Server information not available"
                )

            agents = [
                a
                for a in server_info.agents
                if _agent_matches(a, status, agent_type, search)
            ]
            _sort_rows(agents, sort, _AGENT_SORT_DEFAULTS)

            return templates.TemplateResponse(
                request,
                "agents_grid.html",
                {"request": request, "agents": agents},
            )

    async def get_agent_details(
        self,
        request: Request,
        agent_slug: str,
    ) -> Response:
        """Get detailed agent information."""
        with _http_errors("Get agent details"):
            server_info = _get_server_info(request)
            if not server_info:
                raise HTTPException(
                    status_code=503, detail="Server information not available"
                )

            # Find the agent by slug
            agent = None
            for a in server_info.agents:
                if a.get("slug") == agent_slug:
                    agent = a
                    break

            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            return templates.TemplateResponse(
                request,
                "agent_detail.html",
                {
                    "request": request,
                    "agent": agent,
                },
            )

    async def get_jobs_api(
        self,
        request: Request,
        status: str | None = Query(None),
        agent_name: str | None = Query(None),
        search: str | None = Query(None),
        sort: str = Query("-created_at"),
        limit: int = Query(50, le=100),
        skip: int = Query(0, ge=0),
    ) -> Response:
        """Get jobs with filtering and pagination."""
        with _http_errors("Get jobs API", keep_http=False):
            jobs = [
                j
                for j in self.storage.get_objects("Job")
                if _job_matches(j, status, agent_name, search)
            ]
            _sort_rows(jobs, sort, _JOB_SORT_DEFAULTS)
            jobs_page, paging = _paginate(jobs, skip, limit)

            return templates.TemplateResponse(
                request,
                "jobs_table.html",
                {
                    "request": request,
                    "jobs": [_job_row(j) for j in jobs_page],
                    **paging,
                },
            )

    async def get_job_details(self, request: Request, job_id: str) -> Response:
        """Get detailed job information."""
        with _http_errors("Get job details"):
            job_data = self.storage.get_object_by_id("Job", job_id)
            if not job_data:
                raise HTTPException(status_code=404, detail="Job not found")

            # Get related cases
            cases_data = self.storage.get_cases_for_job(job_id)

            return templates.TemplateResponse(
                request,
                "job_detail.html",
                {
                    "request": request,
                    "job": job_data,
                    "cases": cases_data,
                },
            )

    async def get_cases_api(
        self,
        request: Request,
        status: str | None = Query(None),
        job_id: str | None = Query(None),
        search: str | None = Query(None),
        sort: str = Query("-created_at"),
        limit: int = Query(50, le=100),
        skip: int = Query(0, ge=0),
    ) -> Response:
        """Get cases with filtering and pagination."""
        with _http_errors("Get cases API", keep_http=False):
            cases = [
                c
                for c in self.storage.get_objects("Case")
                if _case_matches(c, status, job_id, search)
            ]
            _sort_rows(cases, sort, _CASE_SORT_DEFAULTS)
            cases_page, paging = _paginate(cases, skip, limit)

            return templates.TemplateResponse(
                request,
                "cases_table.html",
                {
                    "request": request,
                    "cases": [_case_row(c) for c in cases_page],
                    **paging,
                },
            )

    async def get_case_details(self, request: Request, case_id: str) -> Response:
        """Get detailed case information."""
        with _http_errors("Get case details"):
            case_data = self.storage.get_object_by_id("Case", case_id)
            if not case_data:
                raise HTTPException(status_code=404, detail="Case not found")

            # Get parent job if exists
            job_data = None
            if case_data.get("job_id"):
                job_data = self.storage.get_object_by_id("Job", case_data["job_id"])

            return templates.TemplateResponse(
                request,
                "case_detail.html",
                {
                    "request": request,
                    "case": case_data,
                    "job": job_data,
                },
            )

    async def update_job_status(
        self,
        job_id: str,
        status_data: dict[str, str],
    ) -> dict[str, str]:
        """Update job status."""
        with _http_errors("Update job status"):
            return _set_status(self.storage, "Job", job_id, status_data)

    async def update_case_status(
        self,
        case_id: str,
        status_data: dict[str, str],
    ) -> dict[str, str]:
        """Update case status."""
        with _http_errors("Update case status"):
            return _set_status(self.storage, "Case", case_id, status_data)

    async def delete_job(self, job_id: str) -> dict[str, str]:
        """Delete a job and its related cases."""
        with _http_errors("Delete job"):
            # Delete related cases first
            cases_data = self.storage.get_cases_for_job(job_id)
            for case_data in cases_data:
                self.storage.delete_object("Case", case_data["id"])

            # Delete the job
            deleted = self.storage.delete_object("Job", job_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Job not found")

            return {"message": "Job and related cases deleted successfully"}

    async def delete_case(self, case_id: str) -> dict[str, str]:
        """Delete a case."""
        with _http_errors("Delete case"):
            deleted = self.storage.delete_object("Case", case_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Case not found")

            return {"message": "Case deleted successfully"}

    async def get_recent_activity(self, request: Request) -> Response:
        """Get recent entity activity."""
        with _http_errors("Get recent activity", keep_http=False):
            # Get recent jobs and cases
            recent_jobs = self.storage.get_objects("Job")[-5:]  # Last 5 jobs
            recent_cases = self.storage.get_objects("Case")[-5:]  # Last 5 cases

            # Combine and sort by created_at
            activities = []
            for job in recent_jobs:
                activities.append({
                    "type": "job",
                    "id": job.get("id"),
                    "name": job.get("name"),
                    "status": job.get("status"),
                    "created_at": job.get("created_at"),
                    "agent_name": job.get("agent_name"),
                })

            for case in recent_cases:
                activities.append({
                    "type": "case",
                    "id": case.get("id"),
                    "name": case.get("name"),
                    "status": case.get("status"),
                    "created_at": case.get("created_at"),
                    "job_id": case.get("job_id"),
                })

            # Sort by created_at descending
            activities.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
            activities = activities[:10]  # Top 10 recent activities

            return templates.TemplateResponse(
                request,
                "recent_activity.html",
                {
                    "request": request,
                    "activities": activities,
                },
            )

    async def log_stream(self) -> EventSourceResponse:
        """Stream log messages via Server-Sent Events."""
        return EventSourceResponse(_log_events())

    async def test_log(self) -> dict[str, str]:
        """Test endpoint to generate a log message."""
        test_message = f"Test log message generated at {datetime.now().isoformat()}"
        add_log_to_queue(
            timestamp=datetime.now().isoformat(), level="INFO", message=test_message
        )

        # Also test the loguru logger directly
        log.info(f"Direct loguru test message: {test_message}")

        return {"message": "Test log added to queue"}

    async def test_loguru(self) -> dict[str, str]:
        """Test endpoint to generate loguru messages."""
        log.info("Testing loguru INFO message")
        log.warning("Testing loguru WARNING message")
        log.error("Testing loguru ERROR message")
        return {"message": "Loguru test messages sent"}

    async def debug_queue(self) -> dict[str, Any]:
        """Debug endpoint to check log queue status."""
        queue_size = log_queue.qsize()

        # Add a test message directly to queue
        add_log_to_queue(
            timestamp=datetime.now().isoformat(),
            level="DEBUG",
            message="Direct queue test message",
        )

        return {
            "queue_size_before": queue_size,
            "queue_size_after": log_queue.qsize(),
            "message": "Test message added to queue",
        }

    async def execute_console_command(
        self,
        request: Request,
        command_data: dict[str, str],
    ) -> dict[str, str]:
        """Execute a console command — access enforced by Tailscale at router level."""

        command = command_data.get("command", "").strip()
        if not command:
            return {"status": "error", "message": "No command provided"}

        # Add command to log stream
        add_log_to_queue(
            timestamp=datetime.now().isoformat(), level="USER", message=f"$ {command}"
        )

        # Process the command
        try:
            result = await process_console_command(command)
            # Add result to log stream
            add_log_to_queue(
                timestamp=datetime.now().isoformat(),
                level=result.get("level", "INFO"),
                message=result.get("message", "Command executed"),
            )
            return {"status": "success", "message": "Command executed"}
        except Exception as e:
            add_log_to_queue(
                timestamp=datetime.now().isoformat(),
                level="ERROR",
                message=f"Command execution failed: {e!s}",
            )
            return {"status": "error", "message": str(e)}


# (HTTP method, path, AdminHandlers method name, extra add_api_route options).
# Order matters: FastAPI matches the first route that fits.
_ADMIN_ROUTES: list[tuple[str, str, str, dict[str, Any]]] = [
    ("GET", "/", "admin_dashboard", {"response_class": HTMLResponse}),
    ("GET", "/jobs", "admin_jobs_page", {"response_class": HTMLResponse}),
    ("GET", "/cases", "admin_cases_page", {"response_class": HTMLResponse}),
    ("GET", "/server", "admin_server_page", {"response_class": HTMLResponse}),
    ("GET", "/agents", "admin_agents_page", {"response_class": HTMLResponse}),
    ("GET", "/static/{file_path:path}", "serve_static", {}),
    ("GET", "/console", "admin_console_page", {"response_class": HTMLResponse}),
    ("GET", "/api/stats", "get_stats", {}),
    ("GET", "/api/server/status", "get_server_status_api", {}),
    ("POST", "/api/server/register", "register_server_with_supervisor", {}),
    ("GET", "/api/agents", "get_agents_api", {}),
    ("GET", "/api/agents/{agent_slug}", "get_agent_details", {}),
    ("GET", "/api/jobs", "get_jobs_api", {}),
    ("GET", "/api/jobs/{job_id}", "get_job_details", {}),
    ("GET", "/api/cases", "get_cases_api", {}),
    ("GET", "/api/cases/{case_id}", "get_case_details", {}),
    ("POST", "/api/jobs/{job_id}/status", "update_job_status", {}),
    ("POST", "/api/cases/{case_id}/status", "update_case_status", {}),
    ("DELETE", "/api/jobs/{job_id}", "delete_job", {}),
    ("DELETE", "/api/cases/{case_id}", "delete_case", {}),
    ("GET", "/api/recent-activity", "get_recent_activity", {}),
    ("GET", "/log-stream", "log_stream", {}),
    ("GET", "/test-log", "test_log", {}),
    ("GET", "/test-loguru", "test_loguru", {}),
    ("GET", "/debug-queue", "debug_queue", {}),
    ("POST", "/api/console/execute", "execute_console_command", {}),
]


def create_admin_routes() -> APIRouter:
    """Create and configure admin routes."""
    router = APIRouter(tags=["admin"])
    handlers = AdminHandlers(StorageManager())
    for method, route_path, name, options in _ADMIN_ROUTES:
        router.add_api_route(
            route_path, getattr(handlers, name), methods=[method], **options
        )

    # Include workbench sub-router
    from supervaizer.admin.workbench_routes import create_workbench_routes

    # Tailscale covers both HTTP and WS, so no extra dependency here.
    router.include_router(create_workbench_routes())
    # WebSocket routes are included in private_router (routers/private.py)

    return router


def get_dashboard_stats(storage: StorageManager) -> AdminStats:
    """Get statistics for dashboard."""
    try:
        # Get all jobs and cases
        all_jobs = storage.get_objects("Job")
        all_cases = storage.get_objects("Case")

        # Calculate job stats
        job_total = len(all_jobs)
        job_running = len([
            j for j in all_jobs if j.get("status") in ["in_progress", "awaiting"]
        ])
        job_completed = len([j for j in all_jobs if j.get("status") == "completed"])
        job_failed = len([
            j for j in all_jobs if j.get("status") in ["failed", "cancelled"]
        ])

        # Calculate case stats
        case_total = len(all_cases)
        case_running = len([
            c for c in all_cases if c.get("status") in ["in_progress", "awaiting"]
        ])
        case_completed = len([c for c in all_cases if c.get("status") == "completed"])
        case_failed = len([
            c for c in all_cases if c.get("status") in ["failed", "cancelled"]
        ])

        # TinyDB collections count (tables)
        collections_count = len(storage._db.tables())

        return AdminStats(
            jobs={
                "total": job_total,
                "running": job_running,
                "completed": job_completed,
                "failed": job_failed,
            },
            cases={
                "total": case_total,
                "running": case_running,
                "completed": case_completed,
                "failed": case_failed,
            },
            collections=collections_count,
        )

    except Exception as e:
        log.error(f"Get dashboard stats error: {e}")
        return AdminStats(
            jobs={"total": 0, "running": 0, "completed": 0, "failed": 0},
            cases={"total": 0, "running": 0, "completed": 0, "failed": 0},
            collections=0,
        )


def _info(message: str) -> dict[str, str]:
    return {"level": "INFO", "message": message}


def _server_info_command() -> dict[str, str]:
    status = get_server_status()
    return _info(
        f"Server: {status.status} | Uptime: {status.uptime} | CPU: {status.cpu_percent:.1f}% | Memory: {status.memory_usage}"
    )


def _memory_command() -> dict[str, str]:
    status = get_server_status()
    return _info(f"Memory Usage: {status.memory_usage} ({status.memory_percent:.1f}%)")


def _uptime_command() -> dict[str, str]:
    status = get_server_status()
    return _info(f"Server uptime: {status.uptime} ({status.uptime_seconds} seconds)")


def _debug_command() -> dict[str, str]:
    environment = os.getenv("SUPERVAIZER_ENVIRONMENT", "dev")
    return {
        "level": "DEBUG",
        "message": f"Environment: {environment} | API Version: {API_VERSION}",
    }


def _test_log_command() -> dict[str, str]:
    add_log_to_queue(
        timestamp=datetime.now().isoformat(),
        level="INFO",
        message="This is a test log message from console command",
    )
    return {"level": "SUCCESS", "message": "Test log message sent"}


_CONSOLE_COMMANDS: dict[str, Callable[[], dict[str, str]]] = {
    "help": lambda: _info(
        "Available commands: status, help, clear, reconnect, debug, server-info, memory, uptime"
    ),
    "status": lambda: _info("Server is running and log stream is active"),
    "server-info": _server_info_command,
    "memory": _memory_command,
    "uptime": _uptime_command,
    "debug": _debug_command,
    "clear": lambda: {"level": "SYSTEM", "message": "Console cleared"},
    "test-log": _test_log_command,
}


async def process_console_command(command: str) -> dict[str, str]:
    """Process a console command and return the result."""
    handler = _CONSOLE_COMMANDS.get(command.lower().strip())
    if handler is None:
        return {
            "level": "ERROR",
            "message": f"Unknown command: {command}. Type 'help' for available commands.",
        }
    try:
        return handler()
    except Exception as e:
        return {"level": "ERROR", "message": f"Command processing error: {e!s}"}
