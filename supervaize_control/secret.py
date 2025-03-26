# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from typing import List

from .common import SvBaseModel


class Secret(SvBaseModel):
    name: str
    value: str = None
    description: str | None = None


class Secrets(SvBaseModel):
    secrets: dict[str, Secret]

    def __init__(self, secrets: List[Secret]):
        super().__init__(secrets={secret.name: secret for secret in secrets})

    def get_secret(self, name: str) -> Secret:
        return self.secrets[name]
