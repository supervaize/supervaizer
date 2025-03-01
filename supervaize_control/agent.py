from typing import Any, ClassVar, Dict, List
from .job import Job
import shortuuid
from pydantic import BaseModel
from slugify import slugify

from .__version__ import AGENT_VERSION, VERSION


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
       - type: Field type (e.g. ChoiceField, TextField)
       - choices: For choice fields, list of [value, label] pairs
       - widget: UI widget to use (e.g. RadioSelect, TextInput)
       - required: Whether field is required


       Example:
       [
           {
                "name": "color",
                "type": "ChoiceField",
                "choices": [["B", "Blue"], ["R", "Red"], ["G", "Green"]],
                "widget": "RadioSelect",
                "required": True,
            },
            {
                "name": "age",
                "type": "IntegerField",
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
    def fields_dict(self) -> dict:
        if self.fields:
            return {field["name"]: field["type"] for field in self.fields}
        return {}


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
            "tags": self.tags,
        }

    def _execute(self, method: str, params: Dict[str, Any] = {}):
        module_name, func_name = method.rsplit(".", 1)
        module = __import__(module_name, fromlist=[func_name])
        method = getattr(module, func_name)
        return method(**params)

    def start(self, call_params: Dict[str, Any] = {}):
        method = self.start_method.method
        params = self.start_method.params | call_params
        new_job = Job.new(response=self._execute(method, params))
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
