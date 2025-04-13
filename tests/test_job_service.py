# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import pytest

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
    mock_job.id = "test-job-id"  # Add id attribute to mock
    mock_job.to_dict = {"content": "of the job"}

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
        supervaize_context=context_fixture,
        agent_name=agent_fixture.name,
        parameters=None,
    )

    # Assert background_tasks.add_task was called
    background_tasks.add_task.assert_called_once_with(
        agent_fixture.job_start, mock_job, job_fields, context_fixture
    )

    # Assert an event was sent to the account
    assert mock_event_sent.call_count == 1

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
    mock_job.id = "test-job-id"  # Add id attribute to mock
    mock_job.to_dict = {"content": "of the job"}
    # Mock encrypted parameters
    encrypted_params = "encrypted_string"

    # Patch the necessary functions
    mock_job_new = mocker.patch("supervaizer.job.Job.new", return_value=mock_job)

    # Mock decrypt from common module
    mock_decrypt_value = mocker.patch(
        "supervaizer.job_service.decrypt_value", return_value="decrypted_string"
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
        supervaize_context=context_fixture,
        agent_name=agent_fixture.name,
        parameters="decrypted_string",
    )

    # Assert background_tasks.add_task was called
    background_tasks.add_task.assert_called_once_with(
        agent_fixture.job_start, mock_job, job_fields, context_fixture
    )

    # Assert an event was sent to the account
    assert mock_send_event.call_count == 1

    # Assert the result is the created job
    assert result == mock_job


@pytest.mark.current
@pytest.mark.asyncio
async def test_service_job_start_event_sending(
    server_fixture, agent_fixture, context_fixture, mocker
):
    """Test that JobStartConfirmationEvent is created and sent correctly."""
    # Create a mock for BackgroundTasks
    background_tasks = mocker.MagicMock()
    background_tasks.add_task = mocker.MagicMock(return_value=None)

    # Create mock job fields
    job_fields = mocker.MagicMock()

    # Create a mock job with required attributes
    mock_job = mocker.MagicMock(spec=Job)
    mock_job.id = "test-job-id"  # Add id attribute to mock
    mock_job.to_dict = {"content": "of the job"}
    # Patch Job.new and JobStartConfirmationEvent
    mocker.patch("supervaizer.job.Job.new", return_value=mock_job)
    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event", return_value=None
    )

    # Mock event instance
    mock_event = mocker.MagicMock()
    mock_event_class = mocker.patch("supervaizer.job_service.JobStartConfirmationEvent")
    mock_event_class.return_value = mock_event

    # Call the function
    await service_job_start(
        server=server_fixture,
        background_tasks=background_tasks,
        agent=agent_fixture,
        sv_context=context_fixture,
        job_fields=job_fields,
    )

    # Assert JobStartConfirmationEvent was created correctly
    mock_event_class.assert_called_once()

    # Assert the event was sent to the account
    mock_send_event.assert_called_once()
