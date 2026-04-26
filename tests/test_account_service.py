# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import pytest
from httpx import ConnectError, HTTPStatusError
from pytest_mock import MockerFixture

from supervaizer import Account, ApiSuccess
import supervaizer.account_service as account_service
from supervaizer.account_service import send_event, send_event_sync
from supervaizer.common import SvBaseModel
from supervaizer.event import Event
from supervaizer.server import Server

from . import AUTH_ERROR_RESPONSE, WAKEUP_EVENT_RESPONSE


@pytest.mark.asyncio
async def test_send_event_success(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    # Patch the method on the client instance used in account_service
    mock_post = mocker.patch(
        "supervaizer.account_service._httpx_client.post",
        new=mocker.AsyncMock(),
    )
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = str(WAKEUP_EVENT_RESPONSE)
    mock_post.return_value.raise_for_status = mocker.Mock()

    result = await send_event(
        account=account_fixture, sender=server_fixture, event=event_fixture
    )

    mock_post.assert_called_once_with(
        account_fixture.url_event,
        headers=account_fixture.api_headers,
        json=SvBaseModel.serialize_value(event_fixture.payload),
    )
    assert isinstance(result, ApiSuccess)
    assert result.message == f"POST Event {event_fixture.type.name} sent"
    assert result.detail == {"object": WAKEUP_EVENT_RESPONSE}


@pytest.mark.asyncio
async def test_send_event_auth_error(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch(
        "supervaizer.account_service._httpx_client.post",
        new=mocker.AsyncMock(),
    )

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
        await send_event(
            account=account_fixture, sender=server_fixture, event=event_fixture
        )


@pytest.mark.asyncio
async def test_send_event_url_error(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch(
        "supervaizer.account_service._httpx_client.post",
        new=mocker.AsyncMock(),
    )
    mock_post.side_effect = ConnectError("HTTPSConnectionPool(host='...")

    with pytest.raises(ConnectError, match="HTTPSConnectionPool"):
        await send_event(
            account=account_fixture, sender=server_fixture, event=event_fixture
        )


def test_send_event_sync_success(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch("supervaizer.account_service._sync_httpx_client.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = str(WAKEUP_EVENT_RESPONSE)
    mock_post.return_value.raise_for_status = mocker.Mock()

    result = send_event_sync(
        account=account_fixture, sender=server_fixture, event=event_fixture
    )

    mock_post.assert_called_once_with(
        account_fixture.url_event,
        headers=account_fixture.api_headers,
        json=SvBaseModel.serialize_value(event_fixture.payload),
    )
    assert isinstance(result, ApiSuccess)
    assert result.message == f"POST Event {event_fixture.type.name} sent"


def test_send_event_sync_auth_error(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch("supervaizer.account_service._sync_httpx_client.post")
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
        send_event_sync(
            account=account_fixture, sender=server_fixture, event=event_fixture
        )


def test_send_event_sync_url_error(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    mock_post = mocker.patch("supervaizer.account_service._sync_httpx_client.post")
    mock_post.side_effect = ConnectError("HTTPSConnectionPool(host='...")

    with pytest.raises(ConnectError, match="HTTPSConnectionPool"):
        send_event_sync(
            account=account_fixture, sender=server_fixture, event=event_fixture
        )


def test_send_event_sync_local_mode_skips_http(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
    mock_post = mocker.patch("supervaizer.account_service._sync_httpx_client.post")

    result = send_event_sync(
        account=account_fixture, sender=server_fixture, event=event_fixture
    )

    assert isinstance(result, ApiSuccess)
    assert result.message == f"Event {event_fixture.type.name} skipped (local mode)"
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_send_event_local_mode_skips_http(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
    mock_post = mocker.patch(
        "supervaizer.account_service._httpx_client.post",
        new=mocker.AsyncMock(),
    )

    result = await send_event(
        account=account_fixture, sender=server_fixture, event=event_fixture
    )

    assert isinstance(result, ApiSuccess)
    assert result.message == f"Event {event_fixture.type.name} skipped (local mode)"
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_close_httpx_client_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAsyncClient:
        is_closed = False

        def __init__(self) -> None:
            self.close_calls = 0

        async def aclose(self) -> None:
            self.close_calls += 1
            self.is_closed = True

    fake_async_client = FakeAsyncClient()
    monkeypatch.setattr(account_service, "_httpx_client", fake_async_client)

    await account_service.close_httpx_client()
    await account_service.close_httpx_client()

    assert fake_async_client.close_calls == 1


def test_close_httpx_client_sync_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAsyncClient:
        is_closed = False

        def __init__(self) -> None:
            self.close_calls = 0

        async def aclose(self) -> None:
            self.close_calls += 1
            self.is_closed = True

    class FakeSyncClient:
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    fake_async_client = FakeAsyncClient()
    fake_sync_client = FakeSyncClient()
    monkeypatch.setattr(account_service, "_httpx_client", fake_async_client)
    monkeypatch.setattr(account_service, "_sync_httpx_client", fake_sync_client)

    account_service.close_httpx_client_sync()
    account_service.close_httpx_client_sync()

    assert fake_async_client.close_calls == 1
    assert fake_sync_client.close_calls == 2
