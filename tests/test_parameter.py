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


def test_parameters_setup_value(parameters_setup_fixture: ParametersSetup) -> None:
    assert parameters_setup_fixture.value("parameter1") == "value1"
    assert parameters_setup_fixture.value("parameter2") == "value2"
    assert parameters_setup_fixture.value("parameterUNKNOWN") is None


def test_parameters_setup_validation_valid_parameters() -> None:
    """Test parameter validation with valid parameters."""
    parameters_setup = ParametersSetup.from_list(
        [
            Parameter(name="string_param", value="test", is_required=True),
            Parameter(name="int_param", value="42", is_required=True),
            Parameter(name="bool_param", value="true", is_required=False),
            Parameter(name="list_param", value="a,b", is_required=False),
        ]
    )

    test_parameters = {
        "string_param": "new_string",
        "int_param": "100",
        "bool_param": "false",
        "list_param": "x,y",
    }

    result = parameters_setup.validate_parameters(test_parameters)
    assert result["valid"] is True
    assert len(result["errors"]) == 0
    assert len(result["invalid_parameters"]) == 0


def test_parameters_setup_validation_invalid_types() -> None:
    """Test parameter validation with invalid types."""
    parameters_setup = ParametersSetup.from_list(
        [
            Parameter(name="string_param", value="test", is_required=True),
            Parameter(name="int_param", value="42", is_required=True),
            Parameter(name="bool_param", value="true", is_required=False),
        ]
    )

    test_parameters = {
        "string_param": 123,  # Should be string
        "int_param": "not_a_number",  # Should be string (Parameter values are always strings)
        "bool_param": "not_a_bool",  # Should be string
    }

    result = parameters_setup.validate_parameters(test_parameters)
    assert result["valid"] is False
    assert len(result["errors"]) == 1  # Only unknown parameter type error
    assert "string_param" in result["invalid_parameters"]
    assert "must be a string" in result["invalid_parameters"]["string_param"]


def test_parameters_setup_validation_missing_required() -> None:
    """Test parameter validation with missing required parameters."""
    parameters_setup = ParametersSetup.from_list(
        [
            Parameter(name="required_param", value="test", is_required=True),
            Parameter(name="optional_param", value="test", is_required=False),
        ]
    )

    test_parameters = {
        "optional_param": "present",
        # required_param is missing
    }

    result = parameters_setup.validate_parameters(test_parameters)
    assert result["valid"] is False
    assert len(result["errors"]) == 1
    assert "required_param" in result["invalid_parameters"]
    assert "is missing" in result["invalid_parameters"]["required_param"]


def test_parameters_setup_validation_unknown_parameters() -> None:
    """Test parameter validation with unknown parameters."""
    parameters_setup = ParametersSetup.from_list(
        [
            Parameter(name="known_param", value="test", is_required=True),
        ]
    )

    test_parameters = {"known_param": "valid_value", "unknown_param": "should_fail"}

    result = parameters_setup.validate_parameters(test_parameters)
    assert result["valid"] is False
    assert len(result["errors"]) == 1
    assert "unknown_param" in result["invalid_parameters"]
    assert "Unknown parameter" in result["invalid_parameters"]["unknown_param"]


def test_parameters_setup_validation_none_values() -> None:
    """Test parameter validation with None values for optional parameters."""
    parameters_setup = ParametersSetup.from_list(
        [
            Parameter(name="required_param", value="test", is_required=True),
            Parameter(name="optional_param", value="test", is_required=False),
        ]
    )

    test_parameters = {"required_param": "present", "optional_param": None}

    result = parameters_setup.validate_parameters(test_parameters)
    assert result["valid"] is True
    assert len(result["errors"]) == 0
    assert len(result["invalid_parameters"]) == 0


def test_parameters_setup_validation_float_types() -> None:
    """Test parameter validation with float types."""
    parameters_setup = ParametersSetup.from_list(
        [
            Parameter(name="float_param", value="3.14", is_required=True),
        ]
    )

    # Test with float string
    test_parameters_float = {"float_param": "2.718"}
    result_float = parameters_setup.validate_parameters(test_parameters_float)
    assert result_float["valid"] is True

    # Test with integer string
    test_parameters_int = {"float_param": "42"}
    result_int = parameters_setup.validate_parameters(test_parameters_int)
    assert result_int["valid"] is True

    # Test with invalid type
    test_parameters_invalid = {"float_param": 123}  # Should be string
    result_invalid = parameters_setup.validate_parameters(test_parameters_invalid)
    assert result_invalid["valid"] is False
    assert "must be a string" in result_invalid["invalid_parameters"]["float_param"]


def test_parameters_setup_validation_list_and_dict_types() -> None:
    """Test parameter validation with list and dict types."""
    parameters_setup = ParametersSetup.from_list(
        [
            Parameter(name="list_param", value="", is_required=True),
            Parameter(name="dict_param", value="", is_required=True),
        ]
    )

    test_parameters = {"list_param": "item1,item2", "dict_param": "key:value"}

    result = parameters_setup.validate_parameters(test_parameters)
    assert result["valid"] is True

    # Test with invalid types
    test_parameters_invalid = {
        "list_param": 123,  # Should be string
        "dict_param": True,  # Should be string
    }

    result_invalid = parameters_setup.validate_parameters(test_parameters_invalid)
    assert result_invalid["valid"] is False
    assert "must be a string" in result_invalid["invalid_parameters"]["list_param"]
    assert "must be a string" in result_invalid["invalid_parameters"]["dict_param"]
