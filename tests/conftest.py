# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Generator
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from typing_extensions import Annotated

import supervaizer.storage as storage_module
from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    AgentMethods,
    Case,
    CaseNodeUpdate,
    EntityStatus,
    Event,
    EventType,
    Job,
    JobContext,
    Parameter,
    ParametersSetup,
    Server,
    Telemetry,
    TelemetryCategory,
    TelemetrySeverity,
    TelemetryType,
)
from supervaizer.storage import EntityRepository, StorageManager


@pytest.fixture(scope="session")
def temp_db_path() -> Generator[str, None, None]:
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield os.path.join(temp_dir, "test_entities.json")


@pytest.fixture
def storage_manager(temp_db_path: str) -> StorageManager:
    """Create a clean StorageManager instance for testing."""
    # Clear the singleton instance to ensure fresh instance
    # The singleton decorator creates a closure with instances dict
    storage_get_instance = storage_module.StorageManager
    if (
        hasattr(storage_get_instance, "__closure__")
        and storage_get_instance.__closure__
    ):
        # Clear the instances dict in the closure
        for cell in storage_get_instance.__closure__:
            if hasattr(cell.cell_contents, "clear"):
                cell.cell_contents.clear()

    storage = StorageManager(db_path=temp_db_path)
    storage.reset_storage()  # Ensure clean state
    return storage


@pytest.fixture
def mock_entity_class() -> Any:
    """Create a mock entity class for testing repositories."""

    class MockEntity:
        def __init__(self, id: str, name: str, status: str = "active"):
            self.id = id
            self.name = name
            self.status = status

        @property
        def to_dict(self) -> Dict[str, Any]:
            return {"id": self.id, "name": self.name, "status": self.status}

        @classmethod
        def model_validate(cls, data: Dict[str, Any]) -> "MockEntity":
            return cls(**data)

    return MockEntity


@pytest.fixture
def mock_entity_repository(
    storage_manager: "StorageManager", mock_entity_class: Any
) -> "EntityRepository[MockEntity]":  # type: ignore
    """Create a repository with mock entity class for testing."""
    return EntityRepository(mock_entity_class, storage_manager)


@pytest.fixture
def account_fixture() -> Annotated[Account, "fixture"]:
    return Account(
        workspace_id="o34Z484gY9Nxz8axgTAdiH",
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


@pytest.fixture
def context_fixture() -> Annotated[JobContext, "fixture"]:
    # Generate unique IDs for each test run
    unique_id = str(uuid4())[:8]
    return JobContext(
        workspace_id="test-workspace",
        job_id=f"test-job-{unique_id}",
        started_by="test-user",
        started_at=datetime.now(),
        mission_id="test-mission",
        mission_name="Test Mission",
        mission_context={"test": "context"},
    )


@pytest.fixture
def job_fixture(context_fixture: JobContext) -> Annotated[Job, "fixture"]:
    return Job.new(
        job_context=context_fixture,
        agent_name="test-agent",
        name=context_fixture.job_id,
    )


@pytest.fixture
def test_job_context() -> JobContext:
    """Create a test job context for storage tests."""
    return JobContext(
        workspace_id="test-workspace",
        job_id="test-job-123",
        started_by="test-user",
        started_at=datetime.now(),
        mission_id="test-mission",
        mission_name="Test Mission",
    )


@pytest.fixture
def event_fixture(account_fixture: Account) -> Annotated[Event, "fixture"]:
    return Event(
        type=EventType.AGENT_WAKEUP,
        source={"test": "value"},
        details={"test": "value"},
        account=account_fixture,
        object_type="test_event",
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
def case_fixture(
    account_fixture: Account,
) -> Annotated[Case, "fixture"]:
    return Case(
        id=str(uuid4()),
        job_id="job123",
        account=account_fixture,
        status=EntityStatus.IN_PROGRESS,
        name="Test Case",
        description="Test Case Description",
    )


@pytest.fixture
def case_node_update_fixture() -> Annotated[CaseNodeUpdate, "fixture"]:
    return CaseNodeUpdate(
        index=1,
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
        methods=AgentMethods(
            job_start=agent_method_fixture,
            job_stop=agent_method_fixture,
            job_status=agent_method_fixture,
            chat=None,
            custom={"method1": agent_method_fixture, "method2": agent_method_fixture},
        ),
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
        private_key=private_key,
        acp_endpoints=True,
        a2a_endpoints=True,
        supervisor_account=account_fixture,
        agents=[agent_fixture],
        api_key="test-api-key",
    )


@pytest.fixture
def parameters_fixture(
    parameters_setup_fixture: ParametersSetup,
) -> Annotated[ParametersSetup, "fixture"]:
    return ParametersSetup.from_list(
        parameter_list=[
            Parameter(name="parameter1", value="value1", is_environment=True),
            Parameter(name="parameter2", value="value2", description="desc2"),
        ]
    )


@pytest.fixture(autouse=True, scope="function")
def reset_storage_manager_singleton_global():
    storage_module.StorageManager._singleton_instance = None
