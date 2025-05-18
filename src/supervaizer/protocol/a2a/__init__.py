# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""A2A protocol implementation for SUPERVAIZER."""

from supervaizer.protocol.a2a.model import (
    create_agent_card,
    create_agents_list,
    create_health_data,
)
from supervaizer.protocol.a2a.routes import create_routes

__all__ = [
    "create_agent_card",
    "create_agents_list",
    "create_health_data",
    "create_routes",
]
