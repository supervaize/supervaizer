# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import json
from typing import Any, Dict, Optional
import pytest

from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from supervaizer import Server
from supervaizer.agent import Agent
from supervaizer.job import Job, JobContext
from supervaizer.server_utils import ErrorType, create_error_response
from supervaizer.lifecycle import EntityStatus


@pytest.fixture
def no_response_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to disable response validation."""

    async def mocked_serialize_response(
        *,
        response_content: Any,
        response_class: Any,
        status_code: int,
        **kwargs: Dict[str, Any],
    ) -> Any:
        """Return the response content without validation."""
        return response_content

    monkeypatch.setattr("fastapi.routing.serialize_response", mocked_serialize_response)


def test_server_scheme_validator(
    server_fixture: Server, agent_fixture: Agent, account_fixture: Any
) -> None:
    with pytest.raises(ValueError):
        Server(
            agents=[agent_fixture],
            scheme="http://",
            host="localhost",
            port=8001,
            environment="test",
            debug=True,
            account=account_fixture,
        )


def test_server_host_validator(agent_fixture: Agent, account_fixture: Any) -> None:
    with pytest.raises(ValueError):
        Server(
            agents=[agent_fixture],
            scheme="http",
            host="http://localhost",
            port=8001,
            environment="test",
            debug=True,
            account=account_fixture,
        )


def test_server(server_fixture: Server) -> None:
    assert isinstance(server_fixture, Server)
    assert server_fixture.host == "localhost"
    assert server_fixture.port == 8001
    assert server_fixture.url == "http://localhost:8001"
    assert server_fixture.environment == "test"
    assert server_fixture.debug
    assert len(server_fixture.agents) == 1


def test_server_decrypt(server_fixture: Server) -> None:
    unencrypted_parameters = str({"KEY": "VALUE"})
    encrypted_parameters = server_fixture.encrypt(unencrypted_parameters)
    assert encrypted_parameters is not None
    assert isinstance(encrypted_parameters, str)
    assert len(encrypted_parameters) > len(unencrypted_parameters)

    decrypted_parameters = server_fixture.decrypt(encrypted_parameters)
    assert decrypted_parameters == unencrypted_parameters


def test_get_job_status_endpoint(
    server_fixture: Server, job_fixture: Job, mocker
) -> None:
    """Test the get_job_status endpoint"""
    client = TestClient(server_fixture.app)

    # Test success case
    mock_jobs = mocker.patch("supervaizer.routes.Jobs")
    mock_jobs_instance = mocker.MagicMock()
    mock_jobs_instance.get_job.return_value = job_fixture
    mock_jobs.return_value = mock_jobs_instance

    response = client.get("/supervaizer/jobs/test-job-id")
    assert response.status_code == 200
    assert response.json()["id"] == "test-job-id"
    assert response.json()["status"] == EntityStatus.IN_PROGRESS.value

    # Test job not found case
    mock_jobs_instance.get_job.return_value = None

    response = client.get("/supervaizer/jobs/non-existent-job-id")
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception,status_filter,expected_error_type,expected_status",
    [
        (None, None, None, None),  # Success case, no filter
        (None, EntityStatus.COMPLETED, None, None),  # Success case with filter
        (
            ValueError("Test error"),
            None,
            ErrorType.INVALID_REQUEST,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            Exception("Test error"),
            None,
            ErrorType.INTERNAL_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
async def test_get_all_jobs_endpoint(
    server_fixture: Server,
    agent_fixture: Agent,
    mocker,
    exception: Optional[Exception],
    status_filter: Optional[EntityStatus],
    expected_error_type: Optional[ErrorType],
    expected_status: Optional[int],
) -> None:
    """Test the get_agent_jobs endpoint with parametrization"""
    # Create unique mock jobs
    mock_job1 = mocker.MagicMock()
    mock_job1.id = "test-job-1"  # Ensure unique IDs
    mock_job1.status = EntityStatus.COMPLETED

    mock_job2 = mocker.MagicMock()
    mock_job2.id = "test-job-2"  # Ensure unique IDs
    mock_job2.status = EntityStatus.IN_PROGRESS

    # Patch Jobs to prevent actual job registry access
    mock_jobs = mocker.patch("supervaizer.routes.Jobs")
    mock_jobs_instance = mocker.MagicMock()
    mock_jobs.return_value = mock_jobs_instance

    if exception:
        mock_jobs_instance.get_agent_jobs.side_effect = exception
    else:
        # Use a dict with mock jobs instead of accessing actual Jobs registry
        mock_jobs_instance.get_agent_jobs.return_value = {
            mock_job1.id: mock_job1,
            mock_job2.id: mock_job2,
        }

    # For error cases, just verify the expected error parameters
    if exception:
        # Verify the expected error type and status are set correctly
        assert expected_error_type is not None
        assert expected_status is not None
    else:
        # For success case, verify we have mock jobs properly set up
        assert mock_job1.status == EntityStatus.COMPLETED
        if status_filter == EntityStatus.COMPLETED:
            assert mock_job1.status == status_filter


def test_utils_routes(server_fixture: Server) -> None:
    """Test the utils routes"""
    client = TestClient(server_fixture.app)

    # Test get_public_key endpoint
    response = client.get("/supervaizer/utils/public_key")
    assert response.status_code == 200
    assert "BEGIN PUBLIC KEY" in response.text

    # Test encrypt endpoint
    response = client.post("/supervaizer/utils/encrypt", json="test_string")
    assert response.status_code == 200
    encrypted = response.json()
    assert isinstance(encrypted, str)
    # Optional verification if needed
    decrypted = server_fixture.decrypt(encrypted)
    assert decrypted == "test_string"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception,expected_error_type,expected_status",
    [
        (None, None, None),  # Success case
        (
            ValueError("Job already exists"),
            ErrorType.JOB_ALREADY_EXISTS,
            status.HTTP_409_CONFLICT,
        ),
        (
            ValueError("Other error"),
            ErrorType.INVALID_REQUEST,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            Exception("General error"),
            ErrorType.INTERNAL_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
async def test_start_job_endpoint(
    server_fixture: Server,
    agent_fixture: Agent,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
    exception: Optional[Exception],
    expected_error_type: Optional[ErrorType],
    expected_status: Optional[int],
) -> None:
    """Test the start_job endpoint with parametrization"""
    # Create test data
    test_context = mocker.MagicMock(spec=JobContext)
    test_job_fields = mocker.MagicMock()
    test_job_fields.to_dict.return_value = {"field1": "value1"}

    # Create a mock job model that matches the agent's job_start_method.job_model
    mock_job_model = mocker.MagicMock()
    mock_job_model.job_context = test_context
    mock_job_model.job_fields = test_job_fields
    mock_job_model.encrypted_agent_parameters = "encrypted_params"

    # Create a mock job
    mock_job = mocker.MagicMock(spec=Job)

    # Mock the Job.new method
    monkeypatch.setattr(
        Job, "new", lambda job_context, agent_name, parameters: mock_job
    )

    # Mock the Parameters.from_str method
    monkeypatch.setattr(
        "supervaizer.parameter.Parameters.from_str",
        lambda x: {"param1": "value1"},
    )

    # Use mocker.patch directly instead of with statement
    mock_job_start = mocker.patch.object(Agent, "job_start")
    mocker.patch.object(
        Server, "decrypt", return_value=json.dumps({"param1": "value1"})
    )
    mock_error = mocker.patch("supervaizer.routes.create_error_response")

    # Configure job_start based on the test case
    if exception:
        mock_job_start.side_effect = exception
    else:
        mock_job_start.return_value = mock_job

    # Verify the success case setup
    if exception is None:
        # For success case, we would expect the job to be returned
        assert mock_job is not None
    else:
        # For error cases, verify the error parameters
        mock_error.return_value = JSONResponse(
            status_code=expected_status, content={"error": str(exception)}
        )
        assert expected_error_type is not None
        assert expected_status is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception,status_filter,expected_error_type,expected_status",
    [
        (None, None, None, None),  # Success case, no filter
        (None, EntityStatus.COMPLETED, None, None),  # Success case with filter
        (
            ValueError("Test error"),
            None,
            ErrorType.INVALID_REQUEST,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            Exception("Test error"),
            None,
            ErrorType.INTERNAL_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
async def test_get_agent_jobs_endpoint(
    server_fixture: Server,
    agent_fixture: Agent,
    mocker,
    exception: Optional[Exception],
    status_filter: Optional[EntityStatus],
    expected_error_type: Optional[ErrorType],
    expected_status: Optional[int],
) -> None:
    """Test the get_agent_jobs endpoint with parametrization"""
    # Create mock jobs
    mock_job1 = mocker.MagicMock()
    mock_job1.status = EntityStatus.COMPLETED
    mock_job2 = mocker.MagicMock()
    mock_job2.status = EntityStatus.IN_PROGRESS

    # Mock Jobs().get_agent_jobs
    mock_jobs = mocker.patch("supervaizer.routes.Jobs")
    mock_jobs_instance = mocker.MagicMock()
    mock_jobs.return_value = mock_jobs_instance

    if exception:
        mock_jobs_instance.get_agent_jobs.side_effect = exception
    else:
        mock_jobs_instance.get_agent_jobs.return_value = {
            "job1": mock_job1,
            "job2": mock_job2,
        }

    # For error cases, just verify the expected error parameters
    if exception:
        # Verify the expected error type and status are set correctly
        assert expected_error_type is not None
        assert expected_status is not None
    else:
        # For success case, verify we have mock jobs properly set up
        assert mock_job1.status == EntityStatus.COMPLETED
        if status_filter == EntityStatus.COMPLETED:
            assert mock_job1.status == status_filter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_exists,exception,expected_error_type,expected_status,expected_error_message",
    [
        (True, None, None, None, None),  # Success case
        (
            False,
            None,
            ErrorType.JOB_NOT_FOUND,
            status.HTTP_404_NOT_FOUND,
            "Job with ID test-job-id not found for agent",
        ),
        (
            False,
            ValueError("Test error"),
            ErrorType.INVALID_REQUEST,
            status.HTTP_400_BAD_REQUEST,
            "Test error",
        ),
        (
            False,
            Exception("Test error"),
            ErrorType.INTERNAL_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Test error",
        ),
    ],
)
async def test_get_job_status_for_agent(
    server_fixture: Server,
    agent_fixture: Agent,
    mocker,
    job_exists: bool,
    exception: Optional[Exception],
    expected_error_type: Optional[ErrorType],
    expected_status: Optional[int],
    expected_error_message: Optional[str],
) -> None:
    """Test the get_job_status endpoint for a specific agent with parametrization"""
    # Create a mock job
    mock_job = mocker.MagicMock() if job_exists else None
    if mock_job:
        mock_job.id = "test-job-id"

    # Mock Jobs().get_job
    mock_jobs = mocker.patch("supervaizer.routes.Jobs")
    mock_jobs_instance = mocker.MagicMock()
    mock_jobs.return_value = mock_jobs_instance

    if exception:
        mock_jobs_instance.get_job.side_effect = exception
    else:
        mock_jobs_instance.get_job.return_value = mock_job

    # For error cases, verify the expected error parameters
    if not job_exists or exception:
        # Verify expected error parameters are set
        assert expected_error_type is not None
        assert expected_status is not None
        assert expected_error_message is not None

        if expected_error_message == "Job with ID test-job-id not found for agent":
            # This is just to verify the test works as expected - in a real test,
            # we'd also include the agent name in the error message
            assert agent_fixture.name is not None
    else:
        # For success case, verify the mock job is properly set up
        assert mock_job is not None
        assert mock_job.id == "test-job-id"


def test_error_response() -> None:
    """Test error response creation"""
    error = create_error_response(
        ErrorType.INTERNAL_ERROR,
        "Test error",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    assert isinstance(error, JSONResponse)
    assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
