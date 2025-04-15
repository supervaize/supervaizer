# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from fastapi.testclient import TestClient
import jsonschema

from supervaizer import Agent, Server
from supervaizer.protocol.acp import (
    create_agent_detail,
    list_agents,
    create_health_data,
)


def test_create_agent_detail(agent_fixture: Agent) -> None:
    """Test the create_agent_detail function."""
    base_url = "http://test.example.com"
    detail = create_agent_detail(agent_fixture, base_url)

    # Test that the required ACP fields are present
    assert "name" in detail
    assert detail["name"] == agent_fixture.name
    assert "description" in detail
    assert "interfaces" in detail
    assert "metadata" in detail
    assert "status" in detail

    # Test that the interfaces are correctly structured
    assert "input" in detail["interfaces"]
    assert "output" in detail["interfaces"]
    assert "awaits" in detail["interfaces"]
    assert isinstance(detail["interfaces"]["awaits"], list)

    # Test that metadata is correctly structured
    metadata = detail["metadata"]
    assert "documentation" in metadata
    assert "license" in metadata
    assert metadata["license"] == "MPL-2.0"
    assert "programmingLanguage" in metadata
    assert metadata["programmingLanguage"] == "Python"
    assert "naturalLanguages" in metadata
    assert isinstance(metadata["naturalLanguages"], list)
    assert "en" in metadata["naturalLanguages"]
    assert "framework" in metadata
    assert metadata["framework"] == "SUPERVAIZER"
    assert "useCases" in metadata
    assert isinstance(metadata["useCases"], list)
    assert "tags" in metadata
    assert agent_fixture.slug in metadata["tags"]
    assert "createdAt" in metadata
    assert "updatedAt" in metadata
    assert "author" in metadata
    assert "links" in metadata
    assert isinstance(metadata["links"], list)
    assert len(metadata["links"]) > 0

    # Test that the status is correctly structured
    status = detail["status"]
    assert "avgRunTokens" in status
    assert "avgRunTimeSeconds" in status
    assert "successRate" in status
    assert 0 <= status["successRate"] <= 100


def test_list_agents(agent_fixture: Agent) -> None:
    """Test the list_agents function."""
    base_url = "http://test.example.com"
    agents_list = list_agents([agent_fixture], base_url)

    # Check it returns a list
    assert isinstance(agents_list, list)
    assert len(agents_list) == 1

    # Check the agent entry
    agent_entry = agents_list[0]
    assert "name" in agent_entry
    assert agent_entry["name"] == agent_fixture.name
    assert "description" in agent_entry
    assert "interfaces" in agent_entry
    assert "metadata" in agent_entry
    assert "status" in agent_entry


def test_create_health_data(agent_fixture: Agent) -> None:
    """Test the create_health_data function."""
    health_data = create_health_data([agent_fixture])

    # Test that the required fields are present
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


def test_acp_route_endpoints(server_fixture: Server) -> None:
    """Test the ACP route endpoints."""
    # Create a FastAPI test client
    client = TestClient(server_fixture.app)

    # Test the agents listing endpoint
    response = client.get("/agents")
    assert response.status_code == 200
    agents_list = response.json()
    print(agents_list)
    # Verify the structure
    assert isinstance(agents_list, list)
    assert len(agents_list) == 1
    assert "name" in agents_list[0]
    assert "description" in agents_list[0]
    assert "interfaces" in agents_list[0]
    assert "metadata" in agents_list[0]
    assert "status" in agents_list[0]

    # Test the agent detail endpoint
    agent = server_fixture.agents[0]
    response = client.get(f"/agents/{agent.slug}")
    assert response.status_code == 200
    agent_detail = response.json()

    # Verify the structure
    assert "name" in agent_detail
    assert agent_detail["name"] == agent.name
    assert "description" in agent_detail
    assert "interfaces" in agent_detail
    assert "metadata" in agent_detail
    assert "status" in agent_detail

    # Test the health endpoint
    response = client.get("/agents/health")
    assert response.status_code == 200
    health_data = response.json()

    # Verify the structure
    assert "status" in health_data
    assert "timestamp" in health_data
    assert "agents" in health_data

    # Test 404 for non-existent agent
    response = client.get("/agents/nonexistent_agent")
    assert response.status_code == 404


def test_acp_schema_conformance(agent_fixture: Agent) -> None:
    """Test that the ACP output conforms to the JSON schema."""
    # Define a minimal ACP schema for validation
    acp_agent_schema = {
        "type": "object",
        "required": ["name", "description", "interfaces", "metadata", "status"],
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "interfaces": {
                "type": "object",
                "required": ["input", "output", "awaits"],
                "properties": {
                    "input": {"type": "string"},
                    "output": {"type": "string"},
                    "awaits": {"type": "array"},
                },
            },
            "metadata": {
                "type": "object",
                "required": [
                    "documentation",
                    "license",
                    "programmingLanguage",
                    "naturalLanguages",
                    "framework",
                    "useCases",
                    "tags",
                    "createdAt",
                    "updatedAt",
                    "author",
                    "links",
                ],
                "properties": {
                    "documentation": {"type": "string"},
                    "license": {"type": "string"},
                    "programmingLanguage": {"type": "string"},
                    "naturalLanguages": {"type": "array", "items": {"type": "string"}},
                    "framework": {"type": "string"},
                    "useCases": {"type": "array", "items": {"type": "string"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "createdAt": {"type": "string"},
                    "updatedAt": {"type": "string"},
                    "author": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "url": {"type": "string"},
                        },
                    },
                    "links": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type", "url"],
                            "properties": {
                                "type": {"type": "string"},
                                "url": {"type": "string"},
                            },
                        },
                    },
                },
            },
            "status": {
                "type": "object",
                "required": ["avgRunTokens", "avgRunTimeSeconds", "successRate"],
                "properties": {
                    "avgRunTokens": {"type": "number"},
                    "avgRunTimeSeconds": {"type": "number"},
                    "successRate": {"type": "number", "minimum": 0, "maximum": 100},
                },
            },
        },
    }

    # Validate the agent detail against the schema
    base_url = "http://test.example.com"
    agent_detail = create_agent_detail(agent_fixture, base_url)
    jsonschema.validate(instance=agent_detail, schema=acp_agent_schema)

    # Validate agents list
    agents_list = list_agents([agent_fixture], base_url)
    for agent_item in agents_list:
        jsonschema.validate(instance=agent_item, schema=acp_agent_schema)

    # Health endpoint schema
    health_schema = {
        "type": "object",
        "required": ["status", "timestamp", "agents"],
        "properties": {
            "status": {"type": "string"},
            "timestamp": {"type": "string"},
            "agents": {"type": "object"},
        },
    }

    # Validate health data against schema
    health_data = create_health_data([agent_fixture])
    jsonschema.validate(instance=health_data, schema=health_schema)
