# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


from supervaize_control.parameter import Parameter, ParametersSetup


def test_parameter_creation():
    parameter = Parameter(name="test")
    assert parameter.name == "test"
    assert parameter.value is None
    assert parameter.description is None


def test_parameter_with_all_fields(parameter_fixture):
    assert parameter_fixture.name == "test_parameter"
    assert parameter_fixture.value == "test_value"
    assert parameter_fixture.description == "test description"


def test_parameters_setup_creation():
    parameters_setup = ParametersSetup.from_list(
        parameter_list=[
            Parameter(name="parameter1", value="value1"),
            Parameter(name="parameter2", value="value2", description="desc2"),
        ]
    )
    assert isinstance(parameters_setup, ParametersSetup)
    assert parameters_setup.definitions.keys() == {"parameter1", "parameter2"}


def test_parameters_initialization(parameters_setup_fixture):
    assert len(parameters_setup_fixture.definitions) == 2
    assert all(
        isinstance(p, Parameter) for p in parameters_setup_fixture.definitions.values()
    )
    assert "parameter1" in parameters_setup_fixture.definitions
    assert "parameter2" in parameters_setup_fixture.definitions
