# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import os
from supervaizer.parameter import Parameter, ParametersSetup


def test_parameter_creation() -> None:
    parameter = Parameter(name="test")
    assert parameter.name == "test"
    assert parameter.value is None
    assert parameter.description is None
    assert parameter.is_environment is False


def test_parameter_with_all_fields(parameter_fixture: Parameter) -> None:
    assert parameter_fixture.name == "test_parameter"
    assert parameter_fixture.value == "test_value"
    assert parameter_fixture.description == "test description"


def test_parameters_setup_creation() -> None:
    parameters_setup = ParametersSetup.from_list(
        parameter_list=[
            Parameter(name="parameter1", value="value1"),
            Parameter(name="parameter2", value="value2", description="desc2"),
        ]
    )
    assert isinstance(parameters_setup, ParametersSetup)
    assert parameters_setup.definitions.keys() == {"parameter1", "parameter2"}


def test_parameters_initialization(parameters_setup_fixture: ParametersSetup) -> None:
    assert len(parameters_setup_fixture.definitions) == 2
    assert all(
        isinstance(p, Parameter) for p in parameters_setup_fixture.definitions.values()
    )
    assert "parameter1" in parameters_setup_fixture.definitions
    assert "parameter2" in parameters_setup_fixture.definitions


def test_parameter_set_value(parameter_fixture: Parameter) -> None:
    assert parameter_fixture.is_environment is False
    assert parameter_fixture.name == "test_parameter"
    assert parameter_fixture.value == "test_value"
    assert parameter_fixture.description == "test description"

    # Set value
    parameter_fixture.set_value("new_value")
    assert parameter_fixture.value == "new_value"
    assert "test_parameter" not in os.environ


def test_parameter_set_value_in_environment(parameter_fixture: Parameter) -> None:
    os.environ["test_parameter"] = "old_value"
    assert os.environ.get("test_parameter") == "old_value"
    parameter_fixture.is_environment = True
    parameter_fixture.set_value("newer_value")

    assert parameter_fixture.value == "newer_value"
    assert "test_parameter" in os.environ
    assert os.environ["test_parameter"] == "newer_value"


def test_parameters_setup_update_values_from_server(
    parameters_setup_fixture: ParametersSetup,
) -> None:
    parameters_setup_fixture.update_values_from_server(
        server_parameters_setup=[
            {"name": "parameter1", "value": "new_value1"},
            {"name": "parameter2", "value": "new_value2"},
        ]
    )
    assert isinstance(parameters_setup_fixture.definitions["parameter1"], Parameter)
    assert isinstance(parameters_setup_fixture.definitions["parameter2"], Parameter)
    assert parameters_setup_fixture.definitions["parameter1"].value == "new_value1"
    assert parameters_setup_fixture.definitions["parameter2"].value == "new_value2"
