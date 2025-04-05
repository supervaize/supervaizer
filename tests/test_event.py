# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from supervaize_control import (
    Account,
    Agent,
    AgentRegisterEvent,
    Case,
    CaseNodeUpdate,
    CaseStartEvent,
    CaseUpdateEvent,
    Event,
    EventType,
    Server,
    ServerRegisterEvent,
)


def test_event(event_fixture: Event) -> None:
    assert isinstance(event_fixture, Event)
    assert event_fixture.type == EventType.AGENT_WAKEUP
    assert event_fixture.source == "test"
    assert event_fixture.details == {"test": "value"}
    assert list(event_fixture.payload.keys()) == [
        "name",
        "source",
        "account",
        "event_type",
        "details",
    ]


def test_agent_register_event(agent_fixture: Agent, account_fixture: Account) -> None:
    agent_register_event = AgentRegisterEvent(
        agent=agent_fixture,
        account=account_fixture,
        polling=False,
    )
    assert isinstance(agent_register_event, AgentRegisterEvent)
    assert agent_register_event.type == EventType.AGENT_REGISTER
    assert agent_register_event.source.split(":")[0] == "agent"
    assert agent_register_event.details["name"] == "agentName"
    assert agent_register_event.details["polling"] is False


def test_server_register_event(
    server_fixture: Server, account_fixture: Account
) -> None:
    server_register_event = ServerRegisterEvent(
        server=server_fixture,
        account=account_fixture,
    )
    assert isinstance(server_register_event, ServerRegisterEvent)
    assert server_register_event.type == EventType.SERVER_REGISTER
    assert server_register_event.source.split(":")[0] == "server"
    assert server_register_event.details == server_fixture.registration_info


def test_case_start_event(case_fixture: Case, account_fixture: Account) -> None:
    case_start_event = CaseStartEvent(
        case=case_fixture,
        account=account_fixture,
    )
    assert isinstance(case_start_event, CaseStartEvent)
    assert case_start_event.type == EventType.CASE_START
    assert case_start_event.source.split(":")[0] == "case"
    assert case_start_event.details == case_fixture.to_dict


def test_case_update_event(
    case_fixture: Case,
    account_fixture: Account,
    case_node_update_fixture: CaseNodeUpdate,
) -> None:
    case_update_event = CaseUpdateEvent(
        case=case_fixture,
        account=account_fixture,
        update=case_node_update_fixture,
    )
    assert isinstance(case_update_event, CaseUpdateEvent)
    assert case_update_event.type == EventType.CASE_UPDATE
    assert case_update_event.source.split(":")[0] == "case"
    assert case_update_event.details == case_node_update_fixture.to_dict
