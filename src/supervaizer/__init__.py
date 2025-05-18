# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from supervaizer import protocol
from supervaizer.account import Account
from supervaizer.agent import (
    Agent,
    AgentCustomMethodParams,
    AgentMethod,
    AgentMethodParams,
    AgentMethods,
)
from supervaizer.case import Case, CaseNode, CaseNodeUpdate, CaseNoteType
from supervaizer.common import ApiError, ApiResult, ApiSuccess
from supervaizer.event import (
    AgentRegisterEvent,
    CaseStartEvent,
    CaseUpdateEvent,
    Event,
    EventType,
    JobFinishedEvent,
    JobStartConfirmationEvent,
    ServerRegisterEvent,
)
from supervaizer.job import Job, JobContext, JobInstructions, JobResponse, Jobs
from supervaizer.lifecycle import EntityEvents, EntityLifecycle, EntityStatus
from supervaizer.parameter import Parameter, Parameters, ParametersSetup
from supervaizer.server import Server
from supervaizer.server_utils import ErrorResponse, ErrorType, create_error_response
from supervaizer.telemetry import (
    Telemetry,
    TelemetryCategory,
    TelemetrySeverity,
    TelemetryType,
)

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
    "EntityStatus",
    "EntityEvents",
    "EntityLifecycle",
    "AgentRegisterEvent",
    "AgentMethod",
    "AgentCustomMethodParams",
    "AgentMethodParams",
    "ApiResult",
    "ApiSuccess",
    "ApiError",
    "JobResponse",
    "Job",
    "Jobs",
    "EntityStatus",
    "EntityEvents",
    "EntityLifecycle",
    "JobContext",
    "JobInstructions",
    "Case",
    "CaseNodeUpdate",
    "CaseNode",
    "CaseNodeUpdate",
    "CaseStartEvent",
    "CaseNoteType",
    "CaseUpdateEvent",
    "ServerRegisterEvent",
    "Parameter",
    "Parameters",
    "ParametersSetup",
    "ErrorResponse",
    "ErrorType",
    "create_error_response",
    "JobFinishedEvent",
    "JobStartConfirmationEvent",
    "protocol",
]

# Rebuild models to resolve forward references after all imports are done
Case.model_rebuild()
