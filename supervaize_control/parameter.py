# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from typing import List

from .common import SvBaseModel


class Parameter(SvBaseModel):
    name: str
    value: str = None
    description: str | None = None
    is_secret: bool = False

    @property
    def registration_info(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "description": self.description,
            "is_secret": self.is_secret,
        }


class Parameters(SvBaseModel):
    parameters: dict[str, Parameter]

    def __init__(self, parameters: List[Parameter]):
        super().__init__(
            parameters={parameter.name: parameter for parameter in parameters}
        )

    def get_parameter(self, name: str) -> Parameter:
        return self.parameters[name]

    @property
    def registration_info(self) -> dict:
        return {
            "parameters": [
                parameter.registration_info for parameter in self.parameters.values()
            ],
        }
