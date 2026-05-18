# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Stateless Studio-signed workspace authorization for Supervaizer v2."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterable, Mapping
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import httpx
from pydantic import Field, ValidationError, field_validator

from supervaizer.contracts import (
    ContractModel,
    V2VerifiedWorkspaceContext,
    V2WorkspaceAuthorizationSettings,
    V2WorkspaceContext,
)

WORKSPACE_AUTHORIZATION_HEADER = "X-Supervaize-Workspace-Authorization"
WORKSPACE_AUTHORIZATION_ALGORITHM = "EdDSA"

WorkspaceAuthorizationPublicKey = ed25519.Ed25519PublicKey


class WorkspaceAuthorizationError(ValueError):
    """Raised when a workspace authorization token cannot authorize a request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WorkspaceAuthorizationClaims(ContractModel):
    iss: str
    aud: str | list[str]
    sub: str | None = None
    grant_id: str
    workspace_id: str
    workspace_slug: str | None = None
    agent_id: str
    agent_slug: str
    server_id: str
    scopes: list[str] = Field(default_factory=list)
    agent_tenant_ref: str | None = None
    iat: int | None = None
    exp: int
    jti: str | None = None

    @field_validator("scopes")
    @classmethod
    def scopes_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("workspace authorization token must include scopes")
        return value


def workspace_authorization_enabled(server: Any) -> bool:
    settings = get_workspace_authorization_settings(server)
    return settings.enabled


def get_workspace_authorization_settings(
    server: Any,
) -> V2WorkspaceAuthorizationSettings:
    value = getattr(server, "workspace_authorization", None)
    if isinstance(value, V2WorkspaceAuthorizationSettings):
        return value
    if value is None:
        return V2WorkspaceAuthorizationSettings()
    return V2WorkspaceAuthorizationSettings.model_validate(value)


def validate_workspace_authorization_settings(
    settings: V2WorkspaceAuthorizationSettings,
) -> None:
    if not settings.enabled:
        return
    if not settings.issuer:
        raise ValueError(
            "Workspace authorization is enabled but issuer is not configured"
        )
    if not settings.public_key_pem and not settings.jwks_url:
        raise ValueError(
            "Workspace authorization is enabled but no public_key_pem or jwks_url "
            "is configured"
        )


def extract_workspace_authorization_token(headers: Mapping[str, str]) -> str | None:
    raw_value = _get_header(headers, WORKSPACE_AUTHORIZATION_HEADER)
    if raw_value is None:
        return None
    value = raw_value.strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value or None


def verify_workspace_authorization_for_request(
    *,
    server: Any,
    token: str | None,
    required_scopes: Iterable[str],
    request_workspace: V2WorkspaceContext,
    agent_slug: str,
) -> V2VerifiedWorkspaceContext | None:
    settings = get_workspace_authorization_settings(server)
    if not settings.enabled:
        return None
    validate_workspace_authorization_settings(settings)
    if not token:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_missing",
            f"Missing {WORKSPACE_AUTHORIZATION_HEADER} header",
        )

    claims = _verify_signed_token(
        token=token,
        settings=settings,
        expected_audience=settings.audience or f"supervaizer-server:{server.server_id}",
    )
    _validate_claims_against_request(
        claims=claims,
        server=server,
        agent_slug=agent_slug,
        request_workspace=request_workspace,
        required_scopes=list(required_scopes),
        leeway_seconds=settings.leeway_seconds,
    )
    return V2VerifiedWorkspaceContext(
        grant_id=claims.grant_id,
        workspace_id=claims.workspace_id,
        workspace_slug=claims.workspace_slug,
        agent_id=claims.agent_id,
        agent_slug=claims.agent_slug,
        server_id=claims.server_id,
        scopes=claims.scopes,
        agent_tenant_ref=claims.agent_tenant_ref,
    )


def _verify_signed_token(
    *,
    token: str,
    settings: V2WorkspaceAuthorizationSettings,
    expected_audience: str,
) -> WorkspaceAuthorizationClaims:
    header, payload, signature, signed_data = _split_jwt(token)
    algorithm = header.get("alg")
    if algorithm != WORKSPACE_AUTHORIZATION_ALGORITHM:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_unsupported_alg",
            "Workspace authorization token must be signed with EdDSA",
        )

    public_key = _load_public_key(
        header=header,
        settings=settings,
    )
    try:
        _verify_signature(
            public_key=public_key,
            signature=signature,
            signed_data=signed_data,
        )
    except InvalidSignature as exc:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_bad_signature",
            "Workspace authorization token signature is invalid",
        ) from exc

    try:
        claims = WorkspaceAuthorizationClaims.model_validate(payload)
    except ValidationError as exc:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_invalid_claims",
            f"Workspace authorization token claims are invalid: {exc.errors()}",
        ) from exc

    if claims.iss != settings.issuer:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_wrong_issuer",
            "Workspace authorization token issuer does not match this server "
            "configuration",
        )
    if not _audience_matches(claims.aud, expected_audience):
        raise WorkspaceAuthorizationError(
            "workspace_authorization_wrong_audience",
            "Workspace authorization token audience does not match this server",
        )
    return claims


def _validate_claims_against_request(
    *,
    claims: WorkspaceAuthorizationClaims,
    server: Any,
    agent_slug: str,
    request_workspace: V2WorkspaceContext,
    required_scopes: list[str],
    leeway_seconds: int,
) -> None:
    now = int(time.time())
    if claims.exp + leeway_seconds < now:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_expired",
            "Workspace authorization token is expired",
        )
    if claims.iat is not None and claims.iat - leeway_seconds > now:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_not_yet_valid",
            "Workspace authorization token was issued in the future",
        )
    if claims.server_id != server.server_id:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_wrong_server",
            "Workspace authorization token server_id does not match this server",
        )
    agent = _get_agent_by_slug(server, agent_slug)
    if claims.agent_slug != agent_slug:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_wrong_agent",
            "Workspace authorization token agent_slug does not match the request",
        )
    if claims.agent_id != agent.id:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_wrong_agent",
            "Workspace authorization token agent_id does not match the request",
        )
    if claims.workspace_id != request_workspace.id:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_wrong_workspace",
            "Workspace authorization token workspace_id does not match the request",
        )
    if (
        request_workspace.slug
        and claims.workspace_slug
        and claims.workspace_slug != request_workspace.slug
    ):
        raise WorkspaceAuthorizationError(
            "workspace_authorization_wrong_workspace",
            "Workspace authorization token workspace_slug does not match the request",
        )
    missing_scopes = [
        scope for scope in required_scopes if scope not in set(claims.scopes)
    ]
    if missing_scopes:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_missing_scope",
            f"Workspace authorization token is missing scope(s): "
            f"{', '.join(missing_scopes)}",
        )


def _get_agent_by_slug(server: Any, agent_slug: str) -> Any:
    for agent in server.agents:
        if agent.slug == agent_slug:
            return agent
    raise WorkspaceAuthorizationError(
        "workspace_authorization_unknown_agent",
        f"Unknown agent_slug for workspace authorization: {agent_slug}",
    )


def _split_jwt(
    token: str,
) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_malformed",
            "Workspace authorization token must be a compact JWT",
        )
    encoded_header, encoded_payload, encoded_signature = parts
    try:
        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
        signature = _base64url_decode(encoded_signature)
    except (json.JSONDecodeError, ValueError) as exc:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_malformed",
            "Workspace authorization token is malformed",
        ) from exc
    return (
        header,
        payload,
        signature,
        f"{encoded_header}.{encoded_payload}".encode("ascii"),
    )


def _load_public_key(
    *,
    header: dict[str, Any],
    settings: V2WorkspaceAuthorizationSettings,
) -> WorkspaceAuthorizationPublicKey:
    if settings.public_key_pem:
        return _load_public_key_pem(settings.public_key_pem)
    if settings.jwks_url:
        return _load_public_key_from_jwks(
            header=header,
            jwks_url=settings.jwks_url,
        )
    raise WorkspaceAuthorizationError(
        "workspace_authorization_not_configured",
        "Workspace authorization public key is not configured",
    )


def _load_public_key_pem(public_key_pem: str) -> WorkspaceAuthorizationPublicKey:
    key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise WorkspaceAuthorizationError(
            "workspace_authorization_invalid_key",
            "Workspace authorization EdDSA public key must be an Ed25519 public key",
        )
    return key


def _verify_signature(
    *,
    public_key: WorkspaceAuthorizationPublicKey,
    signature: bytes,
    signed_data: bytes,
) -> None:
    public_key.verify(signature, signed_data)


def _load_public_key_from_jwks(
    *, header: dict[str, Any], jwks_url: str
) -> WorkspaceAuthorizationPublicKey:
    key_id = header.get("kid")
    if not isinstance(key_id, str) or not key_id:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_missing_kid",
            "Workspace authorization token header must include kid for JWKS",
        )
    try:
        response = httpx.get(jwks_url, timeout=5)
        response.raise_for_status()
        jwks = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_jwks_unavailable",
            "Workspace authorization JWKS could not be loaded",
        ) from exc
    keys = jwks.get("keys", [])
    if not isinstance(keys, list):
        raise WorkspaceAuthorizationError(
            "workspace_authorization_invalid_jwks",
            "Workspace authorization JWKS payload has no keys list",
        )
    for key_data in keys:
        if key_data.get("kid") == key_id:
            return _ed25519_public_key_from_jwk(key_data)
    raise WorkspaceAuthorizationError(
        "workspace_authorization_unknown_kid",
        "Workspace authorization JWKS has no key matching token kid",
    )


def _ed25519_public_key_from_jwk(jwk: dict[str, Any]) -> ed25519.Ed25519PublicKey:
    if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519":
        raise WorkspaceAuthorizationError(
            "workspace_authorization_invalid_jwk",
            "Workspace authorization EdDSA JWK must be OKP/Ed25519",
        )
    key_material = jwk.get("x")
    if not isinstance(key_material, str) or not key_material:
        raise WorkspaceAuthorizationError(
            "workspace_authorization_invalid_jwk",
            "Workspace authorization Ed25519 JWK must include x",
        )
    return ed25519.Ed25519PublicKey.from_public_bytes(_base64url_decode(key_material))


def _audience_matches(audience: str | list[str], expected: str) -> bool:
    if isinstance(audience, str):
        return audience == expected
    return expected in audience


def _base64url_decode(value: str) -> bytes:
    padding_length = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + ("=" * padding_length))


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    lower_name = name.lower()
    for key, value in headers.items():
        if key.lower() == lower_name:
            return value
    return None
