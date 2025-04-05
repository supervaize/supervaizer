# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


# Empty file to mark directory as a Python package
from .mock_api_responses import (
    AUTH_ERROR_RESPONSE,
    SERVER_REGISTER_RESPONSE,
    SERVER_REGISTER_RESPONSE_NO_AGENTS_ERROR,
    SERVER_REGISTER_RESPONSE_UNKNOWN_AGENTS_ERROR,
    SERVER_REGISTER_RESPONSE_UNKNOWN_AND_UNKNOWN_AGENTS_ERROR,
    WAKEUP_EVENT_RESPONSE,
)

__all__ = [
    "WAKEUP_EVENT_RESPONSE",
    "SERVER_REGISTER_RESPONSE",
    "SERVER_REGISTER_RESPONSE_NO_AGENTS_ERROR",
    "SERVER_REGISTER_RESPONSE_UNKNOWN_AGENTS_ERROR",
    "AUTH_ERROR_RESPONSE",
    "SERVER_REGISTER_RESPONSE_UNKNOWN_AND_UNKNOWN_AGENTS_ERROR",
]
