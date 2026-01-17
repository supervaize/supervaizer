# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import psutil
from fastapi import APIRouter, HTTPException, Query, Request, Security
from fastapi.responses import HTMLResponse, Response
from fastapi.security import APIKeyHeader
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from supervaizer.__version__ import API_VERSION, VERSION
from supervaizer.common import log
from supervaizer.lifecycle import EntityStatus
from supervaizer.storage import (
    StorageManager,
    create_case_repository,
    create_job_repository,
)

# Global log queue for streaming
log_queue: asyncio.Queue[Dict[str, str]] = asyncio.Queue()

# Server start time for uptime calculation
# This will be set when the server actually starts
SERVER_START_TIME = time.time()

# Console token storage (in production, use Redis or database)
_console_tokens: Dict[str, float] = {}  # token -> expiry_timestamp


def set_server_start_time(start_time: float) -> None:
    """Set the server start time for uptime calculation."""
    global SERVER_START_TIME
    SERVER_START_TIME = start_time


def add_log_to_queue(timestamp: str, level: str, message: str) -> None:
    """Add a log message to the streaming queue."""
    try:
        log_data = {"timestamp": timestamp, "level": level, "message": message}
        # Non-blocking put - if queue is full, skip the message
        try:
            log_queue.put_nowait(log_data)
        except asyncio.QueueFull:
            pass  # Skip if queue is full
    except Exception:
        pass  # Silently ignore errors to avoid breaking logging


# Initialize templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# API key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AdminStats(BaseModel):
    """Statistics for admin dashboard."""

    jobs: Dict[str, int]
    cases: Dict[str, int]
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
    agents: List[Dict[str, str]]


class EntityFilter(BaseModel):
    """Filter parameters for entity queries."""

    status: Optional[str] = None
    agent_name: Optional[str] = None
    search: Optional[str] = None
    sort: str = "-created_at"
    limit: int = 50
    skip: int = 0


async def verify_admin_access(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    key: Optional[str] = Query(None),
) -> bool:
    """Verify admin access via API key in header or query parameter."""
    # First try header authentication
    if api_key:
        expected_key = os.getenv("SUPERVAIZER_API_KEY")
        if expected_key is None:
            expected_key = "admin-secret-key-123"

        if api_key == expected_key:
            return True

    # For browser access, try query parameter
    if key:
        expected_key = os.getenv("SUPERVAIZER_API_KEY")
        if expected_key is None:
            expected_key = "admin-secret-key-123"

        if key == expected_key:
            return True

    raise HTTPException(
        status_code=403,
        detail="Invalid API key. Provide via X-API-Key header or ?key=<api_key> parameter",
        headers={"WWW-Authenticate": "APIKey"},
    )


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


def get_server_status() -> ServerStatus:
    """Get current server status and metrics."""
    # Get server info from storage - required, no fallback
    from supervaizer.server import get_server_info_from_storage

    server_info = get_server_info_from_storage()
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


def get_server_configuration(storage: StorageManager) -> ServerConfiguration:
    """Get server configuration details."""
    # Get server info from storage - required, no fallback
    from supervaizer.server import get_server_info_from_storage

    server_info = get_server_info_from_storage()
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


def create_admin_routes() -> APIRouter:
    """Create and configure admin routes."""
    router = APIRouter(tags=["admin"])

    # Initialize storage manager
    storage = StorageManager()
    _job_repo = create_job_repository()
    _case_repo = create_case_repository()

    @router.get("/", response_class=HTMLResponse)
    async def admin_dashboard(request: Request) -> Response:
        """Admin dashboard page."""
        try:
            # Get stats
            stats = get_dashboard_stats(storage)

            return templates.TemplateResponse(
                request,
                "dashboard.html",
                {
                    "request": request,
                    "api_version": VERSION,
                    "stats": stats,
                    "system_status": "Online",
                    "db_name": "TinyDB",
                    "data_storage_path": str(storage.db_path.absolute()),
                    "api_key": os.getenv("SUPERVAIZER_API_KEY"),
                },
            )
        except Exception as e:
            log.error(f"Admin dashboard error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/jobs", response_class=HTMLResponse)
    async def admin_jobs_page(request: Request) -> Response:
        """Jobs management page."""
        return templates.TemplateResponse(
            request,
            "jobs_list.html",
            {
                "request": request,
                "api_version": VERSION,
                "api_key": os.getenv("SUPERVAIZER_API_KEY"),
            },
        )

    @router.get("/cases", response_class=HTMLResponse)
    async def admin_cases_page(request: Request) -> Response:
        """Cases management page."""
        return templates.TemplateResponse(
            request,
            "cases_list.html",
            {
                "request": request,
                "api_version": VERSION,
                "api_key": os.getenv("SUPERVAIZER_API_KEY"),
            },
        )

    @router.get("/server", response_class=HTMLResponse)
    async def admin_server_page(request: Request) -> Response:
        """Server status and configuration page."""
        try:
            # Get initial server data
            server_status = get_server_status()
            server_config = get_server_configuration(storage)

            return templates.TemplateResponse(
                request,
                "server.html",
                {
                    "request": request,
                    "api_version": VERSION,
                    "server_status": server_status,
                    "server_config": server_config,
                    "api_key": os.getenv("SUPERVAIZER_API_KEY"),
                },
            )
        except Exception as e:
            log.error(f"Admin server page error: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get("/agents", response_class=HTMLResponse)
    async def admin_agents_page(request: Request) -> Response:
        """Agents management page."""
        try:
            from supervaizer.server import get_server_info_from_storage

            server_info = get_server_info_from_storage()
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
                    "api_key": os.getenv("SUPERVAIZER_API_KEY"),
                },
            )
        except Exception as e:
            log.error(f"Admin agents page error: {e}")
            raise HTTPException(
                status_code=503, detail="Server information unavailable"
            ) from e

    @router.get("/job-start-test", response_class=HTMLResponse)
    async def admin_job_start_test_page(request: Request) -> Response:
        """Job start form test page."""
        return templates.TemplateResponse(
            request,
            "job_start_test.html",
            {
                "request": request,
                "api_version": VERSION,
                "api_key": os.getenv("SUPERVAIZER_API_KEY"),
            },
        )

    @router.get("/static/js/job-start-form.js")
    async def serve_job_start_form_js() -> Response:
        """Serve the JobStartForm JavaScript file."""
        js_file_path = Path(__file__).parent / "static" / "js" / "job-start-form.js"
        if js_file_path.exists():
            with open(js_file_path, "r") as f:
                content = f.read()
            return Response(content=content, media_type="application/javascript")
        else:
            raise HTTPException(status_code=404, detail="JavaScript file not found")

    @router.get("/console", response_class=HTMLResponse)
    async def admin_console_page(request: Request) -> Response:
        """Interactive console page - publicly accessible, authentication handled by frontend."""
        # Clean up expired tokens
        cleanup_expired_tokens()

        # Generate a secure token for this console session
        console_token = generate_console_token()

        return templates.TemplateResponse(
            request,
            "console.html",
            {"request": request, "console_token": console_token},
        )

    # API Routes
    @router.get("/api/stats")
    async def get_stats() -> AdminStats:
        """Get system statistics."""
        return get_dashboard_stats(storage)

    @router.get("/api/server/status")
    async def get_server_status_api(request: Request) -> Response:
        """Get current server status for HTMX refresh."""
        try:
            server_status = get_server_status()

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

    @router.get("/api/agents")
    async def get_agents_api(
        request: Request,
        status: Optional[str] = Query(None),
        agent_type: Optional[str] = Query(None),
        search: Optional[str] = Query(None),
        sort: str = Query("-created_at"),
    ) -> Response:
        """Get agents with filtering for HTMX refresh."""
        try:
            from supervaizer.server import get_server_info_from_storage

            server_info = get_server_info_from_storage()
            if not server_info:
                raise HTTPException(
                    status_code=503, detail="Server information not available"
                )

            agents = server_info.agents

            # Apply filters
            filtered_agents = []
            for agent in agents:
                # Status filter (we'll add this to agent data later)
                if status and status != "all":
                    # For now, assume all agents are active since we don't have status
                    if status != "active":
                        continue

                # Agent type filter
                if agent_type and agent_type != "":
                    # Default to "conversational" if no type specified
                    agent_agent_type = agent.get("type", "conversational")
                    if agent_type.lower() != agent_agent_type.lower():
                        continue

                # Search filter
                if search:
                    search_lower = search.lower()
                    if not (
                        search_lower in agent.get("name", "").lower()
                        or search_lower in agent.get("description", "").lower()
                    ):
                        continue

                filtered_agents.append(agent)

            # Sort agents
            if sort.startswith("-"):
                reverse = True
                sort_key = sort[1:]
            else:
                reverse = False
                sort_key = sort

            if sort_key == "name":
                filtered_agents.sort(key=lambda x: x.get("name", ""), reverse=reverse)
            elif sort_key == "created_at":
                # For now, maintain original order since we don't have created_at
                pass

            return templates.TemplateResponse(
                request,
                "agents_grid.html",
                {
                    "request": request,
                    "agents": filtered_agents,
                },
            )

        except Exception as e:
            log.error(f"Get agents API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/agents/{agent_slug}")
    async def get_agent_details(
        request: Request,
        agent_slug: str,
    ) -> Response:
        """Get detailed agent information."""
        try:
            from supervaizer.server import get_server_info_from_storage

            server_info = get_server_info_from_storage()
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

    @router.get("/api/jobs")
    async def get_jobs_api(
        request: Request,
        status: Optional[str] = Query(None),
        agent_name: Optional[str] = Query(None),
        search: Optional[str] = Query(None),
        sort: str = Query("-created_at"),
        limit: int = Query(50, le=100),
        skip: int = Query(0, ge=0),
    ) -> Response:
        """Get jobs with filtering and pagination."""
        try:
            # Get all jobs
            jobs_data = storage.get_objects("Job")

            # Apply filters
            filtered_jobs = []
            for job_data in jobs_data:
                # Status filter
                if status and job_data.get("status") != status:
                    continue

                # Agent name filter
                if (
                    agent_name
                    and agent_name.lower() not in job_data.get("agent_name", "").lower()
                ):
                    continue

                # Search filter
                if search:
                    search_lower = search.lower()
                    if not (
                        search_lower in job_data.get("name", "").lower()
                        or search_lower in job_data.get("id", "").lower()
                    ):
                        continue

                filtered_jobs.append(job_data)

            # Sort jobs
            if sort.startswith("-"):
                reverse = True
                sort_key = sort[1:]
            else:
                reverse = False
                sort_key = sort

            if sort_key in ["created_at", "name", "status"]:
                filtered_jobs.sort(key=lambda x: x.get(sort_key, ""), reverse=reverse)

            # Apply pagination
            total = len(filtered_jobs)
            jobs_page = filtered_jobs[skip : skip + limit]

            # Format for display
            jobs = []
            for job_data in jobs_page:
                job = {
                    "id": job_data.get("id", ""),
                    "name": job_data.get("name", ""),
                    "agent_name": job_data.get("agent_name", ""),
                    "status": job_data.get("status", ""),
                    "created_at": job_data.get("created_at", ""),
                    "finished_at": job_data.get("finished_at"),
                    "case_count": len(job_data.get("case_ids", [])),
                }
                jobs.append(job)

            return templates.TemplateResponse(
                request,
                "jobs_table.html",
                {
                    "request": request,
                    "jobs": jobs,
                    "total": total,
                    "limit": limit,
                    "skip": skip,
                    "has_next": skip + limit < total,
                    "has_prev": skip > 0,
                },
            )

        except Exception as e:
            log.error(f"Get jobs API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/jobs/{job_id}")
    async def get_job_details(request: Request, job_id: str) -> Response:
        """Get detailed job information."""
        try:
            job_data = storage.get_object_by_id("Job", job_id)
            if not job_data:
                raise HTTPException(status_code=404, detail="Job not found")

            # Get related cases
            cases_data = storage.get_cases_for_job(job_id)

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

    @router.get("/api/cases")
    async def get_cases_api(
        request: Request,
        status: Optional[str] = Query(None),
        job_id: Optional[str] = Query(None),
        search: Optional[str] = Query(None),
        sort: str = Query("-created_at"),
        limit: int = Query(50, le=100),
        skip: int = Query(0, ge=0),
    ) -> Response:
        """Get cases with filtering and pagination."""
        try:
            # Get all cases
            cases_data = storage.get_objects("Case")

            # Apply filters
            filtered_cases = []
            for case_data in cases_data:
                # Status filter
                if status and case_data.get("status") != status:
                    continue

                # Job ID filter
                if job_id and case_data.get("job_id") != job_id:
                    continue

                # Search filter
                if search:
                    search_lower = search.lower()
                    if not (
                        search_lower in case_data.get("name", "").lower()
                        or search_lower in case_data.get("id", "").lower()
                        or search_lower in case_data.get("description", "").lower()
                    ):
                        continue

                filtered_cases.append(case_data)

            # Sort cases
            if sort.startswith("-"):
                reverse = True
                sort_key = sort[1:]
            else:
                reverse = False
                sort_key = sort

            if sort_key in ["created_at", "name", "status", "total_cost"]:
                if sort_key == "total_cost":
                    filtered_cases.sort(
                        key=lambda x: x.get(sort_key, 0), reverse=reverse
                    )
                else:
                    filtered_cases.sort(
                        key=lambda x: x.get(sort_key, ""), reverse=reverse
                    )

            # Apply pagination
            total = len(filtered_cases)
            cases_page = filtered_cases[skip : skip + limit]

            # Format for display
            cases = []
            for case_data in cases_page:
                case = {
                    "id": case_data.get("id", ""),
                    "name": case_data.get("name", ""),
                    "description": case_data.get("description", ""),
                    "status": case_data.get("status", ""),
                    "job_id": case_data.get("job_id", ""),
                    "created_at": case_data.get("created_at", ""),
                    "finished_at": case_data.get("finished_at"),
                    "total_cost": case_data.get("total_cost", 0.0),
                }
                cases.append(case)

            return templates.TemplateResponse(
                request,
                "cases_table.html",
                {
                    "request": request,
                    "cases": cases,
                    "total": total,
                    "limit": limit,
                    "skip": skip,
                    "has_next": skip + limit < total,
                    "has_prev": skip > 0,
                },
            )

        except Exception as e:
            log.error(f"Get cases API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/cases/{case_id}")
    async def get_case_details(request: Request, case_id: str) -> Response:
        """Get detailed case information."""
        try:
            case_data = storage.get_object_by_id("Case", case_id)
            if not case_data:
                raise HTTPException(status_code=404, detail="Case not found")

            # Get parent job if exists
            job_data = None
            if case_data.get("job_id"):
                job_data = storage.get_object_by_id("Job", case_data["job_id"])

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

    @router.post("/api/jobs/{job_id}/status")
    async def update_job_status(
        job_id: str,
        status_data: Dict[str, str],
    ) -> Dict[str, str]:
        """Update job status."""
        try:
            new_status = status_data.get("status")
            if not new_status or new_status not in [s.value for s in EntityStatus]:
                raise HTTPException(status_code=400, detail="Invalid status")

            job_data = storage.get_object_by_id("Job", job_id)
            if not job_data:
                raise HTTPException(status_code=404, detail="Job not found")

            # Update job status
            job_data["status"] = new_status
            if new_status in ["completed", "failed", "cancelled"]:
                job_data["finished_at"] = datetime.now().isoformat()

            storage.save_object("Job", job_data)

            return {"message": "Job status updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Update job status error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/api/cases/{case_id}/status")
    async def update_case_status(
        case_id: str,
        status_data: Dict[str, str],
    ) -> Dict[str, str]:
        """Update case status."""
        try:
            new_status = status_data.get("status")
            if not new_status or new_status not in [s.value for s in EntityStatus]:
                raise HTTPException(status_code=400, detail="Invalid status")

            case_data = storage.get_object_by_id("Case", case_id)
            if not case_data:
                raise HTTPException(status_code=404, detail="Case not found")

            # Update case status
            case_data["status"] = new_status
            if new_status in ["completed", "failed", "cancelled"]:
                case_data["finished_at"] = datetime.now().isoformat()

            storage.save_object("Case", case_data)

            return {"message": "Case status updated successfully"}

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Update case status error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/api/jobs/{job_id}")
    async def delete_job(job_id: str) -> Dict[str, str]:
        """Delete a job and its related cases."""
        try:
            # Delete related cases first
            cases_data = storage.get_cases_for_job(job_id)
            for case_data in cases_data:
                storage.delete_object("Case", case_data["id"])

            # Delete the job
            deleted = storage.delete_object("Job", job_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Job not found")

            return {"message": "Job and related cases deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Delete job error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/api/cases/{case_id}")
    async def delete_case(case_id: str) -> Dict[str, str]:
        """Delete a case."""
        try:
            deleted = storage.delete_object("Case", case_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Case not found")

            return {"message": "Case deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Delete case error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/recent-activity")
    async def get_recent_activity(request: Request) -> Response:
        """Get recent entity activity."""
        try:
            # Get recent jobs and cases
            recent_jobs = storage.get_objects("Job")[-5:]  # Last 5 jobs
            recent_cases = storage.get_objects("Case")[-5:]  # Last 5 cases

            # Combine and sort by created_at
            activities = []
            for job in recent_jobs:
                activities.append(
                    {
                        "type": "job",
                        "id": job.get("id"),
                        "name": job.get("name"),
                        "status": job.get("status"),
                        "created_at": job.get("created_at"),
                        "agent_name": job.get("agent_name"),
                    }
                )

            for case in recent_cases:
                activities.append(
                    {
                        "type": "case",
                        "id": case.get("id"),
                        "name": case.get("name"),
                        "status": case.get("status"),
                        "created_at": case.get("created_at"),
                        "job_id": case.get("job_id"),
                    }
                )

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

    @router.get("/log-stream")
    async def log_stream(
        token: Optional[str] = Query(None, alias="token"),
        key: Optional[str] = Query(None, alias="key"),
    ) -> EventSourceResponse:
        """Stream log messages via Server-Sent Events."""

        # Support both console token and API key authentication
        auth_valid = False
        auth_method = None

        if token:
            auth_valid = validate_console_token(token)
            auth_method = "console_token"
            # If token validation fails, fall back to admin console mode
            if not auth_valid:
                auth_valid = True
                auth_method = "admin_console_fallback"
        elif key:
            # Use API key validation
            try:
                from supervaizer.server import get_server_info_from_storage

                server_info = get_server_info_from_storage()
                if (
                    server_info
                    and hasattr(server_info, "api_key")
                    and key == server_info.api_key
                ):
                    auth_valid = True
                    auth_method = "api_key"
            except Exception:
                # Fallback: just check if key is provided for now
                if key:
                    auth_valid = True
                    auth_method = "api_key_fallback"
        else:
            # Allow access without authentication for admin interface live console
            # In a production environment, you might want to add additional security
            auth_valid = True
            auth_method = "admin_console"

        if not auth_valid:
            raise HTTPException(
                status_code=403,
                detail=f"Invalid or expired authentication token (method: {auth_method or 'none'})",
            )

        async def generate_log_events() -> AsyncGenerator[str, None]:
            try:
                # Send connection message immediately
                test_message = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": f"Log stream connected using {auth_method}",
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
                    except asyncio.TimeoutError:
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
                            "message": f"Log stream error: {str(e)}",
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {error_data}\n\n"
                except Exception:
                    # If even error formatting fails, just close
                    pass

        return EventSourceResponse(generate_log_events())

    @router.get("/test-log")
    async def test_log() -> Dict[str, str]:
        """Test endpoint to generate a log message."""
        test_message = f"Test log message generated at {datetime.now().isoformat()}"
        add_log_to_queue(
            timestamp=datetime.now().isoformat(), level="INFO", message=test_message
        )

        # Also test the loguru logger directly
        log.info(f"Direct loguru test message: {test_message}")

        return {"message": "Test log added to queue"}

    @router.get("/debug-tokens")
    async def debug_tokens() -> Dict[str, Any]:
        """Debug endpoint to see current tokens."""
        cleanup_expired_tokens()
        return {
            "current_tokens": [
                {
                    "token": token[:10] + "...",
                    "expires_at": expiry,
                    "expires_in": expiry - time.time(),
                    "is_valid": expiry > time.time(),
                }
                for token, expiry in _console_tokens.items()
            ],
            "token_count": len(_console_tokens),
            "current_time": time.time(),
        }

    @router.get("/test-loguru")
    async def test_loguru() -> Dict[str, str]:
        """Test endpoint to generate loguru messages."""
        log.info("Testing loguru INFO message")
        log.warning("Testing loguru WARNING message")
        log.error("Testing loguru ERROR message")
        return {"message": "Loguru test messages sent"}

    @router.get("/debug-queue")
    async def debug_queue() -> Dict[str, Any]:
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

    @router.post("/api/console/execute")
    async def execute_console_command(
        request: Request,
        command_data: Dict[str, str],
        token: Optional[str] = Query(None, alias="token"),
    ) -> Dict[str, str]:
        """Execute a console command and add output to log stream."""
        # Validate console token
        if not validate_console_token(token):
            raise HTTPException(
                status_code=401, detail="Invalid or expired console token"
            )

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
                message=f"Command execution failed: {str(e)}",
            )
            return {"status": "error", "message": str(e)}

    return router


def get_dashboard_stats(storage: StorageManager) -> AdminStats:
    """Get statistics for dashboard."""
    try:
        # Get all jobs and cases
        all_jobs = storage.get_objects("Job")
        all_cases = storage.get_objects("Case")

        # Calculate job stats
        job_total = len(all_jobs)
        job_running = len(
            [j for j in all_jobs if j.get("status") in ["in_progress", "awaiting"]]
        )
        job_completed = len([j for j in all_jobs if j.get("status") == "completed"])
        job_failed = len(
            [j for j in all_jobs if j.get("status") in ["failed", "cancelled"]]
        )

        # Calculate case stats
        case_total = len(all_cases)
        case_running = len(
            [c for c in all_cases if c.get("status") in ["in_progress", "awaiting"]]
        )
        case_completed = len([c for c in all_cases if c.get("status") == "completed"])
        case_failed = len(
            [c for c in all_cases if c.get("status") in ["failed", "cancelled"]]
        )

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


async def process_console_command(command: str) -> Dict[str, str]:
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
        return {"level": "ERROR", "message": f"Command processing error: {str(e)}"}


def generate_console_token() -> str:
    """Generate a temporary token for console access."""
    token = secrets.token_urlsafe(32)
    # Token expires in 1 hour
    _console_tokens[token] = time.time() + 3600
    return token


def validate_console_token(token: Optional[str]) -> bool:
    """Validate a console token."""
    if not token or token not in _console_tokens:
        return False

    # Check if token is expired
    if time.time() > _console_tokens[token]:
        del _console_tokens[token]
        return False

    return True


def cleanup_expired_tokens() -> None:
    """Clean up expired tokens."""
    current_time = time.time()
    expired_tokens = [
        token for token, expiry in _console_tokens.items() if current_time > expiry
    ]
    for token in expired_tokens:
        del _console_tokens[token]
