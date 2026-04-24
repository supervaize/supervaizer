"""Tests for versioned Studio controller contracts."""

from __future__ import annotations

from supervaizer.contracts import (
    ControllerContract,
    ServerRegistrationContract,
    controller_contract_info,
)


def test_controller_contract_endpoints_are_api_prefixed() -> None:
    info = controller_contract_info()

    assert info["controller_contract_version"] == "1.0"
    assert info["api_base_path"] == "/api"
    assert info["endpoints"]["POST_AGENT_JOB_START"] == "/api/supervaizer/agents/{agent_slug}/jobs"
    assert info["endpoints"]["DATA_RESOURCE"] == "/api/agents/{agent_slug}/data/{resource_name}/"


def test_contract_models_export_json_schema() -> None:
    controller_schema = ControllerContract.model_json_schema()
    server_schema = ServerRegistrationContract.model_json_schema()

    assert controller_schema["properties"]["endpoints"]["type"] == "object"
    assert server_schema["properties"]["agents"]["type"] == "array"
