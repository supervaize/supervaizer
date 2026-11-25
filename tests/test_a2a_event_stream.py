# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import json

import pytest

from supervaizer import Server
from supervaizer.protocol.a2a import events


@pytest.mark.asyncio
async def test_event_stream_continues_after_heartbeat_and_unsubscribes(
    server_fixture: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(events, "HEARTBEAT_SECONDS", 0.01)
    stream = events.stream_v2_events(server_fixture)
    try:
        connected = await asyncio.wait_for(anext(stream), timeout=1)
        heartbeat = await asyncio.wait_for(anext(stream), timeout=1)
        events.publish_v2_event(
            server_fixture, "supervaizer.effect", {"id": "effect-1"}
        )
        effect = await asyncio.wait_for(anext(stream), timeout=1)

        assert connected["event"] == "supervaizer.connected"
        assert heartbeat["event"] == "supervaizer.heartbeat"
        assert json.loads(heartbeat["data"]) == {"status": "ok"}
        assert effect["event"] == "supervaizer.effect"
        assert json.loads(effect["data"]) == {"id": "effect-1"}
    finally:
        await stream.aclose()

    assert not server_fixture.app.state.supervaizer_v2_event_subscribers
