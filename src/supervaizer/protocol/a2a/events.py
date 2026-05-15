# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""SSE event stream support for the Supervaizer v2 A2A controller."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import Request

    from supervaizer.server import Server

A2A_EFFECT_EVENT = "supervaizer.effect"
DEFAULT_QUEUE_SIZE = 100
HEARTBEAT_SECONDS = 15.0


def subscribe_v2_events(
    server: "Server",
    *,
    max_size: int = DEFAULT_QUEUE_SIZE,
) -> asyncio.Queue[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_size)
    subscribers = _event_subscribers(server)
    subscribers.add(queue)
    return queue


def unsubscribe_v2_events(server: "Server", queue: asyncio.Queue[dict[str, Any]]) -> None:
    _event_subscribers(server).discard(queue)


def publish_v2_event(server: "Server", event: str, data: dict[str, Any]) -> None:
    payload = {"event": event, "data": data}
    for queue in tuple(_event_subscribers(server)):
        _enqueue_event(queue, payload)


async def stream_v2_events(
    server: "Server",
    *,
    request: "Request | None" = None,
) -> AsyncIterator[dict[str, str]]:
    queue = subscribe_v2_events(server)
    try:
        yield _sse_event("supervaizer.connected", {"status": "connected"})
        while True:
            if request is not None and await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield _sse_event("supervaizer.heartbeat", {"status": "ok"})
                continue
            yield _sse_event(event["event"], event["data"])
    finally:
        unsubscribe_v2_events(server, queue)


def _event_subscribers(server: "Server") -> set[asyncio.Queue[dict[str, Any]]]:
    state = server.app.state
    subscribers = getattr(state, "supervaizer_v2_event_subscribers", None)
    if subscribers is None:
        subscribers = set()
        state.supervaizer_v2_event_subscribers = subscribers
    return subscribers


def _enqueue_event(queue: asyncio.Queue[dict[str, Any]], payload: dict[str, Any]) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(payload)


def _sse_event(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, default=str)}
