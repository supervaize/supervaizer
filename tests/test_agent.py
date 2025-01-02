import pytest

from supervaize_control import Agent, AgentMethod


@pytest.fixture
def agent_method_fixture():
    return AgentMethod(
        name="start",
        method="start",
        params={"param1": "value1"},
        description="Start the agent",
    )


@pytest.fixture
def agent_fixture(agent_method_fixture):
    return Agent(
        id="LMKyPAS2Q8sKWBY34DS37a",
        name="agentName",
        author="authorName",
        developer="Dev",
        version="1.0.0",
        description="description",
        start_method=agent_method_fixture,
        stop_method=agent_method_fixture,
        status_method=agent_method_fixture,
        chat_method=agent_method_fixture,
        custom_methods={
            "method1": agent_method_fixture,
            "method2": agent_method_fixture,
        },
    )


def test_agent(agent_fixture):
    assert isinstance(agent_fixture, Agent)
    assert isinstance(agent_fixture.start_method, AgentMethod)
    assert isinstance(agent_fixture.stop_method, AgentMethod)
    assert isinstance(agent_fixture.status_method, AgentMethod)
    assert isinstance(agent_fixture.chat_method, AgentMethod)
    assert isinstance(agent_fixture.custom_methods, dict)
    assert isinstance(agent_fixture.custom_methods["method1"], AgentMethod)
    assert isinstance(agent_fixture.custom_methods["method2"], AgentMethod)


def test_account_error(agent_method_fixture):
    with pytest.raises(ValueError):
        Agent(
            id="WILLFAIL",
            name="agentName",
            author="authorName",
            developer="Dev",
            version="1.0.0",
            description="description",
            start_method=agent_method_fixture,
            stop_method=agent_method_fixture,
            status_method=agent_method_fixture,
            chat_method=agent_method_fixture,
            custom_methods={"method1": agent_method_fixture},
        )


def test_agent_custom_methods(agent_fixture):
    assert agent_fixture.custom_methods_names == ["method1", "method2"]
