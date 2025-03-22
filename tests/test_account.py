# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


import pytest

from supervaize_control import Account, ApiSuccess


def test_account(account_fixture):
    assert isinstance(account_fixture, Account)
    assert account_fixture.name == "CUSTOMERFIRST"
    assert account_fixture.id == "o34Z484gY9Nxz8axgTAdiH"


def test_account_error():
    with pytest.raises(ValueError):
        Account(
            name="CUSTOMERFIRST",
            id="NOTWORKING",
            api_key="1234567890",
            api_url="https://supervaize.com",
        )


def test_account_api_headers(account_fixture):
    apikey = account_fixture.api_key
    assert account_fixture.api_headers == {
        "Authorization": f"Api-Key {apikey}",
        "accept": "application/json",
    }


def test_account_url_event(account_fixture):
    apiurl = account_fixture.api_url
    assert account_fixture.url_event == f"{apiurl}/api/v1/ctrl-events/"


def test_account_send_event_success(
    account_fixture, event_fixture, server_fixture, mocker
):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_response = {
        "id": "01JPZ430YYATCVK48ADMSC8QDV",
        "name": "agent.wakeup test",
        "source": "test",
        "account": "o34Z484gY9Nxz8axgTAdiH",
        "event_type": "agent.wakeup",
        "details": {"test": "value"},
        "created_at": "2025-03-22T14:28:39.519242Z",
        "updated_at": "2025-03-22T14:28:39.519254Z",
        "created_by": 1,
        "updated_by": 1,
    }
    mock_post.return_value.text = str(mock_response)
    result = account_fixture.send_event(sender=server_fixture, event=event_fixture)
    assert isinstance(result, ApiSuccess)
    assert result.message == "Event AGENT_WAKEUP sent"
    assert result.detail == mock_response


def test_account_send_event_auth_error(
    account_fixture, event_fixture, server_fixture, mocker
):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 403
    mock_post.return_value.text = "Unauthorized"
    mock_response = {"detail": "Authentication credentials were not provided."}
    mock_post.return_value.text = str(mock_response)
    from requests.exceptions import HTTPError

    mock_post.side_effect = HTTPError(
        "403 Client Error: Forbidden for url: https://api.example.com"
    )

    with pytest.raises(HTTPError, match="403 Client Error: Forbidden for url"):
        account_fixture.send_event(sender=server_fixture, event=event_fixture)


def test_account_send_event_url_error(
    account_fixture, event_fixture, server_fixture, mocker
):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = ""
    from requests.exceptions import ConnectionError

    mock_post.side_effect = ConnectionError("HTTPSConnectionPool(host='...")

    with pytest.raises(ConnectionError, match="HTTPSConnectionPool"):
        account_fixture.send_event(sender=server_fixture, event=event_fixture)


def test_account_register_server_success(account_fixture, server_fixture, mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_response = {
        "id": "01JPZ7414FX3JHPNA8N1JXDADX",
        "name": "server.send.registration server:E2-AC-ED-22-BF-B1",
        "source": "server:E2-AC-ED-22-BF-B1",
        "account": "o34Z484gY9Nxz8axgTAdiH",
        "event_type": "server.register",
        "details": {
            "url": "http://localhost:8001",
            "uri": "server:E2-AC-ED-22-BF-B1",
            "environment": "test",
            "agents": [
                {
                    "name": "agentName",
                    "id": "LMKyPAS2Q8sKWBY34DS37a",
                    "author": "authorName",
                    "developer": "Dev",
                    "version": "1.0.0",
                    "description": "description",
                    "tags": None,
                    "uri": "agent:LMKyPAS2Q8sKWBY34DS37a",
                    "slug": "agentname",
                    "job_start_method": {
                        "name": "start",
                        "method": "start",
                        "params": {"param1": "value1"},
                        "fields": [],
                        "description": "Start the agent",
                    },
                    "job_stop_method": {
                        "name": "start",
                        "method": "start",
                        "params": {"param1": "value1"},
                        "fields": [],
                        "description": "Start the agent",
                    },
                    "job_status_method": {
                        "name": "start",
                        "method": "start",
                        "params": {"param1": "value1"},
                        "fields": [],
                        "description": "Start the agent",
                    },
                    "chat_method": {
                        "name": "start",
                        "method": "start",
                        "params": {"param1": "value1"},
                        "fields": [],
                        "description": "Start the agent",
                    },
                    "custom_methods": {
                        "method1": {
                            "name": "start",
                            "method": "start",
                            "params": {"param1": "value1"},
                            "fields": [],
                            "description": "Start the agent",
                        },
                        "method2": {
                            "name": "start",
                            "method": "start",
                            "params": {"param1": "value1"},
                            "fields": [],
                            "description": "Start the agent",
                        },
                    },
                }
            ],
        },
        "created_at": "2025-03-22T15:21:38.191669Z",
        "updated_at": "2025-03-22T15:21:38.191675Z",
        "created_by": 1,
        "updated_by": 1,
    }
    mock_post.return_value.text = str(mock_response)

    result = account_fixture.register_server(server_fixture)
    assert isinstance(result, ApiSuccess)
    assert result.message == "Event SERVER_REGISTER sent"
