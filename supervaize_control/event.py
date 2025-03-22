# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from enum import Enum
from typing import ClassVar

from pydantic import BaseModel

from .__version__ import VERSION
from .account import Account
from .agent import Agent
from .case import Case
from .server import Server


class EventType(str, Enum):
    AGENT_REGISTER = "agent.register"
    SERVER_REGISTER = "server.register"
    AGENT_WAKEUP = "agent.wakeup"
    AGENT_SEND_ANOMALY = "agent.anomaly"
    INTERMEDIARY = "agent.intermediary"
    JOB_START = "agent.job.start"
    JOB_END = "agent.job.end"
    JOB_STATUS = "agent.job.status"
    JOB_RESULT = "agent.job.result"
    JOB_ERROR = "agent.job.error"
    CASE_START = "agent.case.start"
    CASE_END = "agent.case.end"
    CASE_STATUS = "agent.case.status"
    CASE_RESULT = "agent.case.result"
    CASE_UPDATE = "agent.case.update"


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

    Tests in tests/test_event.py
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


class AgentRegisterEvent(Event):
    """Event sent when an agent registers with the control system.

    Test in tests/test_agent_register_event.py
    """

    def __init__(
        self,
        agent: "Agent",
        account: "Account",
        polling: bool = True,
    ):
        super().__init__(
            type=EventType.AGENT_REGISTER.value,
            account=account,
            source=agent.uri,
            details=agent.registration_info | {"polling": polling},
        )


class ServerRegisterEvent(Event):
    def __init__(
        self,
        account: "Account",
        server: "Server",
    ):
        super().__init__(
            type=EventType.SERVER_REGISTER.value,
            account=account,
            source=server.uri,
            details=server.registration_info,
        )


class CaseStartEvent(Event):
    def __init__(self, case: "Case", account: "Account"):
        super().__init__(
            type=EventType.CASE_START.value,
            account=account,
            source=case.uri,
            details=case.to_dict,
        )


class CaseUpdateEvent(Event):
    def __init__(self, case: "Case", account: "Account"):
        super().__init__(
            type=EventType.CASE_UPDATE.value,
            account=account,
            source=case.uri,
            details=case.to_dict,
        )
