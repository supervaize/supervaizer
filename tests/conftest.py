# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from datetime import datetime
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from typing_extensions import Annotated

from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    Case,
    CaseNode,
    CaseNodeUpdate,
    CaseStatus,
    Event,
    EventType,
    Job,
    JobContext,
    Parameter,
    Parameters,
    ParametersSetup,
    Server,
    Telemetry,
    TelemetryCategory,
    TelemetrySeverity,
    TelemetryType,
)


@pytest.fixture
def account_fixture() -> Annotated[Account, "fixture"]:
    return Account(
        name="CUSTOMERFIRST",
        id="o34Z484gY9Nxz8axgTAdiH",
        workspace="test-workspace",
        api_key="zYx680h5.73IZfE7c1tPNr6rvdeNwV3IahI6VzHYj",
        api_url="https://ample-strong-coyote.ngrok-free.app",
    )


@pytest.fixture
def agent_method_fixture() -> Annotated[AgentMethod, "fixture"]:
    return AgentMethod(
        name="start",
        method="start",
        params={"param1": "value1"},
        description="Start the agent",
    )


@pytest.fixture(scope="session")
def context_fixture() -> Annotated[JobContext, "fixture"]:
    return JobContext(
        workspace_id="test-workspace",
        job_id="test-job-id",
        started_by="test-user",
        started_at=datetime.now(),
        mission_id="test-mission",
        mission_name="Test Mission",
        mission_context={"test": "context"},
    )


@pytest.fixture(scope="session")
def job_fixture(context_fixture: JobContext) -> Annotated[Job, "fixture"]:
    return Job.new(supervaize_context=context_fixture, agent_name="test-agent")


@pytest.fixture
def event_fixture(account_fixture: Account) -> Annotated[Event, "fixture"]:
    return Event(
        type=EventType.AGENT_WAKEUP,
        source="test",
        details={"test": "value"},
        account=account_fixture,
    )


@pytest.fixture
def telemetry_fixture() -> Annotated[Telemetry, "fixture"]:
    return Telemetry(
        agentId="123",
        type=TelemetryType.LOGS,
        category=TelemetryCategory.SYSTEM,
        severity=TelemetrySeverity.INFO,
        details={"message": "Test message"},
    )


@pytest.fixture
def case_node_fixture() -> Annotated[CaseNode, "fixture"]:
    return CaseNode(
        name="Test Node", description="Test Node Description", type="node_type"
    )


@pytest.fixture
def case_fixture(
    account_fixture: Account, case_node_fixture: CaseNode
) -> Annotated[Case, "fixture"]:
    return Case(
        id=str(uuid4()),
        job_id="job123",
        account=account_fixture,
        status=CaseStatus.IN_PROGRESS,
        name="Test Case",
        description="Test Case Description",
        nodes=[case_node_fixture],
    )


@pytest.fixture
def case_node_update_fixture() -> Annotated[CaseNodeUpdate, "fixture"]:
    return CaseNodeUpdate(
        payload={"test": "value"},
        is_final=True,
        cost=10.0,
    )


@pytest.fixture
def parameter_fixture() -> Annotated[Parameter, "fixture"]:
    return Parameter(
        name="test_parameter",
        value="test_value",
        description="test description",
        is_environment=False,
    )


@pytest.fixture
def parameters_setup_fixture() -> Annotated[ParametersSetup, "fixture"]:
    return ParametersSetup.from_list(
        parameter_list=[
            Parameter(name="parameter1", value="value1", is_environment=True),
            Parameter(name="parameter2", value="value2", description="desc2"),
        ]
    )


@pytest.fixture
def agent_fixture(
    agent_method_fixture: AgentMethod, parameters_setup_fixture: ParametersSetup
) -> Annotated[Agent, "fixture"]:
    return Agent(
        id="LMKyPAS2Q8sKWBY34DS37a",
        name="agentName",
        author="authorName",
        developer="Dev",
        version="1.0.0",
        description="description",
        job_start_method=agent_method_fixture,
        job_stop_method=agent_method_fixture,
        job_status_method=agent_method_fixture,
        chat_method=agent_method_fixture,
        custom_methods={
            "method1": agent_method_fixture,
            "method2": agent_method_fixture,
        },
        parameters_setup=parameters_setup_fixture,
    )


@pytest.fixture
def server_fixture(
    account_fixture: Account, agent_fixture: Agent
) -> Annotated[Server, "fixture"]:
    """Create a server fixture."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return Server(
        scheme="http",
        host="localhost",
        port=8001,
        environment="test",
        mac_addr="E2-AC-ED-22-BF-B2",
        debug=True,
        agent_timeout=10,
        jobs=[],
        private_key=private_key,
        account=account_fixture,
        agents=[agent_fixture],
    )


@pytest.fixture
def parameters_fixture(
    parameters_setup_fixture: ParametersSetup,
) -> Annotated[Parameters, "fixture"]:
    return Parameters(values={"parameter1": "value1", "parameter2": "value2"})
