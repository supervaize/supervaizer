# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import json
import re
from enum import Enum
from importlib import import_module
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    TypeVar,
    cast,
)

import shortuuid
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)
from slugify import slugify

from supervaizer.__version__ import VERSION
from supervaizer.case import CaseNodes
from supervaizer.common import ApiSuccess, SvBaseModel, log
from supervaizer.contracts import (
    BillingCatalogItem,
    SupervaizerV2AgentRegistrationContract,
    V2ActionDefinition,
    V2ActionRequest,
    V2AgentFullDescription,
    V2AgentIntroduction,
    V2AgentMethod,
    V2AgentMethods,
    validate_billing_catalog,
)
from supervaizer.data_resource import DataResource
from supervaizer.event import JobStartConfirmationEvent
from supervaizer.job import Job, JobContext, JobResponse
from supervaizer.job_service import service_job_finished
from supervaizer.lifecycle import EntityStatus
from supervaizer.parameter import ParametersSetup

if TYPE_CHECKING:
    from supervaizer.server import Server

T = TypeVar("T")
BLOCKED_AGENT_METHOD_MODULE_ROOTS = frozenset({
    "builtins",
    "importlib",
    "os",
    "pathlib",
    "shutil",
    "subprocess",
    "sys",
})


def _agent_detail_from_server_response(detail: Any) -> dict[str, Any]:
    if not isinstance(detail, dict):
        raise ValueError(
            "Agent update from Studio failed: response body must be an object"
        )
    nested_detail = detail.get("object") or detail.get("agent") or detail.get("data")
    if isinstance(nested_detail, dict):
        return nested_detail
    return detail


def _agent_id_from_server_detail(agent_detail: dict[str, Any]) -> str | None:
    value = agent_detail.get("id")
    if value is None:
        return None
    return str(value)


class FieldTypeEnum(str, Enum):
    CHAR = "CharField"
    INT = "IntegerField"
    BOOL = "BooleanField"
    CHOICE = "ChoiceField"
    MULTICHOICE = "MultipleChoiceField"
    DATE = "DateField"
    DATETIME = "DateTimeField"
    FLOAT = "FloatField"
    EMAIL = "EmailField"


class AgentMethodField(BaseModel):
    """
    Represents a field specification for generating forms/UI in the Supervaize platform.

    Fields are used to define user input parameters that will be collected through
    the UI and passed as kwargs to the AgentMethod.method. They follow Django forms
    field definitions for consistency.


    - [Django Widgets](https://docs.djangoproject.com/en/5.2/ref/forms/widgets/)


    ** field_type  - available field types ** [Django Field classes](https://docs.djangoproject.com/en/5.2/ref/forms/fields/#built-in-field-classes)

        - `CharField` - Text input
        - `IntegerField` - Number input
        - `BooleanField` - Checkbox
        - `ChoiceField` - Dropdown with options
        - `MultipleChoiceField` - Multi-select
        - `JSONField` - JSON data input

    """

    name: str = Field(description="The name of the field - displayed in the UI")
    type: Any = Field(
        description="Python type of the field for pydantic validation - note , ChoiceField and MultipleChoiceField are a list[str]"
    )
    field_type: FieldTypeEnum | str = Field(
        default=FieldTypeEnum.CHAR, description="Field type for persistence"
    )
    description: str | None = Field(
        default=None, description="Description of the field - displayed in the UI"
    )
    choices: list[tuple[str, str]] | list[str] | None = Field(
        default=None, description="For choice fields, list of [value, label] pairs"
    )

    default: Any = Field(
        default=None, description="Default value for the field - displayed in the UI"
    )
    widget: str | None = Field(
        default=None,
        description="UI widget to use (e.g. RadioSelect, TextInput) - as a django widget name",
    )
    required: bool = Field(
        default=False, description="Whether field is required for form submission"
    )

    @model_validator(mode="before")
    @classmethod
    def reject_dynamic_choices(cls, data: Any) -> Any:
        if isinstance(data, dict) and "dynamic_choices" in data:
            raise ValueError(
                "dynamic_choices was removed in Supervaizer v2. "
                "Use v2 resource option_sources or typed A2A actions for dynamic options."
            )
        return data

    model_config = cast(
        ConfigDict,
        {
            "reference_group": "Core",
            "json_schema_extra": {
                "examples": [
                    {
                        "name": "color",
                        "type": "list[str]",
                        "field_type": "MultipleChoiceField",
                        "choices": [["B", "Blue"], ["R", "Red"], ["G", "Green"]],
                        "widget": "RadioSelect",
                        "required": True,
                    },
                    {
                        "name": "age",
                        "type": "int",
                        "field_type": "IntegerField",
                        "widget": "NumberInput",
                        "required": False,
                    },
                ]
            },
        },
    )


class AgentJobContextBase(BaseModel):
    """
    Base model for agent job context parameters
    """

    job_context: JobContext
    job_fields: dict[str, Any]


class AgentMethodAbstract(BaseModel):
    """
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
       {
           "verbose": True,
           "timeout": 60,
           "max_retries": 3
       }

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



    """

    name: str = Field(description="The name of the method")
    method: str = Field(
        description="The name of the method in the project's codebase that will be called with the provided parameters"
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs",
    )
    fields: list[AgentMethodField] | None = Field(
        default=None,
        description="A list of field specifications for generating forms/UI, following the django.forms.fields definition",
    )

    description: str | None = Field(
        default=None, description="Optional description of what the method does"
    )
    is_async: bool = Field(
        default=False, description="Whether the method is asynchronous"
    )
    timeout: int | None = Field(
        default=600,
        description=(
            "Maximum automatic job duration in seconds. Use None for jobs that "
            "must run until Studio stops them manually."
        ),
    )

    model_config = cast(
        ConfigDict,
        {
            "reference_group": "Core",
            "example_dict": {
                "name": "start",
                "method": "example_agent.example_synchronous_job_start",
                "params": {"action": "start"},
                "fields": [
                    {
                        "name": "Company to research",
                        # String label for docs / JSON Schema — not the `str` type object (Pydantic 2.12+ OpenAPI)
                        "type": "str",
                        "field_type": "CharField",
                        "max_length": 100,
                        "required": True,
                    },
                ],
                "description": "Start the collection of new competitor summary",
            },
        },
    )

    nodes: CaseNodes | None = Field(
        default=None,
        description="The definition of the Case Nodes (=steps) for this method",
    )

    @field_validator("method")
    @classmethod
    def reject_unsafe_method_module_roots(cls, value: str) -> str:
        root_module = value.split(".", 1)[0]
        if root_module in BLOCKED_AGENT_METHOD_MODULE_ROOTS:
            raise ValueError(
                f"Agent method path '{value}' uses blocked module root '{root_module}'"
            )
        return value


_FIELD_TYPE_RULES: tuple[
    tuple[type[Any], type[Any] | tuple[type[Any], ...], str], ...
] = (
    (str, str, "a string"),
    (int, int, "an integer"),
    (bool, bool, "a boolean"),
    (list, list, "a list"),
    (dict, dict, "a dictionary"),
    (float, (int, float), "a number"),
)

_DYNAMIC_FIELD_TYPES: tuple[tuple[type[Any], type[Any]], ...] = (
    (str, str),
    (int, int),
    (bool, bool),
    (list, list),
    (dict, dict),
    (float, float),
)


def _field_annotation(field: AgentMethodField) -> Any:
    """Return the dynamic Pydantic annotation for an agent method field."""
    annotation_type = _normalize_field_annotation_type(field.type)
    return annotation_type if field.required else annotation_type | None


def _normalize_field_annotation_type(field_type: Any) -> type[Any]:
    """Map supported field types to the annotations used in dynamic models."""
    for supported_type, annotation_type in _DYNAMIC_FIELD_TYPES:
        if field_type is supported_type:
            return annotation_type

    origin = getattr(field_type, "__origin__", None)
    if origin is list:
        return list
    if origin is dict:
        return dict
    return Any


def _field_type_validation_error(
    field_name: str, field_value: Any, expected_type: Any
) -> str | None:
    """Return the public type-validation error for one supplied field value."""
    for supported_type, value_type, type_name in _FIELD_TYPE_RULES:
        if expected_type is supported_type and not isinstance(field_value, value_type):
            return (
                f"Field '{field_name}' must be {type_name}, "
                f"got {type(field_value).__name__}"
            )
    return None


def _missing_required_field_errors(
    fields: list[AgentMethodField], job_fields: dict[str, Any]
) -> tuple[list[str], dict[str, str]]:
    """Collect missing required-field errors in declared field order."""
    errors: list[str] = []
    invalid_fields: dict[str, str] = {}
    for field in fields:
        if field.required and field.name not in job_fields:
            error_msg = f"Required field '{field.name}' is missing"
            errors.append(error_msg)
            invalid_fields[field.name] = error_msg
    return errors, invalid_fields


def _provided_field_validation_errors(
    fields: list[AgentMethodField], job_fields: dict[str, Any]
) -> tuple[list[str], dict[str, str]]:
    """Collect unknown and type errors in supplied field order."""
    errors: list[str] = []
    invalid_fields: dict[str, str] = {}
    for field_name, field_value in job_fields.items():
        error_msg: str | None
        field_def = next((field for field in fields if field.name == field_name), None)
        if not field_def:
            error_msg = f"Unknown field '{field_name}'"
        elif field_value is None:
            continue
        else:
            try:
                error_msg = _field_type_validation_error(
                    field_name, field_value, field_def.type
                )
            except Exception as e:
                error_msg = f"Field '{field_name}' validation failed: {e!s}"

        if error_msg:
            errors.append(error_msg)
            invalid_fields[field_name] = error_msg
    return errors, invalid_fields


class AgentMethod(AgentMethodAbstract):
    @property
    def fields_definitions(self) -> list[dict[str, Any]]:
        """
        Returns a list of the fields with the type key as a string
        Used for the API response.
        """
        if self.fields:
            result = []
            for field in self.fields:
                d = {k: v for k, v in field.__dict__.items() if k != "type"}
                # type as string
                type_val = field.type
                if hasattr(type_val, "__name__"):
                    d["type"] = type_val.__name__
                elif hasattr(type_val, "_name") and type_val._name:
                    d["type"] = type_val._name
                else:
                    d["type"] = str(type_val)
                result.append(d)
            return result
        return []

    @property
    def fields_annotations(self) -> type[BaseModel]:
        """
        Creates and returns a dynamic Pydantic model class based on the field definitions.
        """
        if not self.fields:
            return type("EmptyFieldsModel", (BaseModel,), {"to_dict": lambda self: {}})

        field_annotations = {
            field.name: _field_annotation(field) for field in self.fields
        }

        # Create the dynamic model with proper module information
        model_dict = {
            "__module__": "supervaizer.agent",
            "__annotations__": field_annotations,
            "to_dict": lambda self: {
                k: getattr(self, k) for k in field_annotations if hasattr(self, k)
            },
        }

        return type("DynamicFieldsModel", (BaseModel,), model_dict)

    def validate_method_fields(self, job_fields: dict[str, Any]) -> dict[str, Any]:
        """Validate job fields against the method's field definitions.

        Args:
            job_fields: Dictionary of field names and values to validate

        Returns:
            Dictionary with validation results:
            - "valid": bool - whether all fields are valid
            - "errors": list[str] - list of validation error messages
            - "invalid_fields": dict[str, str] - field name to error message mapping
        """
        if self.fields is None:
            return {
                "valid": True,
                "message": "Method has no field definitions",
                "errors": [],
                "invalid_fields": {},
            }

        if len(self.fields) == 0:
            return {
                "valid": True,
                "message": "Method fields validated successfully",
                "errors": [],
                "invalid_fields": {},
            }

        errors, invalid_fields = _missing_required_field_errors(self.fields, job_fields)
        provided_errors, provided_invalid_fields = _provided_field_validation_errors(
            self.fields, job_fields
        )
        errors.extend(provided_errors)
        invalid_fields.update(provided_invalid_fields)

        return {
            "valid": len(errors) == 0,
            "message": "Method fields validated successfully"
            if len(errors) == 0
            else "Method field validation failed",
            "errors": errors,
            "invalid_fields": invalid_fields,
        }

    @property
    def job_model(self) -> type[AgentJobContextBase]:
        """
        Creates and returns a dynamic Pydantic model class combining job context and job fields.
        """
        fields_model = self.fields_annotations

        return type(
            "AgentJobAbstract",
            (AgentJobContextBase,),
            {
                "__annotations__": {
                    "job_context": JobContext,
                    "job_fields": fields_model,
                    "encrypted_agent_parameters": str | None,
                }
            },
        )

    @property
    def registration_info(self) -> dict[str, Any]:
        """
        Returns a JSON-serializable dictionary representation of the AgentMethod.
        """
        return {
            "name": self.name,
            "method": str(self.method),
            "params": self.params,
            "fields": self.fields_definitions,
            "description": self.description,
            "is_async": self.is_async,
            "timeout": self.timeout,
            "nodes": self.nodes.registration_info if self.nodes else None,
        }


class AgentMethodParams(BaseModel):
    """
    Method parameters for agent operations.

    """

    params: dict[str, Any] = Field(
        default_factory=dict,
        description="A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs",
    )


class AgentCustomMethodParams(AgentMethodParams):
    method_name: str


class AgentMethodsAbstract(BaseModel):
    job_start: AgentMethod
    job_stop: AgentMethod | None = None
    job_status: AgentMethod | None = None
    human_answer: AgentMethod | None = None
    chat: AgentMethod | None = None
    custom: dict[str, AgentMethod] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_job_poll(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("job_poll") is not None:
            raise ValueError(
                "job_poll was removed. Use Supervaizer v2 job.sync for status convergence."
            )
        return value

    @field_validator("custom")
    @classmethod
    def validate_custom_method_keys(
        cls, value: dict[str, AgentMethod]
    ) -> dict[str, AgentMethod]:
        """Validate that custom method keys are valid slug-like values suitable for endpoints."""
        if value:
            for key in value:
                # Check if key is a valid slug format
                if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", key):
                    raise ValueError(
                        f"Custom method key '{key}' is not a valid slug. "
                        f"Keys must contain only lowercase letters, numbers, and hyphens, "
                        f"and cannot start or end with a hyphen. "
                        f"Examples: 'backup', 'health-check', 'sync-data'"
                    )

                # Additional checks for endpoint safety
                if len(key) > 50:
                    raise ValueError(
                        f"Custom method key '{key}' is too long (max 50 characters)"
                    )

        return value


class AgentMethods(AgentMethodsAbstract):
    @property
    def registration_info(self) -> dict[str, Any]:
        return {
            "job_start": self.job_start.registration_info,
            "job_stop": self.job_stop.registration_info if self.job_stop else None,
            "job_status": self.job_status.registration_info
            if self.job_status
            else None,
            "human_answer": self.human_answer.registration_info
            if self.human_answer
            else None,
            "chat": self.chat.registration_info if self.chat else None,
            "custom": {
                name: method.registration_info
                for name, method in (self.custom or {}).items()
            },
        }


class AgentAbstract(SvBaseModel):
    """
            Agent model for the Supervaize Control API.

            This represents an agent that can be registered with the Supervaize Control API.
            It contains metadata about the agent like name, version, description etc. as well as
            the methods it supports and any parameter configurations.

            The agent ID is automatically generated from the name and must match.

            Example:
            ```python
            Agent(
        name="Email AI Agent",
        author="@parthshr370",  # Author of the agent
        developer="@alain_sv",  # Developer of the controller
        maintainer="@aintainer",
        editor="AI Editor",
        version="1.0.0",
        description="AI-powered email processing agent that can fetch, analyze, generate responses, and send/draft emails",
        tags=["email", "ai", "automation", "communication"],
        methods=AgentMethods(
            job_start=process_email_method, # Job start method
            job_stop=job_stop, # Job stop method
            job_status=job_status, # Job status method
            chat=None,
            custom=None,
        ),
        parameters_setup=ParametersSetup.from_list([
            Parameter(
                name="IMAP_USERNAME",
                description="IMAP username for email access",
                is_environment=True,
                is_secret=False,
            ),
            Parameter(
                name="IMAP_PASSWORD",
                description="IMAP password for email access",
                is_environment=True,
                is_secret=True,
            ),
        ]),
    )
            ```
    """

    supervaizer_VERSION: ClassVar[str] = VERSION
    name: str = Field(description="Display name of the agent")
    id: str = Field(
        description=(
            "Stable ID derived from name via shortuuid.uuid(name=...). "
            "Renaming the agent changes this value."
        )
    )
    author: str | None = Field(default=None, description="Author of the agent")
    developer: str | None = Field(
        default=None, description="Developer of the controller integration"
    )
    maintainer: str | None = Field(
        default=None, description="Maintainer of the integration"
    )
    editor: str | None = Field(default=None, description="Editor (usually a company)")
    version: str = Field(default="", description="Version string")
    release_notes_url: str | None = Field(
        default=None,
        description="URL for release notes matching this agent version",
    )
    description: str = Field(
        default="", description="Description of what the agent does"
    )
    introduction: V2AgentIntroduction | None = Field(
        default=None,
        description="Optional roster block (tagline, summary, example goals, avatar)",
    )
    full_description: V2AgentFullDescription | None = Field(
        default=None,
        description=(
            "Optional long-form markdown or HTML for the agent detail page. "
            "The SDK only types and bounds it; Studio sanitizes it."
        ),
    )
    billing_catalog: list[BillingCatalogItem] | None = Field(
        default=None,
        description=(
            "Optional billable SKUs (sku, unit, description) the agent reports "
            "consumption for. No prices; Studio prices them per workspace."
        ),
    )
    tags: list[str] | None = Field(
        default=None, description="Tags for categorizing the agent"
    )
    methods: AgentMethods | None = Field(
        default=None, description="Methods supported by this agent"
    )
    parameters_setup: ParametersSetup | None = Field(
        default=None, description="Parameter configuration"
    )
    server_agent_id: str | None = Field(
        default=None, description="ID assigned by server - Do not set this manually"
    )
    server_agent_status: str | None = Field(
        default=None, description="Current status on server - Do not set this manually"
    )
    server_agent_onboarding_status: str | None = Field(
        default=None, description="Onboarding status - Do not set this manually"
    )
    max_execution_time: int = Field(
        default=60 * 60,
        description="Maximum execution time in seconds, defaults to 1 hour",
    )
    supervaize_instructions_template_path: str | None = Field(
        default=None,
        description="Optional path to a custom template file for supervaize_instructions.html page",
    )
    instructions_path: str = Field(
        default="supervaize_instructions.html",
        description="Path where the supervaize instructions page is served (relative to agent path)",
    )
    custom_routes: Any | None = Field(
        default=None,
        description="Optional FastAPI APIRouter; mounted on the API app at /api/agents/{slug}/...",
        exclude=True,
    )
    data_resources: list[DataResource] = Field(
        default_factory=list,
        description="Data resources this agent exposes for Studio CRUD access",
        exclude=True,
    )
    supervaizer_v2_registration: SupervaizerV2AgentRegistrationContract | None = Field(
        default=None,
        description="Optional Supervaizer v2 registration contract for A2A/A2UI Studio integrations",
    )
    v2_methods: V2AgentMethods | None = Field(
        default=None,
        description="Optional agent-level Supervaizer v2 method declarations",
        exclude=True,
    )

    model_config = cast(
        ConfigDict, {"reference_group": "Core", "arbitrary_types_allowed": True}
    )

    @field_validator("billing_catalog")
    @classmethod
    def check_billing_catalog(
        cls, value: list[BillingCatalogItem] | None
    ) -> list[BillingCatalogItem] | None:
        return validate_billing_catalog(value)


_TERMINAL_JOB_STATUSES = frozenset({
    EntityStatus.COMPLETED,
    EntityStatus.FAILED,
    EntityStatus.CANCELLED,
    EntityStatus.CANCELLING,
})


def _job_start_action(methods: AgentMethods, method_name: str) -> AgentMethod:
    """Return the declared start action for a job request."""
    if method_name == "job_start":
        return methods.job_start
    if not methods.custom:
        raise ValueError(f"Custom method {method_name} not found")
    return methods.custom[method_name]


def _job_start_params(
    action: AgentMethod,
    job: Job,
    job_fields: dict[str, Any],
    context: JobContext,
    agent_parameters: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Build the public parameters for an agent job-start method."""
    return (
        (action.params or {})
        | {"fields": job_fields}
        | {"context": context}
        | {
            "agent_parameters": job.agent_parameters
            if agent_parameters is None
            else agent_parameters
        }
    )


def _apply_job_start_response(
    job: Job, response: JobResponse, server: "Server"
) -> None:
    """Apply response side effects in the established job-start order."""
    if response.payload:
        job.metadata = response.payload
    if server.supervisor_account is not None:
        event = JobStartConfirmationEvent(job=job, account=server.supervisor_account)
        server.supervisor_account.send_event_sync(sender=job, event=event)
    else:
        log.warning(
            f"[Agent job_start] No supervisor account defined for server, skipping event send for job {job.id}"
        )
    if response.status in _TERMINAL_JOB_STATUSES:
        job.add_response(response)
        service_job_finished(job, server=server)
    elif response.status == EntityStatus.AWAITING:
        log.debug(
            f"[Agent job_start] Job is awaiting input, adding response : Job {job.id} status {response} §SAS02"
        )
        job.add_response(response)
    else:
        log.warning(
            f"[Agent job_start] Job is not a terminal status, skipping job finish : Job {job.id} status {response} §SAS01"
        )


def _validate_agent_constructor_kwargs(kwargs: dict[str, Any]) -> None:
    """Reject constructor options removed by the v2 contract."""
    if "dynamic_choices_callback" in kwargs:
        raise ValueError(
            "dynamic_choices_callback was removed in Supervaizer v2. "
            "Use v2 resource option_sources or typed A2A actions for dynamic options."
        )


def _agent_constructor_id(name: str, supplied_id: str | None) -> str:
    """Return the deterministic identifier after validating an optional override."""
    expected_id = shortuuid.uuid(name=name)
    if supplied_id is not None and supplied_id != expected_id:
        raise ValueError(
            f"Agent id {supplied_id!r} does not match deterministic id for name {name!r} "
            f"({expected_id!r}); omit id or use the expected value"
        )
    return supplied_id or expected_id


def _agent_v2_constructor_values(
    registration: SupervaizerV2AgentRegistrationContract | dict[str, Any] | None,
    methods: V2AgentMethods | dict[str, Any] | None,
    introduction: V2AgentIntroduction | dict[str, Any] | None,
    full_description: V2AgentFullDescription | dict[str, Any] | None,
    billing_catalog: list[BillingCatalogItem | dict[str, Any]] | None,
) -> tuple[
    SupervaizerV2AgentRegistrationContract | None,
    V2AgentMethods | None,
    V2AgentIntroduction | None,
    V2AgentFullDescription | None,
    list[BillingCatalogItem] | None,
]:
    """Normalize v2 constructor values before Pydantic receives them."""
    normalized_registration = (
        SupervaizerV2AgentRegistrationContract.model_validate(registration)
        if isinstance(registration, dict)
        else registration
    )
    normalized_methods = (
        V2AgentMethods.model_validate(methods) if isinstance(methods, dict) else methods
    )
    normalized_introduction = (
        V2AgentIntroduction.model_validate(introduction)
        if isinstance(introduction, dict)
        else introduction
    )
    normalized_full_description = (
        V2AgentFullDescription.model_validate(full_description)
        if isinstance(full_description, dict)
        else full_description
    )
    normalized_catalog = (
        None
        if billing_catalog is None
        else [BillingCatalogItem.model_validate(item) for item in billing_catalog]
    )
    return (
        normalized_registration,
        normalized_methods,
        normalized_introduction,
        normalized_full_description,
        normalized_catalog,
    )


def _validate_unique_data_resource_names(
    resources: list["DataResource"], agent_name: str
) -> None:
    """Require each resource name to be unique within its agent."""
    seen_resource_names: set[str] = set()
    for resource in resources:
        if resource.name in seen_resource_names:
            raise ValueError(
                f"Duplicate DataResource name {resource.name!r} on agent {agent_name!r}; "
                "each data resource must have a unique name per agent."
            )
        seen_resource_names.add(resource.name)


def _get_agent_update_response(agent: "Agent", account: Any) -> Any:
    """Look up an agent by its Studio id, or its stable slug."""
    if agent.server_agent_id:
        return account.get_agent_by(agent_id=agent.server_agent_id)
    return account.get_agent_by(agent_slug=agent.slug)


def _agent_detail_from_update_response(
    response: Any, slug: str, server_agent_id: str | None
) -> dict[str, Any]:
    """Return a Studio agent detail or preserve the launch-stopping error."""
    if isinstance(response, ApiSuccess):
        return _agent_detail_from_server_response(response.detail)
    error_response = getattr(response.exception, "response", None)
    status = error_response.status_code if error_response is not None else "no response"
    raise RuntimeError(
        f"Agent update from Studio failed for slug={slug} "
        f"server_agent_id={server_agent_id}: GET {response.url} "
        f"returned {status} ({response.exception})"
    )


def _validated_server_agent_id(
    current_id: str | None, agent_detail: dict[str, Any], slug: str
) -> str | None:
    """Return the Studio id after enforcing stable agent identity."""
    returned_id = _agent_id_from_server_detail(agent_detail)
    if current_id and returned_id and current_id != returned_id:
        raise ValueError(f"Agent ID mismatch: {current_id} != {returned_id}")
    if not current_id and not returned_id:
        response_keys = sorted(str(key) for key in agent_detail)
        raise ValueError(
            "Agent update from Studio failed: response did not include agent id "
            f"for slug={slug}. response_keys={response_keys}"
        )
    return returned_id or current_id


class Agent(AgentAbstract):
    _server_encrypted_parameters: str | None = PrivateAttr(default=None)

    def __init__(
        self,
        name: str,
        id: str | None = None,
        author: str | None = None,
        developer: str | None = None,
        maintainer: str | None = None,
        editor: str | None = None,
        version: str = "",
        release_notes_url: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
        methods: AgentMethods | None = None,
        parameters_setup: ParametersSetup | None = None,
        server_agent_id: str | None = None,
        server_agent_status: str | None = None,
        server_agent_onboarding_status: str | None = None,
        max_execution_time: int = 60 * 60,  # 1 hour (in seconds)
        custom_routes: Any | None = None,
        data_resources: list["DataResource"] | None = None,
        supervaizer_v2_registration: SupervaizerV2AgentRegistrationContract
        | dict[str, Any]
        | None = None,
        v2_methods: V2AgentMethods | dict[str, Any] | None = None,
        introduction: V2AgentIntroduction | dict[str, Any] | None = None,
        full_description: V2AgentFullDescription | dict[str, Any] | None = None,
        billing_catalog: list[BillingCatalogItem | dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        This represents an agent that can be registered with the Supervaize Control API.
        It contains metadata about the agent like name, version, description etc. as well as
        the methods it supports and any parameter configurations.

        The agent ID is deterministically derived from ``name`` (``shortuuid.uuid(name=name)``).
        Pass ``id`` only when it matches that derivation; renaming changes the ID.

        Attributes:
            name (str): Display name of the agent
            id (str): Stable ID derived from name; omit to auto-generate
            author (str, optional): Original author
            developer (str, optional): Current developer
            maintainer (str, optional): Current maintainer
            editor (str, optional): Current editor
            version (str): Version string
            release_notes_url (str, optional): URL for this version's release notes
            description (str): Description of what the agent does
            tags (list[str], optional): Tags for categorizing the agent
            methods (AgentMethods): Methods supported by this agent
            parameters_setup (ParametersSetup, optional): Parameter configuration
            server_agent_id (str, optional): ID assigned by server
            server_agent_status (str, optional): Current status on server
            server_agent_onboarding_status (str, optional): Onboarding status
            max_execution_time (int):  Maximum execution time in seconds, defaults to 1 hour
            introduction (V2AgentIntroduction, optional): Roster block Studio shows
                before any job exists; sent as ``introduction`` only when set
            full_description (V2AgentFullDescription, optional): Long-form markdown
                or HTML Studio shows on the agent detail page; sent as
                ``full_description`` only when set. Studio sanitizes it.
            billing_catalog (list[BillingCatalogItem], optional): Billable SKUs the
                agent reports consumption for; sent as ``billing_catalog`` only
                when set. SKUs must be unique.

        Tested in tests/test_agent.py
        """
        _validate_agent_constructor_kwargs(kwargs)
        agent_id = _agent_constructor_id(name, id)
        (
            v2_registration,
            v2_method_declarations,
            v2_introduction,
            v2_full_description,
            catalog,
        ) = _agent_v2_constructor_values(
            supervaizer_v2_registration,
            v2_methods,
            introduction,
            full_description,
            billing_catalog,
        )

        # Initialize using Pydantic's mechanism
        super().__init__(
            name=name,
            id=agent_id,
            author=author,
            developer=developer,
            maintainer=maintainer,
            editor=editor,
            version=version,
            release_notes_url=release_notes_url,
            description=description,
            tags=tags,
            methods=methods,
            parameters_setup=parameters_setup,
            server_agent_id=server_agent_id,
            server_agent_status=server_agent_status,
            server_agent_onboarding_status=server_agent_onboarding_status,
            max_execution_time=max_execution_time,
            custom_routes=custom_routes,
            data_resources=data_resources or [],
            supervaizer_v2_registration=v2_registration,
            v2_methods=v2_method_declarations,
            introduction=v2_introduction,
            full_description=v2_full_description,
            billing_catalog=catalog,
            **kwargs,
        )

        self._validate_supervaizer_v2_identity()
        self._apply_v2_method_capabilities()

        _validate_unique_data_resource_names(self.data_resources, self.name)

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    def _validate_supervaizer_v2_identity(self) -> None:
        registration = self.supervaizer_v2_registration
        if registration is None:
            return

        declared_slug = registration.agent.slug
        if declared_slug != self.slug:
            raise ValueError(
                "Supervaizer v2 registration agent.slug must match Agent.slug: "
                f"{declared_slug!r} != {self.slug!r}"
            )

    def _apply_v2_method_capabilities(self) -> None:
        if self.supervaizer_v2_registration is None or self.v2_methods is None:
            return
        declared = self.supervaizer_v2_registration.capabilities.actions
        known_ids = {action.id for action in declared}
        self.supervaizer_v2_registration.capabilities.actions = [
            *declared,
            *(
                V2ActionDefinition(id=action_id, mutating=True, scope="job")
                for action_id in dict.fromkeys(self.v2_methods.action_ids)
                if action_id not in known_ids
            ),
        ]

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def path(self) -> str:
        return f"/agents/{self.slug}"

    @property
    def registration_info(self) -> dict[str, Any]:
        """Returns registration info for the agent.

        ``introduction``, ``full_description`` and ``billing_catalog`` are added
        only when set, so agents without them send exactly the keys they sent
        before.
        """
        info = {
            "name": self.name,
            "id": f"{self.id}",
            "author": self.author,
            "developer": self.developer,
            "maintainer": self.maintainer,
            "editor": self.editor,
            "version": self.version,
            "release_notes_url": self.release_notes_url,
            "description": self.description,
            "api_path": self.path,
            "slug": self.slug,
            "tags": self.tags,
            "methods": self.methods.registration_info if self.methods else {},
            "parameters_setup": self.parameters_setup.registration_info
            if self.parameters_setup
            else [],
            "server_agent_id": f"{self.server_agent_id}",
            "server_agent_status": self.server_agent_status,
            "server_agent_onboarding_status": self.server_agent_onboarding_status,
            "max_execution_time": self.max_execution_time,
            "instructions_path": self.instructions_path,
            "data_resources": [r.registration_info for r in self.data_resources],
            "supervaizer_v2": self.supervaizer_v2_registration.model_dump(mode="json")
            if self.supervaizer_v2_registration
            else None,
        }
        if self.introduction is not None:
            info["introduction"] = self.introduction.model_dump(mode="json")
        if self.full_description is not None:
            info["full_description"] = self.full_description.model_dump(mode="json")
        if self.billing_catalog is not None:
            info["billing_catalog"] = [
                item.model_dump(mode="json") for item in self.billing_catalog
            ]
        return info

    def update_agent_from_server(self, server: "Server") -> "Agent | None":
        """
        Update agent attributes and parameters from server registration information.
        Example of agent_registration data is available in mock_api_responses.py

        Server is used to decrypt parameters if needed
        Returns None without a Studio account; raises if the Studio lookup fails.
        Tested in tests/test_agent.py/test_agent_update_agent_from_server
        """
        supervisor_account = server.supervisor_account
        if not supervisor_account:
            return None
        from_server = _get_agent_update_response(self, supervisor_account)
        agent_from_server = _agent_detail_from_update_response(
            from_server, self.slug, self.server_agent_id
        )
        server_agent_id = _validated_server_agent_id(
            self.server_agent_id, agent_from_server, self.slug
        )

        # Update agent attributes
        self.server_agent_id = server_agent_id or self.server_agent_id
        self.server_agent_status = (
            agent_from_server.get("status") if agent_from_server else None
        )
        self.server_agent_onboarding_status = (
            agent_from_server.get("onboarding_status") if agent_from_server else None
        )

        # If agent is configured, get encrypted parameters
        if self.server_agent_onboarding_status == "configured":
            log.debug(
                f"[Agent configured] getting encrypted parameters for {self.name}"
            )
            server_encrypted_parameters = (
                agent_from_server.get("parameters_encrypted")
                if agent_from_server
                else None
            )
            self.update_parameters_from_server(server, server_encrypted_parameters)
        else:
            log.debug("[Agent not onboarded] skipping encrypted parameters")

        return self

    def update_parameters_from_server(
        self, server: "Server", server_encrypted_parameters: str | None
    ) -> None:
        if server_encrypted_parameters and self.parameters_setup:
            self._server_encrypted_parameters = server_encrypted_parameters
            decrypted = server.decrypt(server_encrypted_parameters)
            self.parameters_setup.update_values_from_server(json.loads(decrypted))
        else:
            log.debug("[No encrypted parameters] for {self.name}")

    def _execute(self, action: str, params: dict[str, Any] = {}) -> JobResponse:
        """Execute an agent method and return a JobResponse.

        Runs synchronously in the caller's thread; HTTP entrypoints typically
        offload this via ``asyncio.to_thread`` so user code cannot block the
        event loop.
        """

        if action not in self._declared_method_paths():
            raise ValueError(f"Agent method path is not declared on agent: {action}")

        module_name, func_name = action.rsplit(".", 1)
        module = __import__(module_name, fromlist=[func_name])
        method = getattr(module, func_name)
        # agent_parameters holds decrypted secrets: never log it.
        log.debug(
            f"[Agent method] {method.__name__} with params "
            f"{ {k: v for k, v in params.items() if k != 'agent_parameters'} }"
        )
        result = method(**params)
        if not isinstance(result, JobResponse):
            raise TypeError(
                f"Method {func_name} must return a JobResponse object, got {type(result).__name__}"
            )
        return result

    def _declared_method_paths(self) -> set[str]:
        if not self.methods:
            return set()
        methods = [
            self.methods.job_start,
            self.methods.job_stop,
            self.methods.job_status,
            self.methods.human_answer,
            self.methods.chat,
        ]
        if self.methods.custom:
            methods.extend(self.methods.custom.values())
        return {method.method for method in methods if method is not None}

    @property
    def v2_action_ids(self) -> list[str]:
        if self.v2_methods is None:
            return []
        return self.v2_methods.action_ids

    def v2_method_for_action(self, action: str) -> V2AgentMethod | None:
        if self.v2_methods is None:
            return None
        return self.v2_methods.method_for_action(action)

    def _declared_v2_method_paths(self) -> set[str]:
        if self.v2_methods is None:
            return set()
        methods = [self.v2_methods.refresh, *self.v2_methods.custom.values()]
        return {method.method for method in methods if method is not None}

    def execute_v2_action_method(self, action: str, request: V2ActionRequest) -> Any:
        agent_method = self.v2_method_for_action(action)
        if agent_method is None:
            raise ValueError(f"Agent v2 action is not declared on agent: {action}")
        if agent_method.method not in self._declared_v2_method_paths():
            raise ValueError(
                f"Agent v2 method path is not declared on agent: {agent_method.method}"
            )

        module_name, func_name = agent_method.method.rsplit(".", 1)
        module = import_module(module_name)
        action_method = getattr(module, func_name)
        return action_method(request=request, **agent_method.params)

    def job_start(
        self,
        job: Job,
        job_fields: dict[str, Any],
        context: JobContext,
        server: "Server",
        method_name: str = "job_start",
        agent_parameters: list[dict[str, Any]] | None = None,
    ) -> Job:
        """Execute the agent's start method in the background

        Args:
            job (Job): The job instance to execute
            job_fields (dict): The job-specific parameters
            context (SupervaizeContextModel): The context of the job
            agent_parameters (list | None): Decrypted parameters for this call
                only; None uses job.agent_parameters
        Returns:
            Job: The updated job instance
        """
        if not self.methods:
            raise ValueError("Agent methods not defined")

        action = _job_start_action(self.methods, method_name)

        log.debug(f"[Agent job_start] Run <{action.method}> - Job <{job.id}>")
        # Mark job as in progress when execution starts
        job.add_response(
            JobResponse(
                job_id=job.id,
                status=EntityStatus.IN_PROGRESS,
                message="Starting job execution",
                payload=None,
            )
        )

        # Execute the method
        action_method = action.method
        params = _job_start_params(action, job, job_fields, context, agent_parameters)
        # agent_parameters holds decrypted secrets: never log it.
        log.debug(
            f"[Agent job_start] action_method : {action_method} - params : "
            f"{ {k: v for k, v in params.items() if k != 'agent_parameters'} }"
        )
        try:
            if action.is_async:
                # TODO: Implement async job execution & test
                raise NotImplementedError(
                    "[Agent job_start] Async job execution is not implemented"
                )
                started = self._execute(action_method, params)
                job_response = JobResponse(
                    job_id=job.id,
                    status=EntityStatus.IN_PROGRESS,
                    message="Job started ",
                    payload={"intermediary_deliverable": started},
                )
            else:
                job_response = self._execute(action_method, params)
                _apply_job_start_response(job, job_response, server)

        except Exception as e:
            # Handle any execution errors
            error_msg = f"Job execution failed: {e!s}"
            log.error(f"[Agent job_start] Job failed : {job.id} - {error_msg}")
            job_response = JobResponse(
                job_id=job.id,
                status=EntityStatus.FAILED,
                message=error_msg,
                payload=None,
                error=e,
            )
            job.add_response(job_response)
            raise
        return job

    def job_stop(self, params: dict[str, Any] = {}) -> Any:
        """Synchronous stop hook; controller ``POST /stop`` runs it in a worker thread."""
        return self._execute_lifecycle_hook("job_stop", params)

    def job_status(self, params: dict[str, Any] = {}) -> Any:
        """Synchronous status hook; controller ``POST /status`` runs it in a worker thread."""
        return self._execute_lifecycle_hook("job_status", params)

    def _execute_lifecycle_hook(
        self,
        hook_name: Literal["job_stop", "job_status"],
        params: dict[str, Any],
    ) -> Any:
        """Run a configured stop or status hook with the supplied parameters."""
        if not self.methods:
            raise ValueError("Agent methods not defined")
        method = getattr(self.methods, hook_name)
        if not method:
            raise ValueError("Agent methods not defined")
        return self._execute(method.method, params)

    def chat(self, context: str, message: str) -> Any:
        if not self.methods or not self.methods.chat:
            raise ValueError("Chat method not configured")
        method = self.methods.chat.method
        params = {"context": context, "message": message}
        return self._execute(method, params)

    @property
    def custom_methods_names(self) -> list[str] | None:
        if self.methods and self.methods.custom:
            return list(self.methods.custom.keys())
        return None


class AgentResponse(BaseModel):
    """Response model for agent endpoints - values provided by Agent.registration_info"""

    name: str
    id: str
    author: str | None = None
    developer: str | None = None
    maintainer: str | None = None
    editor: str | None = None
    version: str
    release_notes_url: str | None = None
    api_path: str
    description: str
    tags: list[str] | None = None
    methods: AgentMethods | None = None
    parameters_setup: list[dict[str, Any]] | None = None
    server_agent_id: str | None = None
    server_agent_status: str | None = None
    server_agent_onboarding_status: str | None = None

    @field_validator("methods", mode="before")
    @classmethod
    def empty_methods_mean_none(cls, value: Any) -> Any:
        """registration_info sends {} for a v2-only agent (no v1 methods)."""
        return None if value == {} else value
