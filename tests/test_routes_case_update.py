# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.

from collections.abc import Generator
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    AgentMethods,
    Case,
    CaseNodeUpdate,
    Job,
    JobResponse,
    Parameter,
    ParametersSetup,
    Server,
)
from supervaizer.job import Jobs
from supervaizer.lifecycle import EntityStatus


@pytest.fixture(autouse=True)
def _jobs_registry_isolation() -> Generator[None, None, None]:
    Jobs().reset()
    yield
    Jobs().reset()


@pytest.fixture
def job_on_server(job_fixture: Job, server_fixture: Server) -> Job:
    """Register job_fixture in Jobs() under the server's agent name (required for POST .../update)."""
    # Server startup reloads persisted jobs into Jobs(); clear so this job is authoritative.
    Jobs().reset()
    job_fixture.agent_name = server_fixture.agents[0].name
    Jobs().add_job(job_fixture)
    return job_fixture


def test_update_case_with_answer_success(
    server_fixture: Server,
    job_on_server: Job,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """Test successful case update with answer."""

    test_case = Case(
        id=f"test-case-{uuid4()}",
        job_id=job_on_server.id,
        account=account_fixture,
        status=EntityStatus.AWAITING,  # Set to awaiting for testing
        name="Test Case",
        description="Test Case Description",
    )

    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    # Mock the account service's send_event method to prevent actual API calls
    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event",
        new=mocker.AsyncMock(return_value=None),
    )

    # Test data
    request_data = {
        "answer": {"field1": "value1", "field2": "value2"},
        "message": "This is my answer",
    }

    response = client.post(
        f"/api/supervaizer/jobs/{job_on_server.id}/cases/{test_case.id}/update",
        headers=headers,  # type: ignore
        json=request_data,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert response_data["job_id"] == job_on_server.id
    assert response_data["case_id"] == test_case.id
    assert response_data["case_status"] == EntityStatus.IN_PROGRESS.value

    # Verify the case was updated
    assert test_case.status == EntityStatus.IN_PROGRESS
    assert len(test_case.updates) == 1
    assert test_case.updates[0].payload["answer"] == request_data["answer"]
    assert test_case.updates[0].payload["message"] == request_data["message"]

    # Verify send_event was called (send_update_case calls send_event internally)
    assert mock_send_event.call_count == 1


def test_update_case_with_casestep_index_patches_step(
    server_fixture: Server,
    job_on_server: Job,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """answer.casestep_index routes to Case.patch_step (upsert) instead of receive_human_input."""
    test_case = Case(
        id=f"test-case-upsert-{uuid4()}",
        job_id=job_on_server.id,
        account=account_fixture,
        status=EntityStatus.AWAITING,
        name="Test Case",
        description="Test Case Description",
    )
    prior = CaseNodeUpdate(name="Question", payload={"supervaizer_form": {"q": "?"}})
    prior.index = 1
    test_case.updates = [prior]

    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event",
        new=mocker.AsyncMock(return_value=None),
    )

    request_data = {
        "answer": {"field1": "value1", "casestep_index": 1},
        "message": "Human reply",
    }

    response = client.post(
        f"/api/supervaizer/jobs/{job_on_server.id}/cases/{test_case.id}/update",
        headers=headers,  # type: ignore
        json=request_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["case_status"] == EntityStatus.IN_PROGRESS.value

    assert len(test_case.updates) == 1
    assert test_case.updates[0].upsert is True
    assert test_case.updates[0].index == 1
    assert test_case.status == EntityStatus.IN_PROGRESS
    assert mock_send_event.call_count == 1


def test_update_case_job_not_found(server_fixture: Server) -> None:
    """Unknown job_id returns 404; human_answer is not dispatched."""
    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    request_data = {
        "answer": {"field1": "value1"},
    }

    response = client.post(
        "/api/supervaizer/jobs/nonexistent-job/cases/test-case/update",
        headers=headers,
        json=request_data,
    )

    assert response.status_code == 404
    data = response.json()
    assert "nonexistent-job" in data["detail"]


def test_update_case_case_not_found(
    server_fixture: Server,
    job_on_server: Job,
) -> None:
    """Unknown case_id for the job returns 404; no success body or human_answer path."""
    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    request_data = {
        "answer": {"field1": "value1"},
    }

    response = client.post(
        f"/api/supervaizer/jobs/{job_on_server.id}/cases/nonexistent-case/update",
        headers=headers,
        json=request_data,
    )

    assert response.status_code == 404
    assert "nonexistent-case" in response.json()["detail"]


def test_update_case_not_awaiting_input(
    server_fixture: Server,
    job_on_server: Job,
    account_fixture: Account,
) -> None:
    """Test case update when case is not in AWAITING status."""

    test_case = Case(
        id=f"test-case-not-awaiting-{uuid4()}",
        job_id=job_on_server.id,
        account=account_fixture,
        status=EntityStatus.IN_PROGRESS,  # Not awaiting
        name="Test Case",
        description="Test Case Description",
    )

    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    request_data = {
        "answer": {"field1": "value1"},
    }

    response = client.post(
        f"/api/supervaizer/jobs/{job_on_server.id}/cases/{test_case.id}/update",
        headers=headers,
        json=request_data,
    )

    assert response.status_code == 400
    assert f"Case {test_case.id} is not awaiting input" in response.json()["detail"]


def test_update_case_unauthorized(
    server_fixture: Server, job_on_server: Job, account_fixture: Account
) -> None:
    """Test case update without API key."""

    test_case = Case(
        id=f"test-case-unauth-{uuid4()}",
        job_id=job_on_server.id,
        account=account_fixture,
        status=EntityStatus.AWAITING,
        name="Test Case",
        description="Test Case Description",
    )

    client = TestClient(server_fixture.app)

    request_data = {
        "answer": {"field1": "value1"},
    }

    response = client.post(
        f"/api/supervaizer/jobs/{job_on_server.id}/cases/{test_case.id}/update",
        json=request_data,
    )

    assert response.status_code == 401
    assert (
        "API key" in response.json()["detail"]
    )  # <-- MODIFIED: require_api_key message


def test_human_answer_uses_workbench_style_params_and_strips_casestep_index(
    server_fixture: Server,
    job_on_server: Job,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """human_answer is invoked via Agent._execute with fields/context (not answer=)."""
    ha = AgentMethod(
        name="human_answer",
        method="supervaizer.examples.hello_world_agent.human_answer",
        params={},
        description="HITL",
        is_async=False,
    )
    agent = server_fixture.agents[0]
    assert agent.methods is not None
    agent.methods = agent.methods.model_copy(update={"human_answer": ha})

    mock_execute = mocker.patch.object(
        agent,
        "_execute",
        return_value=JobResponse(
            job_id=job_on_server.id,
            status=EntityStatus.IN_PROGRESS,
            message="ok",
        ),
    )

    test_case = Case(
        id=f"test-case-ha-{uuid4()}",
        job_id=job_on_server.id,
        account=account_fixture,
        status=EntityStatus.AWAITING,
        name="Test Case",
        description="Test",
    )
    mocker.patch(
        "supervaizer.account_service.send_event",
        new=mocker.AsyncMock(return_value=None),
    )

    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}
    request_data = {
        "answer": {"field1": "x", "casestep_index": 2},
        "message": "hi",
    }

    response = client.post(
        f"/api/supervaizer/jobs/{job_on_server.id}/cases/{test_case.id}/update",
        headers=headers,
        json=request_data,
    )
    assert response.status_code == 200
    mock_execute.assert_called_once()
    _method, params = mock_execute.call_args[0]
    assert "human_answer" in _method
    # casestep_index is stripped from fields for the hook only; payload keeps full answer
    assert params["fields"] == {"field1": "x"}
    assert params["context"] == {"job_id": job_on_server.id, "case_id": test_case.id}
    assert params["payload"] == request_data["answer"]
    assert params["job_id"] == job_on_server.id
    assert params["case_id"] == test_case.id
    assert params["message"] == "hi"


def test_human_answer_only_owning_agent_executed(
    account_fixture: Account,
    job_fixture: Job,
    mocker: MockerFixture,
) -> None:
    """Only the job owner's human_answer runs when multiple agents are registered."""
    ha = AgentMethod(
        name="human_answer",
        method="supervaizer.examples.hello_world_agent.human_answer",
        params={},
        description="HITL",
        is_async=False,
    )
    stub_method = AgentMethod(
        name="start",
        method="start",
        params={},
        description="s",
        is_async=False,
    )
    methods = AgentMethods(
        job_start=stub_method,
        job_stop=stub_method,
        job_status=stub_method,
        chat=None,
        custom={"m1": stub_method},
        human_answer=ha,
    )
    params_setup = ParametersSetup.from_list([
        Parameter(name="p", value="v", is_environment=True)
    ])
    assert params_setup is not None
    owner = Agent(
        name="owner-agent",
        author="a",
        developer="d",
        version="1",
        description="d",
        methods=methods,
        parameters_setup=params_setup,
    )
    other = Agent(
        name="other-agent",
        author="a",
        developer="d",
        version="1",
        description="d",
        methods=methods,
        parameters_setup=params_setup,
    )
    server = Server(
        scheme="http",
        host="localhost",
        port=8011,
        environment="test",
        mac_addr="E2-AC-ED-22-BF-B2",
        debug=True,
        agent_timeout=10,
        private_key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
        a2a_endpoints=True,
        supervisor_account=account_fixture,
        agents=[owner, other],
        api_key="test-api-key-two",
    )
    Jobs().reset()
    job_fixture.agent_name = "owner-agent"
    Jobs().add_job(job_fixture)

    test_case = Case(
        id=f"case-owner-only-{uuid4()}",
        job_id=job_fixture.id,
        account=account_fixture,
        status=EntityStatus.AWAITING,
        name="c",
        description="c",
    )
    mocker.patch(
        "supervaizer.account_service.send_event",
        new=mocker.AsyncMock(return_value=None),
    )

    mock_owner = mocker.patch.object(
        owner,
        "_execute",
        return_value=JobResponse(
            job_id=job_fixture.id,
            status=EntityStatus.IN_PROGRESS,
            message="ok",
        ),
    )
    mock_other = mocker.patch.object(
        other,
        "_execute",
        return_value=JobResponse(
            job_id=job_fixture.id,
            status=EntityStatus.IN_PROGRESS,
            message="ok",
        ),
    )

    client = TestClient(server.app)
    headers = {"X-API-Key": server.api_key}
    response = client.post(
        f"/api/supervaizer/jobs/{job_fixture.id}/cases/{test_case.id}/update",
        headers=headers,
        json={"answer": {"a": 1}},
    )
    assert response.status_code == 200
    mock_owner.assert_called_once()
    mock_other.assert_not_called()


def test_human_answer_skipped_when_job_agent_not_on_server(
    server_fixture: Server,
    job_on_server: Job,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """If job.agent_name does not match any server agent, hook is skipped (no crash)."""
    job_on_server.agent_name = "ghost-agent-not-on-server"
    Jobs().reset()
    Jobs().add_job(job_on_server)

    test_case = Case(
        id=f"case-ghost-{uuid4()}",
        job_id=job_on_server.id,
        account=account_fixture,
        status=EntityStatus.AWAITING,
        name="c",
        description="c",
    )
    mocker.patch(
        "supervaizer.account_service.send_event",
        new=mocker.AsyncMock(return_value=None),
    )

    spy = mocker.patch.object(
        server_fixture.agents[0],
        "_execute",
        return_value=JobResponse(
            job_id=job_on_server.id,
            status=EntityStatus.IN_PROGRESS,
            message="ok",
        ),
    )

    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}
    response = client.post(
        f"/api/supervaizer/jobs/{job_on_server.id}/cases/{test_case.id}/update",
        headers=headers,
        json={"answer": {"x": 1}},
    )
    assert response.status_code == 200
    spy.assert_not_called()
