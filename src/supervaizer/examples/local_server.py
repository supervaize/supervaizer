# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Local test server: no Studio registration, built-in Hello World agent.

Use with `supervaizer start --local` to run the FastAPI server and agent workbench
without Supervaize Studio credentials.
"""

import os
import shortuuid
from typing import Any, Optional

from supervaizer import (
    Agent,
    AgentMethod,
    AgentMethods,
    AgentMethodField,
    ParametersSetup,
    Parameter,
    Server,
)


def get_default_local_agent() -> Agent:
    """Default Hello World agent for local test mode (mirrors supervaize_hello_world)."""
    agent_name = "Hello World AI Agent"
    module = "supervaizer.examples.hello_world_agent"

    parameters = ParametersSetup.from_list([
        Parameter(
            name="SIMPLE AGENT PARAMETER",
            description="Setup agent parameter in this workspace",
            is_environment=True,
        ),
        Parameter(
            name="SIMPLE AGENT SECRET",
            description="Setup agent secret in this workspace",
            is_environment=True,
            is_secret=True,
        ),
    ])

    job_start_method = AgentMethod(
        name="start",
        method=f"{module}.job_start",
        is_async=False,
        params={"action": "start"},
        fields=[
            AgentMethodField(
                name="How many times to say hello",
                type=int,
                field_type="IntegerField",
                required=True,
                default=3,
            ),
            AgentMethodField(
                name="Enable human review",
                type=bool,
                field_type="BooleanField",
                required=False,
                default=False,
            ),
        ],
        description="Say hello N times (local test)",
    )
    job_stop_method = AgentMethod(
        name="stop",
        method=f"{module}.job_stop",
        is_async=False,
        params={"action": "stop"},
        description="Stop the running job",
    )
    job_status_method = AgentMethod(
        name="status",
        method=f"{module}.job_status",
        is_async=False,
        params={"action": "status"},
        description="Get the status of the agent",
    )
    human_answer_method = AgentMethod(
        name="human_answer",
        method=f"{module}.human_answer",
        is_async=False,
        params={"action": "human_answer"},
        description="Handle human-in-the-loop answers",
    )

    return Agent(
        name=agent_name,
        id=shortuuid.uuid(agent_name),
        author="Supervaizer (local test)",
        version="1.0",
        description="Built-in Hello World agent for local testing without Studio.",
        tags=["hello world", "ai agent", "local"],
        methods=AgentMethods(
            job_start=job_start_method,
            job_stop=job_stop_method,
            job_status=job_status_method,
            human_answer=human_answer_method,
        ),
        parameters_setup=parameters,
    )


def create_local_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
    public_url: Optional[str] = None,
    debug: bool = False,
    reload: bool = False,
    environment: str = "dev",
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Server:
    """Create a Server with no supervisor_account and the default Hello World agent."""
    return Server(
        agents=[get_default_local_agent()],
        supervisor_account=None,
        a2a_endpoints=True,
        admin_interface=True,
        host=host or os.environ.get("SUPERVAIZER_HOST", "0.0.0.0"),
        port=port or int(os.environ.get("SUPERVAIZER_PORT") or "8000"),
        public_url=public_url or os.environ.get("SUPERVAIZER_PUBLIC_URL"),
        debug=debug,
        reload=reload,
        environment=environment,
        api_key=api_key or os.environ.get("SUPERVAIZER_API_KEY") or "local-dev",
        **kwargs,
    )
