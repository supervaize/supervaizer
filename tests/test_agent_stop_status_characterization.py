# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize Agent stop and status hook behavior before deduplication."""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest

from supervaizer.agent import Agent, AgentMethod, AgentMethods
from supervaizer.job import JobResponse
from supervaizer.lifecycle import EntityStatus


def _agent(
    job_stop: AgentMethod | None = None, job_status: AgentMethod | None = None
) -> Agent:
    return Agent(
        name="Stop Status Agent",
        methods=AgentMethods(
            job_start=AgentMethod(name="start", method="control.start"),
            job_stop=job_stop,
            job_status=job_status,
        ),
    )


@pytest.mark.parametrize(
    ("hook_name", "method"),
    [
        ("job_stop", AgentMethod(name="stop", method="control.stop")),
        ("job_status", AgentMethod(name="status", method="control.status")),
    ],
)
def test_hooks_forward_declared_method_params_and_return_response(
    monkeypatch: pytest.MonkeyPatch, hook_name: str, method: AgentMethod
) -> None:
    agent = _agent(
        job_stop=method if hook_name == "job_stop" else None,
        job_status=method if hook_name == "job_status" else None,
    )
    params = {"reason": "requested"}
    response = JobResponse(
        job_id="job-1",
        status=EntityStatus.AWAITING,
        message="waiting",
        payload={"progress": 50},
    )
    execute = Mock(return_value=response)
    monkeypatch.setattr(agent, "_execute", execute)

    hook = getattr(agent, hook_name)
    returned = hook(params)

    execute.assert_called_once_with(method.method, params)
    assert returned is response
    assert response.status == EntityStatus.AWAITING


@pytest.mark.parametrize("hook_name", ["job_stop", "job_status"])
def test_hooks_reject_missing_declared_method(hook_name: str) -> None:
    agent = _agent()

    hook = getattr(agent, hook_name)

    with pytest.raises(ValueError, match="Agent methods not defined"):
        hook()


@pytest.mark.parametrize(
    ("hook_name", "method"),
    [
        ("job_stop", AgentMethod(name="stop", method="control.stop")),
        ("job_status", AgentMethod(name="status", method="control.status")),
    ],
)
def test_hooks_reraise_execution_errors(
    monkeypatch: pytest.MonkeyPatch, hook_name: str, method: AgentMethod
) -> None:
    agent = _agent(
        job_stop=method if hook_name == "job_stop" else None,
        job_status=method if hook_name == "job_status" else None,
    )
    failure = RuntimeError("hook failed")
    execute = Mock(side_effect=failure)
    monkeypatch.setattr(agent, "_execute", execute)
    hook: Callable[[dict[str, Any]], Any] = getattr(agent, hook_name)

    with pytest.raises(RuntimeError, match="hook failed"):
        hook({"reason": "requested"})

    execute.assert_called_once_with(method.method, {"reason": "requested"})
