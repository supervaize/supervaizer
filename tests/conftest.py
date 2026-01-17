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
    CaseNode,
    CaseNodeType,
    CaseNodeUpdate,
    CaseNodes,
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
) -> "EntityRepository[Any]":  # type: ignore
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
        is_async=False,
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
def case_node_confirm_call() -> Annotated[CaseNode, "fixture"]:
    """Fixture based on step0 from call_agent.py example."""
    return CaseNode(
        name="confirm_call",
        type=CaseNodeType.VALIDATION,
        factory=lambda phone_number: CaseNodeUpdate(
            name=f"Confirm call {phone_number}",
            cost=0.0,
            is_final=False,
            payload={
                "supervaizer_form": {
                    "question": f"Do you really want to place a call to {phone_number}",
                    "answer": {
                        "fields": [
                            {
                                "name": "Place the call",
                                "description": "Place the call",
                                "type": bool,
                                "field_type": "BooleanField",
                                "required": False,
                            },
                            {
                                "name": "Skip",
                                "description": "Skip this call and mark as failed",
                                "type": bool,
                                "field_type": "BooleanField",
                                "required": False,
                            },
                        ],
                    },
                }
            },
        ),
        description="Confirm call before placing it",
    )


@pytest.fixture
def case_node_start_call() -> Annotated[CaseNode, "fixture"]:
    """Fixture based on step_start_call from call_agent.py example."""
    return CaseNode(
        name="start_call",
        type=CaseNodeType.TRIGGER,
        can_be_confirmed=True,
        factory=lambda attempt, call_id: CaseNodeUpdate(
            name=f"📞 Starting Outgoing Call (Try #{attempt})",
            cost=0.0,
            is_final=False,
            payload={
                "attempt": attempt,
                "call_id": call_id,
            },
        ),
        description="Start the call",
    )


@pytest.fixture
def case_node_update_call_status() -> Annotated[CaseNode, "fixture"]:
    """Fixture based on step_update_call_status from call_agent.py example."""
    return CaseNode(
        name="update_call_status",
        type=CaseNodeType.INFO,
        factory=lambda attempt, call_status: CaseNodeUpdate(
            name=f"📞 Call Status (Try #{attempt})",
            cost=0.0,
            payload={
                "call_status": call_status,
            },
            is_final=False,
        ),
        description="Update call status",
    )


@pytest.fixture
def case_node_update_call_completed() -> Annotated[CaseNode, "fixture"]:
    """Fixture based on step_update_call_completed from call_agent.py example."""
    return CaseNode(
        name="update_call_completed",
        type=CaseNodeType.DELIVERY,
        factory=lambda call,
        call_status,
        duration_seconds,
        extracted_values,
        metadata: CaseNodeUpdate(
            name="✅ Call Completed Successfully",
            cost=getattr(call, "cost", 0.0),
            payload={
                "call_id": getattr(call, "call_id", None),
                "call_status": call_status,
                "duration_seconds": duration_seconds,
                "extracted_values": extracted_values,
                "metadata": metadata,
            },
            is_final=False,
        ),
        description="Call completed successfully",
    )


@pytest.fixture
def case_node_update_call_failed() -> Annotated[CaseNode, "fixture"]:
    """Fixture based on step_update_call_failed from call_agent.py example."""
    return CaseNode(
        name="update_call_failed",
        type=CaseNodeType.ERROR,
        factory=lambda call, attempt, error: CaseNodeUpdate(
            name=f"❌ Call Failed (Try #{attempt})",
            cost=getattr(call, "cost", 0.0),
            error=str(error),
            payload={
                "status": "failed",
                "attempt": attempt,
                "error": str(error),
            },
            is_final=False,
        ),
        description="Call failed",
    )


@pytest.fixture
def case_nodes_all_steps(
    case_node_confirm_call: CaseNode,
    case_node_start_call: CaseNode,
    case_node_update_call_status: CaseNode,
    case_node_update_call_completed: CaseNode,
    case_node_update_call_failed: CaseNode,
) -> Annotated[CaseNodes, "fixture"]:
    """Fixture based on all_steps_start_method from call_agent.py example."""
    return CaseNodes(
        nodes=[
            case_node_confirm_call,
            case_node_start_call,
            case_node_update_call_status,
            case_node_update_call_completed,
            case_node_update_call_failed,
        ]
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
    result = ParametersSetup.from_list(
        parameter_list=[
            Parameter(name="parameter1", value="value1", is_environment=True),
            Parameter(name="parameter2", value="value2", description="desc2"),
        ]
    )
    assert result is not None
    return result


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
        a2a_endpoints=True,
        supervisor_account=account_fixture,
        agents=[agent_fixture],
        api_key="test-api-key",
    )


@pytest.fixture
def parameters_fixture(
    parameters_setup_fixture: ParametersSetup,
) -> Annotated[ParametersSetup, "fixture"]:
    result = ParametersSetup.from_list(
        parameter_list=[
            Parameter(name="parameter1", value="value1", is_environment=True),
            Parameter(name="parameter2", value="value2", description="desc2"),
        ]
    )
    assert result is not None
    return result


@pytest.fixture(autouse=True, scope="function")
def reset_storage_manager_singleton_global():
    storage_module.StorageManager._singleton_instance = None


@pytest.fixture(autouse=True, scope="function")
def reset_supervaizer_environment():
    """Reset Supervaizer environment variables to defaults between tests."""
    # Store original values
    original_env = {}
    for key in os.environ:
        if key.startswith("SUPERVAIZER_"):
            original_env[key] = os.environ[key]

    yield

    # Restore original values
    for key in original_env:
        os.environ[key] = original_env[key]
    # Remove any new SUPERVAIZER_ variables that were added
    for key in list(os.environ.keys()):
        if key.startswith("SUPERVAIZER_") and key not in original_env:
            del os.environ[key]
