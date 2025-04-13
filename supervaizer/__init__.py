# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from .account import Account
from .agent import (
    Agent,
    AgentCustomMethodParams,
    AgentMethod,
    AgentMethodParams,
    AgentMethods,
)
from .case import Case, CaseNode, CaseNodeUpdate, CaseStatus
from .common import ApiError, ApiResult, ApiSuccess
from .event import (
    AgentRegisterEvent,
    CaseUpdateEvent,
    JobFinishedEvent,
    JobStartConfirmationEvent,
    Event,
    EventType,
    ServerRegisterEvent,
    CaseStartEvent,
)
from .job import Job, JobInstructions, JobContext, JobResponse, JobStatus
from .parameter import Parameter, Parameters, ParametersSetup
from .server import Server
from .server_utils import ErrorResponse, ErrorType, create_error_response
from .telemetry import Telemetry, TelemetryCategory, TelemetrySeverity, TelemetryType

__all__ = [
    "Agent",
    "AgentMethods",
    "Server",
    "Account",
    "Telemetry",
    "TelemetryType",
    "TelemetryCategory",
    "TelemetrySeverity",
    "Event",
    "EventType",
    "AgentRegisterEvent",
    "AgentMethod",
    "AgentCustomMethodParams",
    "AgentMethodParams",
    "ApiResult",
    "ApiSuccess",
    "ApiError",
    "JobResponse",
    "Job",
    "JobStatus",
    "JobContext",
    "JobInstructions",
    "Case",
    "CaseNodeUpdate",
    "CaseNode",
    "CaseNodeUpdate",
    "CaseStartEvent",
    "CaseUpdateEvent",
    "CaseStatus",
    "ServerRegisterEvent",
    "Parameter",
    "Parameters",
    "ParametersSetup",
    "ErrorResponse",
    "ErrorType",
    "create_error_response",
    "JobFinishedEvent",
    "JobStartConfirmationEvent",
]

# Rebuild models to resolve forward references after all imports are done
Case.model_rebuild()
