# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Versioned controller contract shared with Studio integrations.

This module is intentionally import-light. Studio imports it directly as the
single source of truth for the controller wire contract, so it must not import
the Supervaizer server/runtime surface.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

CONTROLLER_CONTRACT_VERSION = "1.0"
API_VERSION = "v1"
API_BASE_PATH = "/api"
SUPERVAIZER_V2_CONTRACT_VERSION: Literal[2] = 2
SUPERVAIZER_V2_A2UI_VERSION = "v0.8"
SUPERVAIZER_V2_A2A_VERSION = "0.2.6"


class ContractModel(BaseModel):
    """Base class for SDK-owned wire contract models."""

    model_config = {"use_enum_values": True, "extra": "allow"}


class ControllerEndpoint(StrEnum):
    POST_AGENT_JOB_START = "POST_AGENT_JOB_START"
    POST_AGENT_JOB_CUSTOM = "POST_AGENT_JOB_CUSTOM"
    POST_AGENT_STATUS = "POST_AGENT_STATUS"
    GET_JOB_STATUS = "GET_JOB_STATUS"
    GET_AGENT_JOB_STATUS = "GET_AGENT_JOB_STATUS"
    POST_AGENT_STOP = "POST_AGENT_STOP"
    GET_AGENT_JOB_LIST = "GET_AGENT_JOB_LIST"
    GET_AGENT_BY_ID = "GET_AGENT_BY_ID"
    GET_AGENT_LIST = "GET_AGENT_LIST"
    GET_AGENT_BY_SLUG = "GET_AGENT_BY_SLUG"
    POST_AGENT_PARAMETERS = "POST_AGENT_PARAMETERS"
    POST_AGENT_CASE_UPDATE = "POST_AGENT_CASE_UPDATE"
    POST_AGENT_PARAMETER_VALIDATION = "POST_AGENT_PARAMETER_VALIDATION"
    POST_AGENT_METHOD_FIELD_VALIDATION = "POST_AGENT_METHOD_FIELD_VALIDATION"
    POST_AGENT_JOB_START_DYNAMIC_CHOICES = "POST_AGENT_JOB_START_DYNAMIC_CHOICES"
    DATA_RESOURCE = "DATA_RESOURCE"
    DATA_RESOURCE_ITEM = "DATA_RESOURCE_ITEM"
    DATA_RESOURCE_IMPORT = "DATA_RESOURCE_IMPORT"
    HEALTH_CHECK = "HEALTH_CHECK"
    CONTROLLER_CONTRACT = "CONTROLLER_CONTRACT"
    POST_CONTROLLER_REGISTRATION_REFRESH = "POST_CONTROLLER_REGISTRATION_REFRESH"


CONTROLLER_ENDPOINTS: dict[ControllerEndpoint, str] = {
    ControllerEndpoint.POST_AGENT_JOB_START: "/api/supervaizer/agents/{agent_slug}/jobs",
    ControllerEndpoint.POST_AGENT_JOB_CUSTOM: "/api/supervaizer/agents/{agent_slug}/custom/{method_name}",
    ControllerEndpoint.POST_AGENT_STATUS: "/api/supervaizer/agents/{agent_slug}/status",
    ControllerEndpoint.GET_JOB_STATUS: "/api/supervaizer/jobs/{job_id}",
    ControllerEndpoint.GET_AGENT_JOB_STATUS: "/api/supervaizer/agents/{agent_slug}/jobs/{job_id}",
    ControllerEndpoint.POST_AGENT_STOP: "/api/supervaizer/agents/{agent_slug}/stop",
    ControllerEndpoint.GET_AGENT_JOB_LIST: "/api/supervaizer/agents/{agent_slug}/jobs",
    ControllerEndpoint.GET_AGENT_BY_ID: "/api/supervaizer/agents/{agent_id}",
    ControllerEndpoint.GET_AGENT_LIST: "/api/supervaizer/agents",
    ControllerEndpoint.GET_AGENT_BY_SLUG: "/api/supervaizer/agents/{agent_slug}",
    ControllerEndpoint.POST_AGENT_PARAMETERS: "/api/supervaizer/agents/{agent_slug}/parameters",
    ControllerEndpoint.POST_AGENT_CASE_UPDATE: "/api/supervaizer/jobs/{job_id}/cases/{case_id}/update",
    ControllerEndpoint.POST_AGENT_PARAMETER_VALIDATION: "/api/supervaizer/agents/{agent_slug}/validate-agent-parameters",
    ControllerEndpoint.POST_AGENT_METHOD_FIELD_VALIDATION: "/api/supervaizer/agents/{agent_slug}/validate-method-fields",
    ControllerEndpoint.POST_AGENT_JOB_START_DYNAMIC_CHOICES: "/api/supervaizer/agents/{agent_slug}/start/dynamic_choices",
    ControllerEndpoint.DATA_RESOURCE: "/api/agents/{agent_slug}/data/{resource_name}/",
    ControllerEndpoint.DATA_RESOURCE_ITEM: "/api/agents/{agent_slug}/data/{resource_name}/{item_id}",
    ControllerEndpoint.DATA_RESOURCE_IMPORT: "/api/agents/{agent_slug}/data/{resource_name}/import/",
    ControllerEndpoint.HEALTH_CHECK: ".well-known/health",
    ControllerEndpoint.CONTROLLER_CONTRACT: "/api/supervaizer/contract",
    ControllerEndpoint.POST_CONTROLLER_REGISTRATION_REFRESH: "/api/supervaizer/registration/refresh",
}


class EventType(StrEnum):
    SERVER_REGISTER = "server.register"
    SERVER_ONLINE = "server.online"
    SERVER_DOWN = "server.down"
    AGENT_REGISTER = "agent.register"
    AGENT_WAKEUP = "agent.wakeup"
    AGENT_ANOMALY = "agent.anomaly"
    AGENT_SEND_ANOMALY = "agent.anomaly"
    AGENT_PING = "agent.ping"
    INTERMEDIARY = "agent.intermediary"
    JOB_START = "agent.job.start"
    JOB_START_CONFIRMATION = "agent.job.start.confirmation"
    JOB_END = "agent.job.end"
    JOB_STATUS = "agent.job.status"
    JOB_RESULT = "agent.job.result"
    JOB_ERROR = "agent.job.error"
    JOB_TIMEOUT = "agent.job.timeout"
    CASE_START = "agent.case.start"
    CASE_END = "agent.case.end"
    CASE_STATUS = "agent.case.status"
    CASE_RESULT = "agent.case.result"
    CASE_UPDATE = "agent.case.update"
    CASE_ERROR = "agent.case.error"


class DataResourceContextContract(ContractModel):
    workspace_id: str | None = None
    workspace_slug: str | None = None
    mission_id: str | None = None
    agent_slug: str | None = None
    request_id: str | None = None


class DataResourceFieldContract(ContractModel):
    name: str
    field_type: str = "string"
    label: str | None = None
    required: bool = False
    editable: str = "always"
    visible_on: list[str] = Field(
        default_factory=lambda: ["list", "detail", "create", "edit"]
    )
    description: str | None = None
    related_resource: str | None = None
    sensitive: bool = False
    display_label: str | None = None


class DataResourceContract(ContractModel):
    name: str
    display_name: str
    description: str = ""
    fields: list[DataResourceFieldContract] = Field(default_factory=list)
    read_only: bool = False
    importable: bool = False
    operations: dict[str, bool] = Field(default_factory=dict)


class AgentMethodFieldContract(ContractModel):
    name: str
    type: str | None = None
    field_type: str = "CharField"
    description: str | None = None
    choices: list[Any] | None = None
    default: Any = None
    widget: str | None = None
    required: bool = False
    dynamic_choices: str | None = None


class AgentMethodContract(ContractModel):
    name: str
    method: str
    params: dict[str, Any] | None = None
    fields: list[AgentMethodFieldContract | dict[str, Any]] | None = None
    description: str | None = None
    is_async: bool = False
    timeout: int | None = 600
    nodes: dict[str, Any] | None = None


class AgentMethodsContract(ContractModel):
    job_start: AgentMethodContract
    job_stop: AgentMethodContract | None = None
    job_status: AgentMethodContract | None = None
    job_poll: AgentMethodContract | None = None
    human_answer: AgentMethodContract | None = None
    chat: AgentMethodContract | None = None
    custom: dict[str, AgentMethodContract] | None = None


class ControllerContract(ContractModel):
    """Canonical controller surface advertised by a Supervaizer server."""

    controller_contract_version: str = Field(default=CONTROLLER_CONTRACT_VERSION)
    api_base_path: str = Field(default=API_BASE_PATH)
    endpoints: dict[str, str] = Field(
        default_factory=lambda: {
            endpoint.value: template
            for endpoint, template in CONTROLLER_ENDPOINTS.items()
        }
    )


class AgentRegistrationContract(ContractModel):
    """Minimal schema for agent registration payloads consumed by Studio."""

    id: str | None = None
    slug: str
    name: str
    api_path: str
    release_notes_url: str | None = None
    methods: AgentMethodsContract | dict[str, Any] = Field(default_factory=dict)
    parameters_setup: list[dict[str, Any]] = Field(default_factory=list)
    data_resources: list[DataResourceContract | dict[str, Any]] = Field(
        default_factory=list
    )


class ServerRegistrationContract(ControllerContract):
    """Minimal schema for server.register details."""

    server_id: str
    url: str
    uri: str
    api_version: str
    environment: str | None = None
    agents: list[AgentRegistrationContract] = Field(default_factory=list)


class JobStartRequest(ContractModel):
    job_context: dict[str, Any]
    job_fields: dict[str, Any] = Field(default_factory=dict)
    encrypted_agent_parameters: str | None = None


class DynamicChoicesRequest(ContractModel):
    workspace_id: str
    mission_id: str
    workspace_slug: str | None = None


class DynamicChoicesResponse(ContractModel):
    choices: dict[str, list[Any]] = Field(default_factory=dict)


class CaseUpdateEvent(ContractModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    cost: float = 0.0
    index: int | None = None
    is_final: bool = False


class CaseUpdateRequest(ContractModel):
    answer: dict[str, Any]
    message: str | None = None


class DataResourceListResponse(ContractModel):
    """Structured response shape for DataResource list operations."""

    items: list[dict[str, Any]] = Field(default_factory=list)


class V2AgentIdentity(ContractModel):
    id: str
    slug: str
    display_name: str


class V2ProtocolVersions(ContractModel):
    a2ui_version: str
    a2ui_catalog_version: str
    a2a_version: str
    ag_ui_version: str | None = None


class V2A2ATransport(ContractModel):
    json_rpc: bool = True
    sse: bool = True
    push_notifications: bool = True


class V2A2AExternalInterop(ContractModel):
    inbound_tasks: bool = False
    outbound_delegation: bool = False


class V2A2AController(ContractModel):
    agent_card_url: str
    controller_url: str
    transport: V2A2ATransport = Field(default_factory=V2A2ATransport)
    external_interop: V2A2AExternalInterop = Field(default_factory=V2A2AExternalInterop)


class V2CaseLaneDefinition(ContractModel):
    id: str
    label: str
    default: bool = False


class V2ArtifactTypeDefinition(ContractModel):
    type: str
    label: str
    renderer_surface: str | None = None


class V2AgentCapabilities(ContractModel):
    surfaces: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    case_lanes: list[V2CaseLaneDefinition] = Field(default_factory=list)
    artifact_types: list[V2ArtifactTypeDefinition] = Field(default_factory=list)


class V2JobSyncPolicy(ContractModel):
    action: str = "job.sync"
    supported_statuses: list[str] = Field(default_factory=list)


class V2JobPolicy(ContractModel):
    default_timeout_seconds: int | None = None
    offline_start_policy: Literal["block"] = "block"
    offline_running_policy: Literal["fail_in_studio"] = "fail_in_studio"
    sync: V2JobSyncPolicy | None = None


class V2ResourceDisplayDefinition(ContractModel):
    title_field: str | None = None
    columns: list[str] = Field(default_factory=list)
    search_fields: list[str] = Field(default_factory=list)


class V2MountedResourceViewDefinition(ContractModel):
    view: str
    surface: str


class V2ResourceDefinition(ContractModel):
    id: str
    label: str
    auto_surface: bool = False
    operations: list[str] = Field(default_factory=list)
    display: V2ResourceDisplayDefinition | None = None
    mounted_views: list[V2MountedResourceViewDefinition] = Field(default_factory=list)


class V2DatasetDefinition(ContractModel):
    id: str
    label: str
    auto_surface: bool = False


class SupervaizerV2AgentRegistrationContract(ContractModel):
    supervaizer_contract_version: Literal[2] = SUPERVAIZER_V2_CONTRACT_VERSION
    agent: V2AgentIdentity
    versions: V2ProtocolVersions
    a2a: V2A2AController
    capabilities: V2AgentCapabilities = Field(default_factory=V2AgentCapabilities)
    job_policy: V2JobPolicy = Field(default_factory=V2JobPolicy)
    resources: list[V2ResourceDefinition] = Field(default_factory=list)
    datasets: list[V2DatasetDefinition] = Field(default_factory=list)


class V2ActorContext(ContractModel):
    user_id: str


class V2WorkspaceContext(ContractModel):
    id: str
    slug: str | None = None


class V2ActionRequest(ContractModel):
    request_id: str
    actor: V2ActorContext
    workspace: V2WorkspaceContext
    mission_id: str
    agent_slug: str
    surface: str
    action: str
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    draft_session_id: str | None = None
    job_id: str | None = None
    case_id: str | None = None
    step_id: str | None = None


class V2Effect(ContractModel):
    type: str


class V2ActionResult(ContractModel):
    status: Literal["ok", "error"]
    effects: list[V2Effect] = Field(default_factory=list)


class V2ArtifactRef(ContractModel):
    id: str
    type: str
    title: str | None = None
    external_id: str | None = None
    media_type: str | None = None


class V2AwaitingState(ContractModel):
    reason: str
    surface: str
    action: str


class V2StepSnapshot(ContractModel):
    id: str
    activity: Literal["operation", "delegation"]
    status: str
    title: str | None = None
    external_id: str | None = None
    awaiting: V2AwaitingState | None = None
    outputs: list[V2ArtifactRef] = Field(default_factory=list)


class V2CaseSnapshot(ContractModel):
    id: str
    lane: str = "work"
    title: str | None = None
    status: str | None = None
    external_id: str | None = None
    steps: list[V2StepSnapshot] = Field(default_factory=list)


class V2JobSource(ContractModel):
    type: Literal["fresh_start", "external"]
    external_ref: str | None = None
    previous_job_id: str | None = None


class V2JobSnapshot(ContractModel):
    id: str
    agent_slug: str
    mission_id: str
    status: str
    source: V2JobSource


class V2JobStateSnapshot(ContractModel):
    job: V2JobSnapshot
    cases: list[V2CaseSnapshot] = Field(default_factory=list)


class V2JobSyncResult(V2ActionResult):
    external_ref: str | None = None
    external_version: str | None = None
    sync_cursor: str | None = None
    observed_at: str | None = None
    job_state: V2JobStateSnapshot | None = None


class V2ReplaySafetyMetadata(ContractModel):
    dedupe_keys: list[str] = Field(default_factory=list)
    stable_external_ids_required: bool = True
    strictly_idempotent_response: bool = False
    convergent: bool = True


def _endpoint_key(endpoint: ControllerEndpoint | str) -> str:
    return endpoint.value if isinstance(endpoint, ControllerEndpoint) else endpoint


def resolve_controller_endpoint(
    contract: ControllerContract | dict[str, Any],
    endpoint: ControllerEndpoint | str,
    **params: Any,
) -> str:
    """Resolve a controller endpoint from a registered contract."""
    parsed = (
        contract
        if isinstance(contract, ControllerContract)
        else ControllerContract.model_validate(contract)
    )
    endpoint_key = _endpoint_key(endpoint)
    template = parsed.endpoints.get(endpoint_key)
    if not template:
        raise KeyError(
            f"Controller endpoint {endpoint_key!r} is not advertised by the registered contract"
        )
    try:
        return template.format(**params)
    except KeyError as exc:
        missing = exc.args[0]
        raise KeyError(
            f"Missing parameter {missing!r} for controller endpoint {endpoint_key!r}"
        ) from exc


def build_data_resource_context_headers(
    *,
    workspace_id: str | None = None,
    workspace_slug: str | None = None,
    mission_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, str]:
    """Build Supervaize context headers for Studio DataResource proxy calls."""
    headers: dict[str, str] = {}
    if workspace_id:
        headers["X-Supervaize-Workspace-Id"] = str(workspace_id)
    if workspace_slug:
        headers["X-Supervaize-Workspace-Slug"] = str(workspace_slug)
    if mission_id:
        headers["X-Supervaize-Mission-Id"] = str(mission_id)
    if request_id:
        headers["X-Supervaize-Request-Id"] = str(request_id)
    return headers


def controller_contract_info() -> dict[str, Any]:
    """Return the JSON-serializable controller contract."""
    return ControllerContract().model_dump(mode="json")
