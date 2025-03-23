# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from supervaize_control.case import Case, CaseNodeUpdate, CaseStatus


def test_case(case_fixture, case_node_fixture):
    assert isinstance(case_fixture, Case)
    assert case_fixture.id is not None
    assert case_fixture.name == "Test Case"
    assert case_fixture.description == "Test Case Description"
    assert case_fixture.nodes == [case_node_fixture]


def test_case_start(account_fixture, case_node_fixture, requests_mock):
    api_url = account_fixture.api_url
    # mock the start case event response (example for reference only)
    requests_mock.post(
        f"{api_url}/api/v1/ctrl-events/",
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
    new_case = Case.start(
        job_id="job123",
        account=account_fixture,
        name="New Case",
        description="Test Case Description",
        nodes=[case_node_fixture],
    )

    assert isinstance(new_case, Case)


def test_case_close(account_fixture, requests_mock, case_fixture):
    # Setup

    case = case_fixture
    case_result = {"status": "success"}
    final_cost = 10.0

    # simulate successful event update
    requests_mock.post(
        f"{account_fixture.api_url}/api/v1/ctrl-events/",
        status_code=200,
        json={
            "details": {
                "id": "6be515d3-8f5d-4194-9043-146f17463ee4",
            }
        },
    )
    # Execute
    case.close(case_result=case_result, final_cost=final_cost)

    # Assert
    assert case.status == CaseStatus.COMPLETED
    assert case.total_cost == final_cost
    assert case.final_delivery == case_result


def test_case_close_without_final_cost(account_fixture, requests_mock, case_fixture):
    # Setup
    case = case_fixture

    # Add some updates with costs
    case.updates = [
        CaseNodeUpdate(cost=5.0, payload={}),
        CaseNodeUpdate(cost=3.0, payload={}),
    ]
    case_result = {"status": "success"}

    # simulate successful event update
    requests_mock.post(
        f"{account_fixture.api_url}/api/v1/ctrl-events/",
        status_code=200,
        json={
            "details": {
                "id": "6be515d3-8f5d-4194-9043-146f17463ee4",
            }
        },
    )
    # Execute
    case.close(case_result=case_result, final_cost=None)

    # Assert
    assert case.status == CaseStatus.COMPLETED
    assert case.total_cost == 8.0  # Sum of update costs
    assert case.final_delivery == case_result
