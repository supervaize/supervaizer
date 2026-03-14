"""Tests for workbench routes module."""

import os
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

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
from supervaizer.job import JobContext


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
