# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import pytest
from httpx import ConnectError, HTTPStatusError
from pytest_mock import MockerFixture

from supervaizer import Account, ApiSuccess
from supervaizer.account_service import send_event
from supervaizer.event import Event
from supervaizer.server import Server

from . import AUTH_ERROR_RESPONSE, WAKEUP_EVENT_RESPONSE


def test_send_event_success(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    # Patch the method on the client instance used in account_service
    mock_post = mocker.patch("supervaizer.account_service._httpx_client.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = str(WAKEUP_EVENT_RESPONSE)
    mock_post.return_value.raise_for_status = mocker.Mock()

    result = send_event(
        account=account_fixture, sender=server_fixture, event=event_fixture
    )

    mock_post.assert_called_once_with(
        account_fixture.url_event,
        headers=account_fixture.api_headers,
        json=event_fixture.payload,
    )
    assert isinstance(result, ApiSuccess)
    assert result.message == f"POST Event {event_fixture.type.name} sent"
    assert result.detail == {"object": WAKEUP_EVENT_RESPONSE}


def test_send_event_auth_error(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch("supervaizer.account_service._httpx_client.post")

    # Create a mock response that raises HTTPStatusError when raise_for_status is called
    mock_response = mocker.Mock()
    mock_response.status_code = 403
    mock_response.text = str(AUTH_ERROR_RESPONSE)

    error = HTTPStatusError(
        "403 Client Error: Forbidden for url",
        request=mocker.Mock(),
        response=mock_response,
    )
    mock_response.raise_for_status.side_effect = error
    mock_post.return_value = mock_response

    with pytest.raises(HTTPStatusError, match="403 Client Error: Forbidden for url"):
        send_event(account=account_fixture, sender=server_fixture, event=event_fixture)


def test_send_event_url_error(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch("supervaizer.account_service._httpx_client.post")
    mock_post.side_effect = ConnectError("HTTPSConnectionPool(host='...")

    with pytest.raises(ConnectError, match="HTTPSConnectionPool"):
        send_event(account=account_fixture, sender=server_fixture, event=event_fixture)
