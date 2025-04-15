# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from typing import Dict, List, Any

from .agent import Agent


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

    # Build API endpoints object
    api_endpoints = [
        {
            "type": "json",
            "url": agent_url,
            "name": "Supervaize API",
            "description": f"RESTful API for {agent.name} agent",
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
    tools.append({
        "name": "job_start",
        "description": agent.methods.job_start.description
        or f"Start a job with {agent.name}",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_fields": {"type": "object"},
                "supervaize_context": {"type": "object"},
            },
        },
    })

    tools.append({
        "name": "job_status",
        "description": "Check the status of a job",
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
        },
    })

    # Add custom tools if available
    if agent.methods.custom:
        for name, method in agent.methods.custom.items():
            tools.append({
                "name": name,
                "description": method.description or f"Execute {name} custom method",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "method_name": {"type": "string", "const": name},
                        "params": {"type": "object"},
                    },
                },
            })

    # Build authentication object
    authentication = {
        "type": "none",
        "description": "Authentication is handled at the Supervaize server level",
    }

    # Create the main agent card
    agent_card = {
        "schema_version": "a2a_2023_v1",
        "name": agent.name,
        "description": agent.description,
        "developer": {
            "name": agent.developer or agent.author or "Supervaize",
            "url": "https://supervaize.com/",
            "email": "info@supervaize.com",
        },
        "version": agent.version,
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
                "agent_card_url": f"{base_url}/.well-known/agents/{agent.slug}_agent.json",
            }
            for agent in agents
        ],
    }
