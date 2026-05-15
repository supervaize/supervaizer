# Model Reference extra

**Version:** 0.20.1

### `common.SvBaseModel`

Base model for all Supervaize models.

_No fields found._

### `telemetry.Telemetry`

**Inherits from:** [`telemetry.TelemetryModel`](#telemetrytelemetrymodel)

Base class for all telemetry data in the Supervaize Control system.

Telemetry represents monitoring and observability data sent from agents to the control system.
This includes logs, metrics, events, traces, exceptions, diagnostics and custom telemetry.

Inherits from TelemetryModel which defines the core telemetry attributes:
    - agentId: The ID of the agent sending the telemetry
    - type: The TelemetryType enum indicating the telemetry category (logs, metrics, etc)
    - category: The TelemetryCategory enum for the functional area (system, application, etc)
    - severity: The TelemetrySeverity enum indicating importance (debug, info, warning, etc)
    - details: A dictionary containing telemetry-specific details

_No additional fields beyond parent class._

### `agent.AgentCustomMethodParams`

**Inherits from:** [`agent.AgentMethodParams`](#agentagentmethodparams)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `method_name` | `str` | **required** |  |

### `agent.AgentJobContextBase`

Base model for agent job context parameters

| Field | Type | Default | Description |
|---|---|---|---|
| `job_context` | `JobContext` | **required** |  |
| `job_fields` | `Dict[str, Any]` | **required** |  |

### `agent.AgentMethodParams`

Method parameters for agent operations.

| Field | Type | Default | Description |
|---|---|---|---|
| `params` | `Dict[str, Any]` | — | A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs |

### `agent.AgentMethods`

**Inherits from:** [`agent.AgentMethodsAbstract`](#agentagentmethodsabstract)

_No additional fields beyond parent class._

### `agent.AgentMethodsAbstract`

A base class for creating Pydantic models.

| Field | Type | Default | Description |
|---|---|---|---|
| `job_start` | `AgentMethod` | **required** |  |
| `job_stop` | `AgentMethod` | `None` |  |
| `job_status` | `AgentMethod` | `None` |  |
| `human_answer` | `AgentMethod` | `None` |  |
| `chat` | `AgentMethod` | `None` |  |
| `custom` | `dict[str, supervaizer.agent.AgentMethod]` | `None` |  |

### `agent.AgentResponse`

Response model for agent endpoints - values provided by Agent.registration_info

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `id` | `str` | **required** |  |
| `author` | `str` | `None` |  |
| `developer` | `str` | `None` |  |
| `maintainer` | `str` | `None` |  |
| `editor` | `str` | `None` |  |
| `version` | `str` | **required** |  |
| `release_notes_url` | `str` | `None` |  |
| `api_path` | `str` | **required** |  |
| `description` | `str` | **required** |  |
| `tags` | `list[str]` | `None` |  |
| `methods` | `AgentMethods` | `None` |  |
| `parameters_setup` | `typing.List[typing.Dict[str, typing.Any]]` | `None` |  |
| `server_agent_id` | `str` | `None` |  |
| `server_agent_status` | `str` | `None` |  |
| `server_agent_onboarding_status` | `str` | `None` |  |
| `server_encrypted_parameters` | `str` | `None` |  |

### `case.CaseNodes`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `nodes` | `List[case.CaseNode]` | [] |  |

### `data_resource.DataResource`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

Declares a named data resource the agent exposes for Studio CRUD access.

The agent provides callback functions for each operation. The SDK generates
the corresponding FastAPI routes automatically.

Example::

    contacts_resource = DataResource(
        name="contacts",
        display_name="Contacts",
        fields=[
            DataResourceField(name="id", editable=Editable.NEVER, visible_on=["list", "detail"]),
            DataResourceField(name="email", field_type=FieldType.EMAIL, required=True),
        ],
        on_list=lambda: repo.list_all(),
        on_get=lambda item_id: repo.get(item_id),
        on_create=lambda data: repo.create(data),
        on_update=lambda item_id, data: repo.update(item_id, data),
        on_delete=lambda item_id: repo.delete(item_id),
    )

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | URL-safe resource identifier, e.g. 'contacts'. Lowercase letters, digits, underscores, and hyphens only; must start with a letter or digit. |
| `display_name` | `str` | '' |  |
| `description` | `str` | '' |  |
| `fields` | `list[data_resource.DataResourceField]` | — |  |
| `read_only` | `bool` | False |  |
| `importable` | `bool` | False | Enables CSV bulk import route |
| `on_list` | `typing.Callable[..., list[dict[str, typing.Any]]]` | `None` |  |
| `on_get` | `typing.Callable[..., dict[str, typing.Any] | None]` | `None` |  |
| `on_create` | `typing.Callable[..., dict[str, typing.Any]]` | `None` |  |
| `on_update` | `typing.Callable[..., dict[str, typing.Any] | None]` | `None` |  |
| `on_delete` | `typing.Callable[..., bool]` | `None` |  |
| `on_import` | `typing.Callable[..., dict[str, typing.Any]]` | `None` |  |

### `job.Job`

**Inherits from:** [`job.AbstractJob`](#jobabstractjob)

Jobs are typically created by the platform and are not created by the agent.

Args:
    id (str): Unique identifier for the job - provided by the platform
    agent_name (str): Name (slug) of the agent running the job
    status (EntityStatus): Current status of the job
    job_context (JobContext): Context information for the job
    payload (Any, optional): Job payload data. Defaults to None
    result (Any, optional): Job result data. Defaults to None
    error (str, optional): Error message if job failed. Defaults to None
    responses (list[JobResponse], optional): List of job responses. Defaults to empty list
    finished_at (datetime, optional): When job completed. Defaults to None
    created_at (datetime, optional): When job was created. Defaults to None

_No additional fields beyond parent class._

### `job.JobContext`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `workspace_id` | `str` | **required** |  |
| `job_id` | `str` | **required** |  |
| `started_by` | `str` | **required** |  |
| `started_at` | `datetime` | **required** |  |
| `mission_id` | `str` | **required** |  |
| `mission_name` | `str` | **required** |  |
| `mission_context` | `Any` | `None` |  |
| `job_instructions` | `JobInstructions` | `None` |  |

### `job.JobResponse`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `job_id` | `str` | **required** |  |
| `status` | `<enum 'EntityStatus'>` | **required** |  |
| `message` | `str` | **required** |  |
| `payload` | `dict[str, typing.Any]` | `None` |  |
| `error_message` | `str` | `None` |  |
| `error_traceback` | `str` | `None` |  |

### `event.JobStartConfirmationEvent`

**Inherits from:** [`event.Event`](#eventevent)

_No additional fields beyond parent class._

### `contracts.SupervaizerV2AgentRegistrationContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `supervaizer_contract_version` | `Literal[2]` | 2 |  |
| `agent` | `V2AgentIdentity` | **required** |  |
| `versions` | `V2ProtocolVersions` | **required** |  |
| `a2a` | `V2A2AController` | **required** |  |
| `capabilities` | `V2AgentCapabilities` | — |  |
| `job_policy` | `V2JobPolicy` | — |  |
| `resources` | `list[contracts.V2ResourceDefinition]` | — |  |
| `datasets` | `list[contracts.V2DatasetDefinition]` | — |  |

### `case.Case`

**Inherits from:** [`case.CaseAbstractModel`](#casecaseabstractmodel)

_No additional fields beyond parent class._

### `case.CaseAbstractModel`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `job_id` | `str` | **required** |  |
| `name` | `str` | **required** |  |
| `account` | `ForwardRef('Account')` | **required** |  |
| `description` | `str` | **required** |  |
| `status` | `<enum 'EntityStatus'>` | **required** |  |
| `updates` | `List[case.CaseNodeUpdate]` | [] |  |
| `total_cost` | `float` | 0.0 |  |
| `final_delivery` | `typing.Dict[str, typing.Any]` | `None` |  |
| `finished_at` | `datetime` | `None` |  |
| `metadata` | `Dict[str, Any]` | — | Agent-provided domain metadata (e.g. contact context) |

### `case.CaseNode`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `type` | `<enum 'CaseNodeType'>` | **required** |  |
| `factory` | `Any` | `None` |  |
| `description` | `str` | '' |  |
| `can_be_confirmed` | `bool` | False |  |

### `case.CaseNodeUpdate`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

CaseNodeUpdate is a class that represents an update to a case node.


Returns:
    CaseNodeUpdate: CaseNodeUpdate object

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `index` | `int` | `None` |  |
| `cost` | `float` | `None` |  |
| `name` | `str` | `None` |  |
| `payload` | `typing.Dict[str, typing.Any]` | `None` |  |
| `is_final` | `bool` | False |  |
| `upsert` | `bool` | False |  |
| `error` | `str` | `None` |  |
| `scheduled_at` | `datetime` | `None` |  |
| `scheduled_method` | `str` | `None` |  |
| `scheduled_params` | `typing.Dict[str, typing.Any]` | `None` |  |
| `scheduled_status` | `str` | `None` |  |

### `contracts.AgentMethodContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `method` | `str` | **required** |  |
| `params` | `dict[str, typing.Any]` | `None` |  |
| `fields` | `list[supervaizer.contracts.AgentMethodFieldContract | dict[str, typing.Any]]` | `None` |  |
| `description` | `str` | `None` |  |
| `is_async` | `bool` | False |  |
| `timeout` | `int` | 600 |  |
| `nodes` | `dict[str, typing.Any]` | `None` |  |

### `contracts.AgentMethodFieldContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `type` | `str` | `None` |  |
| `field_type` | `str` | 'CharField' |  |
| `description` | `str` | `None` |  |
| `choices` | `list[typing.Any]` | `None` |  |
| `default` | `Any` | `None` |  |
| `widget` | `str` | `None` |  |
| `required` | `bool` | False |  |

### `contracts.AgentMethodsContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `job_start` | `AgentMethodContract` | **required** |  |
| `job_stop` | `AgentMethodContract` | `None` |  |
| `job_status` | `AgentMethodContract` | `None` |  |
| `human_answer` | `AgentMethodContract` | `None` |  |
| `chat` | `AgentMethodContract` | `None` |  |
| `custom` | `dict[str, supervaizer.contracts.AgentMethodContract]` | `None` |  |

### `contracts.AgentRegistrationContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

Minimal schema for agent registration payloads consumed by Studio.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | `None` |  |
| `slug` | `str` | **required** |  |
| `name` | `str` | **required** |  |
| `api_path` | `str` | **required** |  |
| `release_notes_url` | `str` | `None` |  |
| `methods` | `AgentMethodsContract` \| `dict[str, typing.Any]` | — |  |
| `parameters_setup` | `list[dict[str, Any]]` | — |  |
| `data_resources` | `list[contracts.DataResourceContract | dict[str, Any]]` | — |  |

### `contracts.CaseUpdateEvent`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `payload` | `dict[str, Any]` | — |  |
| `cost` | `float` | 0.0 |  |
| `index` | `int` | `None` |  |
| `is_final` | `bool` | False |  |

### `contracts.CaseUpdateRequest`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `answer` | `dict[str, Any]` | **required** |  |
| `message` | `str` | `None` |  |

### `contracts.ContractModel`

Base class for SDK-owned wire contract models.

_No fields found._

### `contracts.ControllerContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

Canonical controller surface advertised by a Supervaizer server.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `controller_contract_version` | `str` | '1.0' |  |
| `api_base_path` | `str` | '/api' |  |
| `endpoints` | `dict[str, str]` | — |  |

### `contracts.DataResourceContextContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `workspace_id` | `str` | `None` |  |
| `workspace_slug` | `str` | `None` |  |
| `mission_id` | `str` | `None` |  |
| `agent_slug` | `str` | `None` |  |
| `request_id` | `str` | `None` |  |

### `contracts.DataResourceContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `display_name` | `str` | **required** |  |
| `description` | `str` | '' |  |
| `fields` | `list[contracts.DataResourceFieldContract]` | — |  |
| `read_only` | `bool` | False |  |
| `importable` | `bool` | False |  |
| `operations` | `dict[str, bool]` | — |  |

### `contracts.DataResourceFieldContract`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `field_type` | `str` | 'string' |  |
| `label` | `str` | `None` |  |
| `required` | `bool` | False |  |
| `editable` | `str` | 'always' |  |
| `visible_on` | `list[str]` | — |  |
| `description` | `str` | `None` |  |
| `related_resource` | `str` | `None` |  |
| `sensitive` | `bool` | False |  |
| `display_label` | `str` | `None` |  |

### `contracts.DataResourceListResponse`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

Structured response shape for DataResource list operations.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `items` | `list[dict[str, Any]]` | — |  |

### `contracts.JobStartRequest`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `job_context` | `dict[str, Any]` | **required** |  |
| `job_fields` | `dict[str, Any]` | — |  |
| `encrypted_agent_parameters` | `str` | `None` |  |

### `contracts.ServerRegistrationContract`

**Inherits from:** [`contracts.ControllerContract`](#contractscontrollercontract)

Minimal schema for server.register details.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `server_id` | `str` | **required** |  |
| `url` | `str` | **required** |  |
| `uri` | `str` | **required** |  |
| `api_version` | `str` | **required** |  |
| `environment` | `str` | `None` |  |
| `agents` | `list[contracts.AgentRegistrationContract]` | — |  |

### `contracts.V2A2AController`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `agent_card_url` | `str` | **required** |  |
| `controller_url` | `str` | **required** |  |
| `transport` | `V2A2ATransport` | — |  |
| `external_interop` | `V2A2AExternalInterop` | — |  |

### `contracts.V2A2AExternalInterop`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `inbound_tasks` | `bool` | False |  |
| `outbound_delegation` | `bool` | False |  |

### `contracts.V2A2ATransport`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `json_rpc` | `bool` | True |  |
| `sse` | `bool` | True |  |
| `push_notifications` | `bool` | False |  |

### `contracts.V2ActionRequest`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `request_id` | `str` | **required** |  |
| `actor` | `V2ActorContext` | **required** |  |
| `workspace` | `V2WorkspaceContext` | **required** |  |
| `mission_id` | `str` | **required** |  |
| `agent_slug` | `str` | **required** |  |
| `surface` | `str` | **required** |  |
| `action` | `str` | **required** |  |
| `input` | `dict[str, Any]` | — |  |
| `idempotency_key` | `str` | `None` |  |
| `draft_session_id` | `str` | `None` |  |
| `job_id` | `str` | `None` |  |
| `case_id` | `str` | `None` |  |
| `step_id` | `str` | `None` |  |

### `contracts.V2ActionResult`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `status` | `Literal['ok', 'error']` | **required** |  |
| `effects` | `list[contracts.V2Effect]` | — |  |

### `contracts.V2ActorContext`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `user_id` | `str` | **required** |  |

### `contracts.V2AgentCapabilities`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `surfaces` | `list[str]` | — |  |
| `actions` | `list[str]` | — |  |
| `case_lanes` | `list[contracts.V2CaseLaneDefinition]` | — |  |
| `artifact_types` | `list[contracts.V2ArtifactTypeDefinition]` | — |  |

### `contracts.V2AgentIdentity`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `slug` | `str` | **required** |  |
| `display_name` | `str` | **required** |  |

### `contracts.V2ArtifactRef`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `type` | `str` | **required** |  |
| `title` | `str` | `None` |  |
| `external_id` | `str` | `None` |  |
| `media_type` | `str` | `None` |  |

### `contracts.V2ArtifactTypeDefinition`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `str` | **required** |  |
| `label` | `str` | **required** |  |
| `renderer_surface` | `str` | `None` |  |

### `contracts.V2AwaitingFieldDefinition`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `label` | `str` | **required** |  |
| `type` | `str` | 'boolean' |  |
| `required` | `bool` | False |  |

### `contracts.V2AwaitingState`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `reason` | `str` | **required** |  |
| `surface` | `str` | **required** |  |
| `action` | `str` | **required** |  |
| `fields` | `list[contracts.V2AwaitingFieldDefinition]` | — |  |

### `contracts.V2CaseLaneDefinition`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `label` | `str` | **required** |  |
| `default` | `bool` | False |  |

### `contracts.V2CaseSnapshot`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `lane` | `str` | 'work' |  |
| `title` | `str` | `None` |  |
| `status` | `str` | `None` |  |
| `external_id` | `str` | `None` |  |
| `steps` | `list[contracts.V2StepSnapshot]` | — |  |

### `contracts.V2DatasetDefinition`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `label` | `str` | **required** |  |
| `auto_surface` | `bool` | False |  |

### `contracts.V2Effect`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `str` | **required** |  |

### `contracts.V2JobPolicy`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `default_timeout_seconds` | `int` | `None` |  |
| `offline_start_policy` | `Literal['block']` | 'block' |  |
| `offline_running_policy` | `Literal['fail_in_studio']` | 'fail_in_studio' |  |
| `sync` | `V2JobSyncPolicy` | `None` |  |

### `contracts.V2JobSnapshot`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `agent_slug` | `str` | **required** |  |
| `mission_id` | `str` | **required** |  |
| `status` | `str` | **required** |  |
| `source` | `V2JobSource` | **required** |  |

### `contracts.V2JobSource`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `Literal['fresh_start', 'external']` | **required** |  |
| `external_ref` | `str` | `None` |  |
| `previous_job_id` | `str` | `None` |  |
| `target_type` | `str` | `None` |  |

### `contracts.V2JobStateSnapshot`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `job` | `V2JobSnapshot` | **required** |  |
| `cases` | `list[contracts.V2CaseSnapshot]` | — |  |

### `contracts.V2JobSyncPolicy`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `action` | `str` | 'job.sync' |  |
| `supported_statuses` | `list[str]` | — |  |

### `contracts.V2JobSyncResult`

**Inherits from:** [`contracts.V2ActionResult`](#contractsv2actionresult)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `external_ref` | `str` | `None` |  |
| `external_version` | `str` | `None` |  |
| `sync_cursor` | `str` | `None` |  |
| `observed_at` | `str` | `None` |  |
| `job_state` | `V2JobStateSnapshot` | `None` |  |

### `contracts.V2MountedResourceViewDefinition`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `view` | `str` | **required** |  |
| `surface` | `str` | **required** |  |

### `contracts.V2ProtocolVersions`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `a2ui_version` | `str` | **required** |  |
| `a2ui_catalog_version` | `str` | **required** |  |
| `a2a_version` | `str` | **required** |  |
| `ag_ui_version` | `str` | `None` |  |

### `contracts.V2ReplaySafetyMetadata`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `dedupe_keys` | `list[str]` | — |  |
| `stable_external_ids_required` | `bool` | True |  |
| `strictly_idempotent_response` | `bool` | False |  |
| `convergent` | `bool` | True |  |

### `contracts.V2ResourceDefinition`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `label` | `str` | **required** |  |
| `auto_surface` | `bool` | False |  |
| `operations` | `list[str]` | — |  |
| `display` | `V2ResourceDisplayDefinition` | `None` |  |
| `fields` | `list[contracts.V2ResourceFieldDefinition]` | — |  |
| `mounted_views` | `list[contracts.V2MountedResourceViewDefinition]` | — |  |

### `contracts.V2ResourceDisplayDefinition`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `title_field` | `str` | `None` |  |
| `columns` | `list[str]` | — |  |
| `search_fields` | `list[str]` | — |  |

### `contracts.V2ResourceFieldDefinition`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `label` | `str` | **required** |  |
| `type` | `str` | 'string' |  |
| `required` | `bool` | False |  |
| `read_only` | `bool` | False |  |
| `multiline` | `bool` | False |  |
| `options_source` | `V2ResourceFieldOptionsSource` | `None` |  |

### `contracts.V2ResourceFieldOptionsSource`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `Literal['resource']` | 'resource' |  |
| `resource` | `str` | **required** |  |
| `value_field` | `str` | 'id' |  |
| `label_field` | `str` | `None` |  |

### `contracts.V2StepSnapshot`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `activity` | `Literal['operation', 'delegation']` | **required** |  |
| `status` | `str` | **required** |  |
| `title` | `str` | `None` |  |
| `external_id` | `str` | `None` |  |
| `awaiting` | `V2AwaitingState` | `None` |  |
| `outputs` | `list[contracts.V2ArtifactRef]` | — |  |

### `contracts.V2SurfaceRequest`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `request_id` | `str` | **required** |  |
| `actor` | `V2ActorContext` | **required** |  |
| `workspace` | `V2WorkspaceContext` | **required** |  |
| `mission_id` | `str` | **required** |  |
| `agent_slug` | `str` | **required** |  |
| `surface` | `str` | **required** |  |
| `input` | `dict[str, Any]` | — |  |
| `draft_session_id` | `str` | `None` |  |
| `job_id` | `str` | `None` |  |
| `case_id` | `str` | `None` |  |
| `step_id` | `str` | `None` |  |

### `contracts.V2SurfaceResult`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `surface` | `str` | **required** |  |
| `a2ui_version` | `str` | `None` |  |
| `a2ui_catalog_version` | `str` | `None` |  |
| `document` | `dict[str, Any]` | — |  |

### `contracts.V2WorkspaceContext`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `slug` | `str` | `None` |  |

### `data_resource.DataResourceContext`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

Studio request context passed to DataResource callbacks.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `workspace_id` | `str` | `None` |  |
| `workspace_slug` | `str` | `None` |  |
| `mission_id` | `str` | `None` |  |
| `agent_slug` | `str` | **required** |  |
| `request_id` | `str` | `None` |  |

### `data_resource.DataResourceField`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

Describes a single field in a DataResource for Studio rendering.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | Column/attribute name |
| `field_type` | `<enum 'FieldType'>` | `string` | One of: string, integer, boolean, date, datetime, text, email, url |
| `label` | `str` | `None` | Human-readable label; defaults to name.title() |
| `required` | `bool` | False | Required on create form |
| `editable` | `<enum 'Editable'>` | `always` |  |
| `visible_on` | `list[str]` | — | Views that render this field: list, detail, create, edit |
| `description` | `str` | `None` | Help text shown in Studio |
| `related_resource` | `str` | `None` | Name of another DataResource this field FK-references |
| `sensitive` | `bool` | False | True when Studio should mask this field for non-manager users |

### `deploy.drivers.base.DeploymentPlan`

Deployment plan containing all actions to be taken.

| Field | Type | Default | Description |
|---|---|---|---|
| `platform` | `str` | **required** |  |
| `service_name` | `str` | **required** |  |
| `environment` | `str` | **required** |  |
| `region` | `str` | **required** |  |
| `project_id` | `str` | `None` |  |
| `actions` | `List[deploy.drivers.base.ResourceAction]` | [] |  |
| `total_cost_estimate` | `str` | `None` |  |
| `estimated_duration` | `str` | `None` |  |
| `current_image` | `str` | `None` |  |
| `current_url` | `str` | `None` |  |
| `current_status` | `str` | `None` |  |
| `target_image` | `str` | **required** |  |
| `target_port` | `int` | 8000 |  |
| `target_env_vars` | `Dict[str, str]` | {} |  |
| `target_secrets` | `Dict[str, str]` | {} |  |

### `deploy.drivers.base.DeploymentResult`

Result of a deployment operation.

| Field | Type | Default | Description |
|---|---|---|---|
| `success` | `bool` | **required** |  |
| `service_url` | `str` | `None` |  |
| `service_id` | `str` | `None` |  |
| `revision` | `str` | `None` |  |
| `image_digest` | `str` | `None` |  |
| `status` | `str` | 'unknown' |  |
| `health_status` | `str` | 'unknown' |  |
| `deployment_time` | `float` | `None` |  |
| `error_message` | `str` | `None` |  |
| `error_details` | `typing.Dict[str, typing.Any]` | `None` |  |

### `deploy.state.DeploymentState`

Deployment state model.

| Field | Type | Default | Description |
|---|---|---|---|
| `version` | `int` | 2 | State file format version |
| `service_name` | `str` | **required** | Name of the deployed service |
| `platform` | `str` | **required** | Target platform (cloud-run|aws-app-runner|do-app-platform) |
| `environment` | `str` | **required** | Environment (dev|staging|prod) |
| `region` | `str` | **required** | Provider region |
| `project_id` | `str` | `None` | GCP project / AWS account / DO project |
| `image_tag` | `str` | **required** | Docker image tag |
| `image_digest` | `str` | `None` | Docker image digest |
| `service_url` | `str` | `None` | Public service URL |
| `revision` | `str` | `None` | Service revision/version |
| `created_at` | `datetime` | — | Deployment creation time |
| `updated_at` | `datetime` | — | Last update time |
| `status` | `str` | 'unknown' | Deployment status |
| `health_status` | `str` | 'unknown' | Health check status |
| `port` | `int` | 8000 | Application port |
| `api_key_generated` | `bool` | False | Whether API key was generated |
| `rsa_key_generated` | `bool` | False | Whether RSA key was generated |
| `provider_data` | `Dict[str, Any]` | — | Platform-specific data |

### `deploy.drivers.base.ResourceAction`

Represents an action to be taken on a resource.

| Field | Type | Default | Description |
|---|---|---|---|
| `resource_type` | `<enum 'ResourceType'>` | **required** |  |
| `action_type` | `<enum 'ActionType'>` | **required** |  |
| `resource_name` | `str` | **required** |  |
| `description` | `str` | **required** |  |
| `cost_estimate` | `str` | `None` |  |
| `metadata` | `typing.Dict[str, typing.Any]` | `None` |  |

### `deploy.health.HealthCheckConfig`

Configuration for health check operations.

| Field | Type | Default | Description |
|---|---|---|---|
| `timeout` | `int` | 60 |  |
| `max_retries` | `int` | 5 |  |
| `base_delay` | `float` | 1.0 |  |
| `max_delay` | `float` | 30.0 |  |
| `backoff_multiplier` | `float` | 2.0 |  |
| `success_threshold` | `int` | 1 |  |
| `endpoints` | `typing.List[str]` | `None` |  |

### `deploy.health.HealthCheckResult`

Result of a health check operation.

| Field | Type | Default | Description |
|---|---|---|---|
| `status` | `<enum 'HealthStatus'>` | **required** |  |
| `response_time` | `float` | **required** |  |
| `status_code` | `int` | `None` |  |
| `error_message` | `str` | `None` |  |
| `endpoint` | `str` | `None` |  |
| `timestamp` | `float` | 0.0 |  |

### `event.AbstractEvent`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict[str, Any]` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `<enum 'EventType'>` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict[str, Any]` | **required** |  |

### `event.AgentRegisterEvent`

**Inherits from:** [`event.Event`](#eventevent)

Event sent when an agent registers with the control system.

Test in tests/test_agent_register_event.py

_No additional fields beyond parent class._

### `event.CaseStartEvent`

**Inherits from:** [`event.Event`](#eventevent)

_No additional fields beyond parent class._

### `event.CaseUpdateEvent`

**Inherits from:** [`event.Event`](#eventevent)

_No additional fields beyond parent class._

### `event.Event`

**Inherits from:** [`event.AbstractEvent`](#eventabstractevent)

Base class for all events in the Supervaize Control system.

Events represent messages sent from agents to the control system to communicate
status, anomalies, deliverables and other information.

Inherits from AbstractEvent which defines the core event attributes:
    - source: The source/origin of the event (e.g. agent/server URI)
    - type: The EventType enum indicating the event category
    - account: The account that the event belongs to
    - details: A dictionary containing event-specific details

Tests in tests/test_event.py

_No additional fields beyond parent class._

### `event.JobFinishedEvent`

**Inherits from:** [`event.Event`](#eventevent)

_No additional fields beyond parent class._

### `event.ServerRegisterEvent`

**Inherits from:** [`event.Event`](#eventevent)

_No additional fields beyond parent class._

### `job.AbstractJob`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `name` | `str` | **required** |  |
| `agent_name` | `str` | **required** |  |
| `status` | `<enum 'EntityStatus'>` | **required** |  |
| `job_context` | `JobContext` | **required** |  |
| `payload` | `Any` | `None` |  |
| `result` | `Any` | `None` |  |
| `error` | `str` | `None` |  |
| `responses` | `list[job.JobResponse]` | [] |  |
| `finished_at` | `datetime` | `None` |  |
| `created_at` | `datetime` | `None` |  |
| `agent_parameters` | `list[dict[str, typing.Any]]` | `None` |  |
| `case_ids` | `list[str]` | [] |  |
| `metadata` | `dict[str, Any]` | — | Agent-provided domain metadata (e.g. campaign context) |

### `job.JobInstructions`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `max_cases` | `int` | `None` |  |
| `max_duration` | `int` | `None` |  |
| `max_cost` | `float` | `None` |  |
| `stop_on_warning` | `bool` | False |  |
| `stop_on_error` | `bool` | True |  |
| `job_start_time` | `float` | `None` |  |

### `protocol.a2a.controller.JsonRpcError`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `code` | `int` | **required** |  |
| `message` | `str` | **required** |  |
| `data` | `dict[str, typing.Any]` | `None` |  |

### `protocol.a2a.controller.JsonRpcRequest`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `jsonrpc` | `Literal['2.0']` | '2.0' |  |
| `id` | `str` \| `int` | `None` |  |
| `method` | `str` | **required** |  |
| `params` | `dict[str, Any]` | — |  |

### `protocol.a2a.controller.JsonRpcResponse`

**Inherits from:** [`contracts.ContractModel`](#contractscontractmodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `jsonrpc` | `Literal['2.0']` | '2.0' |  |
| `id` | `str` \| `int` | `None` |  |
| `result` | `dict[str, typing.Any]` | `None` |  |
| `error` | `JsonRpcError` | `None` |  |

### `routes.CaseUpdateRequest`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

Request model for updating a case with answer to a question.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `answer` | `dict[str, Any]` | **required** |  |
| `message` | `str` | `None` |  |

### `server_utils.ErrorResponse`

Standard error response model

| Field | Type | Default | Description |
|---|---|---|---|
| `error` | `str` | **required** |  |
| `error_type` | `<enum 'ErrorType'>` | **required** |  |
| `detail` | `str` | `None` |  |
| `timestamp` | `datetime` | datetime.datetime(2026, 5, 15, 20, 25, 31, 892520) |  |
| `status_code` | `int` | **required** |  |

### `routes.RegistrationRefreshRequest`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

Request model for re-sending the server registration event.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `reason` | `str` | `None` |  |
| `requested_at` | `str` | `None` |  |

### `server.ServerInfo`

Complete server information for storage.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | 'server_instance' |  |
| `host` | `str` | **required** |  |
| `port` | `int` | **required** |  |
| `api_version` | `str` | **required** |  |
| `environment` | `str` | **required** |  |
| `agents` | `List[Dict[str, str]]` | **required** |  |
| `start_time` | `float` | **required** |  |
| `created_at` | `str` | **required** |  |
| `updated_at` | `str` | **required** |  |

### `telemetry.TelemetryModel`

A base class for creating Pydantic models.

| Field | Type | Default | Description |
|---|---|---|---|
| `agentId` | `str` | **required** |  |
| `type` | `<enum 'TelemetryType'>` | **required** |  |
| `category` | `<enum 'TelemetryCategory'>` | **required** |  |
| `severity` | `<enum 'TelemetrySeverity'>` | **required** |  |
| `details` | `Dict[str, Any]` | **required** |  |


*Uploaded on 2026-05-15 20:25:31*