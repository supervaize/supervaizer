# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from enum import Enum
from typing import Any, ClassVar, Dict, TYPE_CHECKING
from .__version__ import VERSION
from .common import SvBaseModel

if TYPE_CHECKING:
    from .agent import Agent
    from .case import Case, CaseNodeUpdate
    from .server import Server
    from .job import Job


class EventType(str, Enum):
    AGENT_REGISTER = "agent.register"
    SERVER_REGISTER = "server.register"
    AGENT_WAKEUP = "agent.wakeup"
    AGENT_SEND_ANOMALY = "agent.anomaly"
    INTERMEDIARY = "agent.intermediary"
    JOB_START_CONFIRMATION = "agent.job.start.confirmation"
    JOB_FINISHED = "agent.job.finished"
    JOB_STATUS = "agent.job.status"
    JOB_RESULT = "agent.job.result"
    JOB_ERROR = "agent.job.error"
    CASE_START = "agent.case.start"
    CASE_END = "agent.case.end"
    CASE_STATUS = "agent.case.status"
    CASE_RESULT = "agent.case.result"
    CASE_UPDATE = "agent.case.update"


class EventModel(SvBaseModel):
    supervaizer_VERSION: ClassVar[str] = VERSION
    source: str
    account: Any  # Use Any to avoid Pydantic type resolution issues
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
            "source": f"{self.source}",
            "workspace": f"{self.account.workspace_id}",
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
        account: Any,  # Use Any to avoid type resolution issues
        polling: bool = True,
    ) -> None:
        super().__init__(
            type=EventType.AGENT_REGISTER,
            account=account,
            source=agent.path,
            details=agent.registration_info | {"polling": polling},
        )


class ServerRegisterEvent(Event):
    def __init__(
        self,
        account: Any,  # Use Any to avoid type resolution issues
        server: "Server",
    ) -> None:
        super().__init__(
            type=EventType.SERVER_REGISTER,
            source=server.uri,
            account=account,
            details=server.registration_info,
        )


class JobStartConfirmationEvent(Event):
    def __init__(
        self,
        job: "Job",
        account: Any,  # Use Any to avoid type resolution issues
    ) -> None:
        super().__init__(
            type=EventType.JOB_START_CONFIRMATION,
            account=account,
            source=job.id,
            details=job.to_dict,
        )


class JobFinishedEvent(Event):
    def __init__(self, job: "Job", account: Any) -> None:
        super().__init__(
            type=EventType.JOB_FINISHED,
            account=account,
            source=job.id,
            details=job.to_dict,
        )


class CaseStartEvent(Event):
    def __init__(
        self, case: "Case", account: Any
    ) -> None:  # Use Any to avoid type resolution issues
        super().__init__(
            type=EventType.CASE_START,
            account=account,
            source=case.uri,
            details=case.to_dict,
        )


class CaseUpdateEvent(Event):
    def __init__(
        self,
        case: "Case",
        account: Any,
        update: "CaseNodeUpdate",
    ) -> None:
        super().__init__(
            type=EventType.CASE_UPDATE,
            account=account,
            source=case.uri,
            details=update.to_dict,
        )
