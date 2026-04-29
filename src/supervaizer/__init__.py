# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Public Supervaizer SDK surface.

Exports are resolved lazily so contract-only consumers such as Studio can import
``supervaizer.contracts`` without loading the controller runtime.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str | None]] = {
    "protocol": ("supervaizer.protocol", None),
    "Account": ("supervaizer.account", "Account"),
    "Agent": ("supervaizer.agent", "Agent"),
    "AgentCustomMethodParams": ("supervaizer.agent", "AgentCustomMethodParams"),
    "AgentMethod": ("supervaizer.agent", "AgentMethod"),
    "AgentMethodField": ("supervaizer.agent", "AgentMethodField"),
    "AgentMethodParams": ("supervaizer.agent", "AgentMethodParams"),
    "AgentMethods": ("supervaizer.agent", "AgentMethods"),
    "AgentResponse": ("supervaizer.agent", "AgentResponse"),
    "FieldTypeEnum": ("supervaizer.agent", "FieldTypeEnum"),
    "ApiError": ("supervaizer.common", "ApiError"),
    "ApiResult": ("supervaizer.common", "ApiResult"),
    "ApiSuccess": ("supervaizer.common", "ApiSuccess"),
    "Case": ("supervaizer.case", "Case"),
    "CaseNode": ("supervaizer.case", "CaseNode"),
    "CaseNodes": ("supervaizer.case", "CaseNodes"),
    "CaseNodeType": ("supervaizer.case", "CaseNodeType"),
    "CaseNodeUpdate": ("supervaizer.case", "CaseNodeUpdate"),
    "Cases": ("supervaizer.case", "Cases"),
    "AnalyticsDataset": ("supervaizer.analytics_resource", "AnalyticsDataset"),
    "AnalyticsFilter": ("supervaizer.analytics_resource", "AnalyticsFilter"),
    "AnalyticsResource": ("supervaizer.analytics_resource", "AnalyticsResource"),
    "AnalyticsResourceContext": (
        "supervaizer.analytics_resource",
        "AnalyticsResourceContext",
    ),
    "DataResource": ("supervaizer.data_resource", "DataResource"),
    "DataResourceContext": ("supervaizer.data_resource", "DataResourceContext"),
    "DataResourceField": ("supervaizer.data_resource", "DataResourceField"),
    "Editable": ("supervaizer.data_resource", "Editable"),
    "FieldType": ("supervaizer.data_resource", "FieldType"),
    "AgentRegisterEvent": ("supervaizer.event", "AgentRegisterEvent"),
    "CaseStartEvent": ("supervaizer.event", "CaseStartEvent"),
    "CaseUpdateEvent": ("supervaizer.event", "CaseUpdateEvent"),
    "Event": ("supervaizer.event", "Event"),
    "JobFinishedEvent": ("supervaizer.event", "JobFinishedEvent"),
    "JobStartConfirmationEvent": ("supervaizer.event", "JobStartConfirmationEvent"),
    "ServerRegisterEvent": ("supervaizer.event", "ServerRegisterEvent"),
    "EntityEvents": ("supervaizer.lifecycle", "EntityEvents"),
    "EntityLifecycle": ("supervaizer.lifecycle", "EntityLifecycle"),
    "EntityStatus": ("supervaizer.lifecycle", "EntityStatus"),
    "Job": ("supervaizer.job", "Job"),
    "JobContext": ("supervaizer.job", "JobContext"),
    "JobInstructions": ("supervaizer.job", "JobInstructions"),
    "JobResponse": ("supervaizer.job", "JobResponse"),
    "Jobs": ("supervaizer.job", "Jobs"),
    "Parameter": ("supervaizer.parameter", "Parameter"),
    "ParametersSetup": ("supervaizer.parameter", "ParametersSetup"),
    "Server": ("supervaizer.server", "Server"),
    "create_error_response": ("supervaizer.server_utils", "create_error_response"),
    "ErrorResponse": ("supervaizer.server_utils", "ErrorResponse"),
    "ErrorType": ("supervaizer.server_utils", "ErrorType"),
    "Telemetry": ("supervaizer.telemetry", "Telemetry"),
    "TelemetryCategory": ("supervaizer.telemetry", "TelemetryCategory"),
    "TelemetrySeverity": ("supervaizer.telemetry", "TelemetrySeverity"),
    "TelemetryType": ("supervaizer.telemetry", "TelemetryType"),
    "AgentMethodContract": ("supervaizer.contracts", "AgentMethodContract"),
    "AgentMethodsContract": ("supervaizer.contracts", "AgentMethodsContract"),
    "AgentRegistrationContract": ("supervaizer.contracts", "AgentRegistrationContract"),
    "AnalyticsFilterContract": ("supervaizer.contracts", "AnalyticsFilterContract"),
    "AnalyticsResourceContract": (
        "supervaizer.contracts",
        "AnalyticsResourceContract",
    ),
    "AnalyticsResourceContextContract": (
        "supervaizer.contracts",
        "AnalyticsResourceContextContract",
    ),
    "ControllerContract": ("supervaizer.contracts", "ControllerContract"),
    "ControllerEndpoint": ("supervaizer.contracts", "ControllerEndpoint"),
    "DataResourceContract": ("supervaizer.contracts", "DataResourceContract"),
    "DataResourceFieldContract": ("supervaizer.contracts", "DataResourceFieldContract"),
    "DynamicChoicesRequest": ("supervaizer.contracts", "DynamicChoicesRequest"),
    "DynamicChoicesResponse": ("supervaizer.contracts", "DynamicChoicesResponse"),
    "EventType": ("supervaizer.contracts", "EventType"),
    "JobStartRequest": ("supervaizer.contracts", "JobStartRequest"),
    "ServerRegistrationContract": (
        "supervaizer.contracts",
        "ServerRegistrationContract",
    ),
    "build_data_resource_context_headers": (
        "supervaizer.contracts",
        "build_data_resource_context_headers",
    ),
    "build_analytics_context_headers": (
        "supervaizer.contracts",
        "build_analytics_context_headers",
    ),
    "controller_contract_info": ("supervaizer.contracts", "controller_contract_info"),
    "resolve_controller_endpoint": (
        "supervaizer.contracts",
        "resolve_controller_endpoint",
    ),
}

__all__ = sorted(_EXPORTS)


def _rebuild_forward_refs() -> None:
    """Resolve forward refs for models that depend on the public import order."""
    try:
        case_module = import_module("supervaizer.case")
        agent_module = import_module("supervaizer.agent")
        case_module.Case.model_rebuild()
        agent_module.AgentResponse.model_rebuild()
    except Exception:
        pass


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module 'supervaizer' has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = module if attr_name is None else getattr(module, attr_name)
    globals()[name] = value
    if module_name in {"supervaizer.agent", "supervaizer.case"}:
        _rebuild_forward_refs()
    return value
