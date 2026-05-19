# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import base64
import json
import threading
import time

import jsonschema
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from fastapi.testclient import TestClient

from supervaizer import Agent, Server
from supervaizer.access import API_KEYS
from supervaizer.contracts import (
    V2ActionRequest,
    V2ActionResult,
    V2Effect,
    V2SurfaceRequest,
    V2WorkspaceAuthorizationSettings,
)
from supervaizer.protocol.a2a import (
    create_agent_card,
    create_agents_list,
    create_health_data,
)
from supervaizer.protocol.a2a.model import _agent_health_status
from supervaizer.protocol.a2a.controller import (
    JSON_RPC_ACTION_NOT_REGISTERED,
    JSON_RPC_INTERNAL_ERROR,
    JSON_RPC_METHOD_NOT_FOUND,
    JSON_RPC_SURFACE_NOT_REGISTERED,
    JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED,
    SUPERVAIZER_ACTION_INVOKE_METHOD,
    SUPERVAIZER_SURFACE_LOAD_METHOD,
    dispatch_json_rpc,
    register_v2_action_handler,
    register_v2_surface_handler,
)
from supervaizer.protocol.a2a.events import (
    A2A_EFFECT_EVENT,
    subscribe_v2_events,
    unsubscribe_v2_events,
)
from supervaizer.workspace_authorization import WORKSPACE_AUTHORIZATION_HEADER


def _a2a_write_headers(server: Server) -> dict[str, str]:
    return {"X-API-Key": server.api_key or ""}


def _a2a_workspace_headers(server: Server, token: str) -> dict[str, str]:
    return {
        **_a2a_write_headers(server),
        WORKSPACE_AUTHORIZATION_HEADER: f"Bearer {token}",
    }


def _authorized_a2a_headers(
    server: Server, *, agent_slug: str, scopes: list[str]
) -> dict[str, str]:
    key = _enable_workspace_authorization_eddsa(
        server,
        agent_slug=agent_slug,
        studio_agent_id=f"studio-{agent_slug}",
    )
    token = _workspace_authorization_eddsa_token(
        server,
        key,
        agent_slug=agent_slug,
        scopes=scopes,
    )
    return _a2a_workspace_headers(server, token)


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


def test_create_agent_card_includes_supervaizer_v2_extension() -> None:
    agent = Agent(
        name="Agent Name",
        author="authorName",
        developer="Dev",
        version="1.0.0",
        description="description",
        supervaizer_v2_registration={
            "agent": {
                "id": "agent_name",
                "slug": "agent-name",
                "display_name": "Agent Name",
            },
            "versions": {
                "a2ui_version": "v0.8",
                "a2ui_catalog_version": "test.0",
                "a2a_version": "0.2.6",
            },
            "a2a": {
                "agent_card_url": "/.well-known/agents/v1.0.0/agent-name_agent.json",
                "controller_url": "/a2a",
            },
        },
    )

    card = create_agent_card(agent, "https://agent.example.com")

    assert card["supervaizer"]["v2"]["supervaizer_contract_version"] == 2
    assert card["supervaizer"]["v2"]["a2a"]["controller_url"] == "/a2a"


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


@pytest.mark.parametrize(
    ("total_jobs", "failed_jobs", "in_progress_jobs", "expected"),
    [
        (0, 0, 0, "available"),
        (1, 1, 0, "unavailable"),
        (2, 1, 0, "available"),
        (3, 2, 0, "degraded"),
        (3, 3, 0, "unavailable"),
        (2, 0, 1, "busy"),
    ],
)
def test_agent_health_status(
    total_jobs: int,
    failed_jobs: int,
    in_progress_jobs: int,
    expected: str,
) -> None:
    assert (
        _agent_health_status(
            total_jobs=total_jobs,
            failed_jobs=failed_jobs,
            in_progress_jobs=in_progress_jobs,
        )
        == expected
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


def test_a2a_controller_rejects_unknown_method(server_fixture: Server) -> None:
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_write_headers(server_fixture),
        json={"jsonrpc": "2.0", "id": "rpc-1", "method": "missing.method"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "rpc-1"
    assert payload["error"]["code"] == JSON_RPC_METHOD_NOT_FOUND


def test_a2a_controller_rejects_unregistered_v2_action(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "rpc-2",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "rpc-2"
    assert payload["error"]["code"] == JSON_RPC_ACTION_NOT_REGISTERED
    assert payload["error"]["data"]["agent_slug"] == agent.slug
    assert payload["error"]["data"]["action"] == "job.start"


def test_a2a_controller_rejects_unregistered_v2_surface(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_SURFACE_LOAD_METHOD, "job.start"],
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "rpc-surface-1",
            "method": SUPERVAIZER_SURFACE_LOAD_METHOD,
            "params": _v2_surface_payload(surface="job.start", agent_slug=agent.slug),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "rpc-surface-1"
    assert payload["error"]["code"] == JSON_RPC_SURFACE_NOT_REGISTERED
    assert payload["error"]["data"]["agent_slug"] == agent.slug
    assert payload["error"]["data"]["surface"] == "job.start"


def test_a2a_events_requires_authentication(server_fixture: Server) -> None:
    client = TestClient(server_fixture.app)

    response = client.get("/a2a/events")

    assert response.status_code == 401


def test_a2a_discovery_and_health_remain_public(server_fixture: Server) -> None:
    client = TestClient(server_fixture.app)

    discovery_response = client.get("/.well-known/agents.json")
    health_response = client.get("/.well-known/health")

    assert discovery_response.status_code == 200
    assert health_response.status_code == 200


def test_a2a_controller_requires_authentication(server_fixture: Server) -> None:
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        json={"jsonrpc": "2.0", "id": "rpc-auth", "method": "missing.method"},
    )

    assert response.status_code == 401


def test_a2a_controller_requires_write_scope(server_fixture: Server) -> None:
    client = TestClient(server_fixture.app)
    API_KEYS["a2a-read-key"] = {"scope": "read"}
    try:
        response = client.post(
            "/a2a",
            headers={"X-API-Key": "a2a-read-key"},
            json={"jsonrpc": "2.0", "id": "rpc-read", "method": "missing.method"},
        )
    finally:
        API_KEYS.pop("a2a-read-key", None)

    assert response.status_code == 403


def test_a2a_events_remains_read_scoped(server_fixture: Server) -> None:
    route = next(
        route
        for route in server_fixture.app.routes
        if getattr(route, "path", None) == "/a2a/events"
    )
    dependency = route.dependant.dependencies[0].call
    closure_values = [
        cell.cell_contents for cell in getattr(dependency, "__closure__", None) or ()
    ]

    assert "read" in closure_values


def test_a2a_controller_dispatches_registered_v2_action(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )

    def start_job(request: V2ActionRequest) -> V2ActionResult:
        assert request.action == "job.start"
        return V2ActionResult(
            status="ok",
            effects=[V2Effect(type="job.created", job_id="job-123")],
        )

    register_v2_action_handler(server_fixture, "job.start", start_job)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "rpc-3",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "rpc-3"
    assert payload["result"]["status"] == "ok"
    assert payload["result"]["effects"] == [
        {"type": "job.created", "job_id": "job-123"}
    ]


def test_a2a_workspace_authorization_missing_token_blocks_action_handler(
    server_fixture: Server,
) -> None:
    agent_slug = server_fixture.agents[0].slug
    _enable_workspace_authorization_eddsa(server_fixture)
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_write_headers(server_fixture),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-missing",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent_slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_missing"


def test_a2a_workspace_authorization_not_configured_blocks_action_handler(
    server_fixture: Server,
) -> None:
    agent_slug = server_fixture.agents[0].slug
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_write_headers(server_fixture),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-not-configured",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent_slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_not_configured"


def test_a2a_workspace_binding_options_action_bootstraps_without_token(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    _enable_workspace_authorization_eddsa(server_fixture)
    captured: dict[str, object] = {}

    def list_options(request: V2ActionRequest) -> V2ActionResult:
        captured["workspace_authorization"] = request.workspace_authorization
        return V2ActionResult(
            status="ok",
            effects=[
                V2Effect(
                    type="workspace_binding.options",
                    items=[{"value": "agent-workspace-1", "label": "Workspace 1"}],
                )
            ],
        )

    register_v2_action_handler(
        server_fixture, "workspace_binding.options", list_options
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_write_headers(server_fixture),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-binding-options",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(
                action="workspace_binding.options", agent_slug=agent.slug
            ),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["result"]["status"] == "ok"
    assert payload["result"]["effects"][0]["items"] == [
        {"value": "agent-workspace-1", "label": "Workspace 1"}
    ]
    assert captured == {"workspace_authorization": None}


def test_a2a_workspace_binding_unknown_action_requires_token(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    _enable_workspace_authorization_eddsa(server_fixture)
    called = False

    def delete_binding(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(
        server_fixture, "workspace_binding.delete", delete_binding
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_write_headers(server_fixture),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-binding-delete",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(
                action="workspace_binding.delete", agent_slug=agent.slug
            ),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_missing"


def test_a2a_workspace_binding_create_surface_bootstraps_without_token(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    _enable_workspace_authorization_eddsa(server_fixture)
    captured: dict[str, object] = {}

    def load_create_surface(request: V2SurfaceRequest) -> dict[str, object]:
        captured["workspace_authorization"] = request.workspace_authorization
        return {
            "surface": "workspace_binding.create",
            "document": {
                "type": "Form",
                "fields": [{"id": "display_name", "label": "Display name"}],
            },
        }

    register_v2_surface_handler(
        server_fixture, "workspace_binding.create", load_create_surface
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_write_headers(server_fixture),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-binding-create-surface",
            "method": SUPERVAIZER_SURFACE_LOAD_METHOD,
            "params": _v2_surface_payload(
                surface="workspace_binding.create", agent_slug=agent.slug
            ),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["result"]["surface"] == "workspace_binding.create"
    assert captured == {"workspace_authorization": None}


def test_a2a_workspace_authorization_valid_token_reaches_action_handler(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture)
    captured: dict[str, str] = {}

    def start_job(request: V2ActionRequest) -> V2ActionResult:
        assert request.workspace_authorization is not None
        captured["grant_id"] = request.workspace_authorization.grant_id
        captured["workspace_ref"] = (
            request.workspace_authorization.agent_workspace_ref or ""
        )
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-ok",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "ok"
    assert captured == {"grant_id": "grant-1", "workspace_ref": "agent-workspace-1"}


def test_a2a_workspace_authorization_uses_studio_server_audience(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture)
    server_fixture.workspace_authorization = (
        server_fixture.workspace_authorization.model_copy(
            update={"audience": "supervaizer-server:studio-server-1"}
        )
    )
    captured: dict[str, str] = {}

    def start_job(request: V2ActionRequest) -> V2ActionResult:
        assert request.workspace_authorization is not None
        captured["server_id"] = request.workspace_authorization.server_id
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
        claim_overrides={
            "aud": "supervaizer-server:studio-server-1",
            "server_id": "studio-server-1",
        },
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-studio-server",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "ok"
    assert captured == {"server_id": "studio-server-1"}


def test_a2a_workspace_authorization_uses_studio_agent_id(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture)
    captured: dict[str, str] = {}

    def start_job(request: V2ActionRequest) -> V2ActionResult:
        assert request.workspace_authorization is not None
        captured["agent_id"] = request.workspace_authorization.agent_id
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
        claim_overrides={"agent_id": "studio-agent-1"},
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-studio-agent",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "ok"
    assert captured == {"agent_id": "studio-agent-1"}


def test_a2a_workspace_authorization_requires_studio_agent_id(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture, studio_agent_id=None)

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-missing-studio-agent",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert (
        payload["error"]["data"]["code"]
        == "workspace_authorization_agent_not_registered"
    )


def test_a2a_workspace_authorization_valid_eddsa_token_reaches_action_handler(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture)
    captured: dict[str, str] = {}

    def start_job(request: V2ActionRequest) -> V2ActionResult:
        assert request.workspace_authorization is not None
        captured["field_name_stays_exact"] = "workspace_authorization"
        captured["grant_id"] = request.workspace_authorization.grant_id
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-eddsa-ok",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "ok"
    assert captured == {
        "field_name_stays_exact": "workspace_authorization",
        "grant_id": "grant-1",
    }


def test_a2a_workspace_authorization_eddsa_jwks_token_reaches_action_handler(
    server_fixture: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = server_fixture.agents[0]
    agent.server_agent_id = "studio-agent-1"
    key = ed25519.Ed25519PrivateKey.generate()
    server_fixture.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=True,
        issuer="https://studio.example.test",
        jwks_url="https://studio.example.test/.well-known/jwks.json",
        leeway_seconds=0,
    )
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
        kid="workspace-grant-key-1",
    )
    jwks_fetch_count = 0

    def get_jwks(_url: str, timeout: int) -> _JwksResponse:
        nonlocal jwks_fetch_count
        assert timeout == 5
        jwks_fetch_count += 1
        return _JwksResponse({
            "keys": [
                _ed25519_jwk(
                    key.public_key(),
                    kid="workspace-grant-key-1",
                )
            ]
        })

    monkeypatch.setattr(
        "supervaizer.workspace_authorization.httpx.get",
        get_jwks,
    )
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-eddsa-jwks-ok",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "ok"
    assert called is True

    called = False
    second_response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-eddsa-jwks-cached",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    assert second_response.status_code == 200
    assert second_response.json()["result"]["status"] == "ok"
    assert called is True
    assert jwks_fetch_count == 1


@pytest.mark.asyncio
async def test_a2a_workspace_authorization_jwks_load_runs_off_event_loop(
    server_fixture: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = server_fixture.agents[0]
    agent.server_agent_id = "studio-agent-1"
    key = ed25519.Ed25519PrivateKey.generate()
    server_fixture.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=True,
        issuer="https://studio.example.test",
        jwks_url="https://studio.example.test/.well-known/offloaded-jwks.json",
        leeway_seconds=0,
    )
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
        kid="workspace-grant-key-offloaded",
    )
    event_loop_thread = threading.get_ident()
    fetch_threads: list[int] = []

    def get_jwks(_url: str, timeout: int) -> _JwksResponse:
        assert timeout == 5
        fetch_threads.append(threading.get_ident())
        return _JwksResponse({
            "keys": [
                _ed25519_jwk(
                    key.public_key(),
                    kid="workspace-grant-key-offloaded",
                )
            ]
        })

    monkeypatch.setattr("supervaizer.workspace_authorization.httpx.get", get_jwks)
    register_v2_action_handler(
        server_fixture, "job.start", lambda _request: V2ActionResult(status="ok")
    )

    response = await dispatch_json_rpc(
        server_fixture,
        {
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-eddsa-jwks-offloaded",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
        workspace_authorization_token=token,
    )

    assert response.error is None
    assert response.result is not None
    assert response.result["status"] == "ok"
    assert fetch_threads
    assert event_loop_thread not in fetch_threads


def test_a2a_workspace_authorization_wrong_alg_fails_before_handler(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture)
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
        header_overrides={"alg": "HS256"},
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-wrong-alg",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_unsupported_alg"


@pytest.mark.parametrize("header", [[], "not-an-object", None])
def test_a2a_workspace_authorization_non_object_header_fails_before_handler(
    server_fixture: Server,
    header: object,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture)
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _sign_eddsa_jwt_parts(
        key,
        header=header,
        claims={
            "iss": "https://studio.example.test",
            "aud": f"supervaizer-server:{server_fixture.server_id}",
            "sub": "workspace-agent-grant:grant-1",
            "grant_id": "grant-1",
            "workspace_id": "workspace-1",
            "workspace_slug": "workspace",
            "agent_id": agent.server_agent_id or agent.id,
            "agent_slug": agent.slug,
            "server_id": server_fixture.server_id,
            "scopes": [SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        },
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-non-object-header",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_malformed"


def test_a2a_workspace_authorization_malformed_pem_fails_before_handler(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    agent.server_agent_id = "studio-agent-1"
    server_fixture.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=True,
        issuer="https://studio.example.test",
        public_key_pem="not a pem public key",
        leeway_seconds=0,
    )
    key = ed25519.Ed25519PrivateKey.generate()
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-malformed-pem",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_invalid_key"


def test_a2a_workspace_authorization_rsa_public_key_fails_before_handler(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    _enable_workspace_authorization_with_rsa_public_key(server_fixture)
    ed25519_key = ed25519.Ed25519PrivateKey.generate()
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        ed25519_key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-rsa-public-key",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_invalid_key"


@pytest.mark.parametrize(
    "jwk",
    [
        {
            "kty": "OKP",
            "crv": "Ed25519",
            "kid": "workspace-grant-key-invalid",
            "x": "!!!!",
        },
        {
            "kty": "OKP",
            "crv": "Ed25519",
            "kid": "workspace-grant-key-invalid",
            "x": "dG9vLXNob3J0",
        },
        {
            "kty": "OKP",
            "crv": "X25519",
            "kid": "workspace-grant-key-invalid",
            "x": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        },
    ],
)
def test_a2a_workspace_authorization_malformed_jwks_key_fails_before_handler(
    server_fixture: Server,
    monkeypatch: pytest.MonkeyPatch,
    jwk: dict[str, object],
) -> None:
    agent = server_fixture.agents[0]
    agent.server_agent_id = "studio-agent-1"
    key = ed25519.Ed25519PrivateKey.generate()
    server_fixture.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=True,
        issuer="https://studio.example.test",
        jwks_url="https://studio.example.test/.well-known/invalid-jwks.json",
        leeway_seconds=0,
    )
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
        kid="workspace-grant-key-invalid",
    )
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    def get_jwks(_url: str, timeout: int) -> _JwksResponse:
        assert timeout == 5
        return _JwksResponse({"keys": [jwk]})

    monkeypatch.setattr("supervaizer.workspace_authorization.httpx.get", get_jwks)
    register_v2_action_handler(server_fixture, "job.start", start_job)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-malformed-jwks-key",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_invalid_jwk"


@pytest.mark.parametrize("key_entry", [None, "not-a-key", []])
def test_a2a_workspace_authorization_non_object_jwks_key_fails_before_handler(
    server_fixture: Server,
    monkeypatch: pytest.MonkeyPatch,
    key_entry: object,
) -> None:
    agent = server_fixture.agents[0]
    agent.server_agent_id = "studio-agent-1"
    key = ed25519.Ed25519PrivateKey.generate()
    server_fixture.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=True,
        issuer="https://studio.example.test",
        jwks_url="https://studio.example.test/.well-known/non-object-jwks.json",
        leeway_seconds=0,
    )
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
        kid="workspace-grant-key-non-object",
    )
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    def get_jwks(_url: str, timeout: int) -> _JwksResponse:
        assert timeout == 5
        return _JwksResponse({"keys": [key_entry]})

    monkeypatch.setattr("supervaizer.workspace_authorization.httpx.get", get_jwks)
    register_v2_action_handler(server_fixture, "job.start", start_job)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-non-object-jwks-key",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_invalid_jwks"


def test_a2a_workspace_authorization_missing_scope_blocks_surface_handler(
    server_fixture: Server,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture)
    called = False

    def load_surface(_request: V2SurfaceRequest) -> dict[str, object]:
        nonlocal called
        called = True
        return {"surface": "job.start", "document": {"type": "Form"}}

    register_v2_surface_handler(server_fixture, "job.start", load_surface)
    token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_SURFACE_LOAD_METHOD],
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-workspace-auth-scope",
            "method": SUPERVAIZER_SURFACE_LOAD_METHOD,
            "params": _v2_surface_payload(surface="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == "workspace_authorization_missing_scope"


@pytest.mark.parametrize(
    ("token_overrides", "token_value", "expected_code"),
    [
        ({"exp": 1, "iat": 1}, None, "workspace_authorization_expired"),
        (
            {"aud": "supervaizer-server:another-server"},
            None,
            "workspace_authorization_wrong_audience",
        ),
        (
            {"server_id": "another-server"},
            None,
            "workspace_authorization_wrong_server",
        ),
        (
            {"agent_slug": "another-agent"},
            None,
            "workspace_authorization_wrong_agent",
        ),
        (
            {"agent_id": "another-agent-id"},
            None,
            "workspace_authorization_wrong_agent",
        ),
        (None, "not-a-jwt", "workspace_authorization_malformed"),
    ],
)
def test_a2a_workspace_authorization_failures_block_action_handler(
    server_fixture: Server,
    token_overrides: dict[str, object] | None,
    token_value: str | None,
    expected_code: str,
) -> None:
    agent = server_fixture.agents[0]
    key = _enable_workspace_authorization_eddsa(server_fixture)
    called = False

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        nonlocal called
        called = True
        return V2ActionResult(status="ok")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    token = token_value or _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
        claim_overrides=token_overrides,
    )
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, token),
        json={
            "jsonrpc": "2.0",
            "id": f"rpc-workspace-auth-{expected_code}",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent.slug),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert called is False
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == expected_code


def test_a2a_controller_serializes_v2_action_replay_safety(
    server_fixture: Server,
) -> None:
    agent_slug = server_fixture.agents[0].slug
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent_slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.sync"],
    )

    def sync_job(_request: V2ActionRequest) -> dict[str, object]:
        return {
            "status": "ok",
            "replay_safety": {
                "dedupe_keys": ["job-123", "rev-1"],
                "convergent": True,
                "strictly_idempotent_response": False,
            },
        }

    register_v2_action_handler(server_fixture, "job.sync", sync_job)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "rpc-replay-safety-1",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.sync", agent_slug=agent_slug),
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["replay_safety"] == {
        "dedupe_keys": ["job-123", "rev-1"],
        "stable_external_ids_required": True,
        "strictly_idempotent_response": False,
        "convergent": True,
    }


def test_a2a_controller_action_errors_do_not_leak_exception_details(
    server_fixture: Server,
) -> None:
    agent_slug = server_fixture.agents[0].slug
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent_slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        raise RuntimeError("database password secret-value leaked")

    register_v2_action_handler(server_fixture, "job.start", start_job)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "rpc-error-1",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=agent_slug),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"]["code"] == JSON_RPC_INTERNAL_ERROR
    assert payload["error"]["data"] == {
        "agent_slug": agent_slug,
        "action": "job.start",
    }
    assert "secret-value" not in response.text


def test_a2a_controller_publishes_v2_action_effects(
    server_fixture: Server,
) -> None:
    agent_slug = server_fixture.agents[0].slug
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent_slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )
    queue = subscribe_v2_events(server_fixture)

    def start_job(_request: V2ActionRequest) -> V2ActionResult:
        return V2ActionResult(
            status="ok",
            effects=[V2Effect(type="job.started", job_id="job-123")],
        )

    try:
        register_v2_action_handler(server_fixture, "job.start", start_job)
        client = TestClient(server_fixture.app)

        response = client.post(
            "/a2a",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": "rpc-event-1",
                "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
                "params": _v2_action_payload(action="job.start", agent_slug=agent_slug),
            },
        )

        assert response.status_code == 200
        event = queue.get_nowait()
        assert event["event"] == A2A_EFFECT_EVENT
        assert event["data"] == {
            "agent_slug": agent_slug,
            "action": "job.start",
            "request_id": "request-1",
            "effects": [{"type": "job.started", "job_id": "job-123"}],
        }
    finally:
        unsubscribe_v2_events(server_fixture, queue)


def test_a2a_controller_dispatches_registered_v2_surface(
    server_fixture: Server,
) -> None:
    agent_slug = server_fixture.agents[0].slug
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent_slug,
        scopes=[SUPERVAIZER_SURFACE_LOAD_METHOD, "job.start"],
    )

    def load_job_start(request: V2SurfaceRequest) -> dict[str, object]:
        assert request.surface == "job.start"
        return {
            "surface": "job.start",
            "a2ui_version": "v0.8",
            "document": {"type": "Form", "fields": []},
        }

    register_v2_surface_handler(server_fixture, "job.start", load_job_start)
    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "rpc-surface-2",
            "method": SUPERVAIZER_SURFACE_LOAD_METHOD,
            "params": _v2_surface_payload(surface="job.start", agent_slug=agent_slug),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "rpc-surface-2"
    assert payload["result"] == {
        "surface": "job.start",
        "a2ui_version": "v0.8",
        "a2ui_catalog_version": None,
        "document": {"type": "Form", "fields": []},
    }


def test_server_v2_action_decorator_registers_handler(server_fixture: Server) -> None:
    agent_slug = server_fixture.agents[0].slug
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent_slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start.preview"],
    )

    @server_fixture.v2_action("job.start.preview")
    def preview_job_start(request: V2ActionRequest) -> dict[str, object]:
        assert request.action == "job.start.preview"
        return {"status": "ok", "effects": [{"type": "job.start.previewed"}]}

    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "rpc-4",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(
                action="job.start.preview", agent_slug=agent_slug
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "rpc-4"
    assert payload["result"] == {
        "status": "ok",
        "effects": [{"type": "job.start.previewed"}],
    }


def test_server_v2_surface_decorator_registers_handler(server_fixture: Server) -> None:
    agent_slug = server_fixture.agents[0].slug
    headers = _authorized_a2a_headers(
        server_fixture,
        agent_slug=agent_slug,
        scopes=[SUPERVAIZER_SURFACE_LOAD_METHOD, "job.start"],
    )

    @server_fixture.v2_surface("job.start")
    def load_job_start(request: V2SurfaceRequest) -> dict[str, object]:
        assert request.surface == "job.start"
        return {
            "surface": "job.start",
            "document": {"type": "Form", "submit": {"action": "job.start"}},
        }

    client = TestClient(server_fixture.app)

    response = client.post(
        "/a2a",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "rpc-surface-3",
            "method": SUPERVAIZER_SURFACE_LOAD_METHOD,
            "params": _v2_surface_payload(surface="job.start", agent_slug=agent_slug),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "rpc-surface-3"
    assert payload["result"]["surface"] == "job.start"
    assert payload["result"]["document"]["submit"] == {"action": "job.start"}


def test_v2_action_handlers_are_scoped_by_agent_slug(server_fixture: Server) -> None:
    first_slug = server_fixture.agents[0].slug
    second_agent = Agent(
        name="Second Agent",
        author="authorName",
        developer="Dev",
        version="1.0.0",
        description="description",
    )
    server_fixture.agents.append(second_agent)
    key = _enable_workspace_authorization_eddsa(
        server_fixture,
        agent_slug=first_slug,
        studio_agent_id=f"studio-{first_slug}",
    )
    second_agent.server_agent_id = f"studio-{second_agent.slug}"
    first_token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=first_slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )
    second_token = _workspace_authorization_eddsa_token(
        server_fixture,
        key,
        agent_slug=second_agent.slug,
        scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "job.start"],
    )

    register_v2_action_handler(
        server_fixture,
        "job.start",
        lambda _request: {"status": "ok", "effects": [{"type": "first-agent"}]},
        agent_slug=first_slug,
    )
    register_v2_action_handler(
        server_fixture,
        "job.start",
        lambda _request: {"status": "ok", "effects": [{"type": "second-agent"}]},
        agent_slug=second_agent.slug,
    )
    client = TestClient(server_fixture.app)

    first_response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, first_token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-5",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(action="job.start", agent_slug=first_slug),
        },
    )
    second_response = client.post(
        "/a2a",
        headers=_a2a_workspace_headers(server_fixture, second_token),
        json={
            "jsonrpc": "2.0",
            "id": "rpc-6",
            "method": SUPERVAIZER_ACTION_INVOKE_METHOD,
            "params": _v2_action_payload(
                action="job.start", agent_slug=second_agent.slug
            ),
        },
    )

    assert first_response.json()["result"]["effects"] == [{"type": "first-agent"}]
    assert second_response.json()["result"]["effects"] == [{"type": "second-agent"}]


def test_v2_action_registration_requires_agent_slug_for_multi_agent_server(
    server_fixture: Server,
) -> None:
    server_fixture.agents.append(
        Agent(
            name="Second Agent",
            author="authorName",
            developer="Dev",
            version="1.0.0",
            description="description",
        )
    )

    with pytest.raises(ValueError, match="agent_slug is required"):
        server_fixture.register_v2_action(
            "job.start",
            lambda _request: V2ActionResult(status="ok"),
        )


def _v2_action_payload(
    action: str, agent_slug: str = "agent-interviewer"
) -> dict[str, object]:
    return {
        "request_id": "request-1",
        "actor": {"user_id": "user-1"},
        "workspace": {"id": "workspace-1", "slug": "workspace"},
        "mission_id": "mission-1",
        "agent_slug": agent_slug,
        "surface": "job.start",
        "action": action,
        "input": {"campaign_id": "campaign-1"},
        "draft_session_id": "draft-1",
    }


def _v2_surface_payload(
    surface: str, agent_slug: str = "agent-interviewer"
) -> dict[str, object]:
    return {
        "request_id": "request-1",
        "actor": {"user_id": "user-1"},
        "workspace": {"id": "workspace-1", "slug": "workspace"},
        "mission_id": "mission-1",
        "agent_slug": agent_slug,
        "surface": surface,
        "input": {"campaign_id": "campaign-1"},
        "draft_session_id": "draft-1",
    }


def _enable_workspace_authorization_with_rsa_public_key(
    server: Server,
) -> rsa.RSAPrivateKey:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_pem = (
        key
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    server.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=True,
        issuer="https://studio.example.test",
        public_key_pem=public_key_pem,
        leeway_seconds=0,
    )
    return key


def _enable_workspace_authorization_eddsa(
    server: Server,
    *,
    studio_agent_id: str | None = "studio-agent-1",
    agent_slug: str | None = None,
) -> ed25519.Ed25519PrivateKey:
    key = ed25519.Ed25519PrivateKey.generate()
    public_key_pem = (
        key
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    server.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=True,
        issuer="https://studio.example.test",
        public_key_pem=public_key_pem,
        leeway_seconds=0,
    )
    if studio_agent_id:
        agent = (
            next(item for item in server.agents if item.slug == agent_slug)
            if agent_slug
            else server.agents[0]
        )
        agent.server_agent_id = studio_agent_id
    return key


def _workspace_authorization_eddsa_token(
    server: Server,
    key: ed25519.Ed25519PrivateKey,
    *,
    agent_slug: str,
    scopes: list[str],
    workspace_id: str = "workspace-1",
    workspace_slug: str = "workspace",
    expires_in: int = 300,
    kid: str | None = None,
    header_overrides: dict[str, object] | None = None,
    claim_overrides: dict[str, object] | None = None,
) -> str:
    agent = next(agent for agent in server.agents if agent.slug == agent_slug)
    now = int(time.time())
    claims = {
        "iss": "https://studio.example.test",
        "aud": f"supervaizer-server:{server.server_id}",
        "sub": "workspace-agent-grant:grant-1",
        "grant_id": "grant-1",
        "workspace_id": workspace_id,
        "workspace_slug": workspace_slug,
        "agent_id": agent.server_agent_id or agent.id,
        "agent_slug": agent.slug,
        "server_id": server.server_id,
        "scopes": scopes,
        "agent_workspace_ref": "agent-workspace-1",
        "iat": now,
        "exp": now + expires_in,
        "jti": "token-1",
    }
    header: dict[str, object] = {"alg": "EdDSA", "typ": "JWT"}
    if kid:
        header["kid"] = kid
    if header_overrides:
        header.update(header_overrides)
    if claim_overrides:
        claims.update(claim_overrides)
    return _sign_eddsa_jwt(key, header, claims)


def _sign_eddsa_jwt(
    key: ed25519.Ed25519PrivateKey,
    header: dict[str, object],
    claims: dict[str, object],
) -> str:
    encoded_header = _base64url_json(header)
    encoded_claims = _base64url_json(claims)
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = key.sign(signing_input)
    return f"{encoded_header}.{encoded_claims}.{_base64url(signature)}"


def _sign_eddsa_jwt_parts(
    key: ed25519.Ed25519PrivateKey,
    *,
    header: object,
    claims: object,
) -> str:
    encoded_header = _base64url_json_value(header)
    encoded_claims = _base64url_json_value(claims)
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = key.sign(signing_input)
    return f"{encoded_header}.{encoded_claims}.{_base64url(signature)}"


def _ed25519_jwk(
    public_key: ed25519.Ed25519PublicKey, *, kid: str
) -> dict[str, object]:
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "kid": kid,
        "alg": "EdDSA",
        "use": "sig",
        "x": _base64url(public_bytes),
    }


class _JwksResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def _base64url_json(value: dict[str, object]) -> str:
    return _base64url_json_value(value)


def _base64url_json_value(value: object) -> str:
    return _base64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


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
