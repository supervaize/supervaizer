# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
)  # <-- MODIFIED: removed Depends, Security
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from supervaizer.__version__ import VERSION
from supervaizer.common import log
from supervaizer.contracts import API_VERSION
from supervaizer.lifecycle import EntityStatus
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


# Server start time for uptime calculation
# This will be set when the server actually starts
SERVER_START_TIME = time.time()


def set_server_start_time(start_time: float) -> None:
    """Set the server start time for uptime calculation."""
    global SERVER_START_TIME
    SERVER_START_TIME = start_time


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
# <-- REMOVED: api_key_header / APIKeyHeader (Tailscale enforced at router level)


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


class EntityFilter(BaseModel):
    """Filter parameters for entity queries."""

    status: str | None = None
    agent_name: str | None = None
    search: str | None = None
    sort: str = "-created_at"
    limit: int = 50
    skip: int = 0


def _is_local_mode(request: Request) -> bool:
    """True when server has no Studio registration (supervisor_account is None)."""
    live = getattr(request.app.state, "server", None)
    if live is None:
        return False
    return getattr(live, "supervisor_account", None) is None


# <-- REMOVED: verify_admin_access (Tailscale enforced at router level in private_router)


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


class AdminHandlers:
    """Request handlers of the admin router, bound to one storage manager."""

    def __init__(self, storage: StorageManager) -> None:
        self.storage = storage
        self.static_dir = Path(__file__).parent / "static"

    async def admin_dashboard(self, request: Request) -> Response:
        """Admin dashboard page."""
        try:
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
        except Exception as e:
            log.error(f"Admin dashboard error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def admin_jobs_page(self, request: Request) -> Response:
        """Jobs management page."""
        return templates.TemplateResponse(
            request,
            "jobs_list.html",
            {
                "request": request,
                "api_version": API_VERSION,
                "local_mode": _is_local_mode(request),
            },
        )

    async def admin_cases_page(self, request: Request) -> Response:
        """Cases management page."""
        return templates.TemplateResponse(
            request,
            "cases_list.html",
            {
                "request": request,
                "api_version": API_VERSION,
                "local_mode": _is_local_mode(request),
            },
        )

    async def admin_server_page(self, request: Request) -> Response:
        """Server status and configuration page."""
        try:
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
        except Exception as e:
            log.error(f"Admin server page error: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

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
        # <-- MODIFIED: removed console token generation; Tailscale is the gate
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
        try:
            server_status = get_server_status(request)

            return templates.TemplateResponse(
                request,
                "server_status_cards.html",
                {
                    "request": request,
                    "server_status": server_status,
                },
            )
        except Exception as e:
            log.error(f"Get server status API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def register_server_with_supervisor(self, request: Request) -> JSONResponse:
        """Trigger SERVER_REGISTER to the supervaizer supervisor (no frontend API key; backend sends to SUPERVAIZE_API_URL)."""
        try:
            from supervaizer.common import ApiSuccess
            from supervaizer.routes import get_server

            # Prefer app.state.server (set at launch), else dependency override
            server = getattr(request.app.state, "server", None)
            if server is None:
                get_current = request.app.dependency_overrides.get(get_server)
                if get_current is not None:
                    try:
                        server = await get_current()
                    except (NotImplementedError, TypeError):
                        pass
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
            if isinstance(result, ApiSuccess):
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": result.message,
                        "detail": result.detail,
                    },
                )
            # ApiError
            return JSONResponse(
                status_code=502,
                content={
                    "success": False,
                    "message": result.message,
                    "detail": getattr(result, "detail", None),
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Server register API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_agents_api(
        self,
        request: Request,
        status: str | None = Query(None),
        agent_type: str | None = Query(None),
        search: str | None = Query(None),
        sort: str = Query("-created_at"),
    ) -> Response:
        """Get agents with filtering for HTMX refresh."""
        try:
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

        except Exception as e:
            log.error(f"Get agents API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_agent_details(
        self,
        request: Request,
        agent_slug: str,
    ) -> Response:
        """Get detailed agent information."""
        try:
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

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Get agent details error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

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
        try:
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

        except Exception as e:
            log.error(f"Get jobs API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_job_details(self, request: Request, job_id: str) -> Response:
        """Get detailed job information."""
        try:
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

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Get job details error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

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
        try:
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

        except Exception as e:
            log.error(f"Get cases API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_case_details(self, request: Request, case_id: str) -> Response:
        """Get detailed case information."""
        try:
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

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Get case details error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def update_job_status(
        self,
        job_id: str,
        status_data: dict[str, str],
    ) -> dict[str, str]:
        """Update job status."""
        try:
            new_status = status_data.get("status")
            if not new_status or new_status not in [s.value for s in EntityStatus]:
                raise HTTPException(status_code=400, detail="Invalid status")

            job_data = self.storage.get_object_by_id("Job", job_id)
            if not job_data:
                raise HTTPException(status_code=404, detail="Job not found")

            # Update job status
            job_data["status"] = new_status
            if new_status in ["completed", "failed", "cancelled"]:
                job_data["finished_at"] = datetime.now().isoformat()

            self.storage.save_object("Job", job_data)

            return {"message": "Job status updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Update job status error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def update_case_status(
        self,
        case_id: str,
        status_data: dict[str, str],
    ) -> dict[str, str]:
        """Update case status."""
        try:
            new_status = status_data.get("status")
            if not new_status or new_status not in [s.value for s in EntityStatus]:
                raise HTTPException(status_code=400, detail="Invalid status")

            case_data = self.storage.get_object_by_id("Case", case_id)
            if not case_data:
                raise HTTPException(status_code=404, detail="Case not found")

            # Update case status
            case_data["status"] = new_status
            if new_status in ["completed", "failed", "cancelled"]:
                case_data["finished_at"] = datetime.now().isoformat()

            self.storage.save_object("Case", case_data)

            return {"message": "Case status updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Update case status error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def delete_job(self, job_id: str) -> dict[str, str]:
        """Delete a job and its related cases."""
        try:
            # Delete related cases first
            cases_data = self.storage.get_cases_for_job(job_id)
            for case_data in cases_data:
                self.storage.delete_object("Case", case_data["id"])

            # Delete the job
            deleted = self.storage.delete_object("Job", job_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Job not found")

            return {"message": "Job and related cases deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Delete job error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def delete_case(self, case_id: str) -> dict[str, str]:
        """Delete a case."""
        try:
            deleted = self.storage.delete_object("Case", case_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Case not found")

            return {"message": "Case deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Delete case error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_recent_activity(self, request: Request) -> Response:
        """Get recent entity activity."""
        try:
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

        except Exception as e:
            log.error(f"Get recent activity error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def log_stream(
        self,
    ) -> (
        EventSourceResponse
    ):  # <-- MODIFIED: removed token/key params; Tailscale is the gate
        """Stream log messages via Server-Sent Events."""

        async def generate_log_events() -> AsyncGenerator[str, None]:
            try:
                # Send connection message immediately
                test_message = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": "Log stream connected",
                }
                yield f"data: {json.dumps(test_message, ensure_ascii=False)}\n\n"

                # Send any existing messages in the queue
                while not log_queue.empty():
                    try:
                        log_message = log_queue.get_nowait()
                        if isinstance(log_message, dict):
                            event_data = json.dumps(log_message, ensure_ascii=False)
                            yield f"data: {event_data}\n\n"
                        else:
                            fallback_message = {
                                "timestamp": datetime.now().isoformat(),
                                "level": "INFO",
                                "message": str(log_message),
                            }
                            event_data = json.dumps(
                                fallback_message, ensure_ascii=False
                            )
                            yield f"data: {event_data}\n\n"
                    except Exception:  # QueueEmpty or any other exception
                        break

                # Keep alive and wait for new messages
                while True:
                    try:
                        # Wait for a log message with timeout to send keep-alive
                        log_message = await asyncio.wait_for(
                            log_queue.get(), timeout=30.0
                        )

                        if isinstance(log_message, dict):
                            event_data = json.dumps(log_message, ensure_ascii=False)
                            yield f"data: {event_data}\n\n"
                        else:
                            fallback_message = {
                                "timestamp": datetime.now().isoformat(),
                                "level": "INFO",
                                "message": str(log_message),
                            }
                            event_data = json.dumps(
                                fallback_message, ensure_ascii=False
                            )
                            yield f"data: {event_data}\n\n"
                    except TimeoutError:
                        # Send keep-alive message
                        keepalive_message = {
                            "timestamp": datetime.now().isoformat(),
                            "level": "SYSTEM",
                            "message": "keepalive",
                        }
                        yield f"data: {json.dumps(keepalive_message, ensure_ascii=False)}\n\n"

            except asyncio.CancelledError:
                # Client disconnected
                pass
            except Exception as e:
                # Send error and close
                try:
                    error_data = json.dumps(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "level": "ERROR",
                            "message": f"Log stream error: {e!s}",
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {error_data}\n\n"
                except Exception:
                    # If even error formatting fails, just close
                    pass

        return EventSourceResponse(generate_log_events())

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
        # <-- MODIFIED: removed token parameter; Tailscale is the gate

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

    # <-- MODIFIED: removed verify_admin_access dep; Tailscale covers both HTTP and WS
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


async def process_console_command(command: str) -> dict[str, str]:
    """Process a console command and return the result."""
    cmd = command.lower().strip()

    try:
        if cmd == "help":
            return {
                "level": "INFO",
                "message": "Available commands: status, help, clear, reconnect, debug, server-info, memory, uptime",
            }

        elif cmd == "status":
            return {
                "level": "INFO",
                "message": "Server is running and log stream is active",
            }

        elif cmd == "server-info":
            server_status = get_server_status()
            return {
                "level": "INFO",
                "message": f"Server: {server_status.status} | Uptime: {server_status.uptime} | CPU: {server_status.cpu_percent:.1f}% | Memory: {server_status.memory_usage}",
            }

        elif cmd == "memory":
            server_status = get_server_status()
            return {
                "level": "INFO",
                "message": f"Memory Usage: {server_status.memory_usage} ({server_status.memory_percent:.1f}%)",
            }

        elif cmd == "uptime":
            server_status = get_server_status()
            return {
                "level": "INFO",
                "message": f"Server uptime: {server_status.uptime} ({server_status.uptime_seconds} seconds)",
            }

        elif cmd == "debug":
            return {
                "level": "DEBUG",
                "message": f"Environment: {os.getenv('SUPERVAIZER_ENVIRONMENT', 'dev')} | API Version: {API_VERSION}",
            }

        elif cmd == "clear":
            return {"level": "SYSTEM", "message": "Console cleared"}

        elif cmd == "test-log":
            # Add a test log message
            add_log_to_queue(
                timestamp=datetime.now().isoformat(),
                level="INFO",
                message="This is a test log message from console command",
            )
            return {"level": "SUCCESS", "message": "Test log message sent"}

        else:
            return {
                "level": "ERROR",
                "message": f"Unknown command: {command}. Type 'help' for available commands.",
            }

    except Exception as e:
        return {"level": "ERROR", "message": f"Command processing error: {e!s}"}


# <-- REMOVED: generate_console_token, validate_console_token, cleanup_expired_tokens
# (console token system removed; Tailscale is the sole gate for /manage routes)
