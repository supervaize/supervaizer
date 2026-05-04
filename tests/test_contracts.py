# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for versioned Studio controller contracts."""

from __future__ import annotations

import importlib
import sys

from supervaizer.contracts import (
    ControllerEndpoint,
    ControllerContract,
    ServerRegistrationContract,
    build_data_resource_context_headers,
    controller_contract_info,
    resolve_controller_endpoint,
)


def test_controller_contract_endpoints_are_api_prefixed() -> None:
    info = controller_contract_info()

    assert info["controller_contract_version"] == "1.0"
    assert info["api_base_path"] == "/api"
    assert (
        info["endpoints"]["POST_AGENT_JOB_START"]
        == "/api/supervaizer/agents/{agent_slug}/jobs"
    )
    assert (
        info["endpoints"]["POST_AGENT_STATUS"]
        == "/api/supervaizer/agents/{agent_slug}/status"
    )
    assert (
        info["endpoints"]["DATA_RESOURCE"]
        == "/api/agents/{agent_slug}/data/{resource_name}/"
    )
    assert (
        info["endpoints"]["POST_CONTROLLER_REGISTRATION_REFRESH"]
        == "/api/supervaizer/registration/refresh"
    )


def test_contract_models_export_json_schema() -> None:
    controller_schema = ControllerContract.model_json_schema()
    server_schema = ServerRegistrationContract.model_json_schema()

    assert controller_schema["properties"]["endpoints"]["type"] == "object"
    assert server_schema["properties"]["agents"]["type"] == "array"


def test_contract_module_import_does_not_load_controller_runtime() -> None:
    sys.modules.pop("supervaizer.server", None)
    sys.modules.pop("supervaizer.routes", None)
    importlib.import_module("supervaizer.contracts")

    assert "supervaizer.server" not in sys.modules
    assert "supervaizer.routes" not in sys.modules


def test_resolve_controller_endpoint() -> None:
    contract = ControllerContract()

    assert (
        resolve_controller_endpoint(
            contract,
            ControllerEndpoint.POST_AGENT_JOB_START,
            agent_slug="agent-interviewer",
        )
        == "/api/supervaizer/agents/agent-interviewer/jobs"
    )
    assert (
        resolve_controller_endpoint(
            contract,
            ControllerEndpoint.POST_AGENT_STATUS,
            agent_slug="agent-interviewer",
        )
        == "/api/supervaizer/agents/agent-interviewer/status"
    )
    assert (
        resolve_controller_endpoint(
            contract.model_dump(mode="json"),
            "DATA_RESOURCE_ITEM",
            agent_slug="agent-interviewer",
            resource_name="contacts",
            item_id="c1",
        )
        == "/api/agents/agent-interviewer/data/contacts/c1"
    )


def test_resolve_controller_endpoint_rejects_unknown_endpoint() -> None:
    contract = ControllerContract()

    try:
        resolve_controller_endpoint(contract, "UNKNOWN")
    except KeyError as exc:
        assert "UNKNOWN" in str(exc)
    else:
        raise AssertionError("Expected unknown endpoint to raise KeyError")


def test_data_resource_context_headers() -> None:
    headers = build_data_resource_context_headers(
        workspace_id="1",
        workspace_slug="team-slug",
        mission_id="mission-1",
        request_id="request-1",
    )

    assert headers == {
        "X-Supervaize-Workspace-Id": "1",
        "X-Supervaize-Workspace-Slug": "team-slug",
        "X-Supervaize-Mission-Id": "mission-1",
        "X-Supervaize-Request-Id": "request-1",
    }
