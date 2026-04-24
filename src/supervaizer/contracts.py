"""Versioned controller contract shared with Studio integrations."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from supervaizer.common import SvBaseModel

CONTROLLER_CONTRACT_VERSION = "1.0"
API_BASE_PATH = "/api"

CONTROLLER_ENDPOINTS: dict[str, str] = {
    "POST_AGENT_JOB_START": "/api/supervaizer/agents/{agent_slug}/jobs",
    "POST_AGENT_JOB_CUSTOM": "/api/supervaizer/agents/{agent_slug}/custom/{method_name}",
    "GET_JOB_STATUS": "/api/supervaizer/jobs/{job_id}",
    "GET_AGENT_JOB_STATUS": "/api/supervaizer/agents/{agent_slug}/jobs/{job_id}",
    "POST_AGENT_STOP": "/api/supervaizer/agents/{agent_slug}/stop",
    "GET_AGENT_JOB_LIST": "/api/supervaizer/agents/{agent_slug}/jobs",
    "GET_AGENT_BY_ID": "/api/supervaizer/agents/{agent_id}",
    "GET_AGENT_LIST": "/api/supervaizer/agents",
    "GET_AGENT_BY_SLUG": "/api/supervaizer/agents/{agent_slug}",
    "POST_AGENT_PARAMETERS": "/api/supervaizer/agents/{agent_slug}/parameters",
    "POST_AGENT_CASE_UPDATE": "/api/supervaizer/jobs/{job_id}/cases/{case_id}/update",
    "POST_AGENT_PARAMETER_VALIDATION": "/api/supervaizer/agents/{agent_slug}/validate-agent-parameters",
    "POST_AGENT_METHOD_FIELD_VALIDATION": "/api/supervaizer/agents/{agent_slug}/validate-method-fields",
    "POST_AGENT_JOB_START_DYNAMIC_CHOICES": "/api/supervaizer/agents/{agent_slug}/start/dynamic_choices",
    "DATA_RESOURCE": "/api/agents/{agent_slug}/data/{resource_name}/",
    "DATA_RESOURCE_ITEM": "/api/agents/{agent_slug}/data/{resource_name}/{item_id}",
    "DATA_RESOURCE_IMPORT": "/api/agents/{agent_slug}/data/{resource_name}/import/",
    "HEALTH_CHECK": ".well-known/health",
    "CONTROLLER_CONTRACT": "/api/supervaizer/contract",
}


class ControllerContract(SvBaseModel):
    """Canonical controller surface advertised by a Supervaizer server."""

    controller_contract_version: str = Field(default=CONTROLLER_CONTRACT_VERSION)
    api_base_path: str = Field(default=API_BASE_PATH)
    endpoints: dict[str, str] = Field(default_factory=lambda: CONTROLLER_ENDPOINTS.copy())


class AgentRegistrationContract(SvBaseModel):
    """Minimal schema for agent registration payloads consumed by Studio."""

    id: str | None = None
    slug: str
    name: str
    api_path: str
    methods: dict[str, Any] = Field(default_factory=dict)
    parameters_setup: list[dict[str, Any]] = Field(default_factory=list)
    data_resources: list[dict[str, Any]] = Field(default_factory=list)


class ServerRegistrationContract(ControllerContract):
    """Minimal schema for server.register details."""

    server_id: str
    url: str
    uri: str
    api_version: str
    environment: str | None = None
    agents: list[AgentRegistrationContract] = Field(default_factory=list)


class DataResourceListResponse(SvBaseModel):
    """Structured response shape for DataResource list operations."""

    items: list[dict[str, Any]] = Field(default_factory=list)


def controller_contract_info() -> dict[str, Any]:
    """Return the JSON-serializable controller contract."""
    return ControllerContract().model_dump(mode="json")
