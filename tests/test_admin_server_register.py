# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""POST /manage/api/server/register: where the server comes from and how it fails."""

from types import SimpleNamespace
from typing import Any

import pytest
from pytest_mock import MockerFixture

from supervaizer.common import ApiError, ApiSuccess
from supervaizer.routes import get_server
from tests.admin_rig import AdminRig

URL = "/manage/api/server/register"


def account(
    mocker: MockerFixture, result: Any = None, error: Exception | None = None
) -> Any:
    register = mocker.AsyncMock(return_value=result, side_effect=error)
    return SimpleNamespace(register_server=register)


def post(rig: AdminRig) -> Any:
    return rig.request("POST", URL).response


def test_server_from_app_state_is_registered(
    rig: AdminRig, mocker: MockerFixture
) -> None:
    supervisor = account(mocker, ApiSuccess(message="registered", detail={"id": 1}))
    server = SimpleNamespace(supervisor_account=supervisor)
    rig.client.app.state.server = server  # type: ignore[attr-defined]

    response = post(rig)

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "registered",
        "detail": {"id": 1},
    }
    supervisor.register_server.assert_awaited_once_with(server=server)


def test_failed_registration_is_502_with_the_detail(
    rig: AdminRig, mocker: MockerFixture
) -> None:
    supervisor = account(mocker, ApiError(message="refused", detail={"why": "x"}))
    rig.client.app.state.server = SimpleNamespace(supervisor_account=supervisor)  # type: ignore[attr-defined]
    response = post(rig)
    assert response.status_code == 502
    assert response.json() == {
        "success": False,
        "message": "refused",
        "detail": {"why": "x"},
    }


def test_server_from_dependency_override_is_used_when_app_state_has_none(
    rig: AdminRig, mocker: MockerFixture
) -> None:
    supervisor = account(mocker, ApiSuccess(message="ok", detail=None))

    async def override() -> Any:
        return SimpleNamespace(supervisor_account=supervisor)

    rig.client.app.dependency_overrides[get_server] = override  # type: ignore[attr-defined]
    assert post(rig).status_code == 200
    supervisor.register_server.assert_awaited_once()


@pytest.mark.parametrize("error", [NotImplementedError(), TypeError("bad")])
def test_dependency_override_that_cannot_answer_counts_as_no_server(
    rig: AdminRig, error: Exception
) -> None:
    async def override() -> Any:
        raise error

    rig.client.app.dependency_overrides[get_server] = override  # type: ignore[attr-defined]
    response = post(rig)
    assert response.status_code == 503
    assert "Server instance not available" in response.json()["detail"]


def test_no_server_anywhere_is_503(rig: AdminRig) -> None:
    response = post(rig)
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Server instance not available (admin not running with live server)"
    )


def test_unexpected_error_is_500_with_the_message(
    rig: AdminRig, mocker: MockerFixture
) -> None:
    supervisor = account(mocker, error=RuntimeError("network down"))
    rig.client.app.state.server = SimpleNamespace(supervisor_account=supervisor)  # type: ignore[attr-defined]
    response = post(rig)
    assert response.status_code == 500
    assert response.json()["detail"] == "network down"
