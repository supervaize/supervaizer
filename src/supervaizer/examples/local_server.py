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

"""Local test server fallback: used by `supervaizer start --local` when no supervaizer_control.py exists.

Also exports get_default_local_agent() for Server to import when injecting Hello World.
"""

import os
from typing import Any

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
from supervaizer.contracts import (
    SUPERVAIZER_V2_A2A_VERSION,
    SUPERVAIZER_V2_A2UI_VERSION,
    SUPERVAIZER_V2_CONTRACT_VERSION,
)

HELLO_WORLD_AGENT_NAME = "Hello World AI Agent"
HELLO_WORLD_AGENT_SLUG = "hello-world-ai-agent"
HELLO_WORLD_AGENT_VERSION = "1.0"
HELLO_WORLD_A2UI_CATALOG_VERSION = "supervaizer-v2-local.0"


def build_default_local_v2_registration(
    *,
    agent_slug: str = HELLO_WORLD_AGENT_SLUG,
    agent_version: str = HELLO_WORLD_AGENT_VERSION,
) -> dict[str, Any]:
    """Return the minimal Supervaizer v2 contract for the built-in local agent."""
    return {
        "supervaizer_contract_version": SUPERVAIZER_V2_CONTRACT_VERSION,
        "agent": {
            "id": agent_slug,
            "slug": agent_slug,
            "display_name": HELLO_WORLD_AGENT_NAME,
        },
        "versions": {
            "a2ui_version": SUPERVAIZER_V2_A2UI_VERSION,
            "a2ui_catalog_version": HELLO_WORLD_A2UI_CATALOG_VERSION,
            "a2a_version": SUPERVAIZER_V2_A2A_VERSION,
            "ag_ui_version": None,
        },
        "a2a": {
            "agent_card_url": f"/.well-known/agents/v{agent_version}/{agent_slug}_agent.json",
            "controller_url": "/a2a",
        },
        "capabilities": {
            "surfaces": ["job.start", "case.step.awaiting"],
            "actions": [
                "job.start.preview",
                "job.start",
                "job.sync",
                "step.awaiting.submit",
            ],
            "case_lanes": [{"id": "work", "label": "Work", "default": True}],
            "artifact_types": [],
        },
        "resources": [],
        "datasets": [],
    }


def register_default_local_v2_handlers(
    server: Any,
    *,
    agent_slug: str = HELLO_WORLD_AGENT_SLUG,
) -> None:
    """Register minimal v2 handlers for the built-in local Hello World agent."""
    from supervaizer.examples.hello_world_agent import (
        handle_v2_action,
        handle_v2_surface,
    )

    for surface in ("job.start", "case.step.awaiting"):
        server.register_v2_surface(surface, handle_v2_surface, agent_slug=agent_slug)
    server.register_v2_action(
        "job.start.preview", handle_v2_action, agent_slug=agent_slug
    )
    for action in ("job.start", "job.sync", "step.awaiting.submit"):
        server.register_v2_action(action, handle_v2_action, agent_slug=agent_slug)


def get_default_local_agent() -> Agent:
    """Default Hello World agent for local test mode (mirrors supervaize_hello_world)."""
    agent_name = HELLO_WORLD_AGENT_NAME
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
        version=HELLO_WORLD_AGENT_VERSION,
        description="Built-in Hello World agent for local testing without Studio.",
        tags=["hello world", "ai agent", "local"],
        methods=AgentMethods(
            job_start=job_start_method,
            job_stop=job_stop_method,
            job_status=job_status_method,
            human_answer=human_answer_method,
        ),
        parameters_setup=parameters,
        supervaizer_v2_registration=build_default_local_v2_registration(),
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
