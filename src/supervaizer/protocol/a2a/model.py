# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from datetime import datetime
from typing import Any, Dict, List

from supervaizer.agent import Agent
from supervaizer.job import EntityStatus, Jobs


def create_agent_card(agent: Agent, base_url: str) -> Dict[str, Any]:
    """
    Create an A2A agent card for the given agent.

    This follows the A2A protocol as defined in:
    https://github.com/google/A2A/blob/main/specification/json/a2a.json

    Args:
        agent: The Agent instance
        base_url: The base URL of the server

    Returns:
        A dictionary representing the agent card in A2A format
    """
    # Construct the agent URL
    agent_url = f"{base_url}{agent.path}"

    # Build API endpoints object with OpenAPI integration
    api_endpoints = [
        {
            "type": "json",
            "url": agent_url,
            "name": "Supervaize API - A2A protocol support",
            "description": f"RESTful API for {agent.name} agent",
            "openapi_url": f"{base_url}/openapi.json",
            "docs_url": f"{base_url}/docs",
            "examples": [
                {
                    "name": "Get agent info",
                    "description": "Retrieve information about the agent",
                    "request": {"method": "GET", "url": agent_url},
                },
                {
                    "name": "Start a job",
                    "description": "Start a new job with this agent",
                    "request": {"method": "POST", "url": f"{agent_url}/jobs"},
                },
            ],
        }
    ]

    # Build the tools object based on agent methods
    tools = []

    # Add basic job tools
    tools.append(
        {
            "name": "job_start",
            "description": (
                agent.methods.job_start.description if agent.methods else None
            )
            or f"Start a job with {agent.name}",
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_fields": {"type": "object"},
                    "job_context": {"type": "object"},
                },
            },
        }
    )

    tools.append(
        {
            "name": "job_status",
            "description": "Check the status of a job",
            "input_schema": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
            },
        }
    )

    # Add custom tools if available
    if agent.methods and agent.methods.custom:
        for name, method in agent.methods.custom.items():
            tools.append(
                {
                    "name": name,
                    "description": method.description
                    or f"Execute {name} custom method",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "method_name": {"type": "string", "const": name},
                            "params": {"type": "object"},
                        },
                    },
                }
            )

    # Build authentication object
    authentication = {
        "type": "none",
        "description": "Authentication is handled at the Supervaize server level",
    }

    # Version information
    version_info = {
        "current": agent.version,
        "latest": agent.version,
        "changelog_url": f"{base_url}/changelog/{agent.slug}",
    }

    # Create the main agent card
    agent_card = {
        "name": agent.name,
        "description": agent.description,
        "developer": {
            "name": agent.developer or agent.author or "Supervaize",
            "url": "https://supervaize.com/",
            "email": "info@supervaize.com",
        },
        "version": agent.version,
        "version_info": version_info,
        "logo_url": f"{base_url}/static/agents/{agent.slug}_logo.png",
        "human_url": f"{base_url}/agents/{agent.slug}",
        "contact_information": {"general": {"email": "support@supervaize.com"}},
        "api_endpoints": api_endpoints,
        "tools": tools,
        "authentication": authentication,
    }

    return agent_card


def create_agents_list(agents: List[Agent], base_url: str) -> Dict[str, Any]:
    """
    Create an A2A agents list for all available agents.

    Args:
        agents: List of Agent instances
        base_url: The base URL of the server

    Returns:
        A dictionary representing the list of agent cards in A2A format
    """
    return {
        "schema_version": "a2a_2023_v1",
        "agents": [
            {
                "name": agent.name,
                "description": agent.description,
                "developer": agent.developer or agent.author or "Supervaize",
                "version": agent.version,
                "agent_card_url": f"{base_url}/.well-known/agents/v{agent.version}/{agent.slug}_agent.json",
            }
            for agent in agents
        ],
    }


def create_health_data(agents: List[Agent]) -> Dict[str, Any]:
    """
    Create health data for all agents according to A2A protocol.

    Args:
        agents: List of Agent instances

    Returns:
        A dictionary with health information for all agents
    """
    jobs_registry = Jobs()

    agents_health = {}
    for agent in agents:
        # Get agent jobs
        agent_jobs = jobs_registry.get_agent_jobs(agent.name)

        # Calculate job statistics
        total_jobs = len(agent_jobs)
        completed_jobs = sum(
            1 for j in agent_jobs.values() if j.status == EntityStatus.COMPLETED
        )
        failed_jobs = sum(
            1 for j in agent_jobs.values() if j.status == EntityStatus.FAILED
        )
        in_progress_jobs = sum(
            1 for j in agent_jobs.values() if j.status == EntityStatus.IN_PROGRESS
        )

        # Set agent status based on health indicators
        if total_jobs == 0:
            status = "available"
        elif failed_jobs > total_jobs / 2:  # If more than half are failing
            status = "degraded"
        elif in_progress_jobs > 0:
            status = "busy"
        else:
            status = "available"

        agents_health[agent.id] = {
            "agent_id": agent.id,
            "agent_server_id": agent.server_agent_id,
            "name": agent.name,
            "status": status,
            "version": agent.version,
            "statistics": {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "in_progress_jobs": in_progress_jobs,
                "success_rate": (completed_jobs / total_jobs * 100)
                if total_jobs > 0
                else 100,
            },
        }

    return {
        "schema_version": "a2a_2023_v1",
        "status": "operational",
        "timestamp": str(datetime.now()),
        "agents": agents_health,
    }
