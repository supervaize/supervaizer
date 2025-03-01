from typing import Any, ClassVar, Dict, List

import shortuuid
from loguru import logger
from pydantic import BaseModel
from slugify import slugify

from .__version__ import AGENT_VERSION, VERSION
from .job import Job, JobContextModel


log = logger.bind(module="agent")


class AgentJobContextBase(BaseModel):
    """
    Base model for agent job context parameters
    """

    job_context: JobContextModel
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
                    "job_context": JobContextModel,
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


class AgentModel(BaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    AGENT_VERSION: ClassVar[str] = AGENT_VERSION
    name: str
    id: str
    author: str
    developer: str
    version: str
    description: str
    tags: list[str] | None = None
    start_method: AgentMethod
    stop_method: AgentMethod
    status_method: AgentMethod
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
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "developer": self.developer,
            "description": self.description,
            "start_method": self.start_method.registration_info,
            "stop_method": self.stop_method.registration_info,
            "status_method": self.status_method.registration_info,
            "chat_method": (
                self.chat_method.registration_info if self.chat_method else {}
            ),
            "custom_methods": {
                k: v.registration_info or None for k, v in self.custom_methods.items()
            }
            if self.custom_methods
            else {},
            "tags": self.tags,
        }

    def _execute(self, method: str, params: Dict[str, Any] = {}):
        module_name, func_name = method.rsplit(".", 1)
        module = __import__(module_name, fromlist=[func_name])
        method = getattr(module, func_name)
        log.info(f"Executing method {method.__name__} with params {params}")
        return method(**params)

    def start(self, call_params: AgentJobContextBase):
        method = self.start_method.method
        job_context = call_params.job_context
        job_fields = call_params.job_fields.to_dict()

        params = self.start_method.params | job_fields
        new_job = Job.new(
            job_context=job_context, response=self._execute(method, params)
        )
        return new_job

    def stop(self, params: Dict[str, Any] = {}):
        method = self.stop_method.method
        params = self.stop_method.params
        return self._execute(method, params)

    def status(self, params: Dict[str, Any] = {}):
        method = self.status_method.method
        params = self.status_method.params
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
