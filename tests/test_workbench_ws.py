# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Workbench WebSocket: which refresh signals it pushes, and when."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from supervaizer import CaseNodeUpdate, EntityStatus
from supervaizer.admin import workbench_routes
from supervaizer.admin.workbench_routes import workbench_log_listener
from tests.workbench_rig import JOB_ID, WorkbenchRig


def connect(rig: WorkbenchRig, job_id: str = JOB_ID, slug: str | None = None) -> Any:
    path = f"/manage/agents/{slug or rig.agent.slug}/workbench/jobs/{job_id}/ws"
    return rig.client.websocket_connect(path)


def receive(ws: WebSocketTestSession, count: int) -> list[str]:
    return [ws.receive_text() for _ in range(count)]


def ping(ws: WebSocketTestSession) -> list[str]:
    """Send a ping and collect everything the server pushes until it answers pong."""
    ws.send_text("ping")
    seen = [ws.receive_text()]
    while seen[-1] != "pong":
        seen.append(ws.receive_text())
    return seen


@pytest.fixture(autouse=True)
def _quiet_log(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(workbench_routes, "_workbench_log_version", 0)
    yield


def test_unknown_agent_closes_the_socket(workbench: WorkbenchRig) -> None:
    with connect(workbench, slug="nobody") as ws, pytest.raises(WebSocketDisconnect):
        ws.receive_text()


def test_unknown_job_sends_monitor_once_then_closes(workbench: WorkbenchRig) -> None:
    with connect(workbench, job_id="nope") as ws:
        assert ws.receive_text() == "monitor"


def test_running_job_announces_monitor_and_jobs_then_answers_ping(
    workbench: WorkbenchRig,
) -> None:
    with connect(workbench) as ws:
        assert receive(ws, 2) == ["monitor", "jobs"]
        assert ping(ws) == ["pong"]
        assert ping(ws) == ["pong"]


def test_other_text_gets_no_answer_and_no_repeat_signal(
    workbench: WorkbenchRig,
) -> None:
    with connect(workbench) as ws:
        receive(ws, 2)
        ws.send_text("hello")
        assert ping(ws) == ["pong"]


def test_case_change_triggers_monitor(workbench: WorkbenchRig) -> None:
    with connect(workbench) as ws:
        receive(ws, 2)
        workbench.case.updates = [CaseNodeUpdate(name="step")]
        ws.send_text("ping")
        assert receive(ws, 2) == ["pong", "monitor"]


def test_meaningful_log_entry_triggers_console(workbench: WorkbenchRig) -> None:
    with connect(workbench) as ws:
        receive(ws, 2)
        workbench_log_listener("t", "INFO", "something happened")
        ws.send_text("ping")
        assert receive(ws, 2) == ["pong", "console"]


@pytest.mark.parametrize("message", ["GET /manage/api/jobs", "x HTTP/1.1 200"])
def test_admin_http_noise_does_not_trigger_console(
    workbench: WorkbenchRig, message: str
) -> None:
    with connect(workbench) as ws:
        receive(ws, 2)
        workbench_log_listener("t", "INFO", message)
        assert ping(ws) == ["pong"]


def test_new_job_for_the_agent_triggers_jobs(workbench: WorkbenchRig) -> None:
    other = workbench.job.job_context.model_copy(update={"job_id": "wb-job-2"})
    with connect(workbench) as ws:
        receive(ws, 2)
        type(workbench.job).new(job_context=other, agent_name=workbench.job.agent_name)
        ws.send_text("ping")
        assert receive(ws, 2) == ["pong", "jobs"]


@pytest.mark.parametrize(
    "status",
    [
        EntityStatus.COMPLETED,
        EntityStatus.FAILED,
        EntityStatus.STOPPED,
        EntityStatus.CANCELLED,
    ],
)
def test_finished_job_sends_terminal_burst_then_idles(
    workbench: WorkbenchRig, status: EntityStatus
) -> None:
    workbench.job.status = status
    with connect(workbench) as ws:
        assert receive(ws, 5) == ["monitor", "jobs", "console", "jobs", "terminal"]


@pytest.mark.parametrize("status", [EntityStatus.IN_PROGRESS, EntityStatus.AWAITING])
def test_unfinished_job_never_sends_terminal(
    workbench: WorkbenchRig, status: EntityStatus
) -> None:
    workbench.job.status = status
    with connect(workbench) as ws:
        assert receive(ws, 2) == ["monitor", "jobs"]
        assert "terminal" not in ping(ws)


def test_lookup_error_is_treated_as_missing_job(
    workbench: WorkbenchRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("registry down")

    monkeypatch.setattr(workbench_routes, "Jobs", lambda: SimpleNamespace(get_job=boom))
    with connect(workbench) as ws:
        assert ws.receive_text() == "monitor"
