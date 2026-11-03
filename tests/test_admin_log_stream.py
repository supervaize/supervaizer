# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""The admin log stream: Server-Sent Events built from the log queue."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from supervaizer.admin import routes as admin_routes
from supervaizer.admin.routes import AdminHandlers
from supervaizer.storage import StorageManager


async def open_stream() -> AsyncIterator[str]:
    response = await AdminHandlers(Mock(spec=StorageManager)).log_stream()
    stream: AsyncIterator[str] = response.body_iterator  # type: ignore[assignment]
    return stream


def event(raw: str) -> dict[str, Any]:
    assert raw.startswith("data: ")
    assert raw.endswith("\n\n")
    payload: dict[str, Any] = json.loads(raw.removeprefix("data: "))
    return payload


def waiting_fails_with(mocker: MockerFixture, error: BaseException) -> None:
    """Make every wait on the queue fail at once, without leaving a coroutine unawaited."""

    async def fail(awaitable: Any, timeout: float) -> None:
        awaitable.close()
        raise error

    mocker.patch.object(admin_routes.asyncio, "wait_for", fail)


@pytest.fixture
def queue(mocker: MockerFixture) -> asyncio.Queue[Any]:
    fresh: asyncio.Queue[Any] = asyncio.Queue()
    mocker.patch.object(admin_routes, "log_queue", fresh)
    return fresh


@pytest.mark.asyncio
async def test_first_event_announces_the_connection(queue: asyncio.Queue[Any]) -> None:
    stream = await open_stream()
    first = event(await anext(stream))
    await stream.aclose()  # type: ignore[attr-defined]
    assert first["level"] == "INFO"
    assert first["message"] == "Log stream connected"
    assert first["timestamp"]


@pytest.mark.asyncio
async def test_queued_entries_are_replayed_in_order(queue: asyncio.Queue[Any]) -> None:
    entries = [
        {"timestamp": "t1", "level": "INFO", "message": "one"},
        {"timestamp": "t2", "level": "ERROR", "message": "two"},
    ]
    for entry in entries:
        queue.put_nowait(entry)
    stream = await open_stream()
    await anext(stream)
    replayed = [event(await anext(stream)), event(await anext(stream))]
    await stream.aclose()  # type: ignore[attr-defined]
    assert replayed == entries
    assert queue.empty()


@pytest.mark.asyncio
async def test_queued_entry_that_is_not_a_dict_becomes_an_info_message(
    queue: asyncio.Queue[Any],
) -> None:
    queue.put_nowait("plain text")
    stream = await open_stream()
    await anext(stream)
    replayed = event(await anext(stream))
    await stream.aclose()  # type: ignore[attr-defined]
    assert replayed["level"] == "INFO"
    assert replayed["message"] == "plain text"
    assert replayed["timestamp"]


@pytest.mark.asyncio
async def test_entry_added_after_connect_is_pushed(queue: asyncio.Queue[Any]) -> None:
    stream = await open_stream()
    await anext(stream)
    pending = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)
    queue.put_nowait({"timestamp": "t", "level": "WARNING", "message": "late"})
    pushed = event(await asyncio.wait_for(pending, timeout=2))
    await stream.aclose()  # type: ignore[attr-defined]
    assert pushed == {"timestamp": "t", "level": "WARNING", "message": "late"}


@pytest.mark.asyncio
async def test_late_entry_that_is_not_a_dict_becomes_an_info_message(
    queue: asyncio.Queue[Any],
) -> None:
    stream = await open_stream()
    await anext(stream)
    pending = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)
    queue.put_nowait(42)
    pushed = event(await asyncio.wait_for(pending, timeout=2))
    await stream.aclose()  # type: ignore[attr-defined]
    assert (pushed["level"], pushed["message"]) == ("INFO", "42")


@pytest.mark.asyncio
async def test_idle_stream_sends_a_keepalive(
    queue: asyncio.Queue[Any], mocker: MockerFixture
) -> None:
    waiting_fails_with(mocker, TimeoutError())
    stream = await open_stream()
    await anext(stream)
    keepalive = event(await anext(stream))
    await stream.aclose()  # type: ignore[attr-defined]
    assert (keepalive["level"], keepalive["message"]) == ("SYSTEM", "keepalive")


@pytest.mark.asyncio
async def test_client_disconnect_ends_the_stream_quietly(
    queue: asyncio.Queue[Any], mocker: MockerFixture
) -> None:
    waiting_fails_with(mocker, asyncio.CancelledError())
    stream = await open_stream()
    await anext(stream)
    with pytest.raises(StopAsyncIteration):
        await anext(stream)


@pytest.mark.asyncio
async def test_unexpected_error_is_sent_as_an_error_event_then_the_stream_ends(
    queue: asyncio.Queue[Any], mocker: MockerFixture
) -> None:
    waiting_fails_with(mocker, RuntimeError("queue broke"))
    stream = await open_stream()
    await anext(stream)
    failure = event(await anext(stream))
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert failure["level"] == "ERROR"
    assert failure["message"] == "Log stream error: queue broke"


@pytest.mark.asyncio
async def test_unreadable_queue_during_replay_falls_through_to_waiting(
    mocker: MockerFixture,
) -> None:
    broken = Mock()
    broken.empty.return_value = False
    broken.get_nowait.side_effect = asyncio.QueueEmpty
    mocker.patch.object(admin_routes, "log_queue", broken)
    waiting_fails_with(mocker, TimeoutError())
    stream = await open_stream()
    await anext(stream)
    after_replay = event(await anext(stream))
    await stream.aclose()  # type: ignore[attr-defined]
    assert after_replay["message"] == "keepalive"
