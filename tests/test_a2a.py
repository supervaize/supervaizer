# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import jsonschema
import pytest
from fastapi.testclient import TestClient

from supervaizer import Agent, Server
from supervaizer.protocol.a2a import (
    create_agent_card,
    create_agents_list,
    create_health_data,
)


def test_create_agent_card(agent_fixture: Agent) -> None:
    """Test the create_agent_card function."""
    base_url = "http://test.example.com"
    card = create_agent_card(agent_fixture, base_url)

    # Test that the required A2A fields are present
    assert "name" in card
    assert card["name"] == agent_fixture.name
    assert "description" in card
    assert "developer" in card
    assert "version" in card
    assert card["version"] == agent_fixture.version
    assert "version_info" in card
    assert "logo_url" in card
    assert "human_url" in card
    assert "contact_information" in card
    assert "api_endpoints" in card
    assert "tools" in card
    assert "authentication" in card

    # Test that the API endpoints are correctly structured
    assert isinstance(card["api_endpoints"], list)
    assert len(card["api_endpoints"]) > 0
    assert card["api_endpoints"][0]["type"] == "json"
    assert card["api_endpoints"][0]["url"] == f"{base_url}{agent_fixture.path}"

    # Test OpenAPI integration
    assert "openapi_url" in card["api_endpoints"][0]
    assert card["api_endpoints"][0]["openapi_url"] == f"{base_url}/openapi.json"
    assert "docs_url" in card["api_endpoints"][0]
    assert card["api_endpoints"][0]["docs_url"] == f"{base_url}/docs"

    # Test that the tools are correctly structured
    assert isinstance(card["tools"], list)
    assert len(card["tools"]) > 0

    # Verify all tools have the required fields
    for tool in card["tools"]:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert "type" in tool["input_schema"]
        assert tool["input_schema"]["type"] == "object"
        assert "properties" in tool["input_schema"]

    # Check that job_start and job_status tools are included
    tool_names = [tool["name"] for tool in card["tools"]]
    assert "job_start" in tool_names
    assert "job_status" in tool_names

    # Check that custom methods are included in tools
    if agent_fixture.methods.custom:
        for name in agent_fixture.methods.custom.keys():
            assert name in tool_names

    # Test versioning information
    assert "version_info" in card
    assert "current" in card["version_info"]
    assert "latest" in card["version_info"]
    assert "changelog_url" in card["version_info"]


def test_create_agents_list(agent_fixture: Agent) -> None:
    """Test the create_agents_list function."""
    base_url = "http://test.example.com"
    agents_list = create_agents_list([agent_fixture], base_url)

    # Test that the required A2A fields are present
    assert "schema_version" in agents_list
    assert agents_list["schema_version"] == "a2a_2023_v1"
    assert "agents" in agents_list
    assert isinstance(agents_list["agents"], list)
    assert len(agents_list["agents"]) == 1

    # Test the agent entry
    agent_entry = agents_list["agents"][0]
    assert "name" in agent_entry
    assert agent_entry["name"] == agent_fixture.name
    assert "description" in agent_entry
    assert "developer" in agent_entry
    assert "version" in agent_entry
    assert "agent_card_url" in agent_entry
    assert (
        agent_entry["agent_card_url"]
        == f"{base_url}/.well-known/agents/v{agent_fixture.version}/{agent_fixture.slug}_agent.json"
    )


def test_create_health_data(agent_fixture: Agent) -> None:
    """Test the create_health_data function."""
    health_data = create_health_data([agent_fixture])

    # Test that the required fields are present
    assert "schema_version" in health_data
    assert health_data["schema_version"] == "a2a_2023_v1"
    assert "status" in health_data
    assert "timestamp" in health_data
    assert "agents" in health_data

    # Check that agent health information is included
    assert agent_fixture.id in health_data["agents"]
    agent_health = health_data["agents"][agent_fixture.id]

    # Check agent health fields
    assert "agent_id" in agent_health
    assert "name" in agent_health
    assert "status" in agent_health
    assert "version" in agent_health
    assert "statistics" in agent_health

    # Check statistics fields
    stats = agent_health["statistics"]
    assert "total_jobs" in stats
    assert "completed_jobs" in stats
    assert "failed_jobs" in stats
    assert "in_progress_jobs" in stats
    assert "success_rate" in stats


def test_a2a_route_endpoints(server_fixture: Server) -> None:
    """Test the A2A route endpoints."""
    # Create a FastAPI test client
    client = TestClient(server_fixture.app)

    # Test the agents.json endpoint
    response = client.get("/.well-known/agents.json")
    assert response.status_code == 200
    agents_list = response.json()

    # Verify the structure
    assert "agents" in agents_list
    assert isinstance(agents_list["agents"], list)
    assert len(agents_list["agents"]) == 1

    # Test the v1 agent card endpoint
    agent = server_fixture.agents[0]
    response = client.get(
        f"/.well-known/agents/v{agent.version}/{agent.slug}_agent.json"
    )
    assert response.status_code == 200
    agent_card = response.json()

    # Verify the structure
    assert "name" in agent_card
    assert agent_card["name"] == agent.name

    # Test 404 for non-existent agent
    response = client.get("/.well-known/agents/nonexistent_agent.json")
    assert response.status_code == 404


def test_a2a_schema_conformance(agent_fixture: Agent) -> None:
    """Test that the A2A output conforms to the JSON schema."""
    # Define a minimal A2A schema for validation
    a2a_agent_schema = {
        "type": "object",
        "required": [
            "name",
            "description",
            "developer",
            "version",
            "logo_url",
            "human_url",
            "contact_information",
            "api_endpoints",
            "tools",
        ],
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "developer": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
            "version": {"type": "string"},
            "logo_url": {"type": "string"},
            "human_url": {"type": "string"},
            "contact_information": {"type": "object"},
            "api_endpoints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["type", "url", "name"],
                    "properties": {
                        "type": {"type": "string"},
                        "url": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
            },
            "tools": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "description", "input_schema"],
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "input_schema": {"type": "object"},
                    },
                },
            },
        },
    }

    a2a_agents_list_schema = {
        "type": "object",
        "required": ["schema_version", "agents"],
        "properties": {
            "schema_version": {"type": "string", "const": "a2a_2023_v1"},
            "agents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "name",
                        "description",
                        "developer",
                        "version",
                        "agent_card_url",
                    ],
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "developer": {"type": "string"},
                        "version": {"type": "string"},
                        "agent_card_url": {"type": "string"},
                    },
                },
            },
        },
    }

    base_url = "http://test.example.com"

    # Create and validate agent card
    try:
        card = create_agent_card(agent_fixture, base_url)
        jsonschema.validate(instance=card, schema=a2a_agent_schema)
    except jsonschema.exceptions.ValidationError as e:
        pytest.fail(f"Agent card does not conform to schema: {e}")

    # Create and validate agents list
    try:
        agents_list = create_agents_list([agent_fixture], base_url)
        jsonschema.validate(instance=agents_list, schema=a2a_agents_list_schema)
    except jsonschema.exceptions.ValidationError as e:
        pytest.fail(f"Agents list does not conform to schema: {e}")
