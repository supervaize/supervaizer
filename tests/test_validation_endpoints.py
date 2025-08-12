# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from supervaizer.agent import Agent, AgentMethod, AgentMethodField, AgentMethods
from supervaizer.parameter import Parameter, ParametersSetup
from supervaizer.server import Server
from supervaizer.routes import create_agent_route


@pytest.fixture
def mock_server():
    """Create a mock server for testing."""
    server = MagicMock(spec=Server)
    server.private_key = "test_private_key"

    # Create a proper dependency function for verify_api_key
    def verify_api_key(api_key: str = Header(alias="X-API-Key")):
        return api_key

    server.verify_api_key = verify_api_key
    server.agents = []  # Empty agents list
    server.encrypt = MagicMock(return_value="encrypted_string")
    server.public_key = MagicMock()
    server.public_key.public_bytes = MagicMock(return_value=b"public_key_bytes")
    return server


@pytest.fixture
def test_agent():
    """Create a test agent with validation methods."""
    # Create parameters setup
    parameters_setup = ParametersSetup.from_list(
        [
            Parameter(name="API_KEY", value="test_key", is_required=True),
            Parameter(name="MAX_RETRIES", value="3", is_required=False),
            Parameter(name="TIMEOUT", value="30", is_required=True),
        ]
    )

    # Create method with fields
    job_start_method = AgentMethod(
        name="start",
        method="test.start",
        fields=[
            AgentMethodField(name="company_name", type=str, required=True),
            AgentMethodField(name="max_results", type=int, required=True),
            AgentMethodField(name="subscribe_updates", type=bool, required=False),
        ],
        description="Start a test job",
    )

    # Create custom method
    custom_method = AgentMethod(
        name="custom-action",
        method="test.custom",
        fields=[
            AgentMethodField(name="action_type", type=str, required=True),
            AgentMethodField(name="priority", type=int, required=False),
        ],
        description="Custom test action",
    )

    # Create agent
    agent = Agent(
        name="test_agent",
        author="Test Author",
        developer="Test Developer",
        maintainer="Test Maintainer",
        editor="Test Editor",
        version="1.0.0",
        description="Test agent for validation",
        tags=["test", "validation"],
        methods=AgentMethods(
            job_start=job_start_method,
            job_stop=AgentMethod(name="stop", method="test.stop"),
            job_status=AgentMethod(name="status", method="test.status"),
            chat=None,
            custom={"custom-action": custom_method},
        ),
        parameters_setup=parameters_setup,
    )

    return agent


@pytest.fixture
def test_client(mock_server, test_agent):
    """Create a test client with the validation endpoints."""
    router = create_agent_route(mock_server, test_agent)

    # Create a minimal FastAPI app for testing
    from fastapi import FastAPI

    app = FastAPI()
    # Mount the router at the agent path
    app.include_router(router, prefix="/test-agent")

    return TestClient(app)


class TestValidateAgentParameters:
    """Test the /validate-agent-parameters endpoint."""

    def test_validate_agent_parameters_no_setup(
        self, test_client, mock_server, test_agent
    ):
        """Test validation when agent has no parameter setup."""
        test_agent.parameters_setup = None

        response = test_client.post(
            "/test-agent/agents/test-agent/validate-agent-parameters",
            json={"test": "data"},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["message"] == "Agent has no parameter setup defined"

    def test_validate_agent_parameters_no_encrypted_params(self, test_client):
        """Test validation with no encrypted parameters."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-agent-parameters",
            json={"test": "data"},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["message"] == "Agent parameter validation failed"
        assert "API_KEY" in data["invalid_parameters"]
        assert "TIMEOUT" in data["invalid_parameters"]

    @patch("supervaizer.common.decrypt_value")
    def test_validate_agent_parameters_valid_params(self, mock_decrypt, test_client):
        """Test validation with valid encrypted parameters."""
        mock_decrypt.return_value = '{"API_KEY": "new_key", "TIMEOUT": "60"}'

        response = test_client.post(
            "/test-agent/agents/test-agent/validate-agent-parameters",
            json={"encrypted_agent_parameters": "encrypted_string"},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["message"] == "Agent parameters validated successfully"

    @patch("supervaizer.common.decrypt_value")
    def test_validate_agent_parameters_missing_required(
        self, mock_decrypt, test_client
    ):
        """Test validation with missing required parameters."""
        mock_decrypt.return_value = '{"MAX_RETRIES": "5"}'

        response = test_client.post(
            "/test-agent/agents/test-agent/validate-agent-parameters",
            json={"encrypted_agent_parameters": "encrypted_string"},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["message"] == "Agent parameter validation failed"
        assert "API_KEY" in data["invalid_parameters"]
        assert "TIMEOUT" in data["invalid_parameters"]

    @patch("supervaizer.common.decrypt_value")
    def test_validate_agent_parameters_decryption_failure(
        self, mock_decrypt, test_client
    ):
        """Test validation when decryption fails."""
        mock_decrypt.side_effect = Exception("Decryption failed")

        response = test_client.post(
            "/test-agent/agents/test-agent/validate-agent-parameters",
            json={"encrypted_agent_parameters": "encrypted_string"},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "Decryption failed" in data["message"]
        assert "encrypted_agent_parameters" in data["invalid_parameters"]


class TestValidateMethodFields:
    """Test the /validate-method-fields endpoint."""

    def test_validate_method_fields_job_start(self, test_client):
        """Test validation of job_start method fields."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-method-fields",
            json={
                "method_name": "job_start",
                "job_fields": {"company_name": "Test Company", "max_results": 10},
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["message"] == "Method fields validated successfully"

    def test_validate_method_fields_custom_method(self, test_client):
        """Test validation of custom method fields."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-method-fields",
            json={
                "method_name": "custom-action",
                "job_fields": {"action_type": "process", "priority": 1},
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["message"] == "Method fields validated successfully"

    def test_validate_method_fields_method_not_found(self, test_client):
        """Test validation when method is not found."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-method-fields",
            json={"method_name": "nonexistent_method", "job_fields": {}},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "not found" in data["message"]

    def test_validate_method_fields_missing_required(self, test_client):
        """Test validation with missing required fields."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-method-fields",
            json={
                "method_name": "job_start",
                "job_fields": {
                    "max_results": 10
                    # company_name is missing
                },
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["message"] == "Method field validation failed"
        assert "company_name" in data["invalid_fields"]
        assert "is missing" in data["invalid_fields"]["company_name"]

    def test_validate_method_fields_invalid_types(self, test_client):
        """Test validation with invalid field types."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-method-fields",
            json={
                "method_name": "job_start",
                "job_fields": {
                    "company_name": 123,  # Should be string
                    "max_results": "not_a_number",  # Should be int
                },
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["message"] == "Method field validation failed"
        assert "company_name" in data["invalid_fields"]
        assert "max_results" in data["invalid_fields"]
        assert "must be a string" in data["invalid_fields"]["company_name"]
        assert "must be an integer" in data["invalid_fields"]["max_results"]

    def test_validate_method_fields_unknown_field(self, test_client):
        """Test validation with unknown field."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-method-fields",
            json={
                "method_name": "job_start",
                "job_fields": {
                    "company_name": "Test Company",
                    "max_results": 10,
                    "unknown_field": "should_fail",
                },
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["message"] == "Method field validation failed"
        assert "unknown_field" in data["invalid_fields"]
        assert "Unknown field" in data["invalid_fields"]["unknown_field"]

    def test_validate_method_fields_none_values(self, test_client):
        """Test validation with None values for optional fields."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-method-fields",
            json={
                "method_name": "job_start",
                "job_fields": {
                    "company_name": "Test Company",
                    "max_results": 10,
                    "subscribe_updates": None,
                },
            },
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["message"] == "Method fields validated successfully"

    def test_validate_method_fields_default_method_name(self, test_client):
        """Test validation with default method name (job_start)."""
        response = test_client.post(
            "/test-agent/agents/test-agent/validate-method-fields",
            json={"job_fields": {"company_name": "Test Company", "max_results": 10}},
            headers={"X-API-Key": "test-api-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["message"] == "Method fields validated successfully"
