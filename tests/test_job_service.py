# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import uuid
from typing import TYPE_CHECKING

import pytest
from pytest_mock import MockerFixture

from supervaizer.job import Job
from supervaizer.job_service import (
    service_job_custom,
    service_job_finished,
    service_job_start,
)
from supervaizer.lifecycle import EntityStatus

if TYPE_CHECKING:
    from supervaizer.agent import Agent
    from supervaizer.job import JobContext
    from supervaizer.server import Server


@pytest.mark.asyncio
async def test_service_job_start_without_parameters(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_start function without agent parameters."""
    background_tasks = mocker.MagicMock()
    job_fields = mocker.MagicMock()
    mock_job = mocker.MagicMock(spec=Job)
    mock_job.registration_info = {"content": "of the job"}
    mock_job_new = mocker.patch("supervaizer.job.Job.new", return_value=mock_job)

    result = await service_job_start(
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
        encrypted_agent_parameters=None,
    )

    mock_job_new.assert_called_once_with(
        job_context=context_fixture,
        agent_name=agent_fixture.name,
        name=context_fixture.job_id,
        agent_parameters=None,
    )
    background_tasks.add_task.assert_called_once_with(
        agent_fixture.job_start, mock_job, job_fields, context_fixture, server_fixture
    )
    assert result == mock_job


@pytest.mark.asyncio
async def test_service_job_start_with_parameters(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_start function with agent parameters."""
    background_tasks = mocker.MagicMock()
    job_fields = mocker.MagicMock()
    mock_job = mocker.MagicMock(spec=Job)
    mock_job.registration_info = {"content": "of the job"}
    encrypted_params = "encrypted_string"
    mock_job_new = mocker.patch("supervaizer.job.Job.new", return_value=mock_job)
    mock_decrypt_value = mocker.patch(
        "supervaizer.job_service.decrypt_value",
        return_value='{"test":"decrypted_string"}',
    )

    result = await service_job_start(
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
        encrypted_agent_parameters=encrypted_params,
    )

    mock_decrypt_value.assert_called_once_with(
        encrypted_params, server_fixture.private_key
    )
    mock_job_new.assert_called_once_with(
        job_context=context_fixture,
        agent_name=agent_fixture.name,
        name=context_fixture.job_id,
        agent_parameters=[{"test": "decrypted_string"}],
    )
    background_tasks.add_task.assert_called_once_with(
        agent_fixture.job_start, mock_job, job_fields, context_fixture, server_fixture
    )
    assert result == mock_job


@pytest.mark.asyncio
async def test_service_job_start_with_empty_decrypted_params(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_start with empty decrypted parameters."""
    background_tasks = mocker.MagicMock()
    job_fields = {"key": "value"}
    encrypted_params = "encrypted_string"

    mock_job = mocker.MagicMock(spec=Job)
    mock_job_new = mocker.patch("supervaizer.job.Job.new", return_value=mock_job)

    # Mock decrypt returning empty string
    _mock_decrypt_value = mocker.patch(
        "supervaizer.job_service.decrypt_value", return_value=""
    )

    _result = await service_job_start(
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
        encrypted_agent_parameters=encrypted_params,
    )

    # Should handle empty decrypted parameters gracefully
    mock_job_new.assert_called_once_with(
        job_context=context_fixture,
        agent_name=agent_fixture.name,
        name=context_fixture.job_id,
        agent_parameters=None,
    )


@pytest.mark.asyncio
async def test_service_job_start_without_parameters_setup(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_start with agent that has no parameters_setup."""
    background_tasks = mocker.MagicMock()
    job_fields = {"key": "value"}

    # Remove parameters_setup from agent
    agent_fixture.parameters_setup = None

    mock_job = mocker.MagicMock(spec=Job)
    mock_job_new = mocker.patch("supervaizer.job.Job.new", return_value=mock_job)

    _result = await service_job_start(
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
        encrypted_agent_parameters="some_encrypted_string",
    )

    # Should not try to decrypt parameters when agent has no parameters_setup
    mock_job_new.assert_called_once_with(
        job_context=context_fixture,
        agent_name=agent_fixture.name,
        name=context_fixture.job_id,
        agent_parameters=None,
    )


@pytest.mark.asyncio
async def test_service_job_start_event_sending(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test that JobStartConfirmationEvent is created and sent correctly."""
    # Create a mock for BackgroundTasks
    background_tasks = mocker.MagicMock()
    background_tasks.add_task = mocker.MagicMock(return_value=None)
    job_id = str(uuid.uuid4())
    # Create mock job fields
    job_fields = mocker.MagicMock()
    context_fixture.job_id = job_id

    # Call the function
    job = await service_job_start(
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
    )
    assert isinstance(job, Job)

    # Assert background_tasks.add_task was called
    background_tasks.add_task.assert_called_once()


def test_service_job_finished(server_fixture: "Server", mocker: MockerFixture) -> None:
    """Test service_job_finished function correctly sends the JobFinishedEvent."""
    # Create a mock job
    mock_job = mocker.MagicMock(spec=Job)
    mock_job.id = str(uuid.uuid4())

    # Mock JobFinishedEvent
    mock_event = mocker.MagicMock()
    mock_event_class = mocker.patch("supervaizer.job_service.JobFinishedEvent")
    mock_event_class.return_value = mock_event

    # Mock account send_event to avoid actual API calls
    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event", return_value=None
    )

    # Call the function
    service_job_finished(job=mock_job, server=server_fixture)

    # Assert JobFinishedEvent was created correctly
    mock_event_class.assert_called_once_with(
        job=mock_job,
        account=server_fixture.supervisor_account,
    )

    # Assert the event was sent to the account
    mock_send_event.assert_called_once()


def test_service_job_finished_without_account(
    server_fixture: "Server", mocker: MockerFixture
) -> None:
    """Test service_job_finished raises assertion error when no account is defined."""
    # Create a mock job
    mock_job = mocker.MagicMock(spec=Job)

    # Remove supervisor account
    server_fixture.supervisor_account = None

    # Should raise AssertionError
    with pytest.raises(AssertionError, match="No account defined"):
        service_job_finished(job=mock_job, server=server_fixture)


@pytest.mark.asyncio
async def test_service_job_custom_new_job(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_custom function with new job creation."""
    background_tasks = mocker.MagicMock()
    job_fields = {"custom_param": "value"}
    method_name = "custom_method"

    # Mock Jobs().get_job to return None (no existing job)
    mock_jobs = mocker.MagicMock()
    mock_jobs.get_job.return_value = None
    _mock_jobs_class = mocker.patch(
        "supervaizer.job_service.Jobs", return_value=mock_jobs
    )

    # Mock Job constructor
    mock_job = mocker.MagicMock(spec=Job)
    mock_job_class = mocker.patch("supervaizer.job_service.Job", return_value=mock_job)

    result = await service_job_custom(
        method_name=method_name,
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
    )

    # Assert Jobs().get_job was called
    mock_jobs.get_job.assert_called_once_with(context_fixture.job_id)

    # Assert new Job was created
    mock_job_class.assert_called_once_with(
        id=context_fixture.job_id,
        job_context=context_fixture,
        agent_name=agent_fixture.name,
        name=context_fixture.mission_name,
        status=EntityStatus.STOPPED,
    )

    # Assert background task was added
    background_tasks.add_task.assert_called_once_with(
        agent_fixture.job_start,
        mock_job,
        job_fields,
        context_fixture,
        server_fixture,
        method_name,
    )

    assert result == mock_job


@pytest.mark.asyncio
async def test_service_job_custom_existing_job(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_custom function with existing job."""
    background_tasks = mocker.MagicMock()
    job_fields = {"custom_param": "value"}
    method_name = "custom_method"

    # Mock existing job
    existing_job = mocker.MagicMock(spec=Job)

    # Mock Jobs().get_job to return existing job
    mock_jobs = mocker.MagicMock()
    mock_jobs.get_job.return_value = existing_job
    _mock_jobs_class = mocker.patch(
        "supervaizer.job_service.Jobs", return_value=mock_jobs
    )

    result = await service_job_custom(
        method_name=method_name,
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
    )

    # Assert existing job was used
    assert result == existing_job

    # Assert background task was added with existing job
    background_tasks.add_task.assert_called_once_with(
        agent_fixture.job_start,
        existing_job,
        job_fields,
        context_fixture,
        server_fixture,
        method_name,
    )


@pytest.mark.asyncio
async def test_service_job_custom_with_parameters(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_custom function with encrypted parameters."""
    background_tasks = mocker.MagicMock()
    job_fields = {"custom_param": "value"}
    method_name = "custom_method"
    encrypted_params = "encrypted_string"

    # Mock Jobs().get_job to return None
    mock_jobs = mocker.MagicMock()
    mock_jobs.get_job.return_value = None
    _mock_jobs_class = mocker.patch(
        "supervaizer.job_service.Jobs", return_value=mock_jobs
    )

    # Mock Job constructor
    mock_job = mocker.MagicMock(spec=Job)
    _mock_job_class = mocker.patch("supervaizer.job_service.Job", return_value=mock_job)

    # Mock decrypt_value
    mock_decrypt_value = mocker.patch(
        "supervaizer.job_service.decrypt_value",
        return_value='{"custom_key": "custom_value"}',
    )

    result = await service_job_custom(
        method_name=method_name,
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
        encrypted_agent_parameters=encrypted_params,
    )

    # Assert decryption was called
    mock_decrypt_value.assert_called_once_with(
        encrypted_params, server_fixture.private_key
    )

    assert result == mock_job


@pytest.mark.asyncio
async def test_service_job_custom_no_job_id(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_custom raises ValueError when job_id is missing."""
    background_tasks = mocker.MagicMock()
    job_fields = {"custom_param": "value"}
    method_name = "custom_method"

    # Remove job_id from context
    context_fixture.job_id = None  # type: ignore

    with pytest.raises(ValueError, match="Job ID is required to start a custom job"):
        await service_job_custom(
            method_name=method_name,
            server=server_fixture,
            background_tasks=background_tasks,
            agent=agent_fixture,
            sv_context=context_fixture,
            job_fields=job_fields,
        )


@pytest.mark.asyncio
async def test_service_job_custom_empty_job_id(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_custom raises ValueError when job_id is empty string."""
    background_tasks = mocker.MagicMock()
    job_fields = {"custom_param": "value"}
    method_name = "custom_method"

    # Set job_id to empty string
    context_fixture.job_id = ""

    with pytest.raises(ValueError, match="Job ID is required to start a custom job"):
        await service_job_custom(
            method_name=method_name,
            server=server_fixture,
            background_tasks=background_tasks,
            agent=agent_fixture,
            sv_context=context_fixture,
            job_fields=job_fields,
        )


@pytest.mark.asyncio
async def test_service_job_custom_with_empty_decrypted_params(
    server_fixture: "Server",
    agent_fixture: "Agent",
    context_fixture: "JobContext",
    mocker: MockerFixture,
) -> None:
    """Test service_job_custom with empty decrypted parameters."""
    # Ensure job_id is set (in case previous tests modified it)
    context_fixture.job_id = "test-job-id"

    # Mock encrypted parameters that would decrypt to None/empty
    encrypted_params = "encrypted_but_empty"
    method_name = "custom_method"
    job_fields = {"custom_param": "value"}
    background_tasks = mocker.MagicMock()

    # Mock decrypt_value to return empty string
    mock_decrypt_value = mocker.patch("supervaizer.job_service.decrypt_value")
    mock_decrypt_value.return_value = ""  # Empty decrypted result

    # Mock Jobs to return None (no existing job)
    mock_jobs = mocker.MagicMock()
    mock_jobs.get_job.return_value = None
    mocker.patch("supervaizer.job_service.Jobs", return_value=mock_jobs)

    # Mock Job creation
    mock_job = mocker.MagicMock()
    mocker.patch("supervaizer.job_service.Job", return_value=mock_job)

    result = await service_job_custom(
        method_name=method_name,
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
        encrypted_agent_parameters=encrypted_params,
    )

    # Should succeed even with empty parameters
    assert result == mock_job
    mock_decrypt_value.assert_called_once_with(
        encrypted_params, server_fixture.private_key
    )
