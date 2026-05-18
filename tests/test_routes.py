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

import asyncio
import base64
import json
import time
from io import StringIO
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    AgentMethods,
    Job,
    JobResponse,
    Server,
)
from supervaizer.common import log
from supervaizer.contracts import V2WorkspaceAuthorizationSettings
from supervaizer.data_resource import DataResource, DataResourceContext
from supervaizer.lifecycle import EntityStatus
from supervaizer.parameter import ParametersSetup
from supervaizer.routes import (
    RegistrationRefreshRequest,
    _send_registration_refresh,
    create_agents_routes,
    create_default_routes,
    create_utils_routes,
    get_server,
)
from supervaizer.workspace_authorization import WORKSPACE_AUTHORIZATION_HEADER


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


def test_registration_refresh_endpoint_re_registers_server(
    server_fixture: Server, mocker: Any
) -> None:
    """POST /registration/refresh schedules the canonical server registration."""
    register_server = mocker.patch.object(
        Account, "register_server", new=mocker.AsyncMock(return_value={"valid": True})
    )

    async def get_current_server() -> Server:
        return server_fixture

    app = server_fixture.app
    app.dependency_overrides[get_server] = get_current_server
    app.include_router(create_default_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}
    log_output = StringIO()
    log_sink_id = log.add(log_output, format="{message}", level="INFO")

    try:
        resp = client.post(
            "/supervaizer/registration/refresh",
            headers=headers,
            json={"reason": "manual", "requested_at": "2026-05-04T12:00:00Z"},
        )
    finally:
        log.remove(log_sink_id)

    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted", "reason": "manual"}
    register_server.assert_awaited_once_with(server=server_fixture)
    assert (
        "Registration refresh completed with result=dict reason=manual "
        "requested_at=2026-05-04T12:00:00Z"
    ) in log_output.getvalue()
    assert "result=%s reason=%s requested_at=%s" not in log_output.getvalue()


def test_send_registration_refresh_logs_exception_on_register_failure(
    server_fixture: Server, mocker: Any
) -> None:
    """Background registration refresh must not propagate httpx/HTTP errors."""
    mocker.patch.object(
        Account,
        "register_server",
        new=mocker.AsyncMock(side_effect=httpx.ConnectError("unreachable")),
    )
    log_output = StringIO()
    log_sink_id = log.add(log_output, format="{message}", level="ERROR")
    try:
        asyncio.run(
            _send_registration_refresh(
                server_fixture,
                RegistrationRefreshRequest(
                    reason="studio_push", requested_at="2026-05-04T12:00:00Z"
                ),
            )
        )
    finally:
        log.remove(log_sink_id)

    text = log_output.getvalue()
    assert (
        "Registration refresh failed reason=studio_push "
        "requested_at=2026-05-04T12:00:00Z"
    ) in text


def test_registration_refresh_endpoint_requires_api_key(server_fixture: Server) -> None:
    """POST /registration/refresh is protected by API key authentication."""

    async def get_current_server() -> Server:
        return server_fixture

    app = server_fixture.app
    app.dependency_overrides[get_server] = get_current_server
    app.include_router(create_default_routes(server_fixture))
    client = TestClient(app)

    resp = client.post("/supervaizer/registration/refresh", json={})

    assert resp.status_code == 401


def test_registration_refresh_endpoint_requires_supervisor_account(
    server_fixture: Server,
) -> None:
    """A controller that cannot reach Studio rejects refresh requests explicitly."""

    async def get_current_server() -> Server:
        return server_fixture

    server_fixture.supervisor_account = None
    app = server_fixture.app
    app.dependency_overrides[get_server] = get_current_server
    app.include_router(create_default_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.post(
        "/supervaizer/registration/refresh",
        headers=headers,
        json={"reason": "manual"},
    )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "No supervisor account configured"


def test_dynamic_choices_endpoint_is_removed(server_fixture: Server) -> None:
    """V1 dynamic choices were removed in favor of v2 resource/action option sources."""
    agent = server_fixture.agents[0]
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

    assert resp.status_code == 404


def test_agent_status_endpoint_returns_job_status_response(
    server_fixture: Server, mocker: Any
) -> None:
    """POST /status returns the agent job_status method response."""
    agent = server_fixture.agents[0]
    mocker.patch(
        "supervaizer.agent.Agent.job_status",
        return_value=JobResponse(
            job_id="job-123",
            status=EntityStatus.IN_PROGRESS,
            message="Campaign: in_progress",
            payload={"campaign": {"status": "in_progress"}},
        ),
    )

    app = server_fixture.app
    app.include_router(create_agents_routes(server_fixture))
    client = TestClient(app)
    headers = {"X-API-Key": server_fixture.api_key or ""}

    resp = client.post(
        f"/supervaizer/agents/{agent.slug}/status",
        headers=headers,
        json={"params": {"job_id": "job-123"}},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "job-123"
    assert data["status"] == "in_progress"
    assert data["payload"]["campaign"]["status"] == "in_progress"


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
    dr_a = DataResource(name="items", fields=[], on_list=list, read_only=True)
    dr_b = DataResource(name="items", fields=[], on_list=list, read_only=True)
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


def test_data_resource_callbacks_receive_context(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
) -> None:
    captured: dict[str, DataResourceContext] = {}

    def on_list(*, context: DataResourceContext) -> list[dict[str, Any]]:
        captured["context"] = context
        return [{"id": "1"}]

    resource = DataResource(name="items", fields=[], on_list=on_list, read_only=True)
    methods = AgentMethods(job_start=agent_method_fixture)
    agent = Agent(
        name="Context Agent",
        author="a",
        developer="d",
        version="1.0.0",
        description="d",
        methods=methods,
        parameters_setup=parameters_setup_fixture,
        data_resources=[resource],
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
        agents=[agent],
        api_key="test-api-key",
    )
    client = TestClient(server.app)

    response = client.get(
        f"/api/agents/{agent.slug}/data/items/",
        headers={
            "X-API-Key": "test-api-key",
            "X-Supervaize-Workspace-Id": "team-1",
            "X-Supervaize-Workspace-Slug": "team-slug",
            "X-Supervaize-Mission-Id": "mission-1",
            "X-Supervaize-Request-Id": "request-1",
        },
    )

    assert response.status_code == 200
    context = captured["context"]
    assert context.agent_slug == agent.slug
    assert context.workspace_id == "team-1"
    assert context.workspace_slug == "team-slug"
    assert context.mission_id == "mission-1"
    assert context.request_id == "request-1"


def test_data_resource_workspace_authorization_missing_token_blocks_callback(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
) -> None:
    called = False

    def on_list(*, context: DataResourceContext) -> list[dict[str, Any]]:
        nonlocal called
        called = True
        return [{"workspace": context.workspace_id}]

    resource = DataResource(name="items", fields=[], on_list=on_list, read_only=True)
    server, agent = _make_data_resource_server(
        account_fixture, agent_method_fixture, parameters_setup_fixture, resource
    )
    _enable_workspace_authorization(server)
    client = TestClient(server.app)

    response = client.get(
        f"/api/agents/{agent.slug}/data/items/",
        headers={
            "X-API-Key": "test-api-key",
            "X-Supervaize-Workspace-Id": "team-1",
        },
    )

    assert response.status_code == 403
    assert called is False
    assert "Missing X-Supervaize-Workspace-Authorization" in response.json()["detail"]


def test_data_resource_workspace_authorization_valid_token_sets_context(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
) -> None:
    captured: dict[str, DataResourceContext] = {}

    def on_list(*, context: DataResourceContext) -> list[dict[str, Any]]:
        captured["context"] = context
        return [{"workspace": context.workspace_id}]

    resource = DataResource(name="items", fields=[], on_list=on_list, read_only=True)
    server, agent = _make_data_resource_server(
        account_fixture, agent_method_fixture, parameters_setup_fixture, resource
    )
    key = _enable_workspace_authorization(server)
    token = _workspace_authorization_token(
        server,
        key,
        agent_slug=agent.slug,
        scopes=["resource.items.list"],
        workspace_id="team-1",
        workspace_slug="team-slug",
    )
    client = TestClient(server.app)

    response = client.get(
        f"/api/agents/{agent.slug}/data/items/",
        headers={
            "X-API-Key": "test-api-key",
            WORKSPACE_AUTHORIZATION_HEADER: f"Bearer {token}",
            "X-Supervaize-Workspace-Id": "team-1",
            "X-Supervaize-Workspace-Slug": "team-slug",
        },
    )

    assert response.status_code == 200
    context = captured["context"]
    assert context.workspace_id == "team-1"
    assert context.workspace_slug == "team-slug"
    assert context.workspace_authorization is not None
    assert context.workspace_authorization.grant_id == "grant-1"
    assert context.workspace_authorization.agent_tenant_ref == "tenant-1"


def _make_data_resource_server(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
    resource: DataResource,
) -> tuple[Server, Agent]:
    methods = AgentMethods(job_start=agent_method_fixture)
    agent = Agent(
        name="Data Routes Agent",
        author="a",
        developer="d",
        version="1.0.0",
        description="d",
        methods=methods,
        parameters_setup=parameters_setup_fixture,
        data_resources=[resource],
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
        agents=[agent],
        api_key="test-api-key",
    )
    return server, agent


def _enable_workspace_authorization(server: Server) -> ed25519.Ed25519PrivateKey:
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
    return key


def _workspace_authorization_token(
    server: Server,
    key: ed25519.Ed25519PrivateKey,
    *,
    agent_slug: str,
    scopes: list[str],
    workspace_id: str,
    workspace_slug: str,
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
        "agent_id": agent.id,
        "agent_slug": agent.slug,
        "server_id": server.server_id,
        "scopes": scopes,
        "agent_tenant_ref": "tenant-1",
        "iat": now,
        "exp": now + 300,
        "jti": "token-1",
    }
    return _sign_eddsa_jwt(key, {"alg": "EdDSA", "typ": "JWT"}, claims)


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


def _base64url_json(value: dict[str, object]) -> str:
    return _base64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def test_data_resource_create_requires_id_in_callback_result(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
) -> None:
    resource = DataResource(
        name="items",
        fields=[],
        on_list=list,
        on_create=lambda data: {"name": data["name"]},
    )
    server, agent = _make_data_resource_server(
        account_fixture, agent_method_fixture, parameters_setup_fixture, resource
    )
    client = TestClient(server.app)

    response = client.post(
        f"/api/agents/{agent.slug}/data/items/",
        headers={"X-API-Key": "test-api-key"},
        json={"name": "No ID"},
    )

    assert response.status_code == 500
    assert "must return a dict with 'id'" in response.json()["detail"]


def test_data_resource_update_returns_404_when_callback_returns_none(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
) -> None:
    resource = DataResource(
        name="items",
        fields=[],
        on_list=list,
        on_create=lambda data: {**data, "id": "1"},
        on_update=lambda item_id, data: None,
    )
    server, agent = _make_data_resource_server(
        account_fixture, agent_method_fixture, parameters_setup_fixture, resource
    )
    client = TestClient(server.app)

    response = client.put(
        f"/api/agents/{agent.slug}/data/items/missing",
        headers={"X-API-Key": "test-api-key"},
        json={"name": "Missing"},
    )

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_data_resource_delete_returns_404_when_callback_is_false(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
) -> None:
    resource = DataResource(
        name="items",
        fields=[],
        on_list=list,
        on_create=lambda data: {**data, "id": "1"},
        on_delete=lambda item_id: False,
    )
    server, agent = _make_data_resource_server(
        account_fixture, agent_method_fixture, parameters_setup_fixture, resource
    )
    client = TestClient(server.app)

    response = client.delete(
        f"/api/agents/{agent.slug}/data/items/missing",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_data_resource_permission_error_becomes_403(
    account_fixture: Account,
    agent_method_fixture: AgentMethod,
    parameters_setup_fixture: ParametersSetup,
) -> None:
    def on_list() -> list[dict[str, Any]]:
        raise PermissionError("workspace denied")

    resource = DataResource(name="items", fields=[], on_list=on_list, read_only=True)
    server, agent = _make_data_resource_server(
        account_fixture, agent_method_fixture, parameters_setup_fixture, resource
    )
    client = TestClient(server.app)

    response = client.get(
        f"/api/agents/{agent.slug}/data/items/",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "workspace denied"
