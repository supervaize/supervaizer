# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import json
from typing import Any, Optional

import pytest
from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from rich import inspect

from supervaizer import Server
from supervaizer.agent import Agent
from supervaizer.job import Job, JobContext
from supervaizer.lifecycle import EntityStatus
from supervaizer.parameter import ParametersSetup
from supervaizer.server_utils import ErrorType, create_error_response

insp = inspect


@pytest.fixture
def no_response_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to disable response validation."""

    async def mocked_serialize_response(*args, **kwargs):
        """Accept any args/kwargs and just return the first arg (the response_content)."""
        return args[0] if args else kwargs.get("response_content")

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
    assert server_fixture.url in [
        "http://host.docker.internal:8001",
        "http://localhost:8001",
    ]
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
    server_fixture: Server, job_fixture: Job, mocker: Any
) -> None:
    """Test the get_job_status endpoint"""
    client = TestClient(server_fixture.app)

    # Test success case
    mock_jobs = mocker.patch("supervaizer.routes.Jobs")
    mock_jobs_instance = mocker.MagicMock()
    mock_jobs_instance.get_job.return_value = job_fixture
    mock_jobs.return_value = mock_jobs_instance

    # Use the API key from the server fixture
    headers = {"X-API-Key": server_fixture.api_key or ""}
    response = client.get(f"/supervaizer/jobs/{job_fixture.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["job_id"] == job_fixture.id

    # Test unauthorized access (missing API key)
    response = client.get("/supervaizer/jobs/test-job-id")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]

    # Test job not found case with valid API key
    mock_jobs_instance.get_job.return_value = None
    response = client.get("/supervaizer/jobs/non-existent-job-id", headers=headers)
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception,status_filter,expected_error_type,expected_status",
    [
        (None, None, None, 200),  # Success case, no filter
        (None, EntityStatus.COMPLETED, None, 200),  # Success case with filter
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
    job_fixture: Job,
    mocker: Any,
    monkeypatch: pytest.MonkeyPatch,
    no_response_validation: Any,
    exception: Optional[Exception],
    status_filter: Optional[EntityStatus],
    expected_error_type: Optional[ErrorType],
    expected_status: Optional[int],
) -> None:
    """Test the GET /supervaizer/jobs endpoint for listing all jobs."""
    if not exception:
        monkeypatch.undo()

    if exception:
        # Mock Jobs() to raise an exception when its attribute is accessed
        mock_jobs_class = mocker.patch("supervaizer.routes.Jobs")
        mock_jobs_instance = mocker.MagicMock()
        # Use a property to raise the exception on access
        type(mock_jobs_instance).jobs_by_agent = mocker.PropertyMock(
            side_effect=exception
        )
        mock_jobs_class.return_value = mock_jobs_instance
    else:
        # For non-exception cases, mock the Jobs registry to return jobs
        mock_jobs = mocker.patch("supervaizer.routes.Jobs")
        mock_jobs_instance = mocker.MagicMock()
        mock_jobs.return_value = mock_jobs_instance
        # If filtering, update the job's status to match
        if status_filter:
            job_fixture.status = status_filter
        # The endpoint iterates over jobs_by_agent, so we mock that attribute
        mock_jobs_instance.jobs_by_agent = {
            agent_fixture.name: {job_fixture.id: job_fixture}
        }

    # Add API key headers
    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    # Create test URL and add status filter if provided
    url = "/supervaizer/jobs"
    if status_filter:
        url += f"?status={status_filter.value}"

    # Make the API call for all test cases
    response = client.get(url, headers=headers)

    # Assert expected status code
    assert response.status_code == expected_status

    if not exception:
        # For success cases, check the response body and unauthorized access
        response_data = response.json()
        assert agent_fixture.name in response_data
        assert len(response_data[agent_fixture.name]) > 0
        assert response_data[agent_fixture.name][0]["job_id"] == job_fixture.id

        # Verify unauthorized access
        unauth_response = client.get(url)
        assert unauth_response.status_code == 401
        assert "Not authenticated" in unauth_response.json()["detail"]


def test_utils_routes(server_fixture: Server) -> None:
    """Test the utils routes"""
    client = TestClient(server_fixture.app)

    # Test get_public_key endpoint - note that utils endpoints are not secured
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
    "exception,expected_error_type,expected_status,use_no_response_validation",
    [  # The use_no_response_validation parameter is a dummy to trigger the fixture
        (None, None, status.HTTP_202_ACCEPTED, False),
        (
            ValueError("Job already exists"),
            ErrorType.JOB_ALREADY_EXISTS,
            status.HTTP_409_CONFLICT,
            True,
        ),
        (
            ValueError("Other error"),
            ErrorType.INVALID_REQUEST,
            status.HTTP_400_BAD_REQUEST,
            True,
        ),
        (
            Exception("General error"),
            ErrorType.INTERNAL_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            True,
        ),
    ],
    ids=[
        "success",
        "exception1-job_already_exists",
        "exception2-invalid_request",
        "exception3-internal_error",
    ],
)
async def test_start_job_endpoint(
    server_fixture: Server,
    agent_fixture: Agent,
    job_fixture: Job,
    context_fixture: JobContext,
    parameters_fixture: ParametersSetup,
    monkeypatch: pytest.MonkeyPatch,
    no_response_validation: Any,
    mocker: Any,
    exception: Exception,
    expected_error_type: Optional[ErrorType],
    expected_status: int,
    use_no_response_validation: bool,
) -> None:
    """Test the start_job endpoint with parametrization"""
    i_tested_something = False

    if not use_no_response_validation:
        monkeypatch.undo()

    # Use the real job context and parameters_fixture
    # Remove MagicMock for job context, job fields, job model, etc.

    # Mock the service layer function
    async def mock_service_job_start(*args, **kwargs):
        if exception:
            raise exception
        return job_fixture

    mocker.patch(
        "supervaizer.routes.service_job_start",
        new=mock_service_job_start,
    )

    # Patch Server.decrypt to return parameters_fixture as dict
    mocker.patch(
        "supervaizer.common.decrypt_value",
        "decrypt",
        lambda self, encrypted: json.dumps(
            {k: v.value for k, v in parameters_fixture.definitions.items()}
        ),
    )

    # Set up client with API key
    client = TestClient(server_fixture.app)
    headers: dict[str, Any] = {"X-API-Key": server_fixture.api_key}
    url = f"/supervaizer{agent_fixture.path}/jobs"

    # Always make the API request regardless of exception case
    data = {
        "job_context": {
            "workspace_id": context_fixture.workspace_id,
            "job_id": context_fixture.job_id,
            "started_by": context_fixture.started_by,
            "started_at": context_fixture.started_at.isoformat(),
            "mission_id": context_fixture.mission_id,
            "mission_name": context_fixture.mission_name,
        },
        "job_fields": {},
    }

    # Test with valid auth
    response = client.post(url, json=data, headers=headers)
    i_tested_something = True

    assert response.status_code == expected_status

    if expected_error_type:
        response_data = response.json()
        assert response_data["error_type"] == expected_error_type.value

    assert i_tested_something, "No test was performed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception,status_filter,expected_error_type,expected_status",
    [
        (None, None, None, 200),  # Success case, no filter
        (None, EntityStatus.COMPLETED, None, 200),  # Success case with filter
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
    job_fixture: Job,
    mocker: Any,
    monkeypatch: pytest.MonkeyPatch,
    no_response_validation: Any,
    exception: Optional[Exception],
    status_filter: Optional[EntityStatus],
    expected_error_type: Optional[ErrorType],
    expected_status: Optional[int],
) -> None:
    """Test the get_agent_jobs endpoint with parametrization"""
    i_tested_something = False

    if not exception:
        monkeypatch.undo()

    # Create mock jobs
    mock_jobs = mocker.patch("supervaizer.routes.Jobs")
    mock_jobs_instance = mocker.MagicMock()
    mock_jobs.return_value = mock_jobs_instance

    # Configure based on test parameters
    if exception:
        # Mock the Jobs registry to raise the exception
        mock_jobs_instance.get_agent_jobs.side_effect = exception
    elif status_filter:
        job_fixture.status = status_filter
        jobs_list = [job_fixture]
        mock_jobs_instance.get_agent_jobs.return_value = {j.id: j for j in jobs_list}
    else:
        # The endpoint iterates over the values of the returned dict.
        # Let's make the mock return a list directly to be clearer.
        jobs_list = [job_fixture]
        mock_jobs_instance.get_agent_jobs.return_value = {j.id: j for j in jobs_list}

    # Mock error response for exceptions
    if exception:
        mock_error = mocker.patch("supervaizer.routes.create_error_response")
        error_content = {"detail": str(exception)}
        if expected_error_type:
            error_content["error_type"] = expected_error_type.value
        mock_error.return_value = JSONResponse(
            status_code=expected_status, content=error_content
        )

    # Add API key headers and prepare client
    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    # Create test URL and add status filter if provided
    url = f"/supervaizer/agents/{agent_fixture.slug}/jobs"
    if status_filter:
        url += f"?status={status_filter.value}"

    # Make the API call
    response = client.get(url, headers=headers)
    i_tested_something = True

    assert response.status_code == expected_status

    if not exception:
        assert len(response.json()) > 0

    assert i_tested_something, "No test was performed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_exists,exception,expected_error_type,expected_status,expected_error_message",
    [
        (True, None, None, status.HTTP_200_OK, None),  # Success case
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
    job_fixture: Job,
    mocker: Any,
    monkeypatch: pytest.MonkeyPatch,
    no_response_validation: Any,
    job_exists: bool,
    exception: Optional[Exception],
    expected_error_type: Optional[ErrorType],
    expected_status: Optional[int],
    expected_error_message: Optional[str],
) -> None:
    """Test the get_job_status endpoint for a specific agent with parametrization"""
    i_tested_something = False

    if not exception and job_exists:
        monkeypatch.undo()

    # Simple mocking approach using existing fixtures
    mock_jobs = mocker.patch("supervaizer.routes.Jobs")
    mock_jobs_instance = mocker.MagicMock()
    mock_jobs.return_value = mock_jobs_instance

    # Configure mocks based on test parameters
    if exception:
        mock_jobs_instance.get_job.side_effect = exception
    elif job_exists:
        mock_jobs_instance.get_job.return_value = job_fixture
    else:
        mock_jobs_instance.get_job.return_value = None

    # Mock error response creation for error cases
    if exception or not job_exists:
        mock_error = mocker.patch("supervaizer.routes.create_error_response")
        if exception:
            error_content = {"detail": str(exception)}
            if expected_error_type:
                error_content["error_type"] = expected_error_type.value
            mock_error.return_value = JSONResponse(
                status_code=expected_status, content=error_content
            )
        else:
            error_content = {
                "detail": f"Job with ID {job_fixture.id} not found for agent {agent_fixture.name}"
            }
            if expected_error_type:
                error_content["error_type"] = expected_error_type.value

            mock_error.return_value = JSONResponse(
                status_code=expected_status, content=error_content
            )

    # Set up client and add API key headers
    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    # Create test URL - try different formats
    url = f"/supervaizer{agent_fixture.path}/jobs/{job_fixture.id}"

    # Make the API call
    response = client.get(url, headers=headers)
    i_tested_something = True

    assert response.status_code == expected_status

    if expected_error_type:
        response_data = response.json()
        assert "detail" in response_data
        assert response_data["error_type"] == expected_error_type.value

    assert i_tested_something, "No test was performed"


def test_error_response() -> None:
    """Test error response creation"""
    error = create_error_response(
        ErrorType.INTERNAL_ERROR,
        "Test error",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    assert isinstance(error, JSONResponse)
    assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_server_registration_info(server_fixture: Server) -> None:
    """Test the Server.registration_info property."""
    registration_info = server_fixture.registration_info

    # Verify the structure of registration_info
    assert isinstance(registration_info, dict)

    # Check for required keys
    assert "url" in registration_info
    assert "uri" in registration_info
    assert "api_version" in registration_info
    assert "environment" in registration_info
    assert "public_key" in registration_info
    assert "api_key" in registration_info
    assert "docs" in registration_info
    assert "agents" in registration_info
    assert "url" in registration_info

    # Check values match the fixture
    assert registration_info.pop("public_key").startswith("-----BEGIN PUBLIC KEY")
    assert len(registration_info.pop("agents")) == 1
    url = registration_info.pop("url")
    assert url in [
        "http://host.docker.internal:8001",
        "http://localhost:8001",
    ]
    assert registration_info.pop("docs") == {
        "swagger": f"{url}/docs",
        "redoc": f"{url}/redoc",
        "openapi": f"{url}/openapi.json",
    }
    assert registration_info == {
        "uri": "server:E2-AC-ED-22-BF-B2",
        "api_version": "v1",
        "environment": "test",
        "api_key": "test-api-key",
    }
