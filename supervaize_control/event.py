# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from enum import Enum
from typing import Any, ClassVar, Dict

from .__version__ import VERSION
from .account import Account
from .agent import Agent
from .case import Case, CaseNodeUpdate
from .common import SvBaseModel
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


class EventModel(SvBaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    source: str
    account: Account
    type: EventType
    details: Dict[str, Any]


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

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def payload(self) -> Dict[str, Any]:
        """
        Returns the payload for the event.
        This must be a dictionary that can be serialized to JSON to be sent in the request body.
        """
        return {
            "name": f"{self.type.value} {self.source}",
            "source": f"{self.source}",
            "account": f"{self.account.id}",
            "event_type": f"{self.type.value}",
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
    ) -> None:
        super().__init__(
            type=EventType.AGENT_REGISTER,
            account=account,
            source=agent.uri,
            details=agent.registration_info | {"polling": polling},
        )


class ServerRegisterEvent(Event):
    def __init__(
        self,
        account: "Account",
        server: "Server",
    ) -> None:
        super().__init__(
            type=EventType.SERVER_REGISTER,
            account=account,
            source=server.uri,
            details=server.registration_info,
        )


class CaseStartEvent(Event):
    def __init__(self, case: "Case", account: "Account") -> None:
        super().__init__(
            type=EventType.CASE_START,
            account=account,
            source=case.uri,
            details=case.to_dict,
        )


class CaseUpdateEvent(Event):
    def __init__(
        self, case: "Case", account: "Account", update: "CaseNodeUpdate"
    ) -> None:
        super().__init__(
            type=EventType.CASE_UPDATE,
            account=account,
            source=case.uri,
            details=update.to_dict,
        )
