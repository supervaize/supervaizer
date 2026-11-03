# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize local Hello World control-hook responses."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from pytest_mock import MockerFixture

from supervaizer.examples.hello_world_agent import job_status, job_stop
from supervaizer.job import JobResponse
from supervaizer.lifecycle import EntityStatus

ControlHook = Callable[..., JobResponse]


@pytest.mark.parametrize(
    ("hook", "expected_status", "expected_message", "expected_log"),
    [
        (job_stop, EntityStatus.STOPPED, "Stopped", "Job stopped: explicit-job"),
        (job_status, EntityStatus.STOPPED, "idle", "Job status: explicit-job"),
    ],
)
def test_control_hooks_prefer_explicit_job_id_and_preserve_response_shape(
    hook: ControlHook,
    expected_status: EntityStatus,
    expected_message: str,
    expected_log: str,
    mocker: MockerFixture,
) -> None:
    """An explicit job id takes priority and produces the public response payload."""
    info = mocker.patch("supervaizer.examples.hello_world_agent.log.info")

    response = hook(
        job_id="explicit-job",
        context=SimpleNamespace(job_id="context-job"),
    )

    assert response.registration_info == {
        "job_id": "explicit-job",
        "status": expected_status.value,
        "message": expected_message,
        "payload": None,
        "error_message": "",
        "error_traceback": "",
    }
    info.assert_called_once_with(expected_log)


@pytest.mark.parametrize(
    ("params", "expected_job_id"),
    [
        ({"context": SimpleNamespace(job_id="object-job")}, "object-job"),
        ({"context": {"job_id": "dict-job"}}, "dict-job"),
        ({"context": {}}, "local-job"),
        ({}, "local-job"),
    ],
)
@pytest.mark.parametrize(
    ("hook", "expected_status", "expected_message", "action"),
    [
        (job_stop, EntityStatus.STOPPED, "Stopped", "Job stopped"),
        (job_status, EntityStatus.STOPPED, "idle", "Job status"),
    ],
)
def test_control_hooks_use_context_then_local_job_fallback(
    hook: ControlHook,
    expected_status: EntityStatus,
    expected_message: str,
    action: str,
    params: dict[str, Any],
    expected_job_id: str,
    mocker: MockerFixture,
) -> None:
    """Without an explicit id, object and map contexts select the same job id."""
    info = mocker.patch("supervaizer.examples.hello_world_agent.log.info")

    response = hook(**params)

    assert response.job_id == expected_job_id
    assert response.status == expected_status
    assert response.message == expected_message
    assert response.payload is None
    info.assert_called_once_with(f"{action}: {expected_job_id}")
