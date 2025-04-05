# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from datetime import datetime
from uuid import uuid4

import pytest

from supervaize_control.job import Job, JobContext, JobResponse, JobStatus


@pytest.fixture
def context_fixture() -> JobContext:
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
def job_fixture(context_fixture: JobContext) -> Job:
    return Job.new(supervaize_context=context_fixture, agent_name="test-agent")


def test_job_creation(context_fixture: JobContext, job_fixture: Job) -> None:
    supervaize_context = context_fixture
    job = job_fixture
    job_id = job.id
    response = JobResponse(
        job_id=job_id,
        status=JobStatus.IN_PROGRESS,
        message="Starting job",
        payload={"test": "data"},
    )

    job.add_response(response)
    assert job.supervaize_context == supervaize_context
    assert job.status == JobStatus.IN_PROGRESS
    assert job.finished_at is None
    assert job.error is None
    assert job.payload == {"test": "data"}


def test_job_add_response(job_fixture: Job) -> None:
    job = job_fixture
    job_id = job.id
    # Add intermediary response
    inter_response = JobResponse(
        job_id=job_id,
        status=JobStatus.PAUSED,
        message="Processing",
        payload={"progress": "50%"},
    )
    job.add_response(inter_response)

    assert job.status == JobStatus.PAUSED
    assert job.finished_at is None

    # Add final response
    final_response = JobResponse(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        message="Complete",
        payload={"result": "success"},
    )
    job.add_response(final_response)

    assert job.status == JobStatus.COMPLETED
    assert job.result == {"result": "success"}
    assert isinstance(job.finished_at, datetime)


def test_job_error_response(job_fixture: Job) -> None:
    # Create job and add error response
    job = job_fixture
    job_id = job.id
    error_response = JobResponse(
        job_id=job_id,
        status=JobStatus.FAILED,
        message="Something went wrong",
        payload=None,
    )
    job.add_response(error_response)

    assert job.status == JobStatus.FAILED
    assert job.error == "Something went wrong"
    assert isinstance(job.finished_at, datetime)


def test_job_human_request(job_fixture: Job) -> None:
    job = job_fixture
    assert job.status == JobStatus.IN_PROGRESS
    job_id = job.id
    response = JobResponse(
        job_id=job_id,
        status=JobStatus.WAITING,
        message="Need human input",
        payload={"question": "What next?"},
    )

    job.add_response(response)

    assert job.status == JobStatus.WAITING
    assert job.finished_at is None
    assert job.payload == {"question": "What next?"}
