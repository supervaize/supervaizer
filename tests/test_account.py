# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import pytest
from pytest_mock import MockerFixture
from requests.exceptions import ConnectionError, HTTPError

from supervaizer import Account, ApiSuccess
from supervaizer.event import Event
from supervaizer.server import Server

from . import AUTH_ERROR_RESPONSE, SERVER_REGISTER_RESPONSE, WAKEUP_EVENT_RESPONSE


def test_account(account_fixture: Account) -> None:
    assert isinstance(account_fixture, Account)
    assert account_fixture.name == "CUSTOMERFIRST"
    assert account_fixture.id == "o34Z484gY9Nxz8axgTAdiH"


def test_account_error() -> None:
    with pytest.raises(ValueError):
        Account(
            name="CUSTOMERFIRST",
            id="NOTWORKING",
            api_key="1234567890",
            api_url="https://supervaize.com",
        )


def test_account_api_headers(account_fixture: Account) -> None:
    apikey = account_fixture.api_key
    assert account_fixture.api_headers == {
        "Authorization": f"Api-Key {apikey}",
        "accept": "application/json",
    }


def test_account_url_event(account_fixture: Account) -> None:
    apiurl = account_fixture.api_url
    assert account_fixture.url_event == f"{apiurl}/api/v1/ctrl-events/"


def test_account_send_event_success(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = str(WAKEUP_EVENT_RESPONSE)
    result = account_fixture.send_event(sender=server_fixture, event=event_fixture)
    assert isinstance(result, ApiSuccess)
    assert result.message == "Event AGENT_WAKEUP sent"
    assert result.detail == {"object": WAKEUP_EVENT_RESPONSE}


def test_account_send_event_auth_error(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 403
    mock_post.return_value.text = str(AUTH_ERROR_RESPONSE)
    mock_post.side_effect = HTTPError(
        "403 Client Error: Forbidden for url: https://api.example.com"
    )

    with pytest.raises(HTTPError, match="403 Client Error: Forbidden for url"):
        account_fixture.send_event(sender=server_fixture, event=event_fixture)


def test_account_send_event_url_error(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = ""
    mock_post.side_effect = ConnectionError("HTTPSConnectionPool(host='...")

    with pytest.raises(ConnectionError, match="HTTPSConnectionPool"):
        account_fixture.send_event(sender=server_fixture, event=event_fixture)


def test_account_register_server_success(
    account_fixture: Account, server_fixture: Server, mocker: MockerFixture
) -> None:
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = str(SERVER_REGISTER_RESPONSE)

    result = account_fixture.register_server(server_fixture)
    assert isinstance(result, ApiSuccess)
    assert result.message == "Event SERVER_REGISTER sent"
