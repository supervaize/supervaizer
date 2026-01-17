# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from pydantic import Field
import os
from typing import Any, Dict, List

from supervaizer.common import SvBaseModel, log


class ParameterAbstract(SvBaseModel):
    """
    Base model for agent parameters that defines configuration and metadata.

    Parameters can be environment variables, secrets, or regular configuration values
    that are used by agents during execution. The Supervaize platform uses this
    model to manage parameter definitions and values.
    """

    name: str = Field(
        description="The name of the parameter, as used in the agent code"
    )
    description: str | None = Field(
        default=None,
        description="The description of the parameter, used in the Supervaize UI",
    )
    is_environment: bool = Field(
        default=False,
        description="Whether the parameter is set as an environment variable",
    )
    value: str | None = Field(
        default=None,
        description="The value of the parameter - provided by the Supervaize platform",
    )
    is_secret: bool = Field(
        default=False,
        description="Whether the parameter is a secret - hidden from the user in the Supervaize UI",
    )
    is_required: bool = Field(
        default=False,
        description="Whether the parameter is required, used in the Supervaize UI",
    )

    model_config = {
        "reference_group": "Core",
        "example_dict": {
            "name": "OPEN_API_KEY",
            "description": "OpenAPI Key",
            "is_environment": True,
            "is_secret": True,
            "is_required": True,
        },
    }


class Parameter(ParameterAbstract):
    @property
    def to_dict(self) -> Dict[str, Any]:
        """
        Override the to_dict method to handle the value field.
        """
        data = super().to_dict
        if self.is_secret:
            data["value"] = "********"
        return data

    @property
    def registration_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "is_environment": self.is_environment,
            "is_secret": self.is_secret,
            "is_required": self.is_required,
        }

    def set_value(self, value: str) -> None:
        """
        Set the value of a parameter and update the environment variable if needed.
        Note that environment is updated ONLY if set_value is called explicitly.
        Tested in tests/test_parameter.py
        """
        self.value = value
        if self.is_environment:
            os.environ[self.name] = value


class ParametersSetup(SvBaseModel):
    """
    ParametersSetup model for the Supervaize Control API.

    This represents a collection of parameters that can be used by an agent.
    It contains a dictionary of parameters, where the key is the parameter name
    and the value is the parameter object.

    Example:
    ```python
    ParametersSetup.from_list([
        Parameter(name="parameter1", value="value1"),
        Parameter(name="parameter2", value="value2", description="desc2"),
    ])
    ```
    """

    definitions: Dict[str, Parameter] = Field(
        description="A dictionary of Parameters, where the key is the parameter name and the value is the parameter object.",
    )

    model_config = {
        "reference_group": "Core",
    }

    @classmethod
    def from_list(
        cls, parameter_list: List[Parameter | Dict[str, Any]] | None
    ) -> "ParametersSetup | None":
        if not parameter_list:
            return None

        if parameter_list and isinstance(
            parameter_list[0], dict
        ):  # TODO: add test for this
            parameter_list_casted = [
                Parameter(**parameter)
                for parameter in parameter_list
                if isinstance(parameter, dict)
            ]
            parameter_list = parameter_list_casted  # type: ignore
        return cls(
            definitions={parameter.name: parameter for parameter in parameter_list}  # type: ignore
        )

    def value(self, name: str) -> str | None:
        """
        Get the value of a parameter from the environment.
        """
        parameter = self.definitions.get(name, None)
        return parameter.value if parameter else None

    @property
    def registration_info(self) -> List[Dict[str, Any]]:
        return [parameter.registration_info for parameter in self.definitions.values()]

    def update_values_from_server(
        self, server_parameters_setup: List[Dict[str, Any]]
    ) -> "ParametersSetup":
        """Update the values of the parameters from the server.

        Args:
            server_parameters_setup (List[Dict[str, Any]]): The parameters from the server.

        Raises:
            ValueError: If the parameter is not found in the definitions.

        Returns:
            ParametersSetup: The updated parameters.

        Tested in tests/test_parameter.test_parameters_setup_update_values_from_server
        """
        for parameter in server_parameters_setup:
            if parameter.get("name", None) in self.definitions.keys():
                def_parameter = self.definitions[parameter["name"]]
                def_parameter.set_value(parameter["value"])
            else:
                message = f"Parameter {parameter} not found in definitions"
                log.error(message)
                raise ValueError(message)

        return self

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters against their expected types and return validation errors.

        Args:
            parameters: Dictionary of parameter names and values to validate

        Returns:
            Dictionary with validation results:
            - "valid": bool - whether all parameters are valid
            - "errors": List[str] - list of validation error messages
            - "invalid_parameters": Dict[str, str] - parameter name to error message mapping
        """
        errors = []
        invalid_parameters = {}

        # Ensure parameters is a dictionary
        if not isinstance(parameters, dict):
            error_msg = (
                f"Parameters must be a dictionary, got {type(parameters).__name__}"
            )
            errors.append(error_msg)
            return {
                "valid": False,
                "errors": errors,
                "invalid_parameters": {"parameters": error_msg},
            }

        # First check for missing required parameters
        for param_name, param_def in self.definitions.items():
            if param_def.is_required and param_name not in parameters:
                error_msg = f"Required parameter '{param_name}' is missing"
                errors.append(error_msg)
                invalid_parameters[param_name] = error_msg

        # Then validate the provided parameters
        for param_name, param_value in parameters.items():
            if param_name not in self.definitions:
                error_msg = f"Unknown parameter '{param_name}'"
                errors.append(error_msg)
                invalid_parameters[param_name] = error_msg
                continue

            param_def = self.definitions[param_name]

            # Skip validation for None values (optional parameters)
            if param_value is None:
                continue

            # Since Parameter values are always strings, validate that input parameters are strings
            if not isinstance(param_value, str):
                error_msg = f"Parameter '{param_name}' must be a string, got {type(param_value).__name__}"
                errors.append(error_msg)
                invalid_parameters[param_name] = error_msg

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "invalid_parameters": invalid_parameters,
        }
