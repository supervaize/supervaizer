# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Pin observable admin behavior exposed by mutation testing."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import psutil
import pytest
from pytest_mock import MockerFixture

from supervaizer.admin import routes
from tests.admin_rig import AdminRig


def test_dashboard_without_a_live_server_is_not_local(rig: AdminRig) -> None:
    page = rig.get("/manage/")

    assert page.status == 200
    assert page.context["local_mode"] is False


def test_stats_count_each_job_and_case_status(rig: AdminRig) -> None:
    statuses = [
        "in_progress",
        "awaiting",
        "completed",
        "failed",
        "cancelled",
        "stopped",
    ]
    for kind in ("Job", "Case"):
        rig.seed(
            kind,
            [
                {"id": f"{kind}-{i}", "status": status}
                for i, status in enumerate(statuses)
            ],
        )

    page = rig.get("/manage/api/stats")

    assert page.status == 200
    counts = {"total": 6, "running": 2, "completed": 1, "failed": 2}
    assert page.response.json() == {"jobs": counts, "cases": counts, "collections": 2}


@pytest.mark.parametrize("connection_error", [psutil.AccessDenied(), OSError("denied")])
def test_server_metrics_keep_units_and_connection_failure_default(
    mocker: MockerFixture, connection_error: Exception
) -> None:
    mocker.patch.object(
        routes,
        "_get_server_info",
        return_value=SimpleNamespace(
            start_time=100.0,
            agents=[{"id": "agent-1"}, {"id": "agent-2"}],
            host="127.0.0.1",
            port=8000,
            environment="test",
        ),
    )
    mocker.patch.object(routes.time, "time", return_value=3761.9)
    mocker.patch.object(
        routes.psutil, "virtual_memory", return_value=SimpleNamespace(percent=25.0)
    )
    process = mocker.patch.object(routes.psutil, "Process").return_value
    process.memory_info.return_value = SimpleNamespace(rss=12 * 1024 * 1024)
    mocker.patch.object(routes.psutil, "cpu_percent", return_value=3.5)
    mocker.patch.object(routes.psutil, "net_connections", side_effect=connection_error)

    status = routes.get_server_status()

    assert status.uptime_seconds == 3661
    assert status.uptime == "1h 1m"
    assert status.memory_usage_mb == 12.0
    assert status.memory_usage == "12.0 MB"
    assert status.memory_percent == 25.0
    assert status.cpu_percent == 3.5
    assert status.active_connections == 0
    assert status.agents_count == 2


@pytest.mark.parametrize("path", ["/manage/server", "/manage/api/server/status"])
def test_server_pages_keep_missing_information_as_500(
    rig: AdminRig, mocker: MockerFixture, path: str
) -> None:
    mocker.patch.object(routes, "_get_server_info", return_value=None)

    page = rig.get(path)

    assert page.status == 500


@pytest.mark.asyncio
async def test_stream_skips_invalid_backlog_and_keeps_unicode(
    mocker: MockerFixture,
) -> None:
    queue: asyncio.Queue[Any] = asyncio.Queue()
    queue.put_nowait({"invalid": object()})
    entry = {"timestamp": "now", "level": "INFO", "message": "Caf\u00e9"}
    queue.put_nowait(entry)
    mocker.patch.object(routes, "log_queue", queue)
    stream = routes._log_events()
    try:
        assert "Log stream connected" in await anext(stream)
        event = await anext(stream)
        assert event == f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
        assert "Caf\u00e9" in event
        assert queue.empty()
    finally:
        await stream.aclose()
