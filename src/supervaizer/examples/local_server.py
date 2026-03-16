# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Local test server fallback: used by `supervaizer start --local` when no supervaizer_control.py exists.

Also exports get_default_local_agent() for Server to import when injecting Hello World.
"""

import os

import shortuuid

from supervaizer import (
    Agent,
    AgentMethod,
    AgentMethods,
    Parameter,
    ParametersSetup,
    Server,
)
from supervaizer.agent import AgentMethodField


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


if __name__ == "__main__":
    # Fallback entry point: starts a server with no user agents.
    # Hello World is injected by Server.__init__ when SUPERVAIZER_LOCAL_MODE=true.
    server = Server(
        agents=[],
        supervisor_account=None,
        a2a_endpoints=True,
        admin_interface=True,
        host=os.environ.get("SUPERVAIZER_HOST") or "0.0.0.0",
        port=int(os.environ.get("SUPERVAIZER_PORT") or "8000"),
        public_url=os.environ.get("SUPERVAIZER_PUBLIC_URL"),
        debug=os.environ.get("SUPERVAIZER_DEBUG", "False").lower() == "true",
        reload=os.environ.get("SUPERVAIZER_RELOAD", "False").lower() == "true",
        environment=os.environ.get("SUPERVAIZER_ENVIRONMENT", "dev"),
        # Pass None so Server.__init__ local-mode logic defaults to "local-dev"
        api_key=None,
    )
    log_level = os.environ.get("SUPERVAIZER_LOG_LEVEL", "INFO")
    server.launch(log_level=log_level)
