# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from typing import Dict, List, Any, TYPE_CHECKING
from fastapi import APIRouter

from ...common import log
from ...routes import handle_route_errors
from .model import create_agent_detail, list_agents, create_health_data

if TYPE_CHECKING:
    from ...server import Server


def create_routes(server: "Server") -> APIRouter:
    """Create ACP protocol routes for the server."""
    router = APIRouter(prefix="/agents", tags=["Protocol ACP"])
    base_url = server.public_url

    @router.get(
        "",
        summary="ACP Agents Discovery",
        description="Returns a list of all agents according to ACP protocol specification",
        response_model=List[Dict[str, Any]],
    )
    @handle_route_errors()
    async def get_acp_agents() -> List[Dict[str, Any]]:
        """Get a list of all available agents in ACP format."""
        log.info("[ACP] GET /agents [Agent discovery]")
        return list_agents(server.agents, base_url)

    # Create explicit routes for each agent
    for agent in server.agents:

        def create_agent_route(current_agent):
            route_path = f"/{current_agent.slug}"

            @router.get(
                route_path,
                summary=f"ACP Agent Detail for {current_agent.name}",
                description=f"Returns details for agent {current_agent.name} according to ACP protocol specification",
                response_model=Dict[str, Any],
            )
            @handle_route_errors()
            async def get_agent_detail() -> Dict[str, Any]:
                """Get details for a specific agent in ACP format."""
                log.info(f"[ACP] GET /agents/{current_agent.slug} [Agent detail]")
                return create_agent_detail(current_agent, base_url)

        # Call the closure function with the current agent
        create_agent_route(agent)

    @router.get(
        "/health",
        summary="ACP Health Status",
        description="Returns health information about the server and agents",
        response_model=Dict[str, Any],
    )
    @handle_route_errors()
    async def get_acp_health() -> Dict[str, Any]:
        """Get health information for the server and all agents."""
        log.info("[ACP] GET /agents/health [Health status]")
        return create_health_data(server.agents)

    return router
