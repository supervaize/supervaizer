# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""API router: machine-to-machine surface, API key required."""  # <-- ADDED

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from supervaizer.access import require_api_key  # <-- ADDED

if TYPE_CHECKING:
    from supervaizer.server import Server


def create_api_router(server: "Server") -> APIRouter:  # <-- ADDED
    """Build and return the /api router wired to *server*.

    Router-level ``require_api_key`` covers every sub-route.
    Scope-specific routes add ``Depends(require_scope(...))`` themselves.
    """
    from supervaizer.data_routes import create_agent_data_routes
    from supervaizer.routes import (
        create_agents_routes,
        create_default_routes,
        create_utils_routes,
    )

    api_router = APIRouter(
        prefix="/api",
        dependencies=[Depends(require_api_key)],  # <-- ADDED
    )

    # Supervision + agent API routes
    api_router.include_router(create_default_routes(server))
    api_router.include_router(create_utils_routes(server))
    api_router.include_router(create_agents_routes(server))

    # Data resource CRUD routes
    for agent in server.agents:
        if agent.data_resources:
            api_router.include_router(create_agent_data_routes(server, agent))

    # Agent custom routes (full path: /api/agents/{slug}/... plus each route on the nested router)
    for agent in server.agents:
        if agent.custom_routes:
            api_router.include_router(
                agent.custom_routes,
                prefix=f"/agents/{agent.slug}",
            )

    return api_router
