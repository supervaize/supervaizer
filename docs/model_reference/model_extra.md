# Model Reference extra

**Version:** 0.9.7

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
| `job_stop` | `AgentMethod` | **required** |  |
| `job_status` | `AgentMethod` | **required** |  |
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
| `api_path` | `str` | **required** |  |
| `description` | `str` | **required** |  |
| `tags` | `list[str]` | `None` |  |
| `methods` | `AgentMethods` | `None` |  |
| `parameters_setup` | `typing.List[typing.Dict[str, typing.Any]]` | `None` |  |
| `server_agent_id` | `str` | `None` |  |
| `server_agent_status` | `str` | `None` |  |
| `server_agent_onboarding_status` | `str` | `None` |  |
| `server_encrypted_parameters` | `str` | `None` |  |

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

### `case.CaseNode`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `description` | `str` | **required** |  |
| `type` | `<enum 'CaseNoteType'>` | **required** |  |

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
| `error` | `str` | `None` |  |

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
| `agent_parameters` | `typing.List[dict[str, typing.Any]]` | `None` |  |
| `case_ids` | `List[str]` | [] |  |

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

### `routes.CaseUpdateRequest`

**Inherits from:** [`common.SvBaseModel`](#commonsvbasemodel)

Request model for updating a case with answer to a question.

#### Model Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `answer` | `Dict[str, Any]` | **required** |  |
| `message` | `str` | `None` |  |

### `server_utils.ErrorResponse`

Standard error response model

| Field | Type | Default | Description |
|---|---|---|---|
| `error` | `str` | **required** |  |
| `error_type` | `<enum 'ErrorType'>` | **required** |  |
| `detail` | `str` | `None` |  |
| `timestamp` | `datetime` | datetime.datetime(2025, 8, 11, 2, 52, 31, 774531) |  |
| `status_code` | `int` | **required** |  |

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


*Uploaded on 2025-08-11 02:52:31*