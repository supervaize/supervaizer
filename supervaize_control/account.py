from typing import ClassVar

import requests
import shortuuid
from pydantic import BaseModel

from .__version__ import TELEMETRY_VERSION, VERSION
from .common import ApiError, ApiResult, ApiSuccess
from .telemetry import Telemetry
from loguru import logger

log = logger


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
            "Authorization": f"Api-Key {self.api_key}",
            "accept": "application/json",
        }

    def send_event(self, sender: "Agent | Server", event: "Event") -> ApiResult:
        """Send an event to the Supervaize Control API.

        Args:
            sender (Agent | Server): The sender of the event
            event (Event): The event to be sent

        Returns:
            ApiResult: ApiSuccess with response details if successful,
                      ApiError with error details if request fails
        """

        url = f"{self.api_url}/api/v1/ctrl-events/"
        log.debug(f"Sending event {event.type.name} to {url}")
        headers = self.api_headers
        try:
            log.debug(f"Event payload: {event.payload}")
            response = requests.post(url, headers=headers, data=event.payload)
            response.raise_for_status()
            result = ApiSuccess(
                message=f"Event {event.type.name} sent", detail=response.text
            )

            log.success(result.log_message)
        except requests.exceptions.RequestException as e:
            result = ApiError(
                message=f"Error sending event {event.type.name}",
                url=url,
                payload=event.payload,
                exception=e,
            )
            log.debug(result.dict)
            log.error(result.log_message)
            raise e
        return result

    def register_server(self, server: "server") -> ApiResult:
        """Register a server with the Supervaize Control API.

        Args:
            server (Server): The server to register.

        Returns:
            ApiResult: ApiSuccess with response details if successful,
                      ApiError with error details if request fails
        """
        from .event import ServerSendRegistrationEvent

        event = ServerSendRegistrationEvent(server=server, account=self)
        return self.send_event(server, event)

    def register_agent(self, agent: "Agent", polling: bool = True) -> ApiResult:
        """Send a registration event to the Supervaize Control API.
            This will be used for polling, when the agent is registered without a server.
        Args:
            agent (Agent): The agent sending the registration event
            polling (bool): If server is not defined, polling will be used.

        Returns:
            ApiResult: ApiSuccess with response details if successful,
                      ApiError with error details if request fails
        """
        from .event import AgentSendRegistrationEvent

        event = AgentSendRegistrationEvent(agent=agent, account=self, polling=polling)
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
