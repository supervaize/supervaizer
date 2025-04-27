# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from pytest_mock import MockerFixture

from supervaizer import Account, ApiSuccess
from supervaizer.event import Event
from supervaizer.server import Server


def test_account(account_fixture: Account) -> None:
    assert isinstance(account_fixture, Account)
    assert account_fixture.workspace_id == "o34Z484gY9Nxz8axgTAdiH"


def test_account_api_headers(account_fixture: Account) -> None:
    apikey = account_fixture.api_key
    assert account_fixture.api_headers == {
        "Authorization": f"Api-Key {apikey}",
        "workspace": "o34Z484gY9Nxz8axgTAdiH",
        "accept": "application/json",
    }


def test_account_url_event(account_fixture: Account) -> None:
    apiurl = account_fixture.api_url
    assert account_fixture.url_event == f"{apiurl}/api/v1/ctrl-events/"


def test_account_send_event_delegation(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    # Mock the account_service.send_event function
    mock_service_send_event = mocker.patch("supervaizer.account_service.send_event")
    mock_service_send_event.return_value = ApiSuccess(
        message="Event sent",
        detail={"id": "01JPZ7414FX3JHPNA8N1JXDADX", "response": "success"},
    )

    # Call the account.send_event method
    result = account_fixture.send_event(sender=server_fixture, event=event_fixture)

    # Verify that the account_service.send_event was called with correct parameters
    mock_service_send_event.assert_called_once_with(
        account_fixture, server_fixture, event_fixture
    )
    assert result == mock_service_send_event.return_value


def test_account_register_server_success(
    account_fixture: Account, server_fixture: Server, mocker: MockerFixture
) -> None:
    # Mock the send_event method
    mock_send_event = mocker.patch("supervaizer.account_service.send_event")
    # Use a dictionary instead of SERVER_REGISTER_RESPONSE to avoid JSON decoding issues
    detail = {"id": "01JPZ7414FX3JHPNA8N1JXDADX", "response": "success"}
    mock_send_event.return_value = ApiSuccess(
        message="Event SERVER_REGISTER sent",
        detail=detail,
    )

    result = account_fixture.register_server(server_fixture)
    assert isinstance(result, ApiSuccess)
    assert result.message == "Event SERVER_REGISTER sent"
    # Verify that send_event was called
    mock_send_event.assert_called_once()
