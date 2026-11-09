# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize optional v2 registration model conversion."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from supervaizer.contracts import (
    V2AgentMethod,
    V2AgentMethods,
    V2WorkspaceBindingDefinition,
    _agent_methods,
    _workspace_binding,
)


def test_workspace_binding_converter_returns_none_for_missing_value() -> None:
    assert _workspace_binding(None) is None


def test_agent_methods_converter_returns_none_for_missing_value() -> None:
    assert _agent_methods(None) is None


def test_workspace_binding_converter_validates_dict_to_contract_model() -> None:
    binding = _workspace_binding({
        "required": True,
        "modes": ["bind_existing"],
    })

    assert isinstance(binding, V2WorkspaceBindingDefinition)
    assert binding.required is True
    assert binding.existing is not None


def test_agent_methods_converter_validates_dict_to_contract_model() -> None:
    methods = _agent_methods({"refresh": {"method": "agent.refresh"}})

    assert isinstance(methods, V2AgentMethods)
    assert methods.refresh is not None
    assert methods.refresh.method == "agent.refresh"


def test_workspace_binding_converter_keeps_existing_contract_model_identity() -> None:
    binding = V2WorkspaceBindingDefinition(modes=["bind_existing"])

    assert _workspace_binding(binding) is binding


def test_agent_methods_converter_keeps_existing_contract_model_identity() -> None:
    methods = V2AgentMethods(refresh=V2AgentMethod(method="agent.refresh"))

    assert _agent_methods(methods) is methods


def test_workspace_binding_converter_preserves_model_validation_error() -> None:
    value = {"required": True}

    with pytest.raises(ValidationError) as converted_error:
        _workspace_binding(value)
    with pytest.raises(ValidationError) as model_error:
        V2WorkspaceBindingDefinition.model_validate(value)

    assert converted_error.value.json() == model_error.value.json()


def test_agent_methods_converter_preserves_model_validation_error() -> None:
    value: dict[str, Any] = {"refresh": {}}

    with pytest.raises(ValidationError) as converted_error:
        _agent_methods(value)
    with pytest.raises(ValidationError) as model_error:
        V2AgentMethods.model_validate(value)

    assert converted_error.value.json() == model_error.value.json()
