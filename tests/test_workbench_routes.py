# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for workbench routes module."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from supervaizer import (
    Agent,
    AgentMethod,
    AgentMethods,
    Parameter,
    ParametersSetup,
)
from supervaizer.agent import AgentMethodField, FieldTypeEnum


@pytest.fixture
def test_client_with_agent(monkeypatch):
    """Create a test client with a registered agent."""
    from fastapi import FastAPI
    from supervaizer.admin.routes import create_admin_routes

    monkeypatch.setenv("SUPERVAIZER_API_KEY", "test-api-key")

    agent_method = AgentMethod(
        name="job_start",
        method="test_module.test_function",
        fields=[
            AgentMethodField(
                name="how_many",
                type=int,
                field_type=FieldTypeEnum.INT,
                description="Number of cases",
                required=True,
                default=1,
            ),
        ],
    )

    agent = Agent(
        name="Test Agent",
        version="1.0.0",
        description="A test agent",
        methods=AgentMethods(job_start=agent_method),
        parameters_setup=ParametersSetup.from_list([
            Parameter(
                name="API_KEY", description="Test key", is_required=True, is_secret=True
            ),
        ]),
    )

    # Create a mock server
    server = Mock()
    server.agents = [agent]
    server.api_key = "test-api-key"
    server.supervisor_account = "mock-account"  # non-None = not local mode

    # Mock StorageManager used inside admin routes
    mock_storage = Mock()
    mock_storage.get_objects.side_effect = lambda obj_type: []
    mock_db = Mock()
    mock_db.tables.return_value = []
    mock_storage._db = mock_db
    mock_storage.db_path = Mock()
    mock_storage.db_path.absolute.return_value = "/tmp/test.db"

    app = FastAPI()
    app.state.server = server

    with patch("supervaizer.admin.routes.StorageManager", return_value=mock_storage):
        app.include_router(create_admin_routes(), prefix="/admin")

    client = TestClient(app)
    yield client, agent.slug


class TestWorkbenchPageRendering:
    """Test that the workbench page renders with agent config."""

    def test_workbench_page_loads(self, test_client_with_agent):
        """Workbench page should render for a valid agent slug."""
        client, agent_slug = test_client_with_agent
        response = client.get(f"/admin/agents/{agent_slug}/workbench?key=test-api-key")
        assert response.status_code == 200
        assert "Workbench" in response.text

    def test_workbench_page_404_for_unknown_agent(self, test_client_with_agent):
        """Workbench page should 404 for unknown agent slug."""
        client, _ = test_client_with_agent
        response = client.get("/admin/agents/unknown-agent/workbench?key=test-api-key")
        assert response.status_code == 404


class TestGetAgentBySlug:
    """Tests for the get_agent_by_slug helper."""

    def test_finds_agent_by_slug(self):
        agent = Mock(spec=Agent)
        agent.slug = "hello-world"
        agent.name = "Hello World"

        request = Mock()
        request.app.state.server.agents = [agent]

        from supervaizer.admin.workbench_routes import get_agent_by_slug

        result = get_agent_by_slug(request, "hello-world")
        assert result == agent

    def test_raises_404_for_unknown_slug(self):
        agent = Mock(spec=Agent)
        agent.slug = "hello-world"

        request = Mock()
        request.app.state.server.agents = [agent]

        from supervaizer.admin.workbench_routes import get_agent_by_slug

        with pytest.raises(HTTPException) as exc_info:
            get_agent_by_slug(request, "not-found")
        assert exc_info.value.status_code == 404
