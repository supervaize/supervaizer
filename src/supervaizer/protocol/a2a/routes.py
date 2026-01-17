# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from typing import TYPE_CHECKING, Any, Dict

from fastapi import APIRouter

from supervaizer.common import log
from supervaizer.protocol.a2a.model import (
    create_agent_card,
    create_agents_list,
    create_health_data,
)
from supervaizer.routes import handle_route_errors

if TYPE_CHECKING:
    from supervaizer.agent import Agent
    from supervaizer.server import Server


def create_routes(server: "Server") -> APIRouter:
    """Create A2A protocol routes for the server."""
    router = APIRouter(prefix="/.well-known", tags=["Protocol A2A"])
    base_url = server.public_url or ""

    @router.get(
        "/agents.json",
        summary="A2A Agents Discovery",
        description="Returns a list of all agents according to A2A protocol specification",
        response_model=Dict[str, Any],
    )
    @handle_route_errors()
    async def get_a2a_agents() -> Dict[str, Any]:
        """Get a list of all available agents in A2A format."""
        log.info("[A2A] GET /.well-known/agents.json [Agent discovery]")
        return create_agents_list(server.agents, base_url)

    # Health endpoint
    @router.get(
        "/health",
        summary="A2A Health Status",
        description="Returns health information about the server and agents",
        response_model=Dict[str, Any],
    )
    @handle_route_errors()
    async def get_health() -> Dict[str, Any]:
        """Get health information for the server and all agents."""
        # log.debug("[A2A] GET /.well-known/health [Health status]")
        return create_health_data(server.agents)

    # Create explicit routes for each agent in the versioned format
    for agent in server.agents:
        # V1 endpoints (current version)
        def create_agent_route_versioned(current_agent: "Agent") -> None:
            route_path = (
                f"/agents/v{current_agent.version}/{current_agent.slug}_agent.json"
            )

            @router.get(
                route_path,
                summary=f"A2A Agent Card for {current_agent.name} (v1)",
                description=f"Returns agent card for {current_agent.name} according to A2A protocol specification",
                response_model=Dict[str, Any],
            )
            @handle_route_errors()
            async def get_agent_card() -> Dict[str, Any]:
                """Get an agent card in A2A format."""
                log.info(
                    f"[A2A] GET /.well-known/agents/v{current_agent.version}/"
                    f"{current_agent.slug}_agent.json [Agent card]"
                )
                return create_agent_card(current_agent, base_url)

        # Create routes for backward compatibility to current versions
        def create_agent_route_legacy(current_agent: "Agent") -> None:
            route_path = f"/agents/{current_agent.slug}_agent.json"

            @router.get(
                route_path,
                summary=f"A2A Agent Card for {current_agent.name} (Legacy)",
                description=f"Legacy endpoint for {current_agent.name} agent card",
                response_model=Dict[str, Any],
            )
            @handle_route_errors()
            async def get_agent_card_legacy() -> Dict[str, Any]:
                """Get an agent card in A2A format (legacy endpoint)."""
                log.info(
                    f"[A2A] GET /.well-known/agents/{current_agent.slug}_agent.json [Legacy Agent card]"
                )
                return create_agent_card(current_agent, base_url)

        # Call the closure function with the current agent
        create_agent_route_versioned(agent)
        create_agent_route_legacy(agent)

    return router
