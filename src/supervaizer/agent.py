# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import json
import re
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    TypeVar,
)
import shortuuid
from pydantic import BaseModel, field_validator, Field
from rich import inspect, print
from slugify import slugify
from supervaizer.__version__ import VERSION
from supervaizer.common import ApiSuccess, SvBaseModel, log
from supervaizer.event import JobStartConfirmationEvent
from supervaizer.job import Job, JobContext, JobResponse
from supervaizer.job_service import service_job_finished
from supervaizer.lifecycle import EntityStatus
from supervaizer.parameter import ParametersSetup
from supervaizer.case import CaseNodes

if TYPE_CHECKING:
    from supervaizer.server import Server

insp = inspect
prnt = print

T = TypeVar("T")


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
    field_type: FieldTypeEnum = Field(
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

    model_config = {
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
    }


class AgentJobContextBase(BaseModel):
    """
    Base model for agent job context parameters
    """

    job_context: JobContext
    job_fields: Dict[str, Any]


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
    params: Dict[str, Any] | None = Field(
        default=None,
        description="A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs",
    )
    fields: List[AgentMethodField] | None = Field(
        default=None,
        description="A list of field specifications for generating forms/UI, following the django.forms.fields definition",
    )
    description: str | None = Field(
        default=None, description="Optional description of what the method does"
    )
    is_async: bool = Field(
        default=False, description="Whether the method is asynchronous"
    )

    model_config = {
        "reference_group": "Core",
        "example_dict": {
            "name": "start",
            "method": "example_agent.example_synchronous_job_start",
            "params": {"action": "start"},
            "fields": [
                {
                    "name": "Company to research",
                    "type": str,
                    "field_type": "CharField",
                    "max_length": 100,
                    "required": True,
                },
            ],
            "description": "Start the collection of new competitor summary",
        },
    }

    nodes: CaseNodes | None = Field(
        default=None,
        description="The definition of the Case Nodes (=steps) for this method",
    )


class AgentMethod(AgentMethodAbstract):
    @property
    def fields_definitions(self) -> list[Dict[str, Any]]:
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

        field_annotations = {}
        for field in self.fields:
            field_name = field.name
            field_type = field.type

            # Convert Python types to proper typing annotations
            if field_type is str:
                annotation_type: type = str
            elif field_type is int:
                annotation_type = int
            elif field_type is bool:
                annotation_type = bool
            elif field_type is list:
                annotation_type = list
            elif field_type is dict:
                annotation_type = dict
            elif field_type is float:
                annotation_type = float
            elif hasattr(field_type, "__origin__") and field_type.__origin__ is list:
                # Handle generic list types like list[str]
                annotation_type = list
            elif hasattr(field_type, "__origin__") and field_type.__origin__ is dict:
                # Handle generic dict types like dict[str, Any]
                annotation_type = dict
            else:
                # Default to Any for unknown types
                annotation_type = Any

            # Make field optional if not required
            field_annotations[field_name] = (
                annotation_type if field.required else Optional[annotation_type]
            )

        # Create the dynamic model with proper module information
        model_dict = {
            "__module__": "supervaizer.agent",
            "__annotations__": field_annotations,
            "to_dict": lambda self: {
                k: getattr(self, k)
                for k in field_annotations.keys()
                if hasattr(self, k)
            },
        }

        return type("DynamicFieldsModel", (BaseModel,), model_dict)

    def validate_method_fields(self, job_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Validate job fields against the method's field definitions.

        Args:
            job_fields: Dictionary of field names and values to validate

        Returns:
            Dictionary with validation results:
            - "valid": bool - whether all fields are valid
            - "errors": List[str] - list of validation error messages
            - "invalid_fields": Dict[str, str] - field name to error message mapping
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

        errors = []
        invalid_fields = {}

        # First check for missing required fields
        for field in self.fields:
            if field.required and field.name not in job_fields:
                error_msg = f"Required field '{field.name}' is missing"
                errors.append(error_msg)
                invalid_fields[field.name] = error_msg

        # Then validate the provided fields
        for field_name, field_value in job_fields.items():
            # Find the field definition
            field_def = next((f for f in self.fields if f.name == field_name), None)
            if not field_def:
                error_msg = f"Unknown field '{field_name}'"
                errors.append(error_msg)
                invalid_fields[field_name] = error_msg
                continue

            # Skip validation for None values (optional fields)
            if field_value is None:
                continue

            # Type validation
            expected_type = field_def.type
            if expected_type:
                try:
                    # Handle special cases for type validation
                    if expected_type is str:
                        if not isinstance(field_value, str):
                            error_msg = f"Field '{field_name}' must be a string, got {type(field_value).__name__}"
                            errors.append(error_msg)
                            invalid_fields[field_name] = error_msg
                    elif expected_type is int:
                        if not isinstance(field_value, int):
                            error_msg = f"Field '{field_name}' must be an integer, got {type(field_value).__name__}"
                            errors.append(error_msg)
                            invalid_fields[field_name] = error_msg
                    elif expected_type is bool:
                        if not isinstance(field_value, bool):
                            error_msg = f"Field '{field_name}' must be a boolean, got {type(field_value).__name__}"
                            errors.append(error_msg)
                            invalid_fields[field_name] = error_msg
                    elif expected_type is list:
                        if not isinstance(field_value, list):
                            error_msg = f"Field '{field_name}' must be a list, got {type(field_value).__name__}"
                            errors.append(error_msg)
                            invalid_fields[field_name] = error_msg
                    elif expected_type is dict:
                        if not isinstance(field_value, dict):
                            error_msg = f"Field '{field_name}' must be a dictionary, got {type(field_value).__name__}"
                            errors.append(error_msg)
                            invalid_fields[field_name] = error_msg
                    elif expected_type is float:
                        if not isinstance(field_value, (int, float)):
                            error_msg = f"Field '{field_name}' must be a number, got {type(field_value).__name__}"
                            errors.append(error_msg)
                            invalid_fields[field_name] = error_msg
                except Exception as e:
                    error_msg = f"Field '{field_name}' validation failed: {str(e)}"
                    errors.append(error_msg)
                    invalid_fields[field_name] = error_msg

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
    def registration_info(self) -> Dict[str, Any]:
        """
        Returns a JSON-serializable dictionary representation of the AgentMethod.
        """
        return {
            "name": self.name,
            "method": str(self.method),
            "params": self.params,
            "fields": self.fields_definitions,
            "description": self.description,
            "nodes": self.nodes.registration_info if self.nodes else None,
        }


class AgentMethodParams(BaseModel):
    """
    Method parameters for agent operations.

    """

    params: Dict[str, Any] = Field(
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

    @field_validator("custom")
    @classmethod
    def validate_custom_method_keys(
        cls, value: dict[str, AgentMethod]
    ) -> dict[str, AgentMethod]:
        """Validate that custom method keys are valid slug-like values suitable for endpoints."""
        if value:
            for key in value.keys():
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
    def registration_info(self) -> Dict[str, Any]:
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
    id: str = Field(description="Unique ID generated from name")
    author: Optional[str] = Field(default=None, description="Author of the agent")
    developer: Optional[str] = Field(
        default=None, description="Developer of the controller integration"
    )
    maintainer: Optional[str] = Field(
        default=None, description="Maintainer of the integration"
    )
    editor: Optional[str] = Field(
        default=None, description="Editor (usually a company)"
    )
    version: str = Field(default="", description="Version string")
    description: str = Field(
        default="", description="Description of what the agent does"
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
    server_encrypted_parameters: str | None = Field(
        default=None,
        description="Encrypted parameters from server - Do not set this manually",
    )
    max_execution_time: int = Field(
        default=60 * 60,
        description="Maximum execution time in seconds, defaults to 1 hour",
    )
    supervaize_instructions_template_path: Optional[str] = Field(
        default=None,
        description="Optional path to a custom template file for supervaize_instructions.html page",
    )
    instructions_path: str = Field(
        default="supervaize_instructions.html",
        description="Path where the supervaize instructions page is served (relative to agent path)",
    )

    model_config = {
        "reference_group": "Core",
    }


class Agent(AgentAbstract):
    def __init__(
        self,
        name: str,
        id: str | None = None,
        author: Optional[str] = None,
        developer: Optional[str] = None,
        maintainer: Optional[str] = None,
        editor: Optional[str] = None,
        version: str = "",
        description: str = "",
        tags: list[str] | None = None,
        methods: AgentMethods | None = None,
        parameters_setup: ParametersSetup | None = None,
        server_agent_id: str | None = None,
        server_agent_status: str | None = None,
        server_agent_onboarding_status: str | None = None,
        server_encrypted_parameters: str | None = None,
        max_execution_time: int = 60 * 60,  # 1 hour (in seconds)
        **kwargs: Any,
    ) -> None:
        """
        This represents an agent that can be registered with the Supervaize Control API.
        It contains metadata about the agent like name, version, description etc. as well as
        the methods it supports and any parameter configurations.

        The agent ID is automatically generated from the name and must match.

        Attributes:
            name (str): Display name of the agent
            id (str): Unique ID generated from name
            author (str, optional): Original author
            developer (str, optional): Current developer
            maintainer (str, optional): Current maintainer
            editor (str, optional): Current editor
            version (str): Version string
            description (str): Description of what the agent does
            tags (list[str], optional): Tags for categorizing the agent
            methods (AgentMethods): Methods supported by this agent
            parameters_setup (ParametersSetup, optional): Parameter configuration
            server_agent_id (str, optional): ID assigned by server
            server_agent_status (str, optional): Current status on server
            server_agent_onboarding_status (str, optional): Onboarding status
            server_encrypted_parameters (str, optional): Encrypted parameters from server
            max_execution_time (int):  Maximum execution time in seconds, defaults to 1 hour

        Tested in tests/test_agent.py
        """
        # Validate or generate agent ID
        agent_id = id or shortuuid.uuid(name=name)
        if id is not None and id != shortuuid.uuid(name=name):
            raise ValueError("Agent ID does not match")

        # Initialize using Pydantic's mechanism
        super().__init__(
            name=name,
            id=agent_id,
            author=author,
            developer=developer,
            maintainer=maintainer,
            editor=editor,
            version=version,
            description=description,
            tags=tags,
            methods=methods,
            parameters_setup=parameters_setup,
            server_agent_id=server_agent_id,
            server_agent_status=server_agent_status,
            server_agent_onboarding_status=server_agent_onboarding_status,
            server_encrypted_parameters=server_encrypted_parameters,
            max_execution_time=max_execution_time,
            **kwargs,
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def path(self) -> str:
        return f"/agents/{self.slug}"

    @property
    def registration_info(self) -> Dict[str, Any]:
        """Returns registration info for the agent"""
        return {
            "name": self.name,
            "id": f"{self.id}",
            "author": self.author,
            "developer": self.developer,
            "maintainer": self.maintainer,
            "editor": self.editor,
            "version": self.version,
            "description": self.description,
            "api_path": self.path,
            "slug": self.slug,
            "tags": self.tags,
            "methods": self.methods.registration_info if self.methods else {},
            "parameters_setup": self.parameters_setup.registration_info
            if self.parameters_setup
            else None,
            "server_agent_id": f"{self.server_agent_id}",
            "server_agent_status": self.server_agent_status,
            "server_agent_onboarding_status": self.server_agent_onboarding_status,
            "server_encrypted_parameters": self.server_encrypted_parameters,
            "max_execution_time": self.max_execution_time,
            "instructions_path": self.instructions_path,
        }

    def update_agent_from_server(self, server: "Server") -> Optional["Agent"]:
        """
        Update agent attributes and parameters from server registration information.
        Example of agent_registration data is available in mock_api_responses.py

        Server is used to decrypt parameters if needed
        Tested in tests/test_agent.py/test_agent_update_agent_from_server
        """
        if server.supervisor_account:
            if self.server_agent_id:
                # Get agent by ID from SaaS Server
                from_server = server.supervisor_account.get_agent_by(
                    agent_id=self.server_agent_id
                )

            else:
                # Get agent by name from SaaS Server
                from_server = server.supervisor_account.get_agent_by(
                    agent_slug=self.slug
                )
        else:
            return None
        if not isinstance(from_server, ApiSuccess):
            log.error(f"[Agent update_agent_from_server] Failed : {from_server}")
            return None

        agent_from_server = from_server.detail
        server_agent_id = agent_from_server.get("id") if agent_from_server else None

        # This should never happen, but just in case
        if self.server_agent_id and self.server_agent_id != server_agent_id:
            message = f"Agent ID mismatch: {self.server_agent_id} != {server_agent_id}"
            raise ValueError(message)

        # Update agent attributes
        self.server_agent_id = server_agent_id
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
            self.server_encrypted_parameters = server_encrypted_parameters
            decrypted = server.decrypt(server_encrypted_parameters)
            self.parameters_setup.update_values_from_server(json.loads(decrypted))
        else:
            log.debug("[No encrypted parameters] for {self.name}")

    def _execute(self, action: str, params: Dict[str, Any] = {}) -> JobResponse:
        """
        Execute an agent method and return a JobResponse
        """

        module_name, func_name = action.rsplit(".", 1)
        module = __import__(module_name, fromlist=[func_name])
        method = getattr(module, func_name)
        log.debug(f"[Agent method] {method.__name__} with params {params}")
        result = method(**params)
        if not isinstance(result, JobResponse):
            raise TypeError(
                f"Method {func_name} must return a JobResponse object, got {type(result).__name__}"
            )
        return result

    def job_start(
        self,
        job: Job,
        job_fields: Dict[str, Any],
        context: JobContext,
        server: "Server",
        method_name: str = "job_start",
    ) -> Job:
        """Execute the agent's start method in the background

        Args:
            job (Job): The job instance to execute
            job_fields (dict): The job-specific parameters
            context (SupervaizeContextModel): The context of the job
        Returns:
            Job: The updated job instance
        """
        if not self.methods:
            raise ValueError("Agent methods not defined")
        log.debug(
            f"[Agent job_start] Run <{self.methods.job_start.method}> - Job <{job.id}>"
        )
        event = JobStartConfirmationEvent(
            job=job,
            account=server.supervisor_account,
        )
        if server.supervisor_account is not None:
            server.supervisor_account.send_event(sender=job, event=event)
        else:
            log.warning(
                f"[Agent job_start] No supervisor account defined for server, skipping event send for job {job.id}"
            )

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
        if method_name == "job_start":
            action = self.methods.job_start
        else:
            if not self.methods.custom:
                raise ValueError(f"Custom method {method_name} not found")
            action = self.methods.custom[method_name]

        action_method = action.method
        method_params = action.params or {}
        params = (
            method_params
            | {"fields": job_fields}
            | {"context": context}
            | {"agent_parameters": job.agent_parameters}
        )
        log.debug(
            f"[Agent job_start] action_method : {action_method} - params : {params}"
        )
        try:
            if self.methods.job_start.is_async:
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
                if (
                    job_response.status == EntityStatus.COMPLETED
                    or job_response.status == EntityStatus.FAILED
                    or job_response.status == EntityStatus.CANCELLED
                    or job_response.status == EntityStatus.CANCELLING
                ):
                    job.add_response(job_response)
                    service_job_finished(job, server=server)
                elif job_response.status == EntityStatus.AWAITING:
                    log.debug(
                        f"[Agent job_start] Job is awaiting input, adding response : Job {job.id} status {job_response} §SAS02"
                    )
                    job.add_response(job_response)
                else:
                    log.warning(
                        f"[Agent job_start] Job is not a terminal status, skipping job finish : Job {job.id} status {job_response} §SAS01"
                    )

        except Exception as e:
            # Handle any execution errors
            error_msg = f"Job execution failed: {str(e)}"
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

    def job_stop(self, params: Dict[str, Any] = {}) -> Any:
        if not self.methods or not self.methods.job_stop:
            raise ValueError("Agent methods not defined")
        method = self.methods.job_stop.method
        return self._execute(method, params)

    def job_status(self, params: Dict[str, Any] = {}) -> Any:
        if not self.methods or not self.methods.job_status:
            raise ValueError("Agent methods not defined")
        method = self.methods.job_status.method
        return self._execute(method, params)

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
    author: Optional[str] = None
    developer: Optional[str] = None
    maintainer: Optional[str] = None
    editor: Optional[str] = None
    version: str
    api_path: str
    description: str
    tags: Optional[list[str]] = None
    methods: Optional[AgentMethods] = None
    parameters_setup: Optional[List[Dict[str, Any]]] = None
    server_agent_id: Optional[str] = None
    server_agent_status: Optional[str] = None
    server_agent_onboarding_status: Optional[str] = None
    server_encrypted_parameters: Optional[str] = None
