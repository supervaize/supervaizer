# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from typing import Any

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    AgentMethods,
    Job,
    Server,
)
from supervaizer.data_resource import DataResource
from supervaizer.parameter import ParametersSetup
from supervaizer.routes import (
    create_agents_routes,
    create_default_routes,
    create_utils_routes,
)


def test_utils_public_key_and_encrypt(server_fixture: Server, mocker: Any) -> None:
    """Test /supervaizer/utils/public_key and /encrypt endpoints."""
    app = server_fixture.app
    app.include_router(create_utils_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    # Test public_key endpoint
    resp = client.get("/supervaizer/utils/public_key", headers=headers)
    assert resp.status_code == 200
    assert "BEGIN PUBLIC KEY" in resp.text

    # Test encrypt endpoint
    test_str = "super_secret"
    resp = client.post("/supervaizer/utils/encrypt", headers=headers, json=test_str)
    assert resp.status_code == 200
    encrypted = resp.text.strip('"')
    assert isinstance(encrypted, str)
    assert encrypted != test_str


def test_get_job_status_and_all_jobs(server_fixture: Server, job_fixture: Job) -> None:
    """Test /supervaizer/jobs/{job_id} and /supervaizer/jobs endpoints."""
    app = server_fixture.app
    app.include_router(create_default_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    # Test get_job_status (existing job)
    resp = client.get(f"/supervaizer/jobs/{job_fixture.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_fixture.id
    assert "status" in data

    # Test get_job_status (nonexistent job)
    resp = client.get("/supervaizer/jobs/doesnotexist", headers=headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

    # Test get_all_jobs
    resp = client.get("/supervaizer/jobs", headers=headers)
    assert resp.status_code == 200
    jobs = resp.json()
    assert isinstance(jobs, dict)
    found = False
    for agent_jobs in jobs.values():
        for job in agent_jobs:
            if job["job_id"] == job_fixture.id:
                found = True
    assert found


def test_get_agents_and_agent_details(
    server_fixture: Server, agent_fixture: Agent
) -> None:
    """Test /supervaizer/agents and /supervaizer/agent/{agent_id} endpoints."""
    app = server_fixture.app
    app.include_router(create_default_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    # Test get_all_agents
    resp = client.get("/supervaizer/agents", headers=headers)
    assert resp.status_code == 200
    agents = resp.json()
    assert isinstance(agents, list)
    assert any(a["id"] == agent_fixture.id for a in agents)

    # Test get_agent_details (existing agent)
    resp = client.get(f"/supervaizer/agent/{agent_fixture.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == agent_fixture.id
    assert data["name"] == agent_fixture.name

    # Test get_agent_details (nonexistent agent)
    resp = client.get("/supervaizer/agent/doesnotexist", headers=headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_dynamic_choices_endpoint(server_fixture: Server) -> None:
    """Test POST /supervaizer/agents/{slug}/start/dynamic_choices returns choices."""

    def mock_dynamic_choices(
        method_name: str, context: dict
    ) -> dict[str, list[tuple[str, str]]]:
        if method_name == "start":
            return {"projects": [("P1", "Project 1"), ("P2", "Project 2")]}
        return {}

    agent = server_fixture.agents[0]
    agent.dynamic_choices_callback = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.post(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices",
        headers=headers,
        json={
            "workspace_id": "ws-1",
            "workspace_slug": "adl",
            "mission_id": "m-1",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"]["projects"] == [["P1", "Project 1"], ["P2", "Project 2"]]


def test_dynamic_choices_endpoint_passes_workspace_slug_in_context(
    server_fixture: Server,
) -> None:
    """Callback context includes workspace_slug from the request body."""

    captured: dict[str, Any] = {}

    def mock_dynamic_choices(
        method_name: str, context: dict
    ) -> dict[str, list[tuple[str, str]]]:
        captured["context"] = dict(context)
        return {"projects": [("P1", "Project 1")]}

    agent = server_fixture.agents[0]
    agent.dynamic_choices_callback = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.post(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices",
        headers=headers,
        json={
            "workspace_id": 23,
            "workspace_slug": "adl",
            "mission_id": "01KNPPT249HFSSW662KW9R477N",
        },
    )
    assert resp.status_code == 200
    assert captured["context"] == {
        "workspace_id": 23,
        "workspace_slug": "adl",
        "mission_id": "01KNPPT249HFSSW662KW9R477N",
    }


def test_dynamic_choices_endpoint_multiple_keys(
    server_fixture: Server,
) -> None:
    """Test endpoint returns multiple choice keys."""

    def mock_dynamic_choices(
        method_name: str, context: dict
    ) -> dict[str, list[tuple[str, str]]]:
        return {
            "projects": [("P1", "Project 1")],
            "teams": [("T1", "Team Alpha")],
        }

    agent = server_fixture.agents[0]
    agent.dynamic_choices_callback = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.post(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices",
        headers=headers,
        json={
            "workspace_id": "ws-1",
            "workspace_slug": "slug-1",
            "mission_id": "m-1",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"]["projects"] == [["P1", "Project 1"]]
    assert data["choices"]["teams"] == [["T1", "Team Alpha"]]


def test_dynamic_choices_endpoint_empty_result(
    server_fixture: Server,
) -> None:
    """Test endpoint returns empty choices when callback returns empty dict."""

    def mock_dynamic_choices(
        method_name: str, context: dict
    ) -> dict[str, list[tuple[str, str]]]:
        return {}

    agent = server_fixture.agents[0]
    agent.dynamic_choices_callback = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.post(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices",
        headers=headers,
        json={
            "workspace_id": "ws-1",
            "workspace_slug": "slug-1",
            "mission_id": "m-1",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"] == {}


def test_dynamic_choices_endpoint_requires_api_key(
    server_fixture: Server,
) -> None:
    """Test that the dynamic choices endpoint requires API key authentication."""

    def mock_dynamic_choices(
        method_name: str, context: dict
    ) -> dict[str, list[tuple[str, str]]]:
        return {"projects": [("P1", "Project 1")]}

    agent = server_fixture.agents[0]
    agent.dynamic_choices_callback = mock_dynamic_choices

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)

    # No API key header
    resp = client.post(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices",
        json={},
    )
    assert resp.status_code == 401


def test_dynamic_choices_endpoint_no_callback(
    server_fixture: Server,
) -> None:
    """Test that endpoint returns 404 when no callback is registered."""
    agent = server_fixture.agents[0]
    agent.dynamic_choices_callback = None

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.post(
        f"/supervaizer/agents/{agent.slug}/start/dynamic_choices",
        headers=headers,
        json={
            "workspace_id": "ws-1",
            "workspace_slug": "slug-1",
            "mission_id": "m-1",
        },
    )
    assert resp.status_code == 404


def test_data_resource_openapi_operation_ids_unique_per_agent(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
) -> None:
    """Same resource name on different agents must not share operationId (OpenAPI)."""
    methods = AgentMethods(
        job_start=agent_method_fixture,
        job_stop=agent_method_fixture,
        job_status=agent_method_fixture,
        chat=None,
        custom={"method1": agent_method_fixture},
    )
    dr_a = DataResource(name="items", fields=[], on_list=lambda: [], read_only=True)
    dr_b = DataResource(name="items", fields=[], on_list=lambda: [], read_only=True)
    agent_a = Agent(
        name="First Agent",
        author="a",
        developer="d",
        version="1.0.0",
        description="d",
        methods=methods,
        parameters_setup=parameters_setup_fixture,
        data_resources=[dr_a],
    )
    agent_b = Agent(
        name="Second Agent",
        author="a",
        developer="d",
        version="1.0.0",
        description="d",
        methods=methods,
        parameters_setup=parameters_setup_fixture,
        data_resources=[dr_b],
    )
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = Server(
        scheme="http",
        host="localhost",
        port=8001,
        environment="test",
        mac_addr="E2-AC-ED-22-BF-B2",
        debug=True,
        agent_timeout=10,
        private_key=private_key,
        a2a_endpoints=False,
        supervisor_account=account_fixture,
        agents=[agent_a, agent_b],
        api_key="test-api-key",
    )
    client = TestClient(server.app)
    schema = client.get("/openapi.json").json()
    op_ids: list[str] = []
    for path_item in schema.get("paths", {}).values():
        for op in path_item.values():
            if isinstance(op, dict) and "operationId" in op:
                op_ids.append(op["operationId"])
    list_ids = [oid for oid in op_ids if oid.endswith("_items_list")]
    assert len(list_ids) == 2
    assert len(set(list_ids)) == 2
    assert f"{agent_a.slug}_items_list" in list_ids
    assert f"{agent_b.slug}_items_list" in list_ids
