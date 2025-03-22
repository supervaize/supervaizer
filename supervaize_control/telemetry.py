# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from enum import Enum
from typing import ClassVar

from pydantic import BaseModel

from .__version__ import VERSION


class TelemetryType(str, Enum):
    LOGS = "logs"
    METRICS = "metrics"
    EVENTS = "events"
    TRACES = "traces"
    EXCEPTIONS = "exceptions"
    DIAGNOSTICS = "diagnostics"
    CUSTOM = "custom"


class TelemetryCategory(str, Enum):
    SYSTEM = "system"
    APPLICATION = "application"
    USER_INTERACTION = "user_interaction"
    SECURITY = "security"
    BUSINESS = "business"
    ENVIRONMENT = "environment"
    NETWORKING = "networking"
    CUSTOM = "custom"


class TelemetrySeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TelemetryModel(BaseModel):
    SUPERVAIZE_CONTROL_VERSION: ClassVar[str] = VERSION
    agentId: str
    type: TelemetryType
    category: TelemetryCategory
    severity: TelemetrySeverity
    details: dict


class Telemetry(TelemetryModel):
    """Base class for all telemetry data in the Supervaize Control system.

    Telemetry represents monitoring and observability data sent from agents to the control system.
    This includes logs, metrics, events, traces, exceptions, diagnostics and custom telemetry.

    Inherits from TelemetryModel which defines the core telemetry attributes:
        - agentId: The ID of the agent sending the telemetry
        - type: The TelemetryType enum indicating the telemetry category (logs, metrics, etc)
        - category: The TelemetryCategory enum for the functional area (system, application, etc)
        - severity: The TelemetrySeverity enum indicating importance (debug, info, warning, etc)
        - details: A dictionary containing telemetry-specific details
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def payload(self) -> dict:
        return {
            "agentId": self.agentId,
            "eventType": self.type.value,
            "severity": self.severity.value,
            "eventCategory": self.category.value,
            "details": self.details,
        }
