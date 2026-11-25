# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize internal validation behavior before structural changes."""

from types import SimpleNamespace
from typing import Any

import pytest

from supervaizer.common import ApiError
from supervaizer.contracts import V2WorkspaceAuthorizationSettings, V2WorkspaceContext
from supervaizer.studio_handshake import (
    apply_workspace_authorization_agent_bindings,
    apply_workspace_authorization_handshake,
)
from supervaizer.workspace_authorization import (
    WorkspaceAuthorizationClaims,
    WorkspaceAuthorizationError,
    _validate_claim_times,
    _validate_claims_against_request,
    get_workspace_authorization_settings,
)


@pytest.mark.parametrize("audience", [None, "", "   ", 123])
def test_registration_rejects_invalid_workspace_audience(audience: Any) -> None:
    settings = V2WorkspaceAuthorizationSettings(enabled=True, audience="expected")
    server = SimpleNamespace(workspace_authorization=settings, agents=[])

    with pytest.raises(RuntimeError, match="audience is missing"):
        apply_workspace_authorization_handshake(
            server, {"workspace_authorization": {"audience": audience, "agents": []}}
        )

    assert server.workspace_authorization is settings


@pytest.mark.parametrize(
    "configured_audience", [None, "studio-audience", "other-audience"]
)
def test_registration_checks_configured_workspace_audience(
    configured_audience: str | None,
) -> None:
    settings = V2WorkspaceAuthorizationSettings(
        enabled=True, audience=configured_audience
    )
    server = SimpleNamespace(workspace_authorization=settings, agents=[])
    handshake = {
        "workspace_authorization": {"audience": "studio-audience", "agents": []}
    }

    if configured_audience == "other-audience":
        with pytest.raises(RuntimeError, match="audience does not match"):
            apply_workspace_authorization_handshake(server, handshake)
        assert server.workspace_authorization is settings
    else:
        apply_workspace_authorization_handshake(server, handshake)
        assert server.workspace_authorization.audience == "studio-audience"


class _Response:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class _ResponseError(Exception):
    def __init__(self) -> None:
        super().__init__("rate limited")
        self.response = _Response(429, '{"error":"slow down"}')
        self.metadata = '{"retry":true}'
        self.empty_attribute = ""
        self.zero_attribute = 0


def _claims(**overrides: Any) -> WorkspaceAuthorizationClaims:
    return WorkspaceAuthorizationClaims.model_validate({
        "iss": "studio",
        "aud": "supervaizer-server:server-1",
        "grant_id": "grant-1",
        "workspace_id": "workspace-1",
        "workspace_slug": "workspace",
        "agent_id": "studio-agent-1",
        "agent_slug": "agent",
        "server_id": "server-1",
        "scopes": ["read"],
        "exp": 200,
        "iat": 100,
        **overrides,
    })


def _server(*agents: Any) -> SimpleNamespace:
    return SimpleNamespace(agents=list(agents), server_id="server-1")


def test_api_error_serializes_response_and_json_attributes() -> None:
    """ApiError mutates its code from a response and omits empty attributes."""
    error = ApiError(
        message="request failed",
        code="fallback",
        detail={"operation": "sync"},
        exception=_ResponseError(),
        url="https://service.test/register",
        payload={"agent": "agent"},
    )

    assert error.dict == {
        "message": "request failed",
        "code": "429",
        "url": "https://service.test/register",
        "payload": {"agent": "agent"},
        "detail": {"operation": "sync"},
        "exception": {
            "type": "_ResponseError",
            "message": "rate limited",
            "traceback": "NoneType: None\n",
            "attributes": {"metadata": {"retry": True}},
            "response": {"error": "slow down"},
        },
    }


def test_claim_validation_checks_expiry_before_identity_and_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The expiry error wins when a claim also has invalid identity and scopes."""
    agent = SimpleNamespace(slug="agent", server_agent_id="studio-agent-1")
    monkeypatch.setattr("supervaizer.workspace_authorization.time.time", lambda: 500)

    with pytest.raises(WorkspaceAuthorizationError) as raised:
        _validate_claims_against_request(
            claims=_claims(
                exp=100,
                server_id="wrong-server",
                agent_id="wrong-agent",
                scopes=["read"],
            ),
            server=_server(agent),
            agent_slug="agent",
            request_workspace=V2WorkspaceContext(id="wrong-workspace"),
            required_scopes=["write"],
            leeway_seconds=0,
            expected_server_id="server-1",
        )

    assert raised.value.code == "workspace_authorization_expired"
    assert str(raised.value) == "Workspace authorization token is expired"


def test_claim_validation_uses_registered_agent_identity_before_workspace_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registered agent id mismatch wins over later workspace and scope checks."""
    agent = SimpleNamespace(slug="agent", server_agent_id="studio-agent-1")
    monkeypatch.setattr("supervaizer.workspace_authorization.time.time", lambda: 150)

    with pytest.raises(WorkspaceAuthorizationError) as raised:
        _validate_claims_against_request(
            claims=_claims(agent_id="studio-agent-2"),
            server=_server(agent),
            agent_slug="agent",
            request_workspace=V2WorkspaceContext(id="wrong-workspace"),
            required_scopes=["write"],
            leeway_seconds=0,
            expected_server_id="server-1",
        )

    assert raised.value.code == "workspace_authorization_wrong_agent"
    assert str(raised.value) == (
        "Workspace authorization token agent_id does not match the request"
    )


def test_agent_bindings_apply_earlier_identity_before_later_mismatch() -> None:
    """A later mismatch raises after earlier valid bindings already mutate agents."""
    alpha = SimpleNamespace(slug="alpha", server_agent_id=None)
    beta = SimpleNamespace(slug="beta", server_agent_id="studio-beta-old")

    with pytest.raises(RuntimeError, match="id mismatch for slug=beta"):
        apply_workspace_authorization_agent_bindings(
            _server(alpha, beta),
            [
                {"id": "studio-alpha", "slug": "alpha"},
                {"id": "studio-beta-new", "slug": "beta"},
            ],
        )

    assert alpha.server_agent_id == "studio-alpha"
    assert beta.server_agent_id == "studio-beta-old"


def test_agent_bindings_reject_conflicting_ids_for_same_slug() -> None:
    agent = SimpleNamespace(slug="agent", server_agent_id=None)

    with pytest.raises(RuntimeError, match="conflicting.*agent"):
        apply_workspace_authorization_agent_bindings(
            _server(agent),
            [
                {"id": "studio-agent-1", "slug": "agent"},
                {"id": "studio-agent-2", "slug": "agent"},
            ],
        )

    assert agent.server_agent_id is None


def test_agent_bindings_accept_duplicate_matching_ids() -> None:
    agent = SimpleNamespace(slug="agent", server_agent_id=None)

    apply_workspace_authorization_agent_bindings(
        _server(agent),
        [
            {"id": "studio-agent-1", "slug": "agent"},
            {"id": "studio-agent-1", "slug": "agent"},
        ],
    )

    assert agent.server_agent_id == "studio-agent-1"


@pytest.mark.parametrize(
    ("expiry", "issued_at", "leeway", "expected_error"),
    [
        (95, 90, 5, None),
        (94, 90, 5, "workspace_authorization_expired"),
        (200, 105, 5, None),
        (200, 106, 5, "workspace_authorization_not_yet_valid"),
        (200, None, 5, None),
    ],
)
def test_workspace_token_time_boundaries(
    expiry: int, issued_at: int | None, leeway: int, expected_error: str | None
) -> None:
    claims = _claims(exp=expiry, iat=issued_at)

    if expected_error is None:
        _validate_claim_times(claims, leeway_seconds=leeway, now=100)
    else:
        with pytest.raises(WorkspaceAuthorizationError) as raised:
            _validate_claim_times(claims, leeway_seconds=leeway, now=100)
        assert raised.value.code == expected_error


def test_workspace_authorization_settings_preserve_configured_mapping() -> None:
    server = SimpleNamespace(
        workspace_authorization={
            "enabled": True,
            "issuer": "https://studio.example.test",
            "jwks_url": "https://studio.example.test/jwks",
        }
    )

    settings = get_workspace_authorization_settings(server)

    assert settings.enabled is True
    assert settings.issuer == "https://studio.example.test"
    assert settings.jwks_url == "https://studio.example.test/jwks"


@pytest.mark.parametrize("field", ["id", "slug"])
@pytest.mark.parametrize("value", [None, "", "   ", 123])
def test_agent_bindings_reject_invalid_identity_before_applying_any(
    field: str, value: Any
) -> None:
    agent = SimpleNamespace(slug="agent", server_agent_id=None)
    server = _server(agent)
    invalid = {"id": "studio-agent-2", "slug": "other", field: value}

    with pytest.raises(RuntimeError, match=f"missing {field}"):
        apply_workspace_authorization_agent_bindings(
            server, [{"id": "studio-agent-1", "slug": "agent"}, invalid]
        )

    assert agent.server_agent_id is None
