# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from typing import Dict, List, Any
from datetime import datetime

from ...agent import Agent
from ...job import JobStatus, Jobs


def create_agent_detail(agent: Agent, base_url: str) -> Dict[str, Any]:
    """
    Create an ACP agent detail for the given agent.

    This follows the ACP protocol as defined in:
    https://docs.beeai.dev/acp/spec/concepts/discovery

    Args:
        agent: The Agent instance
        base_url: The base URL of the server

    Returns:
        A dictionary representing the agent detail in ACP format
    """
    # Build the interfaces object
    interfaces = {
        "input": "chat",
        "output": "chat",
        "awaits": [{"name": "user_response", "request": {}, "response": {}}],
    }

    # Build the metadata object
    metadata = {
        "documentation": agent.description or f"Documentation for {agent.name} agent",
        "license": "MPL-2.0",
        "programmingLanguage": "Python",
        "naturalLanguages": ["en"],
        "framework": "SUPERVAIZER",
        "useCases": [f"Agent services provided by {agent.name}"],
        "examples": [
            {
                "prompt": f"Example interaction with {agent.name}",
                "response": "Example response",
            }
        ],
        "tags": [agent.slug] + (agent.tags or []),
        "createdAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "author": {
            "name": agent.author or agent.developer or "SUPERVAIZER",
            "email": "info@supervaize.com",
            "url": "https://supervaize.com/",
        },
        "contributors": [
            {
                "name": agent.maintainer
                or agent.author
                or agent.developer
                or "SUPERVAIZER",
                "email": "info@supervaize.com",
                "url": "https://supervaize.com/",
            }
        ],
        "links": [
            {"type": "homepage", "url": f"{base_url}/agents/{agent.slug}"},
            {"type": "documentation", "url": f"{base_url}/docs"},
            {"type": "source-code", "url": "https://github.com/supervaize/supervaizer"},
        ],
        "dependencies": [{"type": "tool", "name": "supervaizer-core"}],
        "recommendedModels": ["gpt-4", "claude-3-opus"],
    }

    # Get job statistics for status data
    jobs_registry = Jobs()
    agent_jobs = jobs_registry.get_agent_jobs(agent.name)

    total_jobs = len(agent_jobs)
    completed_jobs = sum(
        1 for j in agent_jobs.values() if j.status == JobStatus.COMPLETED
    )

    # Calculate average runtime and success rate for status
    avg_run_time = 0.0
    if total_jobs > 0:
        success_rate = (completed_jobs / total_jobs) * 100

        # Calculate average runtime in seconds
        runtimes = []
        for job in agent_jobs.values():
            if job.created_at and job.finished_at and job.status == JobStatus.COMPLETED:
                runtime = (job.finished_at - job.created_at).total_seconds()
                runtimes.append(runtime)

        if runtimes:
            avg_run_time = sum(runtimes) / len(runtimes)
    else:
        success_rate = 100  # If no jobs, assume 100% success rate

    # Build the status object
    status = {
        "avgRunTokens": 0,  # Placeholder, actual token count if available
        "avgRunTimeSeconds": avg_run_time,
        "successRate": success_rate,
    }

    # Create the main agent detail
    agent_detail = {
        "name": agent.name,
        "description": agent.description,
        "interfaces": interfaces,
        "metadata": metadata,
        "status": status,
    }

    return agent_detail


def list_agents(agents: List[Agent], base_url: str) -> List[Dict[str, Any]]:
    """
    Create a list of ACP agent details for all available agents.

    Args:
        agents: List of Agent instances
        base_url: The base URL of the server

    Returns:
        A list of dictionaries representing agent details in ACP format
    """
    return [create_agent_detail(agent, base_url) for agent in agents]


def create_health_data(agents: List[Agent]) -> Dict[str, Any]:
    """
    Create health data for all agents according to ACP protocol.

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
            1 for j in agent_jobs.values() if j.status == JobStatus.COMPLETED
        )
        failed_jobs = sum(
            1 for j in agent_jobs.values() if j.status == JobStatus.FAILED
        )
        in_progress_jobs = sum(
            1 for j in agent_jobs.values() if j.status == JobStatus.IN_PROGRESS
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
        "status": "operational",
        "timestamp": str(datetime.now()),
        "agents": agents_health,
    }
