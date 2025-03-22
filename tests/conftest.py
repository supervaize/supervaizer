# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


from datetime import datetime
from uuid import uuid4

import pytest

from supervaize_control import (
    Account,
    Agent,
    AgentMethod,
    AgentSendRegistrationEvent,
    Event,
    EventType,
    Server,
    Telemetry,
    TelemetryCategory,
    TelemetrySeverity,
    TelemetryType,
)
from supervaize_control.job import Job, JobContext


@pytest.fixture
def account_fixture():
    return Account(
        name="CUSTOMERFIRST",
        id="o34Z484gY9Nxz8axgTAdiH",
        api_key="1234567890",
        api_url="https://test.supervaize.com",
    )


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
        job_start_method=agent_method_fixture,
        job_stop_method=agent_method_fixture,
        job_status_method=agent_method_fixture,
        chat_method=agent_method_fixture,
        custom_methods={
            "method1": agent_method_fixture,
            "method2": agent_method_fixture,
        },
    )


@pytest.fixture
def context_fixture():
    return JobContext(
        workspace_id="test-workspace",
        job_id=str(uuid4()),
        started_by="test-user",
        started_at=datetime.now(),
        mission_id="test-mission",
        mission_name="Test Mission",
        mission_context={"test": "context"},
    )


@pytest.fixture
def job_fixture(context_fixture):
    return Job.new(supervaize_context=context_fixture, agent_name="test-agent")


@pytest.fixture
def server_fixture(agent_fixture, account_fixture):
    return Server(
        agents=[agent_fixture],
        host="localhost",
        port=8001,
        environment="test",
        debug=True,
        account=account_fixture,
    )


@pytest.fixture
def event_fixture(account_fixture):
    return Event(
        type=EventType.AGENT_WAKEUP,
        source="test",
        details={"test": "value"},
        account=account_fixture,
    )


@pytest.fixture
def AGENT_REGISTER_event_fixture(agent_fixture, account_fixture):
    return AgentSendRegistrationEvent(
        agent=agent_fixture,
        account=account_fixture,
        polling=False,
    )


@pytest.fixture
def telemetry_fixture():
    return Telemetry(
        agentId="123",
        type=TelemetryType.LOGS,
        category=TelemetryCategory.SYSTEM,
        severity=TelemetrySeverity.INFO,
        details={"message": "Test message"},
    )
