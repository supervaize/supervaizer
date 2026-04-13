# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from uuid import uuid4

from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from supervaizer import Account, Case, CaseNodeUpdate, Job, Server
from supervaizer.lifecycle import EntityStatus


def test_update_case_with_answer_success(
    server_fixture: Server,
    job_fixture: Job,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """Test successful case update with answer."""

    test_case = Case(
        id=f"test-case-{uuid4()}",
        job_id=job_fixture.id,
        account=account_fixture,
        status=EntityStatus.AWAITING,  # Set to awaiting for testing
        name="Test Case",
        description="Test Case Description",
    )

    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    # Mock the account service's send_event method to prevent actual API calls
    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event", return_value=None
    )

    # Test data
    request_data = {
        "answer": {"field1": "value1", "field2": "value2"},
        "message": "This is my answer",
    }

    response = client.post(
        f"/supervaizer/jobs/{job_fixture.id}/cases/{test_case.id}/update",
        headers=headers,  # type: ignore
        json=request_data,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert response_data["job_id"] == job_fixture.id
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
    job_fixture: Job,
    account_fixture: Account,
    mocker: MockerFixture,
) -> None:
    """answer.casestep_index routes to Case.patch_step (upsert) instead of receive_human_input."""
    test_case = Case(
        id=f"test-case-upsert-{uuid4()}",
        job_id=job_fixture.id,
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
        "supervaizer.account_service.send_event", return_value=None
    )

    request_data = {
        "answer": {"field1": "value1", "casestep_index": 1},
        "message": "Human reply",
    }

    response = client.post(
        f"/supervaizer/jobs/{job_fixture.id}/cases/{test_case.id}/update",
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
    """When the case is not in the in-memory registry, the route still returns 200.

    Wrong or unknown job_id yields no Case match; the handler forwards to human_answer
    hooks only (stateless replica / empty registry) with case_status unknown — not 404.
    """
    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    request_data = {
        "answer": {"field1": "value1"},
    }

    response = client.post(
        "/supervaizer/jobs/nonexistent-job/cases/test-case/update",
        headers=headers,
        json=request_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["case_status"] == "unknown"
    assert data["job_id"] == "nonexistent-job"


def test_update_case_case_not_found(
    server_fixture: Server,
    job_fixture: Job,
) -> None:
    """When case_id is not registered for the job, registry miss — same as job_not_found path."""
    client = TestClient(server_fixture.app)
    headers = {"X-API-Key": server_fixture.api_key}

    request_data = {
        "answer": {"field1": "value1"},
    }

    response = client.post(
        f"/supervaizer/jobs/{job_fixture.id}/cases/nonexistent-case/update",
        headers=headers,
        json=request_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["case_status"] == "unknown"
    assert data["case_id"] == "nonexistent-case"
    assert data["job_id"] == job_fixture.id


def test_update_case_not_awaiting_input(
    server_fixture: Server,
    job_fixture: Job,
    account_fixture: Account,
) -> None:
    """Test case update when case is not in AWAITING status."""

    test_case = Case(
        id=f"test-case-not-awaiting-{uuid4()}",
        job_id=job_fixture.id,
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
        f"/supervaizer/jobs/{job_fixture.id}/cases/{test_case.id}/update",
        headers=headers,
        json=request_data,
    )

    assert response.status_code == 400
    assert f"Case {test_case.id} is not awaiting input" in response.json()["detail"]


def test_update_case_unauthorized(
    server_fixture: Server, job_fixture: Job, account_fixture: Account
) -> None:
    """Test case update without API key."""

    test_case = Case(
        id=f"test-case-unauth-{uuid4()}",
        job_id=job_fixture.id,
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
        f"/supervaizer/jobs/{job_fixture.id}/cases/{test_case.id}/update",
        json=request_data,
    )

    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]
