import pytest

from supervaize_control import AgentSendRegistrationEvent, Event, EventType
from tests.test_agent import agent_method_fixture, agent_fixture

agent_method_fixture = agent_method_fixture
agent_fixture = agent_fixture


@pytest.fixture
def event_fixture():
    return Event(
        type=EventType.AGENT_SEND_WAKEUP,
        source="test",
        details={"test": "value"},
    )


@pytest.fixture
def agent_send_registration_event_fixture(agent_fixture):
    return AgentSendRegistrationEvent(agent=agent_fixture)


def test_event(event_fixture):
    assert isinstance(event_fixture, Event)
    assert event_fixture.type.value == EventType.AGENT_SEND_WAKEUP.value
    assert event_fixture.source == "test"
    assert event_fixture.details == {"test": "value"}


def test_agent_send_registration_event(
    agent_send_registration_event_fixture, agent_fixture
):
    assert isinstance(agent_send_registration_event_fixture, AgentSendRegistrationEvent)
    assert isinstance(agent_send_registration_event_fixture, Event)
    assert agent_send_registration_event_fixture.source == agent_fixture.uri
    assert (
        agent_send_registration_event_fixture.type == EventType.AGENT_SEND_REGISTRATION
    )
    assert agent_send_registration_event_fixture.details["name"] == agent_fixture.name
