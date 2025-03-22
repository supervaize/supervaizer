from typing import ClassVar
from enum import Enum
from pydantic import BaseModel

from .__version__ import VERSION
from .agent import Agent
from .account import Account
from .case import Case


class EventType(Enum):
    AGENT_SEND_REGISTRATION = "agent.send.registration"
    SERVER_SEND_REGISTRATION = "server.send.registration"
    AGENT_SEND_WAKEUP = "agent.send.wakeup"
    AGENT_SEND_ANOMALY = "agent.send.anomaly"
    INTERMEDIARY = "agent.send.intermediary"
    JOB_START = "agent.send.job.start"
    JOB_END = "agent.send.job.end"
    JOB_STATUS = "agent.send.job.status"
    JOB_RESULT = "agent.send.job.result"
    JOB_ERROR = "agent.send.job.error"
    CASE_START = "agent.send.case.start"
    CASE_END = "agent.send.case.end"
    CASE_STATUS = "agent.send.case.status"
    CASE_RESULT = "agent.send.case.result"


class EventModel(BaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    source: str
    account: Account
    type: EventType
    details: dict


class Event(EventModel):
    """Base class for all events in the Supervaize Control system.

    Events represent messages sent from agents to the control system to communicate
    status, anomalies, deliverables and other information.

    Inherits from EventModel which defines the core event attributes:
        - source: The source/origin of the event (e.g. agent/server URI)
        - type: The EventType enum indicating the event category
        - account: The account that the event belongs to
        - details: A dictionary containing event-specific details
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def payload(self) -> dict:
        return {
            "name": f"{self.type.value} {self.source}",
            "source": self.source,
            "account": self.account.id,
            "event_type": self.type.value,
            "details": self.details,
        }


class AgentSendRegistrationEvent(Event):
    def __init__(
        self,
        agent: "Agent",
        account: "Account",
        polling: bool = True,
    ):
        super().__init__(
            type=EventType.AGENT_SEND_REGISTRATION.value,
            account=account,
            source=agent.uri,
            details=agent.registration_info,
        )


class ServerSendRegistrationEvent(Event):
    def __init__(
        self,
        account: "Account",
        server: "Server",
    ):
        super().__init__(
            type=EventType.SERVER_SEND_REGISTRATION.value,
            account=account,
            source=server.uri,
            details=server.registration_info,
        )


class CaseStartEvent(Event):
    def __init__(self, case: "Case", account: "Account"):
        print(f"CASE_START_EVENT {case} - {account}")
        super().__init__(
            type=EventType.CASE_START.value,
            account=account,
            source=case,
            details=case.to_dict,
        )


class CaseUpdateEvent(Event):
    def __init__(self, case: "Case", account: "Account"):
        super().__init__(
            type=EventType.CASE_UPDATE.value,
            account=account,
            source=case,
            details=case.to_dict,
        )
