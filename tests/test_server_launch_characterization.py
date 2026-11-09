# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize controller launch behavior without opening a server socket."""

import asyncio
from typing import Any

import pytest
from pytest_mock import MockerFixture

import supervaizer.server as server_module
from supervaizer.common import ApiSuccess
from supervaizer.server import Server


def test_launch_validates_standalone_controller_then_runs_uvicorn(
    server_fixture: Server, mocker: MockerFixture
) -> None:
    """A controller without Studio still validates trust before it starts."""
    server_fixture.supervisor_account = None
    validate = mocker.patch.object(
        server_fixture, "_validate_studio_a2a_workspace_authorization"
    )
    run = mocker.patch("uvicorn.run")

    server_fixture.launch(log_level=None)

    validate.assert_called_once_with()
    run.assert_called_once_with(
        server_fixture.app,
        host="localhost",
        port=8001,
        reload=False,
        log_level=None,
    )


def test_launch_registers_studio_controller_before_running_uvicorn(
    server_fixture: Server, mocker: MockerFixture
) -> None:
    """A Studio-backed controller completes registration before uvicorn starts."""
    account = server_fixture.supervisor_account
    assert account is not None
    validation = mocker.patch.object(
        server_fixture, "_validate_studio_a2a_workspace_authorization"
    )
    registration = mocker.patch(
        "supervaizer.account.Account.register_server_sync",
        return_value=ApiSuccess(message="registered", detail={}),
    )
    handshake = mocker.patch.object(server_fixture, "_validate_registration_handshake")
    update_agent = mocker.patch(
        "supervaizer.agent.Agent.update_agent_from_server",
        return_value=server_fixture.agents[0],
    )
    configure_logging = mocker.patch.object(
        server_module, "configure_controller_logging"
    )
    mocker.patch.object(server_module.log, "add")
    run = mocker.patch("uvicorn.run")

    server_fixture.launch(log_level="DEBUG")

    validation.assert_called_once_with()
    registration.assert_called_once_with(server=server_fixture)
    handshake.assert_called_once_with(registration.return_value)
    update_agent.assert_called_once_with(server_fixture)
    configure_logging.assert_called_once_with("DEBUG")
    run.assert_called_once_with(
        server_fixture.app,
        host="localhost",
        port=8001,
        reload=False,
        log_level="debug",
    )


def test_launch_does_not_start_uvicorn_when_trust_validation_fails(
    server_fixture: Server, mocker: MockerFixture
) -> None:
    """Trust validation errors stop launch before any server is started."""
    server_fixture.supervisor_account = None
    mocker.patch.object(
        server_fixture,
        "_validate_studio_a2a_workspace_authorization",
        side_effect=RuntimeError("workspace trust is invalid"),
    )
    run = mocker.patch("uvicorn.run")

    with pytest.raises(RuntimeError, match="workspace trust is invalid"):
        server_fixture.launch(log_level=None)

    run.assert_not_called()


def test_launch_rejects_non_successful_studio_registration(
    server_fixture: Server, mocker: MockerFixture
) -> None:
    """A registration result outside the success contract blocks uvicorn."""
    account = server_fixture.supervisor_account
    assert account is not None
    mocker.patch.object(server_fixture, "_validate_studio_a2a_workspace_authorization")
    mocker.patch(
        "supervaizer.account.Account.register_server_sync", return_value=object()
    )
    run = mocker.patch("uvicorn.run")

    with pytest.raises(AssertionError):
        server_fixture.launch(log_level=None)

    run.assert_not_called()


def test_launch_allows_an_empty_standalone_controller(
    server_fixture: Server, mocker: MockerFixture
) -> None:
    """Current behavior permits a standalone controller without agents."""
    server_fixture.supervisor_account = None
    server_fixture.agents = []
    mocker.patch.object(server_fixture, "_validate_studio_a2a_workspace_authorization")
    run = mocker.patch("uvicorn.run")

    server_fixture.launch(log_level=None)

    run.assert_called_once_with(
        server_fixture.app,
        host="localhost",
        port=8001,
        reload=False,
        log_level=None,
    )


@pytest.mark.asyncio
async def test_server_app_lifespan_starts_and_cancels_the_scheduler(
    server_fixture: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app given to uvicorn owns a cancellable scheduler lifecycle."""

    class SchedulerTask:
        cancelled = False
        awaited = False

        def cancel(self) -> None:
            self.cancelled = True

        def __await__(self) -> Any:
            async def cancelled_task() -> None:
                self.awaited = True
                raise asyncio.CancelledError

            return cancelled_task().__await__()

    scheduler_task = SchedulerTask()

    def create_task(coro: Any, **_kwargs: Any) -> SchedulerTask:
        coro.close()
        return scheduler_task

    async def wait(
        tasks: set[SchedulerTask], *, timeout: float | None = None
    ) -> tuple[set[SchedulerTask], set[SchedulerTask]]:
        assert timeout == server_module.SCHEDULED_STEP_SHUTDOWN_TIMEOUT_SECONDS
        return tasks, set()

    monkeypatch.setattr(server_module.asyncio, "create_task", create_task)
    monkeypatch.setattr(server_module.asyncio, "wait", wait)

    async with server_fixture.app.router.lifespan_context(server_fixture.app):
        assert scheduler_task.cancelled is False

    assert scheduler_task.cancelled is True
    assert scheduler_task.awaited is True
