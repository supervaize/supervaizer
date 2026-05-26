# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from __future__ import annotations

from typing import Any

from supervaizer.common import ApiSuccess, log
from supervaizer.server_config import _controller_key_fingerprint


def validate_registration_handshake(server: Any, result: ApiSuccess) -> None:
    detail = result.detail if isinstance(result.detail, dict) else {}
    response_object = detail.get("object")
    if not isinstance(response_object, dict):
        raise RuntimeError(
            "Studio registration handshake failed: server.register response did not "
            "include a response object. Studio-to-agent API key persistence could not "
            "be verified."
        )
    handshake = response_object.get("supervaizer_handshake")
    if not isinstance(handshake, dict):
        response_keys = sorted(str(key) for key in response_object.keys())
        raise RuntimeError(
            "Studio registration handshake failed: server.register response did not "
            "include supervaizer_handshake. Studio-to-agent API key persistence could "
            "not be verified. Check that SUPERVAIZE_API_URL points to a Studio "
            "instance that supports the Supervaizer v2 registration handshake. "
            f"response_keys={response_keys}"
        )
    if handshake.get("controller_api_key_match") is True:
        apply_workspace_authorization_handshake(server, handshake)
        log.info(
            "[Server launch] Studio registration handshake verified "
            f"server_id={handshake.get('server_id')} "
            f"controller_key_fingerprint={_controller_key_fingerprint(server.api_key)}"
        )
        return
    raise RuntimeError(
        "Studio registration handshake failed: Studio did not persist the controller API key "
        f"for server_id={handshake.get('server_id')}. "
        f"controller_key_fingerprint={_controller_key_fingerprint(server.api_key)} "
        f"studio_fingerprint={handshake.get('stored_controller_api_key_fingerprint')} "
        f"reason={handshake.get('reason')}"
    )


def validate_studio_a2a_workspace_authorization(server: Any) -> None:
    if not server.a2a_endpoints or server.supervisor_account is None:
        return
    if server.workspace_authorization.enabled:
        return
    raise RuntimeError(
        "Studio-registered Supervaizer v2 A2A requires workspace authorization. "
        "Set SUPERVAIZER_WORKSPACE_AUTH_REQUIRED=true and configure "
        "SUPERVAIZER_WORKSPACE_AUTH_ISSUER plus either "
        "SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY or SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL."
    )


def apply_workspace_authorization_handshake(
    server: Any, handshake: dict[str, Any]
) -> None:
    if not server.workspace_authorization.enabled:
        return

    workspace_authorization = handshake.get("workspace_authorization")
    if not isinstance(workspace_authorization, dict):
        raise RuntimeError(
            "Studio registration handshake failed: workspace authorization is enabled "
            "but supervaizer_handshake.workspace_authorization is missing."
        )

    audience = workspace_authorization.get("audience")
    if not isinstance(audience, str) or not audience.strip():
        raise RuntimeError(
            "Studio registration handshake failed: workspace authorization is enabled "
            "but supervaizer_handshake.workspace_authorization.audience is missing."
        )

    configured_audience = server.workspace_authorization.audience
    if configured_audience and configured_audience != audience:
        raise RuntimeError(
            "Studio registration handshake failed: configured workspace authorization "
            "audience does not match Studio's server audience."
        )

    server.workspace_authorization = server.workspace_authorization.model_copy(
        update={"audience": audience}
    )
    agent_bindings = workspace_authorization.get("agents")
    if not isinstance(agent_bindings, list):
        raise RuntimeError(
            "Studio registration handshake failed: workspace authorization is enabled "
            "but supervaizer_handshake.workspace_authorization.agents is missing."
        )
    apply_workspace_authorization_agent_bindings(server, agent_bindings)


def apply_workspace_authorization_agent_bindings(
    server: Any, agent_bindings: list[Any]
) -> None:
    bindings_by_slug: dict[str, str] = {}
    for binding in agent_bindings:
        if not isinstance(binding, dict):
            raise RuntimeError(
                "Studio registration handshake failed: workspace authorization agent "
                "binding must be an object."
            )
        agent_id = binding.get("id")
        agent_slug = binding.get("slug")
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise RuntimeError(
                "Studio registration handshake failed: workspace authorization agent "
                "binding is missing id."
            )
        if not isinstance(agent_slug, str) or not agent_slug.strip():
            raise RuntimeError(
                "Studio registration handshake failed: workspace authorization agent "
                "binding is missing slug."
            )
        bindings_by_slug[agent_slug] = agent_id

    missing_agents = []
    for agent in server.agents:
        studio_agent_id = bindings_by_slug.get(agent.slug)
        if not studio_agent_id:
            missing_agents.append(agent.slug)
            continue
        if agent.server_agent_id and agent.server_agent_id != studio_agent_id:
            raise RuntimeError(
                "Studio registration handshake failed: workspace authorization agent "
                f"id mismatch for slug={agent.slug}."
            )
        agent.server_agent_id = studio_agent_id

    if missing_agents:
        raise RuntimeError(
            "Studio registration handshake failed: workspace authorization did not "
            f"return Studio agent id(s) for slug(s): {', '.join(missing_agents)}"
        )
