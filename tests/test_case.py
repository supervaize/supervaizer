# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# If a copy of the MPL was not distributed with this file, you can obtain one at
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# https://mozilla.org/MPL/2.0/.


from typing import Any

import pytest
from pytest_mock import MockerFixture

from supervaizer import Account, CaseNode, CaseNodeType, CaseNodes
from supervaizer.case import Case, CaseNodeUpdate
from supervaizer.lifecycle import EntityStatus


def test_case(
    case_fixture: Case,
) -> None:
    assert isinstance(case_fixture, Case)
    assert case_fixture.id is not None
    assert case_fixture.name == "Test Case"
    assert case_fixture.description == "Test Case Description"


def test_case_start(
    account_fixture: Account,
    respx_mock: Any,
    mocker: MockerFixture,
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
    )

    assert isinstance(new_case, Case)
    assert mock_send_event.call_count == 1


def test_case_close(
    account_fixture: Account,
    respx_mock: Any,
    case_fixture: Case,
    mocker: MockerFixture,
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
    account_fixture: Account,
    respx_mock: Any,
    case_fixture: Case,
    mocker: MockerFixture,
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


def test_case_node_instantiation(
    case_node_confirm_call: CaseNode,
) -> None:
    """Test CaseNode instantiation with VALIDATION type."""
    assert isinstance(case_node_confirm_call, CaseNode)
    assert case_node_confirm_call.name == "confirm_call"
    assert case_node_confirm_call.type == CaseNodeType.VALIDATION
    assert case_node_confirm_call.description == "Confirm call before placing it"
    assert case_node_confirm_call.can_be_confirmed is False


def test_case_node_instantiation_with_trigger_type(
    case_node_start_call: CaseNode,
) -> None:
    """Test CaseNode instantiation with TRIGGER type and can_be_confirmed=True."""
    assert isinstance(case_node_start_call, CaseNode)
    assert case_node_start_call.name == "start_call"
    assert case_node_start_call.type == CaseNodeType.TRIGGER
    assert case_node_start_call.can_be_confirmed is True


def test_case_node_instantiation_with_info_type(
    case_node_update_call_status: CaseNode,
) -> None:
    """Test CaseNode instantiation with INFO type."""
    assert isinstance(case_node_update_call_status, CaseNode)
    assert case_node_update_call_status.name == "update_call_status"
    assert case_node_update_call_status.type == CaseNodeType.INFO
    assert case_node_update_call_status.can_be_confirmed is False


def test_case_node_callable(
    case_node_confirm_call: CaseNode,
) -> None:
    """Test that CaseNode is callable and returns CaseNodeUpdate."""
    phone_number = "+1234567890"
    update = case_node_confirm_call(phone_number=phone_number)

    assert isinstance(update, CaseNodeUpdate)
    assert update.name == f"Confirm call {phone_number}"
    assert update.cost == 0.0
    assert update.is_final is False
    assert "supervaizer_form" in (update.payload or {})


def test_case_node_callable_with_multiple_args(
    case_node_start_call: CaseNode,
) -> None:
    """Test CaseNode callable with multiple arguments."""
    attempt = 1
    call_id = "call_123"
    update = case_node_start_call(attempt=attempt, call_id=call_id)

    assert isinstance(update, CaseNodeUpdate)
    assert update.name == f"📞 Starting Outgoing Call (Try #{attempt})"
    assert update.cost == 0.0
    assert update.payload is not None
    assert update.payload.get("attempt") == attempt
    assert update.payload.get("call_id") == call_id


def test_case_node_callable_with_error(
    case_node_update_call_failed: CaseNode,
) -> None:
    """Test CaseNode callable that includes error in CaseNodeUpdate."""

    class MockCall:
        cost = 5.0

    call = MockCall()
    attempt = 2
    error = "Connection failed"
    update = case_node_update_call_failed(call=call, attempt=attempt, error=error)

    assert isinstance(update, CaseNodeUpdate)
    assert update.name == f"❌ Call Failed (Try #{attempt})"
    assert update.cost == 5.0
    assert update.error == error
    assert update.payload is not None
    assert update.payload.get("status") == "failed"
    assert update.payload.get("error") == error


def test_case_nodes_instantiation(
    case_nodes_all_steps: CaseNodes,
) -> None:
    """Test CaseNodes instantiation with a list of CaseNode instances."""
    assert isinstance(case_nodes_all_steps, CaseNodes)
    assert len(case_nodes_all_steps.nodes) == 5
    assert all(isinstance(node, CaseNode) for node in case_nodes_all_steps.nodes)


def test_case_nodes_instantiation_empty() -> None:
    """Test CaseNodes instantiation with empty list."""
    case_nodes = CaseNodes(nodes=[])
    assert isinstance(case_nodes, CaseNodes)
    assert len(case_nodes.nodes) == 0


def test_case_nodes_get_method(
    case_nodes_all_steps: CaseNodes,
) -> None:
    """Test CaseNodes.get() method to retrieve a node by name."""
    node = case_nodes_all_steps.get("confirm_call")
    assert node is not None
    assert isinstance(node, CaseNode)
    assert node.name == "confirm_call"

    node = case_nodes_all_steps.get("start_call")
    assert node is not None
    assert node.name == "start_call"

    node = case_nodes_all_steps.get("nonexistent")
    assert node is None


def test_case_nodes_get_method_with_empty_list() -> None:
    """Test CaseNodes.get() method with empty nodes list."""
    case_nodes = CaseNodes(nodes=[])
    node = case_nodes.get("any_name")
    assert node is None


def test_case_node_different_types() -> None:
    """Test CaseNode instantiation with all different CaseNodeType values."""
    types_to_test = [
        CaseNodeType.CHAT,
        CaseNodeType.TRIGGER,
        CaseNodeType.NOTIFICATION,
        CaseNodeType.VALIDATION,
        CaseNodeType.DELIVERY,
        CaseNodeType.ERROR,
        CaseNodeType.WARNING,
        CaseNodeType.INFO,
    ]

    for node_type in types_to_test:
        node = CaseNode(
            name=f"test_{node_type.value}",
            type=node_type,
            factory=lambda: CaseNodeUpdate(name="test", cost=0.0),
            description=f"Test {node_type.value} node",
        )
        assert isinstance(node, CaseNode)
        assert node.type == node_type
        assert node.name == f"test_{node_type.value}"


def test_case_node_with_complex_factory(
    case_node_update_call_completed: CaseNode,
) -> None:
    """Test CaseNode with complex factory function that takes multiple parameters."""

    class MockCall:
        call_id = "call_456"
        cost = 10.5

    call = MockCall()
    call_status = "ended"
    duration_seconds = 120.5
    extracted_values = {"name": "John", "email": "john@example.com"}
    metadata = {"key": "value"}

    update = case_node_update_call_completed(
        call=call,
        call_status=call_status,
        duration_seconds=duration_seconds,
        extracted_values=extracted_values,
        metadata=metadata,
    )

    assert isinstance(update, CaseNodeUpdate)
    assert update.name == "✅ Call Completed Successfully"
    assert update.cost == 10.5
    assert update.payload is not None
    assert update.payload.get("call_id") == "call_456"
    assert update.payload.get("call_status") == call_status
    assert update.payload.get("duration_seconds") == duration_seconds
    assert update.payload.get("extracted_values") == extracted_values
    assert update.payload.get("metadata") == metadata
