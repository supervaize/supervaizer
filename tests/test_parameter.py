# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest

from supervaize_control.parameter import Parameter


def test_parameter_creation():
    parameter = Parameter(name="test")
    assert parameter.name == "test"
    assert parameter.value is None
    assert parameter.description is None


def test_parameter_with_all_fields(parameter_fixture):
    assert parameter_fixture.name == "test_parameter"
    assert parameter_fixture.value == "test_value"
    assert parameter_fixture.description == "test description"


def test_parameters_initialization(parameters_fixture, parameters_list_fixture):
    assert len(parameters_fixture.parameters) == 2
    assert all(isinstance(p, Parameter) for p in parameters_fixture.parameters.values())
    assert "parameter1" in parameters_fixture.parameters
    assert "parameter2" in parameters_fixture.parameters


def test_get_parameter(parameters_fixture):
    parameter = parameters_fixture.get_parameter("parameter1")
    assert isinstance(parameter, Parameter)
    assert parameter.name == "parameter1"
    assert parameter.value == "value1"


def test_get_nonexistent_parameter(parameters_fixture):
    with pytest.raises(KeyError):
        parameters_fixture.get_parameter("nonexistent")
