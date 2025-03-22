# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


import pytest

from supervaize_control import AgentSendRegistrationEvent, Event, EventType


def test_event(event_fixture):
    assert isinstance(event_fixture, Event)
    assert event_fixture.type.value == EventType.AGENT_WAKEUP.value
    assert event_fixture.source == "test"
    assert event_fixture.details == {"test": "value"}


def test_AGENT_REGISTER_event(
    AGENT_REGISTER_event_fixture,
    agent_fixture,
):
    assert isinstance(AGENT_REGISTER_event_fixture, AgentSendRegistrationEvent)
    assert isinstance(AGENT_REGISTER_event_fixture, Event)
    assert AGENT_REGISTER_event_fixture.source == agent_fixture.uri
    assert AGENT_REGISTER_event_fixture.type == EventType.AGENT_REGISTER
    assert AGENT_REGISTER_event_fixture.details["name"] == agent_fixture.name


@pytest.mark.parametrize(
    "event_class,event_type,source,details",
    [
        (Event, EventType.AGENT_WAKEUP, "test", {"test": "value"}),
        (
            AgentSendRegistrationEvent,
            EventType.AGENT_REGISTER,
            "agent:123",
            {"name": "test_agent"},
        ),
        (
            ServerSendRegistrationEvent,
            EventType.SERVER_REGISTER,
            "server:123",
            {"url": "http://test"},
        ),
        (CaseStartEvent, EventType.CASE_START, "case:123", {"case_id": "123"}),
        (CaseUpdateEvent, EventType.CASE_UPDATE, "case:123", {"status": "updated"}),
    ],
)
def test_events(event_class, event_type, source, details, account_fixture):
    event = event_class(
        type=event_type, source=source, details=details, account=account_fixture
    )

    assert isinstance(event, Event)
    assert event.type == event_type
    assert event.source == source
    assert event.details == details
    assert event.account == account_fixture

    payload = event.payload
    assert payload["name"] == f"{event_type.value} {source}"
    assert payload["source"] == source
    assert payload["account"] == account_fixture.id
    assert payload["event_type"] == event_type.value
    assert payload["details"] == details
