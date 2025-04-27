# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# If a copy of the MPL was not distributed with this file, you can obtain one at
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# https://mozilla.org/MPL/2.0/.


from supervaizer import Account
from supervaizer.case import Case, CaseNode, CaseNodeUpdate
from supervaizer.lifecycle import EntityStatus
import pytest


def test_case(case_fixture: Case, case_node_fixture: CaseNode) -> None:
    assert isinstance(case_fixture, Case)
    assert case_fixture.id is not None
    assert case_fixture.name == "Test Case"
    assert case_fixture.description == "Test Case Description"
    assert case_fixture.nodes == [case_node_fixture]


def test_case_start(
    account_fixture: Account, case_node_fixture: CaseNode, respx_mock, mocker
) -> None:
    api_url = account_fixture.api_url
    # mock the start case event response (example for reference only)
    respx_mock.post(f"{api_url}/api/v1/ctrl-events/").respond(
        status_code=200,
        json={
            "id": "01JPZGTY27KFR3Q5P9W2G6NY4E",
            "name": "agent.case.start case:6be515d3-8f5d-4194-9043-146f17463ee4",
            "source": "case:6be515d3-8f5d-4194-9043-146f17463ee4",
            "account": "o34Z484gY9Nxz8axgTAdiH",
            "event_type": "agent.case.start",
            "details": {
                "id": "6be515d3-8f5d-4194-9043-146f17463ee4",
                "job_id": "job123",
                "name": "New Case",
                "account": {
                    "name": "CUSTOMERFIRST",
                    "id": "o34Z484gY9Nxz8axgTAdiH",
                    "api_key": "zYx680h5.73IZfE7c1tPNr6rvdeNwV3IahI6VzHYj",
                    "api_url": "https://ample-strong-coyote.ngrok-free.app",
                },
                "description": "Test Case Description",
                "status": "in_progress",
                "nodes": [
                    {
                        "name": "Test Node",
                        "description": "Test Node Description",
                        "type": "node_type",
                    }
                ],
                "updates": [],
            },
            "created_at": "2025-03-22T18:11:25.896139Z",
            "updated_at": "2025-03-22T18:11:25.896145Z",
            "created_by": 1,
            "updated_by": 1,
        },
    )

    # Mock the account service's send_event method and verify it was called
    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event", return_value=None
    )

    new_case = Case.start(
        job_id="job123",
        account=account_fixture,
        name="New Case",
        description="Test Case Description",
        nodes=[case_node_fixture],
    )

    assert isinstance(new_case, Case)
    assert mock_send_event.call_count == 1


def test_case_close(
    account_fixture: Account, respx_mock, case_fixture: Case, mocker
) -> None:
    # Setup
    case = case_fixture
    case_result = {"status": "success"}
    final_cost = 10.0

    # simulate successful event update
    respx_mock.post(f"{account_fixture.api_url}/api/v1/ctrl-events/").respond(
        status_code=200,
        json={
            "details": {
                "id": "6be515d3-8f5d-4194-9043-146f17463ee4",
            }
        },
    )

    # Mock the account's send_event method to prevent actual API calls
    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event", return_value=None
    )
    # Execute
    case.close(case_result=case_result, final_cost=final_cost)

    # Assert
    assert case.status == EntityStatus.COMPLETED
    assert case.total_cost == final_cost
    assert case.final_delivery == case_result

    assert mock_send_event.call_count == 1


@pytest.mark.asyncio
async def test_case_close_without_final_cost(
    account_fixture: Account, respx_mock, case_fixture: Case, mocker
) -> None:
    # Setup
    case = case_fixture

    # Add some updates with costs
    case.updates = [
        CaseNodeUpdate(cost=5.0, payload={}),
        CaseNodeUpdate(cost=3.0, payload={}),
    ]
    case_result = {"status": "success"}

    # simulate successful event update
    respx_mock.post(f"{account_fixture.api_url}/api/v1/ctrl-events/").respond(
        status_code=200,
        json={
            "details": {
                "id": "6be515d3-8f5d-4194-9043-146f17463ee4",
            }
        },
    )

    # Mock the account's send_event method to prevent actual API calls
    mock_send_event = mocker.patch(
        "supervaizer.account_service.send_event", return_value=None
    )

    # Execute
    case.close(case_result=case_result, final_cost=None)

    # Assert
    assert case.status == EntityStatus.COMPLETED
    assert case.total_cost == 8.0  # Sum of update costs
    assert case.final_delivery == case_result

    assert mock_send_event.call_count == 1
