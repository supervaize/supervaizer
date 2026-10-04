# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Local-mode policy for Supervaizer v2 dispatch over /a2a."""

from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi.testclient import TestClient

from supervaizer import Server
from supervaizer.account import Account
from supervaizer.agent import Agent
from supervaizer.common import log
from supervaizer.contracts import (
    V2ActionRequest,
    V2ActionResult,
    V2VerifiedWorkspaceContext,
    V2WorkspaceAuthorizationSettings,
)
from supervaizer.protocol.a2a.controller import (
    JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED,
    SUPERVAIZER_ACTION_INVOKE_METHOD,
    SUPERVAIZER_SURFACE_LOAD_METHOD,
    register_v2_action_handler,
)
from supervaizer.workspace_authorization import LOCAL_MODE_WORKSPACE_GRANT_ID

_WORKSPACE_AUTH_ENV = (
    "SUPERVAIZER_WORKSPACE_AUTH_REQUIRED",
    "SUPERVAIZER_WORKSPACE_AUTH_ISSUER",
    "SUPERVAIZER_WORKSPACE_AUTH_AUDIENCE",
    "SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY",
    "SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL",
)


def _set_env(monkeypatch: pytest.MonkeyPatch, *, local_mode: bool) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true" if local_mode else "false")
    monkeypatch.delenv("SUPERVAIZER_DISABLE_HELLO_WORLD", raising=False)
    for name in _WORKSPACE_AUTH_ENV:
        monkeypatch.delenv(name, raising=False)


def _server(agents: list[Agent]) -> Server:
    return Server(
        agents=agents, host="localhost", port=8003, environment="test", api_key="k"
    )


@pytest.fixture
def local_server(monkeypatch: pytest.MonkeyPatch) -> Server:
    _set_env(monkeypatch, local_mode=True)
    return _server([])


def _rpc(server: Server, method: str, agent_slug: str, **params: Any) -> dict[str, Any]:
    body = {
        "jsonrpc": "2.0",
        "id": "rpc-1",
        "method": method,
        "params": {
            "request_id": "rpc-1",
            "actor": {"user_id": "user-1"},
            "workspace": {"id": "workspace-1"},
            "mission_id": "mission-1",
            "agent_slug": agent_slug,
            "surface": "job.start",
            "input": {},
        }
        | params,
    }
    response = TestClient(server.app).post(
        "/a2a", headers={"X-API-Key": server.api_key or ""}, json=body
    )
    assert response.status_code == 200
    payload: dict[str, Any] = response.json()
    return payload


def _assert_auth_error(payload: dict[str, Any], code: str) -> None:
    assert payload["error"]["code"] == JSON_RPC_WORKSPACE_AUTHORIZATION_FAILED
    assert payload["error"]["data"]["code"] == code


def test_local_mode_runs_hello_world_without_workspace_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, local_mode=True)
    warnings: list[str] = []
    sink_id = log.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        server = _server([])
    finally:
        log.remove(sink_id)
    assert any("workspace authorization is BYPASSED" in w for w in warnings)
    slug = server.agents[0].slug

    surface = _rpc(server, SUPERVAIZER_SURFACE_LOAD_METHOD, slug, surface="job.start")
    assert surface["result"]["document"]["submit"]["action"] == "job.start"

    started = _rpc(
        server,
        SUPERVAIZER_ACTION_INVOKE_METHOD,
        slug,
        surface="job.start",
        action="job.start",
        input={"count": 1},
        job_id="job-1",
    )
    assert started["result"]["status"] == "ok"
    assert started["result"]["job_state"]["job"]["id"] == "job-1"


def test_local_mode_handler_gets_labelled_local_context(local_server: Server) -> None:
    agent = local_server.agents[0]
    captured: list[V2VerifiedWorkspaceContext | None] = []

    def capture(request: V2ActionRequest) -> V2ActionResult:
        captured.append(request.workspace_authorization)
        return V2ActionResult(status="ok")

    register_v2_action_handler(local_server, "local.capture", capture)
    forged = {
        "grant_id": "forged",
        "workspace_id": "other",
        "agent_id": "x",
        "agent_slug": agent.slug,
        "server_id": "x",
    }
    _rpc(
        local_server,
        SUPERVAIZER_ACTION_INVOKE_METHOD,
        agent.slug,
        action="local.capture",
        workspace_authorization=forged,
    )

    assert captured == [
        V2VerifiedWorkspaceContext(
            grant_id=LOCAL_MODE_WORKSPACE_GRANT_ID,
            workspace_id="workspace-1",
            agent_id=agent.id,
            agent_slug=agent.slug,
            server_id=local_server.server_id,
            scopes=[SUPERVAIZER_ACTION_INVOKE_METHOD, "local.capture"],
        )
    ]


def test_local_mode_unknown_agent_is_rejected(local_server: Server) -> None:
    payload = _rpc(
        local_server, SUPERVAIZER_SURFACE_LOAD_METHOD, "nope", surface="job.start"
    )
    _assert_auth_error(payload, "workspace_authorization_unknown_agent")


def test_non_local_mode_without_config_still_fails_closed(
    monkeypatch: pytest.MonkeyPatch, agent_fixture: Agent
) -> None:
    _set_env(monkeypatch, local_mode=False)
    server = _server([agent_fixture])

    for method, params in (
        (SUPERVAIZER_ACTION_INVOKE_METHOD, {"action": "job.start"}),
        (SUPERVAIZER_SURFACE_LOAD_METHOD, {"surface": "job.start"}),
    ):
        payload = _rpc(server, method, agent_fixture.slug, **params)
        _assert_auth_error(payload, "workspace_authorization_not_configured")


def test_local_mode_with_supervisor_account_is_still_enforced(
    local_server: Server, account_fixture: Account
) -> None:
    # Server.__init__ drops the account in local mode, so attach it afterwards.
    local_server.supervisor_account = account_fixture
    slug = local_server.agents[0].slug

    payload = _rpc(
        local_server, SUPERVAIZER_SURFACE_LOAD_METHOD, slug, surface="job.start"
    )
    _assert_auth_error(payload, "workspace_authorization_not_configured")


@pytest.mark.parametrize(
    "setting", ["issuer", "audience", "public_key_pem", "jwks_url"]
)
def test_local_mode_with_partial_auth_settings_fails_closed(
    local_server: Server, setting: str
) -> None:
    # Trust material without SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=true must not
    # silently fall back to the local-mode bypass.
    local_server.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=False, **{setting: "configured"}
    )
    slug = local_server.agents[0].slug

    payload = _rpc(
        local_server, SUPERVAIZER_SURFACE_LOAD_METHOD, slug, surface="job.start"
    )
    _assert_auth_error(payload, "workspace_authorization_not_configured")


def test_local_mode_with_configured_auth_still_requires_token(
    local_server: Server,
) -> None:
    public_key_pem = (
        ed25519.Ed25519PrivateKey
        .generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    local_server.workspace_authorization = V2WorkspaceAuthorizationSettings(
        enabled=True,
        issuer="https://studio.example.test",
        public_key_pem=public_key_pem,
    )
    slug = local_server.agents[0].slug

    payload = _rpc(
        local_server,
        SUPERVAIZER_ACTION_INVOKE_METHOD,
        slug,
        action="job.start",
        input={"count": 1},
    )
    _assert_auth_error(payload, "workspace_authorization_missing")
