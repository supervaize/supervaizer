# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.


import json

from .common import SvBaseModel


class ParameterModel(SvBaseModel):
    name: str
    description: str | None = None
    is_secret: bool = False
    value: str | None = None


class Parameter(ParameterModel):
    @property
    def registration_info(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "is_secret": self.is_secret,
        }


class ParametersSetup(SvBaseModel):
    definitions: dict[str, Parameter]

    @classmethod
    def from_list(cls, parameter_list: list[Parameter]) -> "ParametersSetup":
        return cls(
            definitions={parameter.name: parameter for parameter in parameter_list}
        )

    @property
    def registration_info(self) -> dict:
        return {
            "parameters": [
                parameter.registration_info for parameter in self.definitions.values()
            ],
        }


class Parameters(SvBaseModel):
    """
    Incoming parameters are received from the SaaS platform. They are encrypted with the agent's public key.
    """

    values: dict[str, str]

    @classmethod
    def from_str(cls, unencrypted: str) -> "Parameters":
        """
        Create a Parameters object from json string of parameters         Not to be used in production - for testing purposes only.
        """
        return cls(values=json.loads(unencrypted))
