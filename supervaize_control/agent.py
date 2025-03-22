# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from typing import Any, ClassVar, Dict, List

import shortuuid
from pydantic import BaseModel
from slugify import slugify

from .__version__ import VERSION
from .common import SvBaseModel, log
from .job import Job, JobContext, JobResponse, JobStatus


class AgentJobContextBase(BaseModel):
    """
    Base model for agent job context parameters
    """

    supervaize_context: JobContext
    job_fields: Dict[str, Any]


class AgentMethod(BaseModel):
    """
    Represents a method that can be called on an agent.

    Attributes:
        name: Display name of the method
        method: Name of the actual method in the project's codebase that will be called with the provided parameters
        params: see below
        fields: see below
        description: Optional description of what the method does


    1. params : Dictionary format
       A simple key-value dictionary of parameters what will be passed to the AgentMethod.method as kwargs.
       Example:
       {
           "verbose": True,
           "timeout": 60,
           "max_retries": 3
       }

    2. fields : Form fields format
       These are the values that will be requested from the user in the Supervaize UI and also passed as kwargs to the AgentMethod.method.
       A list of field specifications for generating forms/UI, following the django.forms.fields definition
       see : https://docs.djangoproject.com/en/5.1/ref/forms/fields/
       Each field is a dictionary with properties like:
       - name: Field identifier
       - type: Python type of the field for pydantic validation - used for API validation
       - field_type: Field type (e.g. ChoiceField, TextField) - used in API response (to build forms)
       - choices: For choice fields, list of [value, label] pairs
       - widget: UI widget to use (e.g. RadioSelect, TextInput)
       - required: Whether field is required


       Example:
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

    """

    name: str
    method: str
    params: Dict[str, Any] | None = None
    fields: List[Dict[str, Any]] | None = None
    description: str | None = None

    @property
    def fields_definitions(self) -> list[dict]:
        """
        Returns a list of the fields without the type key.
        Used for the API response.
        """
        if self.fields:
            return [
                {k: v for k, v in field.items() if k != "type"} for field in self.fields
            ]
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
            field_name = field["name"]
            field_type = field["type"]
            field_annotations[field_name] = field_type

        def to_dict(self):
            return {
                field_name: getattr(self, field_name)
                for field_name in self.__annotations__
            }

        return type(
            "DynamicFieldsModel",
            (BaseModel,),
            {"__annotations__": field_annotations, "to_dict": to_dict},
        )

    @property
    def job_model(self) -> type[AgentJobContextBase]:
        """
        Creates and returns a dynamic Pydantic model class combining job context and job fields.
        """
        fields_model = self.fields_annotations

        return type(
            "AgentJobModel",
            (AgentJobContextBase,),
            {
                "__annotations__": {
                    "supervaize_context": JobContext,
                    "job_fields": fields_model,
                }
            },
        )

    @property
    def registration_info(self) -> dict:
        """
        Returns a JSON-serializable dictionary representation of the AgentMethod.
        """
        return {
            "name": self.name,
            "method": str(self.method),
            "params": self.params,
            "fields": self.fields_definitions,
            "description": self.description,
        }


class AgentMethodParams(BaseModel):
    """
    Method parameters for agent operations.

    """

    params: Dict[str, Any] | None = None


class AgentCustomMethodParams(AgentMethodParams):
    method_name: str


class AgentModel(SvBaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    name: str
    id: str
    author: str
    developer: str
    version: str
    description: str
    tags: list[str] | None = None
    job_start_method: AgentMethod
    job_stop_method: AgentMethod
    job_status_method: AgentMethod
    chat_method: AgentMethod | None = None
    custom_methods: dict[str, AgentMethod] | None = None


class Agent(AgentModel):
    def __init__(self, **kwargs):
        """Tested in tests/test_agent.py"""
        if kwargs.get("id") != shortuuid.uuid(name=kwargs.get("name")):
            raise ValueError("Agent ID does not match")

        super().__init__(**kwargs)

    def __str__(self):
        return f"{self.name} - v{self.version}"

    @property
    def uri(self):
        return f"agent:{self.id}"

    @property
    def slug(self):
        return slugify(self.name)

    @property
    def registration_info(self):
        """Returns a JSON-serializable dictionary representation of the agent.
        Used for API responses and registration.
        """
        return {
            "name": self.name,
            "id": self.id,
            "author": self.author,
            "developer": self.developer,
            "version": self.version,
            "description": self.description,
            "tags": self.tags,
            "uri": self.uri,
            "slug": self.slug,
            "job_start_method": self.job_start_method.registration_info,
            "job_stop_method": self.job_stop_method.registration_info,
            "job_status_method": self.job_status_method.registration_info,
            "chat_method": self.chat_method.registration_info
            if self.chat_method
            else None,
            "custom_methods": {
                k: v.registration_info for k, v in (self.custom_methods or {}).items()
            },
        }

    def _execute(self, action: str, params: Dict[str, Any] = {}):
        module_name, func_name = action.rsplit(".", 1)
        module = __import__(module_name, fromlist=[func_name])
        method = getattr(module, func_name)
        log.info(f"Executing method {method.__name__} with params {params}")
        return method(
            **params,
        )

    def job_start(self, job: Job, job_fields: dict, context: JobContext):
        """Execute the agent's start method in the background

        Args:
            job (Job): The job instance to execute
            job_fields (dict): The job-specific parameters
            context (SupervaizeContextModel): The context of the job
        Returns:
            Job: The updated job instance
        """

        # Mark job as in progress when execution starts
        job.add_response(
            JobResponse(
                job_id=job.id,
                status=JobStatus.IN_PROGRESS,
                message="Starting job execution",
                payload=None,
            )
        )

        # Execute the method
        action = self.job_start_method.method
        params = (
            self.job_start_method.params | {"fields": job_fields} | {"context": context}
        )
        try:
            result = self._execute(action, params)

            # Store result and mark as completed

            job_response = JobResponse(
                job_id=job.id,
                status=JobStatus.COMPLETED,
                message="Job completed successfully",
                payload=result,
            )

        except Exception as e:
            # Handle any execution errors
            error_msg = f"Job execution failed: {str(e)}"
            job_response = JobResponse(
                job_id=job.id,
                status=JobStatus.FAILED,
                message=error_msg,
                payload=None,
            )
            log.error(error_msg)

        job.add_response(job_response)

        return job

    def job_stop(self, params: Dict[str, Any] = {}):
        method = self.job_stop_method.method
        params = self.job_stop_method.params
        return self._execute(method, params)

    def job_status(self, params: Dict[str, Any] = {}):
        method = self.job_status_method.method
        params = self.job_status_method.params
        return self._execute(method, params)

    def chat(self, context: str, message: str):
        method = self.chat_method.method
        params = {"context": context, "message": message}
        return self._execute(method, params)

    def custom(self, method: str, params: Dict[str, Any] = {}):
        """Tested in tests/test_agent.py"""
        if method not in self.custom_methods:
            raise ValueError(f"Method {method} not found")
        method = self.custom_methods[method].method
        params = self.custom_methods[method].params
        return self._execute(method, params)

    @property
    def custom_methods_names(self) -> list[str] | None:
        if self.custom_methods:
            return list(self.custom_methods.keys())
        return None
