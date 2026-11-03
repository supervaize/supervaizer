# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize protocol event, agent-card, and resource-route behavior."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, cast

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.routing import APIRoute

from supervaizer import Agent, DataResource, Server
from supervaizer.data_routes import _add_resource_routes
from supervaizer.protocol.a2a.events import (
    publish_v2_event,
    stream_v2_events,
)
from supervaizer.protocol.a2a.model import create_agent_card


class _DisconnectingRequest:
    """Minimal request boundary that disconnects after a configurable check."""

    def __init__(self, checks_before_disconnect: int) -> None:
        self._remaining_checks = checks_before_disconnect

    async def is_disconnected(self) -> bool:
        """Return false for the requested checks, then report a disconnect."""
        if self._remaining_checks == 0:
            return True
        self._remaining_checks -= 1
        return False


def _list_contacts() -> list[dict[str, Any]]:
    """Provide a resource list callback for route generation."""
    return []


def _get_contact(item_id: str) -> dict[str, str]:
    """Provide a resource get callback for route generation."""
    return {"id": item_id}


def _create_contact(data: dict[str, Any]) -> dict[str, Any]:
    """Provide a resource create callback for route generation."""
    return {"id": "contact-1", **data}


def _update_contact(item_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Provide a resource update callback for route generation."""
    return {"id": item_id, **data}


def _delete_contact(_item_id: str) -> bool:
    """Provide a resource delete callback for route generation."""
    return True


def _import_contacts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Provide a resource import callback for route generation."""
    return {"imported": len(records)}


def _event_subscribers(server: Server) -> set[asyncio.Queue[dict[str, Any]]]:
    """Read the event subscriber set stored on the server app state."""
    return getattr(server.app.state, "supervaizer_v2_event_subscribers", set())


def _event_stream(
    server: Server, request: Request | None = None
) -> AsyncGenerator[dict[str, str], None]:
    """Cast the event iterator to its concrete async-generator runtime type."""
    return cast(
        AsyncGenerator[dict[str, str], None], stream_v2_events(server, request=request)
    )


@pytest.mark.asyncio
async def test_stream_v2_events_replays_connected_then_published_event(
    server_fixture: Server,
) -> None:
    """A subscriber sees its connection event before later published payloads."""
    stream = _event_stream(server_fixture)

    connected = await anext(stream)
    publish_v2_event(server_fixture, "example.updated", {"id": "item-1"})
    published = await anext(stream)
    await stream.aclose()

    assert connected == {
        "event": "supervaizer.connected",
        "data": json.dumps({"status": "connected"}),
    }
    assert published == {
        "event": "example.updated",
        "data": json.dumps({"id": "item-1"}),
    }
    assert _event_subscribers(server_fixture) == set()


@pytest.mark.asyncio
async def test_stream_v2_events_stops_and_unsubscribes_on_disconnect(
    server_fixture: Server,
) -> None:
    """A disconnected request ends the stream without waiting for an event."""
    stream = _event_stream(
        server_fixture,
        request=cast(Request, _DisconnectingRequest(checks_before_disconnect=0)),
    )

    assert (await anext(stream))["event"] == "supervaizer.connected"
    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    assert _event_subscribers(server_fixture) == set()


@pytest.mark.asyncio
async def test_stream_v2_events_emits_heartbeat_after_wait_timeout(
    server_fixture: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A queue timeout becomes an SSE heartbeat and leaves cleanup to close."""

    async def timeout_wait(awaitable: Any, **_kwargs: Any) -> Any:
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(
        "supervaizer.protocol.a2a.events.asyncio.wait_for", timeout_wait
    )
    stream = _event_stream(server_fixture)

    await anext(stream)
    heartbeat = await anext(stream)
    await stream.aclose()

    assert heartbeat == {
        "event": "supervaizer.heartbeat",
        "data": json.dumps({"status": "ok"}),
    }
    assert _event_subscribers(server_fixture) == set()


@pytest.mark.asyncio
async def test_stream_v2_events_propagates_provider_error_and_unsubscribes(
    server_fixture: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider error reaches the caller and still removes the subscriber."""

    async def fail_wait(awaitable: Any, **_kwargs: Any) -> Any:
        awaitable.close()
        raise RuntimeError("queue provider failed")

    monkeypatch.setattr("supervaizer.protocol.a2a.events.asyncio.wait_for", fail_wait)
    stream = _event_stream(server_fixture)

    await anext(stream)
    with pytest.raises(RuntimeError, match="queue provider failed"):
        await anext(stream)

    assert _event_subscribers(server_fixture) == set()


def test_create_agent_card_for_v2_only_agent_omits_v1_tools_and_post_example(
    agent_fixture: Agent,
) -> None:
    """A v2-only agent card advertises discovery without unavailable v1 calls."""
    agent_fixture.methods = None
    agent_fixture.developer = ""
    agent_fixture.author = "Card Author"
    agent_fixture.release_notes_url = "https://example.test/releases"

    card = create_agent_card(agent_fixture, "https://controller.test")
    endpoint = card["api_endpoints"][0]

    assert card["tools"] == []
    assert card["developer"]["name"] == "Card Author"
    assert card["version_info"] == {
        "current": agent_fixture.version,
        "changelog_url": "https://example.test/releases",
    }
    assert [example["request"]["method"] for example in endpoint["examples"]] == ["GET"]


def test_resource_routes_have_stable_names_operation_ids_and_openapi_shapes(
    server_fixture: Server,
) -> None:
    """A full resource exposes one named route for each declared operation."""
    resource = DataResource(
        name="contacts",
        display_name="Contacts",
        fields=[],
        on_list=_list_contacts,
        on_get=_get_contact,
        on_create=_create_contact,
        on_update=_update_contact,
        on_delete=_delete_contact,
        on_import=_import_contacts,
        importable=True,
    )
    router = APIRouter()

    _add_resource_routes(router, resource, "demo-agent", server_fixture)

    app = FastAPI()
    app.include_router(router)
    openapi = app.openapi()
    operations = {
        operation["operationId"]
        for path in openapi["paths"].values()
        for operation in path.values()
    }
    routes = [cast(APIRoute, route) for route in router.routes]
    route_names = {route.name for route in routes}

    assert operations == {
        "demo-agent_contacts_list",
        "demo-agent_contacts_get",
        "demo-agent_contacts_create",
        "demo-agent_contacts_update",
        "demo-agent_contacts_delete",
        "demo-agent_contacts_import",
    }
    assert route_names == operations
    assert set(openapi["paths"]) == {
        "/data/contacts/",
        "/data/contacts/{item_id}",
        "/data/contacts/import/",
    }
    assert openapi["paths"]["/data/contacts/"]["get"]["summary"] == "List Contacts"
    assert (
        openapi["paths"]["/data/contacts/import/"]["post"]["summary"]
        == "Import Contacts (bulk)"
    )


def test_read_only_resource_routes_omit_all_write_operations(
    server_fixture: Server,
) -> None:
    """A read-only resource registers only its configured read route."""
    resource = DataResource(
        name="catalog",
        fields=[],
        on_list=_list_contacts,
        read_only=True,
    )
    router = APIRouter()

    _add_resource_routes(router, resource, "demo-agent", server_fixture)

    routes = [cast(APIRoute, route) for route in router.routes]

    assert [(route.path, route.methods, route.name) for route in routes] == [
        ("/data/catalog/", {"GET"}, "demo-agent_catalog_list")
    ]
