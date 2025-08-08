# Model Reference

**Version:** 0.9.4

## `account.Account`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `workspace_id` | `str` | **required** |  |
| `api_key` | `str` | **required** |  |
| `api_url` | `str` | **required** |  |

## `account.AccountModel`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `workspace_id` | `str` | **required** |  |
| `api_key` | `str` | **required** |  |
| `api_url` | `str` | **required** |  |

## `common.SvBaseModel`

Base model for all Supervaize models.

_No fields found._

## `telemetry.Telemetry`

Base class for all telemetry data in the Supervaize Control system.

Telemetry represents monitoring and observability data sent from agents to the control system.
This includes logs, metrics, events, traces, exceptions, diagnostics and custom telemetry.

Inherits from TelemetryModel which defines the core telemetry attributes:
    - agentId: The ID of the agent sending the telemetry
    - type: The TelemetryType enum indicating the telemetry category (logs, metrics, etc)
    - category: The TelemetryCategory enum for the functional area (system, application, etc)
    - severity: The TelemetrySeverity enum indicating importance (debug, info, warning, etc)
    - details: A dictionary containing telemetry-specific details

| Field | Type | Default | Description |
|---|---|---|---|
| `agentId` | `str` | **required** |  |
| `type` | `TelemetryType` | **required** |  |
| `category` | `TelemetryCategory` | **required** |  |
| `severity` | `TelemetrySeverity` | **required** |  |
| `details` | `Dict` | **required** |  |

## `agent.AbstractAgent`

Agent model for the Supervaize Control API.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `id` | `str` | **required** |  |
| `author` | `str` | `None` | — |  |
| `developer` | `str` | `None` | — |  |
| `maintainer` | `str` | `None` | — |  |
| `editor` | `str` | `None` | — |  |
| `version` | `str` | **required** |  |
| `description` | `str` | **required** |  |
| `tags` | `list[str]` | `None` | — |  |
| `methods` | `AgentMethods` | `None` | — |  |
| `parameters_setup` | `ParametersSetup` | `None` | — |  |
| `server_agent_id` | `str` | `None` | — |  |
| `server_agent_status` | `str` | `None` | — |  |
| `server_agent_onboarding_status` | `str` | `None` | — |  |
| `server_encrypted_parameters` | `str` | `None` | — |  |
| `max_execution_time` | `int` | **required** |  |

## `agent.Agent`

Agent model for the Supervaize Control API.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `id` | `str` | **required** |  |
| `author` | `str` | `None` | — |  |
| `developer` | `str` | `None` | — |  |
| `maintainer` | `str` | `None` | — |  |
| `editor` | `str` | `None` | — |  |
| `version` | `str` | **required** |  |
| `description` | `str` | **required** |  |
| `tags` | `list[str]` | `None` | — |  |
| `methods` | `AgentMethods` | `None` | — |  |
| `parameters_setup` | `ParametersSetup` | `None` | — |  |
| `server_agent_id` | `str` | `None` | — |  |
| `server_agent_status` | `str` | `None` | — |  |
| `server_agent_onboarding_status` | `str` | `None` | — |  |
| `server_encrypted_parameters` | `str` | `None` | — |  |
| `max_execution_time` | `int` | **required** |  |

## `agent.AgentCustomMethodParams`

Method parameters for agent operations.

| Field | Type | Default | Description |
|---|---|---|---|
| `params` | `Dict` | — | A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs |
| `method_name` | `str` | **required** |  |

## `agent.AgentJobContextBase`

Base model for agent job context parameters

| Field | Type | Default | Description |
|---|---|---|---|
| `job_context` | `JobContext` | **required** |  |
| `job_fields` | `Dict` | **required** |  |

## `agent.AgentMethod`

Represents a method that can be called on an agent.

Attributes:
    name: Display name of the method
    method: Name of the actual method in the project's codebase that will be called with the provided parameters
    params: see below
    fields: see below
    description: Optional description of what the method does


1. params : Dictionary format
   A simple key-value dictionary of parameters what will be passed to the
   AgentMethod.method as kwargs.
   Example:

```json
{
  "verbose": true,
  "timeout": 60,
  "max_retries": 3
}
```


2. fields : Form fields format
   These are the values that will be requested from the user in the Supervaize UI
   and also passed as kwargs to the AgentMethod.method.
   A list of field specifications for generating forms/UI, following the
   django.forms.fields definition
   see : https://docs.djangoproject.com/en/5.1/ref/forms/fields/
   Each field is a dictionary with properties like:
   - name: Field identifier
   - type: Python type of the field for pydantic validation - note , ChoiceField and MultipleChoiceField are a list[str]
   - field_type: Field type (one of: CharField, IntegerField, BooleanField, ChoiceField, MultipleChoiceField)
   - choices: For choice fields, list of [value, label] pairs
   - default: (optional) Default value for the field
   - widget: UI widget to use (e.g. RadioSelect, TextInput)
   - required: Whether field is required


   Example:

```json
   [
       {
            "name": "color",
            "type": list[str],
            "field_type": "MultipleChoiceField",
            "choices": [["B", "Blue"], ["R", "Red"], ["G", "Green"]],
            "widget": "RadioSelect",
            "required": True,
        },
        {
            "name": "age",
            "type": int,
            "field_type": "IntegerField",
            "widget": "NumberInput",
            "required": False,
        },
   ]
```


| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | The name of the method |
| `method` | `str` | **required** | The name of the method in the project's codebase that will be called with the provided parameters |
| `params` | `typing.Dict[str, typing.Any]` | `None` | — | A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs |
| `fields` | `typing.List[supervaizer.agent.AgentMethodField]` | `None` | — | A list of field specifications for generating forms/UI, following the django.forms.fields definition |
| `description` | `str` | `None` | — | Optional description of what the method does |
| `is_async` | `bool` | False | Whether the method is asynchronous |

## `agent.AgentMethodField`

A base class for creating Pydantic models.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | The name of the field |
| `type` | `Any` | **required** | The type of the field - as a python type |
| `field_type` | `FieldTypeEnum` | `CharField` | The type of field for UI rendering |
| `description` | `str` | `None` | **required** | The description of the field |
| `choices` | `list[str]` | `None` | **required** | For choice fields, list of [value, label] pairs |
| `default` | `Any` | **required** | Default value for the field |
| `widget` | `str` | `None` | **required** | UI widget to use (e.g. RadioSelect, TextInput) - as a django widget name |
| `required` | `bool` | **required** | Whether field is required |

## `agent.AgentMethodModel`

Represents a method that can be called on an agent.

Attributes:
    name: Display name of the method
    method: Name of the actual method in the project's codebase that will be called with the provided parameters
    params: see below
    fields: see below
    description: Optional description of what the method does


1. params : Dictionary format
   A simple key-value dictionary of parameters what will be passed to the
   AgentMethod.method as kwargs.
   Example:

```json
{
  "verbose": true,
  "timeout": 60,
  "max_retries": 3
}
```


2. fields : Form fields format
   These are the values that will be requested from the user in the Supervaize UI
   and also passed as kwargs to the AgentMethod.method.
   A list of field specifications for generating forms/UI, following the
   django.forms.fields definition
   see : https://docs.djangoproject.com/en/5.1/ref/forms/fields/
   Each field is a dictionary with properties like:
   - name: Field identifier
   - type: Python type of the field for pydantic validation - note , ChoiceField and MultipleChoiceField are a list[str]
   - field_type: Field type (one of: CharField, IntegerField, BooleanField, ChoiceField, MultipleChoiceField)
   - choices: For choice fields, list of [value, label] pairs
   - default: (optional) Default value for the field
   - widget: UI widget to use (e.g. RadioSelect, TextInput)
   - required: Whether field is required


   Example:

```json
   [
       {
            "name": "color",
            "type": list[str],
            "field_type": "MultipleChoiceField",
            "choices": [["B", "Blue"], ["R", "Red"], ["G", "Green"]],
            "widget": "RadioSelect",
            "required": True,
        },
        {
            "name": "age",
            "type": int,
            "field_type": "IntegerField",
            "widget": "NumberInput",
            "required": False,
        },
   ]
```


| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | The name of the method |
| `method` | `str` | **required** | The name of the method in the project's codebase that will be called with the provided parameters |
| `params` | `typing.Dict[str, typing.Any]` | `None` | — | A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs |
| `fields` | `typing.List[supervaizer.agent.AgentMethodField]` | `None` | — | A list of field specifications for generating forms/UI, following the django.forms.fields definition |
| `description` | `str` | `None` | — | Optional description of what the method does |
| `is_async` | `bool` | False | Whether the method is asynchronous |

## `agent.AgentMethodParams`

Method parameters for agent operations.

| Field | Type | Default | Description |
|---|---|---|---|
| `params` | `Dict` | — | A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs |

## `agent.AgentMethods`

A base class for creating Pydantic models.

| Field | Type | Default | Description |
|---|---|---|---|
| `job_start` | `AgentMethod` | **required** |  |
| `job_stop` | `AgentMethod` | **required** |  |
| `job_status` | `AgentMethod` | **required** |  |
| `chat` | `AgentMethod` | `None` | — |  |
| `custom` | `dict[str, supervaizer.agent.AgentMethod]` | `None` | — |  |

## `agent.AgentMethodsModel`

A base class for creating Pydantic models.

| Field | Type | Default | Description |
|---|---|---|---|
| `job_start` | `AgentMethod` | **required** |  |
| `job_stop` | `AgentMethod` | **required** |  |
| `job_status` | `AgentMethod` | **required** |  |
| `chat` | `AgentMethod` | `None` | — |  |
| `custom` | `dict[str, supervaizer.agent.AgentMethod]` | `None` | — |  |

## `agent.AgentResponse`

Response model for agent endpoints - values provided by Agent.registration_info

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `id` | `str` | **required** |  |
| `author` | `str` | `None` | — |  |
| `developer` | `str` | `None` | — |  |
| `maintainer` | `str` | `None` | — |  |
| `editor` | `str` | `None` | — |  |
| `version` | `str` | **required** |  |
| `api_path` | `str` | **required** |  |
| `description` | `str` | **required** |  |
| `tags` | `list[str]` | `None` | — |  |
| `methods` | `AgentMethods` | `None` | — |  |
| `parameters_setup` | `typing.List[typing.Dict[str, typing.Any]]` | `None` | — |  |
| `server_agent_id` | `str` | `None` | — |  |
| `server_agent_status` | `str` | `None` | — |  |
| `server_agent_onboarding_status` | `str` | `None` | — |  |
| `server_encrypted_parameters` | `str` | `None` | — |  |

## `job.Job`

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

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `name` | `str` | **required** |  |
| `agent_name` | `str` | **required** |  |
| `status` | `EntityStatus` | **required** |  |
| `job_context` | `JobContext` | **required** |  |
| `payload` | `Any` | `None` | — |  |
| `result` | `Any` | `None` | — |  |
| `error` | `str` | `None` | — |  |
| `responses` | `list` | [] |  |
| `finished_at` | `datetime` | `None` | — |  |
| `created_at` | `datetime` | `None` | — |  |
| `agent_parameters` | `typing.List[dict[str, typing.Any]]` | `None` | — |  |
| `case_ids` | `List` | [] |  |

## `job.JobContext`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `workspace_id` | `str` | **required** |  |
| `job_id` | `str` | **required** |  |
| `started_by` | `str` | **required** |  |
| `started_at` | `datetime` | **required** |  |
| `mission_id` | `str` | **required** |  |
| `mission_name` | `str` | **required** |  |
| `mission_context` | `Any` | — |  |
| `job_instructions` | `JobInstructions` | `None` | — |  |

## `job.JobResponse`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `job_id` | `str` | **required** |  |
| `status` | `EntityStatus` | **required** |  |
| `message` | `str` | **required** |  |
| `payload` | `dict[str, typing.Any]` | `None` | — |  |
| `error_message` | `str` | `None` | — |  |
| `error_traceback` | `str` | `None` | — |  |

## `event.JobStartConfirmationEvent`

Base class for all events in the Supervaize Control system.

Events represent messages sent from agents to the control system to communicate
status, anomalies, deliverables and other information.

Inherits from AbstractEvent which defines the core event attributes:
    - source: The source/origin of the event (e.g. agent/server URI)
    - type: The EventType enum indicating the event category
    - account: The account that the event belongs to
    - details: A dictionary containing event-specific details

Tests in tests/test_event.py

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `EventType` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict` | **required** |  |

## `parameter.ParametersSetup`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `definitions` | `Dict` | **required** |  |

## `case.Case`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `job_id` | `str` | **required** |  |
| `name` | `str` | **required** |  |
| `account` | `Account` | **required** |  |
| `description` | `str` | **required** |  |
| `status` | `EntityStatus` | **required** |  |
| `updates` | `List` | [] |  |
| `total_cost` | `float` | 0.0 |  |
| `final_delivery` | `typing.Dict[str, typing.Any]` | `None` | — |  |
| `finished_at` | `datetime` | `None` | — |  |

## `case.CaseAbstractModel`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `job_id` | `str` | **required** |  |
| `name` | `str` | **required** |  |
| `account` | `ForwardRef('Account')` | **required** |  |
| `description` | `str` | **required** |  |
| `status` | `EntityStatus` | **required** |  |
| `updates` | `List` | [] |  |
| `total_cost` | `float` | 0.0 |  |
| `final_delivery` | `typing.Dict[str, typing.Any]` | `None` | — |  |
| `finished_at` | `datetime` | `None` | — |  |

## `case.CaseNode`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** |  |
| `description` | `str` | **required** |  |
| `type` | `CaseNoteType` | **required** |  |

## `case.CaseNodeUpdate`

CaseNodeUpdate is a class that represents an update to a case node.


Returns:
    CaseNodeUpdate: CaseNodeUpdate object

| Field | Type | Default | Description |
|---|---|---|---|
| `index` | `int` | `None` | — |  |
| `cost` | `float` | `None` | — |  |
| `name` | `str` | `None` | — |  |
| `payload` | `typing.Dict[str, typing.Any]` | `None` | — |  |
| `is_final` | `bool` | False |  |
| `error` | `str` | `None` | — |  |

## `event.AbstractEvent`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `EventType` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict` | **required** |  |

## `event.AgentRegisterEvent`

Event sent when an agent registers with the control system.

Test in tests/test_agent_register_event.py

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `EventType` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict` | **required** |  |

## `event.CaseStartEvent`

Base class for all events in the Supervaize Control system.

Events represent messages sent from agents to the control system to communicate
status, anomalies, deliverables and other information.

Inherits from AbstractEvent which defines the core event attributes:
    - source: The source/origin of the event (e.g. agent/server URI)
    - type: The EventType enum indicating the event category
    - account: The account that the event belongs to
    - details: A dictionary containing event-specific details

Tests in tests/test_event.py

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `EventType` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict` | **required** |  |

## `event.CaseUpdateEvent`

Base class for all events in the Supervaize Control system.

Events represent messages sent from agents to the control system to communicate
status, anomalies, deliverables and other information.

Inherits from AbstractEvent which defines the core event attributes:
    - source: The source/origin of the event (e.g. agent/server URI)
    - type: The EventType enum indicating the event category
    - account: The account that the event belongs to
    - details: A dictionary containing event-specific details

Tests in tests/test_event.py

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `EventType` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict` | **required** |  |

## `event.Event`

Base class for all events in the Supervaize Control system.

Events represent messages sent from agents to the control system to communicate
status, anomalies, deliverables and other information.

Inherits from AbstractEvent which defines the core event attributes:
    - source: The source/origin of the event (e.g. agent/server URI)
    - type: The EventType enum indicating the event category
    - account: The account that the event belongs to
    - details: A dictionary containing event-specific details

Tests in tests/test_event.py

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `EventType` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict` | **required** |  |

## `event.JobFinishedEvent`

Base class for all events in the Supervaize Control system.

Events represent messages sent from agents to the control system to communicate
status, anomalies, deliverables and other information.

Inherits from AbstractEvent which defines the core event attributes:
    - source: The source/origin of the event (e.g. agent/server URI)
    - type: The EventType enum indicating the event category
    - account: The account that the event belongs to
    - details: A dictionary containing event-specific details

Tests in tests/test_event.py

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `EventType` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict` | **required** |  |

## `event.ServerRegisterEvent`

Base class for all events in the Supervaize Control system.

Events represent messages sent from agents to the control system to communicate
status, anomalies, deliverables and other information.

Inherits from AbstractEvent which defines the core event attributes:
    - source: The source/origin of the event (e.g. agent/server URI)
    - type: The EventType enum indicating the event category
    - account: The account that the event belongs to
    - details: A dictionary containing event-specific details

Tests in tests/test_event.py

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | `Dict` | **required** |  |
| `account` | `Any` | **required** |  |
| `type` | `EventType` | **required** |  |
| `object_type` | `str` | **required** |  |
| `details` | `Dict` | **required** |  |

## `job.AbstractJob`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | **required** |  |
| `name` | `str` | **required** |  |
| `agent_name` | `str` | **required** |  |
| `status` | `EntityStatus` | **required** |  |
| `job_context` | `JobContext` | **required** |  |
| `payload` | `Any` | `None` | — |  |
| `result` | `Any` | `None` | — |  |
| `error` | `str` | `None` | — |  |
| `responses` | `list` | [] |  |
| `finished_at` | `datetime` | `None` | — |  |
| `created_at` | `datetime` | `None` | — |  |
| `agent_parameters` | `typing.List[dict[str, typing.Any]]` | `None` | — |  |
| `case_ids` | `List` | [] |  |

## `job.JobInstructions`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `max_cases` | `int` | `None` | — |  |
| `max_duration` | `int` | `None` | — |  |
| `max_cost` | `float` | `None` | — |  |
| `stop_on_warning` | `bool` | False |  |
| `stop_on_error` | `bool` | True |  |
| `job_start_time` | `float` | `None` | — |  |

## `parameter.Parameter`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | The name of the parameter, as used in the agent code |
| `description` | `str` | `None` | — | The description of the parameter, used in the Supervaize UI |
| `is_environment` | `bool` | False | Whether the parameter is set as an environment variable |
| `value` | `str` | `None` | — | The value of the parameter - provided by the Supervaize platform |
| `is_secret` | `bool` | False | Whether the parameter is a secret - hidden from the user in the Supervaize UI |
| `is_required` | `bool` | False | Whether the parameter is required, used in the Supervaize UI |

## `parameter.ParameterModel`

Base model for all Supervaize models.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | **required** | The name of the parameter, as used in the agent code |
| `description` | `str` | `None` | — | The description of the parameter, used in the Supervaize UI |
| `is_environment` | `bool` | False | Whether the parameter is set as an environment variable |
| `value` | `str` | `None` | — | The value of the parameter - provided by the Supervaize platform |
| `is_secret` | `bool` | False | Whether the parameter is a secret - hidden from the user in the Supervaize UI |
| `is_required` | `bool` | False | Whether the parameter is required, used in the Supervaize UI |

## `routes.CaseUpdateRequest`

Request model for updating a case with answer to a question.

| Field | Type | Default | Description |
|---|---|---|---|
| `answer` | `Dict` | **required** |  |
| `message` | `str` | `None` | — |  |

## `server_utils.ErrorResponse`

Standard error response model

| Field | Type | Default | Description |
|---|---|---|---|
| `error` | `str` | **required** |  |
| `error_type` | `ErrorType` | **required** |  |
| `detail` | `str` | `None` | — |  |
| `timestamp` | `datetime` | datetime.datetime(2025, 8, 9, 1, 50, 39, 848642) |  |
| `status_code` | `int` | **required** |  |

## `server.AbstractServer`

API Server for the Supervaize Controller.

| Field | Type | Default | Description |
|---|---|---|---|
| `scheme` | `str` | **required** |  |
| `host` | `str` | **required** |  |
| `port` | `int` | **required** |  |
| `environment` | `str` | **required** |  |
| `mac_addr` | `str` | **required** |  |
| `debug` | `bool` | **required** |  |
| `agents` | `List` | **required** |  |
| `app` | `FastAPI` | **required** |  |
| `reload` | `bool` | **required** |  |
| `supervisor_account` | `Account` | `None` | — |  |
| `a2a_endpoints` | `bool` | True |  |
| `acp_endpoints` | `bool` | True |  |
| `private_key` | `RSAPrivateKey` | **required** |  |
| `public_key` | `RSAPublicKey` | **required** |  |
| `registration_host` | `str` | `None` | — |  |
| `api_key` | `str` | `None` | — |  |
| `api_key_header` | `APIKeyHeader` | `None` | — |  |

## `server.Server`

API Server for the Supervaize Controller.

| Field | Type | Default | Description |
|---|---|---|---|
| `scheme` | `str` | **required** |  |
| `host` | `str` | **required** |  |
| `port` | `int` | **required** |  |
| `environment` | `str` | **required** |  |
| `mac_addr` | `str` | **required** |  |
| `debug` | `bool` | **required** |  |
| `agents` | `List` | **required** |  |
| `app` | `FastAPI` | **required** |  |
| `reload` | `bool` | **required** |  |
| `supervisor_account` | `Account` | `None` | — |  |
| `a2a_endpoints` | `bool` | True |  |
| `acp_endpoints` | `bool` | True |  |
| `private_key` | `RSAPrivateKey` | **required** |  |
| `public_key` | `RSAPublicKey` | **required** |  |
| `registration_host` | `str` | `None` | — |  |
| `api_key` | `str` | `None` | — |  |
| `api_key_header` | `APIKeyHeader` | `None` | — |  |

## `server.ServerInfo`

Complete server information for storage.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | 'server_instance' |  |
| `host` | `str` | **required** |  |
| `port` | `int` | **required** |  |
| `api_version` | `str` | **required** |  |
| `environment` | `str` | **required** |  |
| `agents` | `List` | **required** |  |
| `start_time` | `float` | **required** |  |
| `created_at` | `str` | **required** |  |
| `updated_at` | `str` | **required** |  |

## `telemetry.TelemetryModel`

A base class for creating Pydantic models.

| Field | Type | Default | Description |
|---|---|---|---|
| `agentId` | `str` | **required** |  |
| `type` | `TelemetryType` | **required** |  |
| `category` | `TelemetryCategory` | **required** |  |
| `severity` | `TelemetrySeverity` | **required** |  |
| `details` | `Dict` | **required** |  |
