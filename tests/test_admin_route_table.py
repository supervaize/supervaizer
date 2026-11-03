# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Pin the public route table of the admin and workbench routers.

The route factories were refactored from nested closures into module-level
handlers. This test fixes the externally visible result: which paths, methods
and handler names the router exposes, in match order.
"""

from fastapi import FastAPI

from supervaizer.admin.routes import create_admin_routes
from supervaizer.admin.workbench_routes import create_workbench_ws_routes

PREFIX = "/manage"

EXPECTED_ROUTES: list[tuple[str, str, str]] = [
    ("/", "GET", "admin_dashboard"),
    ("/jobs", "GET", "admin_jobs_page"),
    ("/cases", "GET", "admin_cases_page"),
    ("/server", "GET", "admin_server_page"),
    ("/agents", "GET", "admin_agents_page"),
    ("/static/{file_path}", "GET", "serve_static"),
    ("/console", "GET", "admin_console_page"),
    ("/api/stats", "GET", "get_stats"),
    ("/api/server/status", "GET", "get_server_status_api"),
    ("/api/server/register", "POST", "register_server_with_supervisor"),
    ("/api/agents", "GET", "get_agents_api"),
    ("/api/agents/{agent_slug}", "GET", "get_agent_details"),
    ("/api/jobs", "GET", "get_jobs_api"),
    ("/api/jobs/{job_id}", "GET", "get_job_details"),
    ("/api/jobs/{job_id}", "DELETE", "delete_job"),
    ("/api/cases", "GET", "get_cases_api"),
    ("/api/cases/{case_id}", "GET", "get_case_details"),
    ("/api/cases/{case_id}", "DELETE", "delete_case"),
    ("/api/jobs/{job_id}/status", "POST", "update_job_status"),
    ("/api/cases/{case_id}/status", "POST", "update_case_status"),
    ("/api/recent-activity", "GET", "get_recent_activity"),
    ("/log-stream", "GET", "log_stream"),
    ("/test-log", "GET", "test_log"),
    ("/test-loguru", "GET", "test_loguru"),
    ("/debug-queue", "GET", "debug_queue"),
    ("/api/console/execute", "POST", "execute_console_command"),
    ("/agents/{slug}/workbench", "GET", "workbench_page"),
    ("/agents/{slug}/workbench/start", "POST", "workbench_start_job"),
    ("/agents/{slug}/workbench/jobs/{job_id}", "GET", "workbench_job_monitor"),
    ("/agents/{slug}/workbench/jobs/{job_id}/stop", "POST", "workbench_stop_job"),
    ("/agents/{slug}/workbench/jobs/{job_id}/status", "GET", "workbench_job_status"),
    (
        "/agents/{slug}/workbench/jobs/{job_id}/cases/{case_id}/answer",
        "POST",
        "workbench_answer_hitl",
    ),
    (
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/execute",
        "POST",
        "workbench_execute_step",
    ),
    (
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/cancel",
        "POST",
        "workbench_cancel_step",
    ),
    (
        "/agents/{slug}/workbench/jobs/{job_id}/steps/{case_id}/{step_index}/schedule",
        "PATCH",
        "workbench_reschedule_step",
    ),
    ("/agents/{slug}/workbench/console", "GET", "workbench_console"),
    ("/agents/{slug}/workbench/jobs", "GET", "workbench_jobs_list"),
]


def _exposed_routes() -> list[tuple[str, str, str]]:
    app = FastAPI()
    app.include_router(create_admin_routes(), prefix=PREFIX)
    rows: list[tuple[str, str, str]] = []
    for path, operations in app.openapi()["paths"].items():
        for method, operation in operations.items():
            handler = operation["operationId"].rsplit(f"_{PREFIX.strip('/')}_", 1)[0]
            rows.append((path.removeprefix(PREFIX), method.upper(), handler))
    return rows


def test_admin_router_exposes_expected_routes_in_order() -> None:
    assert _exposed_routes() == EXPECTED_ROUTES


def test_workbench_websocket_route_is_exposed() -> None:
    routes = [(r.path, r.name) for r in create_workbench_ws_routes().routes]
    assert routes == [
        ("/agents/{slug}/workbench/jobs/{job_id}/ws", "workbench_job_ws")
    ]
