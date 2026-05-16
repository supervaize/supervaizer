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

from collections.abc import Iterable
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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
    AGENT_SEND_ANOMALY = "agent.send_anomaly"
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
    human_answer: AgentMethodContract | None = None
    chat: AgentMethodContract | None = None
    custom: dict[str, AgentMethodContract] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_job_poll(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("job_poll") is not None:
            raise ValueError(
                "job_poll was removed. Use Supervaizer v2 job.sync for status convergence."
            )
        return value


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


def _default_registration_methods() -> dict[str, Any]:
    return {}


def _default_registration_data_resources() -> list[
    DataResourceContract | dict[str, Any]
]:
    return []


class AgentRegistrationContract(ContractModel):
    """Minimal schema for agent registration payloads consumed by Studio."""

    id: str | None = None
    slug: str
    name: str
    api_path: str
    release_notes_url: str | None = None
    methods: AgentMethodsContract | dict[str, Any] = Field(
        default_factory=_default_registration_methods
    )
    parameters_setup: list[dict[str, Any]] = Field(default_factory=list)
    data_resources: list[DataResourceContract | dict[str, Any]] = Field(
        default_factory=_default_registration_data_resources
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
    push_notifications: bool = False


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


class V2ResourceFieldOptionsSource(ContractModel):
    type: Literal["resource"] = "resource"
    resource: str
    value_field: str = "id"
    label_field: str | None = None


class V2ResourceFieldDefinition(ContractModel):
    id: str
    label: str
    type: str = "string"
    required: bool = False
    read_only: bool = False
    multiline: bool = False
    options_source: V2ResourceFieldOptionsSource | None = None


class V2MountedResourceViewDefinition(ContractModel):
    """Agent override that mounts an A2UI surface on a full resource view."""

    view: str = Field(
        description="Generated resource view replaced by the mount (e.g. import, edit)."
    )
    surface: str = Field(
        description="Registered A2UI surface id served for this resource view."
    )


class V2ResourceDefinition(ContractModel):
    id: str
    label: str
    auto_surface: bool = False
    operations: list[str] = Field(default_factory=list)
    display: V2ResourceDisplayDefinition | None = None
    fields: list[V2ResourceFieldDefinition] = Field(default_factory=list)
    mounted_views: list[V2MountedResourceViewDefinition] = Field(default_factory=list)


class V2DatasetDefinition(ContractModel):
    id: str
    label: str
    auto_surface: bool = False
    display: V2ResourceDisplayDefinition | None = None


class SupervaizerV2AgentRegistrationContract(ContractModel):
    supervaizer_contract_version: Literal[2] = SUPERVAIZER_V2_CONTRACT_VERSION
    agent: V2AgentIdentity
    versions: V2ProtocolVersions
    a2a: V2A2AController
    capabilities: V2AgentCapabilities = Field(default_factory=V2AgentCapabilities)
    job_policy: V2JobPolicy = Field(default_factory=V2JobPolicy)
    resources: list[V2ResourceDefinition] = Field(default_factory=list)
    datasets: list[V2DatasetDefinition] = Field(default_factory=list)


def build_v2_agent_registration(
    *,
    agent_id: str,
    agent_slug: str,
    display_name: str,
    agent_card_url: str,
    controller_url: str,
    a2ui_catalog_version: str,
    surfaces: Iterable[str] = (),
    actions: Iterable[str] = (),
    resources: Iterable[V2ResourceDefinition | dict[str, Any]] = (),
    datasets: Iterable[V2DatasetDefinition | dict[str, Any]] = (),
    case_lanes: Iterable[V2CaseLaneDefinition | dict[str, Any]] = (),
    artifact_types: Iterable[V2ArtifactTypeDefinition | dict[str, Any]] = (),
    job_policy: V2JobPolicy | dict[str, Any] | None = None,
    a2ui_version: str = SUPERVAIZER_V2_A2UI_VERSION,
    a2a_version: str = SUPERVAIZER_V2_A2A_VERSION,
    ag_ui_version: str | None = None,
    a2a_transport: V2A2ATransport | dict[str, Any] | None = None,
    a2a_external_interop: V2A2AExternalInterop | dict[str, Any] | None = None,
) -> SupervaizerV2AgentRegistrationContract:
    """Build and validate a Supervaizer v2 registration from SDK primitives."""
    resource_definitions = _contract_list(resources, V2ResourceDefinition)
    dataset_definitions = _contract_list(datasets, V2DatasetDefinition)
    sync_policy = _job_policy(job_policy)

    capability_surfaces = _unique_strings([
        *surfaces,
        *_auto_resource_surface_ids(resource_definitions),
        *_auto_dataset_surface_ids(dataset_definitions),
    ])
    capability_actions = _unique_strings([
        *actions,
        *_resource_action_ids(resource_definitions),
        *_dataset_action_ids(dataset_definitions),
        *(_job_sync_actions(sync_policy)),
    ])

    return SupervaizerV2AgentRegistrationContract(
        agent=V2AgentIdentity(
            id=agent_id,
            slug=agent_slug,
            display_name=display_name,
        ),
        versions=V2ProtocolVersions(
            a2ui_version=a2ui_version,
            a2ui_catalog_version=a2ui_catalog_version,
            a2a_version=a2a_version,
            ag_ui_version=ag_ui_version,
        ),
        a2a=V2A2AController(
            agent_card_url=agent_card_url,
            controller_url=controller_url,
            transport=_contract_or_default(a2a_transport, V2A2ATransport),
            external_interop=_contract_or_default(
                a2a_external_interop,
                V2A2AExternalInterop,
            ),
        ),
        capabilities=V2AgentCapabilities(
            surfaces=capability_surfaces,
            actions=capability_actions,
            case_lanes=_contract_list(case_lanes, V2CaseLaneDefinition),
            artifact_types=_contract_list(artifact_types, V2ArtifactTypeDefinition),
        ),
        job_policy=sync_policy,
        resources=resource_definitions,
        datasets=dataset_definitions,
    )


def _contract_list[ContractModelT: ContractModel](
    values: Iterable[ContractModelT | dict[str, Any]],
    model: type[ContractModelT],
) -> list[ContractModelT]:
    return [
        value if isinstance(value, model) else model.model_validate(value)
        for value in values
    ]


def _contract_or_default[ContractModelT: ContractModel](
    value: ContractModelT | dict[str, Any] | None,
    model: type[ContractModelT],
) -> ContractModelT:
    if value is None:
        return model()
    return value if isinstance(value, model) else model.model_validate(value)


def _job_policy(value: V2JobPolicy | dict[str, Any] | None) -> V2JobPolicy:
    return _contract_or_default(value, V2JobPolicy)


def _unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _auto_resource_surface_ids(resources: Iterable[V2ResourceDefinition]) -> list[str]:
    return [
        f"mission.agent.resource.{resource.id}"
        for resource in resources
        if resource.auto_surface
    ]


def _auto_dataset_surface_ids(datasets: Iterable[V2DatasetDefinition]) -> list[str]:
    return [
        f"mission.agent.dataset.{dataset.id}"
        for dataset in datasets
        if dataset.auto_surface
    ]


def _resource_action_ids(resources: Iterable[V2ResourceDefinition]) -> list[str]:
    return [
        f"resource.{resource.id}.{operation}"
        for resource in resources
        for operation in resource.operations
    ]


def _dataset_action_ids(datasets: Iterable[V2DatasetDefinition]) -> list[str]:
    return [f"dataset.{dataset.id}.query" for dataset in datasets]


def _job_sync_actions(job_policy: V2JobPolicy) -> list[str]:
    if job_policy.sync is None:
        return []
    return [job_policy.sync.action]


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


class V2SurfaceRequest(ContractModel):
    request_id: str
    actor: V2ActorContext
    workspace: V2WorkspaceContext
    mission_id: str
    agent_slug: str
    surface: str
    input: dict[str, Any] = Field(default_factory=dict)
    draft_session_id: str | None = None
    job_id: str | None = None
    case_id: str | None = None
    step_id: str | None = None


class V2Effect(ContractModel):
    type: str
    job_id: str | None = None
    case_id: str | None = None
    step_id: str | None = None
    resource: str | None = None
    dataset: str | None = None
    artifact_id: str | None = None
    status: str | None = None
    message: str | None = None
    item: dict[str, Any] | None = None
    items: list[dict[str, Any]] | None = None
    data: dict[str, Any] | None = None


class V2ReplaySafetyMetadata(ContractModel):
    dedupe_keys: list[str] = Field(default_factory=list)
    stable_external_ids_required: bool = True
    strictly_idempotent_response: bool = False
    convergent: bool = True


class V2ActionResult(ContractModel):
    status: Literal["ok", "error"]
    effects: list[V2Effect] = Field(default_factory=list)
    job_state: V2JobStateSnapshot | None = None
    replay_safety: V2ReplaySafetyMetadata | None = None


class V2SurfaceResult(ContractModel):
    surface: str
    a2ui_version: str | None = None
    a2ui_catalog_version: str | None = None
    document: dict[str, Any] = Field(default_factory=dict)


class V2ArtifactRef(ContractModel):
    id: str
    type: str
    title: str | None = None
    external_id: str | None = None
    media_type: str | None = None


class V2AwaitingFieldDefinition(ContractModel):
    id: str
    label: str
    type: str = "boolean"
    required: bool = False


class V2AwaitingState(ContractModel):
    reason: str
    surface: str
    action: str
    fields: list[V2AwaitingFieldDefinition] = Field(default_factory=list)


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
    target_type: str | None = Field(
        default=None,
        description=(
            "Agent-declared business object type for external sources (e.g. campaign). "
            "Open vocabulary unlike protocol-fixed fields such as step activity."
        ),
    )


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
    agent_slug: str | None = None,
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
    if agent_slug:
        headers["X-Supervaize-Agent-Slug"] = str(agent_slug)
    if request_id:
        headers["X-Supervaize-Request-Id"] = str(request_id)
    return headers


def controller_contract_info() -> dict[str, Any]:
    """Return the JSON-serializable controller contract."""
    return ControllerContract().model_dump(mode="json")
