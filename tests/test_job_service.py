# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import pytest
import uuid
from supervaizer.job_service import service_job_start
from supervaizer.job import Job


@pytest.mark.asyncio
async def test_service_job_start_without_parameters(
    server_fixture, agent_fixture, context_fixture, mocker
):
    """Test service_job_start function without agent parameters."""
    # Create a mock for BackgroundTasks
    background_tasks = mocker.MagicMock()
    background_tasks.add_task = mocker.MagicMock(return_value=None)

    # Create mock job fields (a dictionary with job field values)
    job_fields = mocker.MagicMock()

    # Create a mock job with required attributes
    mock_job = mocker.MagicMock(spec=Job)
    mock_job.id = str(uuid.uuid4())  # Add id attribute to mock
    mock_job.registration_info = {"content": "of the job"}
    # Patch Job.new
    mock_job_new = mocker.patch("supervaizer.job.Job.new", return_value=mock_job)

    # Mock account send_event to avoid actual API calls
    mock_event_sent = mocker.patch(
        "supervaizer.account_service.send_event", return_value=None
    )
    # Call the function
    result = await service_job_start(
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
        encrypted_agent_parameters=None,
    )

    # Assert Job.new was called with correct parameters
    mock_job_new.assert_called_once_with(
        job_context=context_fixture,
        agent_name=agent_fixture.name,
        name="test-job-id",
        parameters=None,
    )

    # Assert background_tasks.add_task was called
    background_tasks.add_task.assert_called_once_with(
        agent_fixture.job_start, mock_job, job_fields, context_fixture, server_fixture
    )

    #
    # Assert no event was sent to the account
    assert mock_event_sent.call_count == 0

    # Assert the result is the created job
    assert result == mock_job


@pytest.mark.asyncio
async def test_service_job_start_with_parameters(
    server_fixture, agent_fixture, context_fixture, mocker
):
    """Test service_job_start function with agent parameters."""
    # Create a mock for BackgroundTasks
    background_tasks = mocker.MagicMock()
    background_tasks.add_task = mocker.MagicMock(return_value=None)

    # Create mock job fields
    job_fields = mocker.MagicMock()

    # Create a mock job with required attributes
    mock_job = mocker.MagicMock(spec=Job)
    mock_job.id = str(uuid.uuid4())
    mock_job.registration_info = {"content": "of the job"}
    # Mock encrypted parameters
    encrypted_params = "encrypted_string"

    # Patch the necessary functions
    mock_job_new = mocker.patch("supervaizer.job.Job.new", return_value=mock_job)

    # Mock decrypt from common module
    mock_decrypt_value = mocker.patch(
        "supervaizer.job_service.decrypt_value",
        return_value='{"test":"decrypted_string"}',
    )

    # Mock account send_event to avoid actual API calls
    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event", return_value=None
    )

    # Call the function
    result = await service_job_start(
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
        encrypted_agent_parameters=encrypted_params,
    )

    # Assert server.decrypt was called
    mock_decrypt_value.assert_called_once_with(
        encrypted_params, server_fixture.private_key
    )

    # Assert Job.new was called with correct parameters
    mock_job_new.assert_called_once_with(
        job_context=context_fixture,
        agent_name=agent_fixture.name,
        name="test-job-id",
        parameters={"test": "decrypted_string"},
    )

    # Assert background_tasks.add_task was called
    background_tasks.add_task.assert_called_once_with(
        agent_fixture.job_start, mock_job, job_fields, context_fixture, server_fixture
    )

    # Assert the result is the created job
    assert result == mock_job

    mock_send_event.assert_not_called()


@pytest.mark.asyncio
async def test_service_job_start_event_sending(
    server_fixture, agent_fixture, context_fixture, mocker
):
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


def test_service_job_finished(server_fixture, mocker):
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

    # Import service_job_finished here to ensure mocks are in place
    from supervaizer.job_service import service_job_finished

    # Call the function
    service_job_finished(job=mock_job, server=server_fixture)

    # Assert JobFinishedEvent was created correctly
    mock_event_class.assert_called_once_with(
        job=mock_job,
        account=server_fixture.supervisor_account,
    )

    # Assert the event was sent to the account
    mock_send_event.assert_called_once()
