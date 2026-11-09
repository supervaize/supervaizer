# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Check observable failure, registration, and WebSocket edge behavior."""

from collections import deque
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, WebSocket
from pytest_mock import MockerFixture

from supervaizer.admin import workbench_routes
from tests.admin_rig import AdminRig
from tests.workbench_rig import WorkbenchRig


def test_stats_return_all_zero_counts_when_the_database_cannot_be_read(
    rig: AdminRig, mocker: MockerFixture
) -> None:
    rig.seed("Job", [{"id": "job-1", "status": "in_progress"}])
    rig.seed("Case", [{"id": "case-1", "status": "completed"}])
    mocker.patch.object(
        rig.storage._db.storage,
        "read",
        side_effect=OSError("dummy database read failure"),
    )

    page = rig.get("/manage/api/stats")

    assert page.status == 200
    assert page.response.json() == {
        "jobs": {"total": 0, "running": 0, "completed": 0, "failed": 0},
        "cases": {"total": 0, "running": 0, "completed": 0, "failed": 0},
        "collections": 0,
    }


def test_workbench_with_a_supervisor_account_is_not_local(
    workbench: WorkbenchRig,
) -> None:
    app = cast(FastAPI, workbench.client.app)
    app.state.server.supervisor_account = object()

    page = workbench.get(workbench.url())

    assert page.status == 200
    assert page.context["local_mode"] is False


@pytest.mark.parametrize(
    "message", ["GET /manage/api/jobs", "GET /api/jobs HTTP/1.1 200"]
)
def test_access_log_noise_stays_visible_without_a_console_refresh_signal(
    workbench: WorkbenchRig,
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    monkeypatch.setattr(workbench_routes, "_workbench_log_buffer", deque(maxlen=500))
    monkeypatch.setattr(workbench_routes, "_workbench_log_version", 0)
    state = workbench_routes._SignalState()
    assert state.changes(workbench.job, workbench.agent.name) == ["monitor", "jobs"]

    workbench_routes.workbench_log_listener("dummy-time", "INFO", message)

    assert state.changes(workbench.job, workbench.agent.name) == []
    page = workbench.get(workbench.url("/console"))
    assert page.status == 200
    assert page.context["entries"] == [
        {"timestamp": "dummy-time", "level": "INFO", "message": message}
    ]
    assert page.context["next_index"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("messages", [[], ["ping"], ["ping", "other text"]])
async def test_terminal_socket_waits_for_disconnect_and_discards_client_messages(
    messages: list[str],
) -> None:
    events: list[dict[str, Any]] = [
        {"type": "websocket.connect"},
        *[{"type": "websocket.receive", "text": message} for message in messages],
        {"type": "websocket.disconnect", "code": 1000},
    ]
    receive = AsyncMock(side_effect=events)
    send = AsyncMock()
    websocket = WebSocket({"type": "websocket"}, receive=receive, send=send)
    await websocket.accept()

    await workbench_routes._idle_until_disconnect(websocket)

    assert receive.await_count == len(events)
    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.args[0]["type"] == "websocket.accept"
