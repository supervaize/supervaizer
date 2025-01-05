from typing import ClassVar, overload

import requests
import shortuuid
from pydantic import BaseModel

from .__version__ import EVENT_VERSION, TELEMETRY_VERSION, VERSION
from .common import ApiError, ApiResult, ApiSuccess
from .event import AgentSendRegistrationEvent
from .telemetry import Telemetry


class AccountModel(BaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    name: str
    id: str
    api_key: str
    api_url: str


class Account(AccountModel):
    def __init__(self, **kwargs):
        if kwargs.get("id") != shortuuid.uuid(name=kwargs.get("name")):
            raise ValueError("Account ID does not match")
        super().__init__(**kwargs)

    def __str__(self):
        return f"{self.api_url} - v{self.version}"

    @property
    def api_headers(self):
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def send_event(self, agent: "Agent", event: "Event") -> ApiResult:
        """Send an event to the Supervaize Control API.

        Args:
            agent (Agent): The agent sending the event
            event (Event): The event to be sent

        Returns:
            ApiResult: ApiSuccess with response details if successful,
                      ApiError with error details if request fails
        """
        url = f"{self.api_url}/{EVENT_VERSION}/event"
        headers = self.api_headers
        event.details |= {"tenantId": self.id, "agentId": agent.id}
        try:
            response = requests.post(url, headers=headers, json=event.payload)
            response.raise_for_status()
            result = ApiSuccess(
                message=f"Event posted {event.type.name}", detail=response.text
            )
        except requests.exceptions.RequestException as e:
            result = ApiError(
                message=f"Error sending event {event.type.name}",
                url=url,
                payload=event.payload,
                exception=e,
            )

        return result

    @overload
    def register_agent(
        self, agent: "Agent", polling: bool, server: None = None
    ) -> ApiResult: ...

    def register_agent(
        self, agent: "Agent", server: "Server", polling: bool = False
    ) -> ApiResult:
        """Send a registration event to the Supervaize Control API.

        Args:
            agent (Agent): The agent sending the registration event
            server (Server): The server to register the agent with.
            polling (bool): If server is not defined, polling will be used.

        Returns:
            ApiResult: ApiSuccess with response details if successful,
                      ApiError with error details if request fails
        """

        event = AgentSendRegistrationEvent(
            agent=agent, account=self, server=server, polling=polling
        )
        return self.send_event(agent, event)

    def send_telemetry(self, telemetry: Telemetry) -> ApiResult:
        """Send telemetry data to the Supervaize Control API.

        Args:
            telemetry (Telemetry): The telemetry object to be sent

        Returns:
            ApiResult: ApiSuccess with response details if successful,
                      ApiError with error details if request fails
        """
        url = f"{self.api_url}/{TELEMETRY_VERSION}/telemetry"
        headers = self.api_headers
        payload = {"tenantId": self.id} | telemetry.payload
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = ApiSuccess(
                message=f"Telemetry sent {telemetry.type.name}", detail=response.text
            )
        except requests.exceptions.RequestException as e:
            result = ApiError(
                message=f"Error sending telemetry {telemetry.type.name}",
                url=url,
                payload=payload,
                exception=e,
            )

        return result
