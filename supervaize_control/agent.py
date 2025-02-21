from enum import Enum
from typing import Any, ClassVar, Dict

import shortuuid
from pydantic import BaseModel
from slugify import slugify

from .__version__ import AGENT_VERSION, VERSION


class MethodType(Enum):
    START = "start"
    STOP = "stop"
    STATUS = "status"
    CHAT = "chat"
    CUSTOM = "custom"


class AgentMethod(BaseModel):
    name: str
    method: str
    params: Dict[str, Any] | None = None
    description: str | None = None


class AgentMethodParams(BaseModel):
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

    def _execute(self, method: str, params: Dict[str, Any] = {}):
        module_name, func_name = method.rsplit(".", 1)
        module = __import__(module_name, fromlist=[func_name])
        method = getattr(module, func_name)
        return method(**params)

    def start(self, params: Dict[str, Any] = {}):
        method = self.start_method.method
        params = self.start_method.params
        return self._execute(method, params)

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
