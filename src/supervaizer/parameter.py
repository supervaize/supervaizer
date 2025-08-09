# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


from pydantic import Field
import os
from typing import Any, Dict, List

from supervaizer.common import SvBaseModel, log


class ParameterModel(SvBaseModel):
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


class Parameter(ParameterModel):
    @property
    def to_dict(self) -> Dict[str, Any]:
        """
        Override the to_dict method to handle the value field.
        """
        data = self.model_dump(mode="json")
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
    definitions: Dict[str, Parameter]

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
