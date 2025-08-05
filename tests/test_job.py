# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from datetime import datetime
from typing import Any, Dict
from unittest.mock import patch
from uuid import uuid4

import pytest

from supervaizer.job import Job, JobContext, JobResponse, Jobs
from supervaizer.lifecycle import EntityStatus


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
    return Job.new(
        job_context=context_fixture, agent_name="test-agent", name="test-job"
    )


def test_job_creation(context_fixture: JobContext, job_fixture: Job) -> None:
    job_context = context_fixture
    job = job_fixture
    job_id = job.id
    response = JobResponse(
        job_id=job_id,
        status=EntityStatus.IN_PROGRESS,
        message="Starting job",
        payload={"test": "data"},
    )

    job.add_response(response)
    assert job.job_context == job_context
    assert job.status == EntityStatus.IN_PROGRESS
    assert job.finished_at is None
    assert job.error is None
    assert job.payload == {"test": "data"}


def test_job_add_response(job_fixture: Job) -> None:
    job = job_fixture
    job_id = job.id
    # Add intermediary response - using AWAITING instead of PAUSED
    inter_response = JobResponse(
        job_id=job_id,
        status=EntityStatus.AWAITING,
        message="Waiting for input",
        payload={"progress": "50%"},
    )
    job.add_response(inter_response)

    assert job.status == EntityStatus.AWAITING
    assert job.finished_at is None

    # Add final response
    final_response = JobResponse(
        job_id=job_id,
        status=EntityStatus.COMPLETED,
        message="Complete",
        payload={"result": "success"},
    )
    job.add_response(final_response)

    assert job.status == EntityStatus.COMPLETED
    assert job.result == {"result": "success"}
    assert isinstance(job.finished_at, datetime)


def test_job_error_response(job_fixture: Job) -> None:
    # Create job and add error response
    job = job_fixture
    job_id = job.id
    error_response = JobResponse(
        job_id=job_id,
        status=EntityStatus.FAILED,
        message="Something went wrong",
        payload=None,
    )
    job.add_response(error_response)

    assert job.status == EntityStatus.FAILED
    assert job.error == "Something went wrong"
    assert isinstance(job.finished_at, datetime)


def test_job_human_request(job_fixture: Job) -> None:
    job = job_fixture
    assert job.status == EntityStatus.IN_PROGRESS
    job_id = job.id
    response = JobResponse(
        job_id=job_id,
        status=EntityStatus.AWAITING,
        message="Need human input",
        payload={"question": "What next?"},
    )

    job.add_response(response)

    assert job.status == EntityStatus.AWAITING
    assert job.finished_at is None
    assert job.payload == {"question": "What next?"}


def test_job_status_transitions(job_fixture: Job) -> None:
    """Test job status transitions"""
    # Initial status
    assert job_fixture.status == EntityStatus.IN_PROGRESS

    # Transition to AWAITING
    job_fixture.add_response(
        JobResponse(
            job_id=job_fixture.id,
            status=EntityStatus.AWAITING,
            message="Job awaiting input",
            payload=None,
        )
    )
    assert job_fixture.status is EntityStatus.AWAITING
    assert job_fixture.status != EntityStatus.COMPLETED

    # Transition back to IN_PROGRESS
    job_fixture.add_response(
        JobResponse(
            job_id=job_fixture.id,
            status=EntityStatus.IN_PROGRESS,
            message="Job resumed",
            payload=None,
        )
    )
    assert job_fixture.status is EntityStatus.IN_PROGRESS

    # Transition to COMPLETED
    job_fixture.add_response(
        JobResponse(
            job_id=job_fixture.id,
            status=EntityStatus.COMPLETED,
            message="Job completed",
            payload={"result": "success"},
        )
    )
    assert job_fixture.status is EntityStatus.COMPLETED
    assert job_fixture.status != EntityStatus.IN_PROGRESS

    # Transition to FAILED (this wouldn't happen in normal workflow but we test it)
    job_fixture.add_response(
        JobResponse(
            job_id=job_fixture.id,
            status=EntityStatus.FAILED,
            message="Job failed",
            payload=None,
        )
    )
    assert job_fixture.status is EntityStatus.FAILED
    assert job_fixture.status != EntityStatus.AWAITING


def make_job_dict(job: Job) -> Dict[str, Any]:
    # Helper to convert a Job to a dict for persistence simulation
    d = job.__dict__.copy()
    d["job_context"] = job.job_context.__dict__
    d["status"] = job.status  # Enum, will be handled in Job init
    d["responses"] = []  # Simplify for test
    d["created_at"] = job.created_at
    d["finished_at"] = job.finished_at
    d["case_ids"] = job.case_ids
    return d


def test_get_job_include_persisted_found(job_fixture: Job) -> None:
    # Reset registry to avoid collision
    Jobs().reset()
    # Patch storage_manager.get_object_by_id to simulate a persisted job found in storage
    job = job_fixture
    job_id = job.id
    job_dict = make_job_dict(job)
    with patch("supervaizer.job.storage_manager.get_object_by_id") as mock_get:
        mock_get.return_value = job_dict  # Simulate job found in persistence
        result = Jobs().get_job(job_id, include_persisted=True)
        assert result is not None
        assert result.id == job_id
        assert isinstance(result, Job)


def test_get_job_include_persisted_not_found() -> None:
    # Reset registry to ensure no job is in memory
    Jobs().reset()
    job_id = str(uuid4())  # Use a unique job_id not in memory
    with patch("supervaizer.job.storage_manager.get_object_by_id") as mock_get:
        mock_get.return_value = None  # Simulate job not found in persistence
        result = Jobs().get_job(job_id, include_persisted=True)
        assert result is None
