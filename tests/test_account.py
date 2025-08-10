# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import httpx
import pytest
from pytest_mock import MockerFixture

from supervaizer import Account, ApiError, ApiSuccess
from supervaizer.event import Event
from supervaizer.server import Server
from supervaizer.telemetry import (
    Telemetry,
    TelemetryCategory,
    TelemetrySeverity,
    TelemetryType,
)


def test_account(account_fixture: Account) -> None:
    assert isinstance(account_fixture, Account)
    assert account_fixture.workspace_id == "o34Z484gY9Nxz8axgTAdiH"


def test_account_api_headers(account_fixture: Account) -> None:
    apikey = account_fixture.api_key
    assert account_fixture.api_headers == {
        "Authorization": f"Api-Key {apikey}",
        "workspace": "o34Z484gY9Nxz8axgTAdiH",
        "accept": "application/json",
    }


def test_account_url_event(account_fixture: Account) -> None:
    apiurl = account_fixture.api_url
    assert (
        account_fixture.url_event
        == f"{apiurl}/w/o34Z484gY9Nxz8axgTAdiH/api/v1/ctrl-events/"
    )


def test_account_api_url_w_v1(account_fixture: Account) -> None:
    """Test the api_url_w_v1 property."""
    expected = f"{account_fixture.api_url}/w/{account_fixture.workspace_id}/api/v1"
    assert account_fixture.api_url_w_v1 == expected


def test_account_api_url_team(account_fixture: Account) -> None:
    """Test the api_url_team property."""
    expected = f"{account_fixture.api_url}/w/{account_fixture.workspace_id}"
    assert account_fixture.api_url_team == expected


def test_get_url_valid_patterns(account_fixture: Account) -> None:
    """Test get_url method with valid patterns."""
    # Test team pattern
    team_url = account_fixture.get_url("team")
    expected = f"{account_fixture.api_url}/w/{account_fixture.workspace_id}"
    assert team_url == expected

    # Test event pattern
    event_url = account_fixture.get_url("event")
    expected = f"{account_fixture.api_url}/w/{account_fixture.workspace_id}/api/v1/ctrl-events/"
    assert event_url == expected

    # Test agent_by_id pattern with kwargs
    agent_url = account_fixture.get_url("agent_by_id", agent_id="test-agent-123")
    expected = f"{account_fixture.api_url}/w/{account_fixture.workspace_id}/api/v1/agents/test-agent-123"
    assert agent_url == expected

    # Test agent_by_slug pattern with kwargs
    slug_url = account_fixture.get_url("agent_by_slug", agent_slug="test-agent")
    expected = f"{account_fixture.api_url}/w/{account_fixture.workspace_id}/api/v1/agents/by-slug/test-agent"
    assert slug_url == expected

    # Test telemetry pattern with default version
    telemetry_url = account_fixture.get_url("telemetry")
    expected = f"{account_fixture.api_url}/v1/telemetry"
    assert telemetry_url == expected

    # Test telemetry pattern with custom version
    telemetry_url_custom = account_fixture.get_url("telemetry", telemetry_version="v2")
    expected = f"{account_fixture.api_url}/v2/telemetry"
    assert telemetry_url_custom == expected


def test_get_url_invalid_pattern(account_fixture: Account) -> None:
    """Test get_url method with invalid pattern name."""
    with pytest.raises(KeyError, match="URL pattern 'invalid_pattern' not found"):
        account_fixture.get_url("invalid_pattern")


def test_create_api_result_success(account_fixture: Account) -> None:
    """Test _create_api_result method for success case."""
    result = account_fixture._create_api_result(
        success=True, message="Success message", detail={"data": "test"}
    )
    assert isinstance(result, ApiSuccess)
    assert result.message == "Success message"
    assert result.detail == {"data": "test"}


def test_create_api_result_error(account_fixture: Account) -> None:
    """Test _create_api_result method for error case."""
    test_exception = Exception("Test error")
    result = account_fixture._create_api_result(
        success=False,
        message="Error message",
        url="http://test.com",
        exception=test_exception,
    )
    assert isinstance(result, ApiError)
    assert result.message == "Error message"
    assert result.url == "http://test.com"
    assert result.exception == test_exception


def test_get_agent_by_id_success(
    account_fixture: Account, mocker: MockerFixture
) -> None:
    """Test get_agent_by method with agent_id - success case."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"id": "agent123", "name": "Test Agent"}
    mock_response.raise_for_status.return_value = None

    mock_get = mocker.patch("httpx.get", return_value=mock_response)

    result = account_fixture.get_agent_by(agent_id="agent123")

    assert isinstance(result, ApiSuccess)
    assert result.message == "GET Agent <agent123>"
    assert result.detail == {"id": "agent123", "name": "Test Agent"}

    # Verify the correct URL was called
    expected_url = f"{account_fixture.api_url_w_v1}/agents/agent123"
    mock_get.assert_called_once_with(
        expected_url, headers=account_fixture.api_headers, follow_redirects=True
    )


def test_get_agent_by_slug_success(
    account_fixture: Account, mocker: MockerFixture
) -> None:
    """Test get_agent_by method with agent_slug - success case."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"slug": "test-agent", "name": "Test Agent"}
    mock_response.raise_for_status.return_value = None

    mock_get = mocker.patch("httpx.get", return_value=mock_response)

    result = account_fixture.get_agent_by(agent_slug="test-agent")

    assert isinstance(result, ApiSuccess)
    assert result.message == "GET Agent <test-agent>"
    assert result.detail == {"slug": "test-agent", "name": "Test Agent"}

    # Verify the correct URL was called
    expected_url = f"{account_fixture.api_url_w_v1}/agents/by-slug/test-agent"
    mock_get.assert_called_once_with(
        expected_url, headers=account_fixture.api_headers, follow_redirects=True
    )


def test_get_agent_by_http_error(
    account_fixture: Account, mocker: MockerFixture
) -> None:
    """Test get_agent_by method with HTTP error."""
    _mock_get = mocker.patch(
        "httpx.get", side_effect=httpx.HTTPError("Connection failed")
    )

    result = account_fixture.get_agent_by(agent_id="agent123")

    assert isinstance(result, ApiError)
    assert result.message == "Error GET Agent <agent123>"
    assert isinstance(result.exception, httpx.HTTPError)


def test_get_agent_by_no_params(account_fixture: Account) -> None:
    """Test get_agent_by method with no parameters - should raise ValueError."""
    with pytest.raises(ValueError, match="No agent ID or slug provided"):
        account_fixture.get_agent_by()


def test_register_agent(account_fixture: Account, mocker: MockerFixture) -> None:
    """Test register_agent method."""
    # Mock the agent
    mock_agent = mocker.Mock()
    mock_agent.name = "test-agent"

    # Mock the account_service.send_event function instead of patching the instance method
    mock_send_event = mocker.patch("supervaizer.account_service.send_event")
    mock_send_event.return_value = ApiSuccess(
        message="Agent registered", detail={"status": "registered"}
    )

    # Mock the AgentRegisterEvent
    mock_event_class = mocker.patch("supervaizer.event.AgentRegisterEvent")
    mock_event = mocker.Mock()
    mock_event_class.return_value = mock_event

    # Test with default polling=True
    result = account_fixture.register_agent(mock_agent)

    assert isinstance(result, ApiSuccess)
    mock_event_class.assert_called_once_with(
        agent=mock_agent, account=account_fixture, polling=True
    )
    mock_send_event.assert_called_once_with(account_fixture, mock_agent, mock_event)

    # Test with polling=False
    mock_send_event.reset_mock()
    mock_event_class.reset_mock()

    account_fixture.register_agent(mock_agent, polling=False)
    mock_event_class.assert_called_once_with(
        agent=mock_agent, account=account_fixture, polling=False
    )


def test_send_start_case(account_fixture: Account, mocker: MockerFixture) -> None:
    """Test send_start_case method."""
    # Mock the case
    mock_case = mocker.Mock()

    # Mock the account_service.send_event function instead of patching the instance method
    mock_send_event = mocker.patch("supervaizer.account_service.send_event")
    mock_send_event.return_value = ApiSuccess(
        message="Case started", detail={"status": "started"}
    )

    # Mock the CaseStartEvent
    mock_event_class = mocker.patch("supervaizer.event.CaseStartEvent")
    mock_event = mocker.Mock()
    mock_event_class.return_value = mock_event

    result = account_fixture.send_start_case(mock_case)

    assert isinstance(result, ApiSuccess)
    mock_event_class.assert_called_once_with(case=mock_case, account=account_fixture)
    mock_send_event.assert_called_once_with(account_fixture, mock_case, mock_event)


def test_send_update_case(account_fixture: Account, mocker: MockerFixture) -> None:
    """Test send_update_case method."""
    # Mock the case and update
    mock_case = mocker.Mock()
    mock_update = mocker.Mock()

    # Mock the account_service.send_event function instead of patching the instance method
    mock_send_event = mocker.patch("supervaizer.account_service.send_event")
    mock_send_event.return_value = ApiSuccess(
        message="Case updated", detail={"status": "updated"}
    )

    # Mock the CaseUpdateEvent
    mock_event_class = mocker.patch("supervaizer.event.CaseUpdateEvent")
    mock_event = mocker.Mock()
    mock_event_class.return_value = mock_event

    result = account_fixture.send_update_case(mock_case, mock_update)

    assert isinstance(result, ApiSuccess)
    mock_event_class.assert_called_once_with(
        case=mock_case, update=mock_update, account=account_fixture
    )
    mock_send_event.assert_called_once_with(account_fixture, mock_update, mock_event)


def test_send_telemetry_success(
    account_fixture: Account, mocker: MockerFixture
) -> None:
    """Test send_telemetry method - success case."""
    # Create a test telemetry object using the correct enum values
    telemetry = Telemetry(
        agentId="test-agent",
        type=TelemetryType.EVENTS,
        category=TelemetryCategory.APPLICATION,
        severity=TelemetrySeverity.INFO,
        details={"test": "data"},
    )

    # Mock httpx.post response
    mock_response = mocker.Mock()
    mock_response.text = '{"status": "success", "id": "telemetry-123"}'
    mock_response.raise_for_status.return_value = None

    mock_post = mocker.patch("httpx.post", return_value=mock_response)

    result = account_fixture.send_telemetry(telemetry)

    assert isinstance(result, ApiSuccess)
    assert result.message == f"Telemetry sent {telemetry.type.name}"
    assert result.detail == {"object": {"status": "success", "id": "telemetry-123"}}

    # Verify the correct parameters were used
    expected_url = account_fixture.get_url("telemetry")
    expected_payload = {
        "workspace_id": account_fixture.workspace_id
    } | telemetry.payload

    mock_post.assert_called_once_with(
        expected_url, headers=account_fixture.api_headers, json=expected_payload
    )


def test_send_telemetry_http_error(
    account_fixture: Account, mocker: MockerFixture
) -> None:
    """Test send_telemetry method - HTTP error case."""
    # Create a test telemetry object using the correct enum values
    telemetry = Telemetry(
        agentId="test-agent",
        type=TelemetryType.EVENTS,
        category=TelemetryCategory.APPLICATION,
        severity=TelemetrySeverity.INFO,
        details={"test": "data"},
    )

    # Mock httpx.post to raise an error
    mock_post = mocker.patch(
        "httpx.post", side_effect=httpx.HTTPError("Connection failed")
    )

    result = account_fixture.send_telemetry(telemetry)

    assert isinstance(result, ApiError)
    assert result.message == f"Error sending telemetry {telemetry.type.name}"
    assert isinstance(result.exception, httpx.HTTPError)
    assert result.url == account_fixture.get_url("telemetry")
    assert (
        result.payload
        == {"workspace_id": account_fixture.workspace_id} | telemetry.payload
    )


def test_account_send_event_delegation(
    account_fixture: Account,
    event_fixture: Event,
    server_fixture: Server,
    mocker: MockerFixture,
) -> None:
    # Mock the account_service.send_event function
    mock_service_send_event = mocker.patch("supervaizer.account_service.send_event")
    mock_service_send_event.return_value = ApiSuccess(
        message="Event sent",
        detail={"id": "01JPZ7414FX3JHPNA8N1JXDADX", "response": "success"},
    )

    # Call the account.send_event method
    result = account_fixture.send_event(sender=server_fixture, event=event_fixture)

    # Verify that the account_service.send_event was called with correct parameters
    mock_service_send_event.assert_called_once_with(
        account_fixture, server_fixture, event_fixture
    )
    assert result == mock_service_send_event.return_value


def test_account_register_server_success(
    account_fixture: Account, server_fixture: Server, mocker: MockerFixture
) -> None:
    # Mock the send_event method
    mock_send_event = mocker.patch("supervaizer.account_service.send_event")
    # Use a dictionary instead of SERVER_REGISTER_RESPONSE to avoid JSON decoding issues
    detail = {"id": "01JPZ7414FX3JHPNA8N1JXDADX", "response": "success"}
    mock_send_event.return_value = ApiSuccess(
        message="Event SERVER_REGISTER sent",
        detail=detail,
    )

    result = account_fixture.register_server(server_fixture)
    assert isinstance(result, ApiSuccess)
    assert result.message == "Event SERVER_REGISTER sent"
    # Verify that send_event was called
    mock_send_event.assert_called_once()
