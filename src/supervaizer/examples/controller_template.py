# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Supervaizer v2 controller template.
# `supervaizer scaffold` copies this file to supervaizer_control.py.
# Try it without Studio:  supervaizer start --local
# Then edit the agent, the surface, and the action below.

import os
from typing import Any

from supervaizer import (
    Account,
    Agent,
    Server,
    V2ActionRequest,
    V2SurfaceRequest,
    build_v2_agent_registration,
)

AGENT_NAME = "My Agent"

# The registration declares what Studio can show (surfaces) and call (actions).
agent: Agent = Agent(
    name=AGENT_NAME,
    version="0.1.0",
    description="Describe what your agent does.",
    supervaizer_v2_registration=build_v2_agent_registration(
        agent_slug="my-agent",  # must equal Agent.slug, the slugified name
        display_name=AGENT_NAME,
        a2ui_catalog_version="my-agent-ui.1",  # bump when your surfaces change
        surfaces=["job.start"],
        actions=["job.start"],
    ),
)

# Studio account, read from the environment. Local mode ignores it.
# For export purposes, use dummy values if environment variables are not set
account: Account = Account(
    workspace_id=os.getenv("SUPERVAIZE_WORKSPACE_ID") or "dummy_workspace_id",
    api_key=os.getenv("SUPERVAIZE_API_KEY") or "dummy_api_key",
    api_url=os.getenv("SUPERVAIZE_API_URL") or "https://app.supervaize.com",
)

sv_server: Server = Server(agents=[agent], supervisor_account=account)


# A surface handler returns the A2UI document Studio renders.
@sv_server.v2_surface("job.start", agent_slug=agent.slug)
def job_start_form(request: V2SurfaceRequest) -> dict[str, Any]:
    return {
        "surface": request.surface,
        "document": {
            "type": "Form",
            "title": "Start job",
            "fields": [
                {"id": "goal", "label": "Goal", "type": "string", "required": True}
            ],
            "submit": {"action": "job.start", "label": "Start"},
        },
    }


# An action handler runs your agent and returns effects plus the job state.
@sv_server.v2_action("job.start", agent_slug=agent.slug)
def start_job(request: V2ActionRequest) -> dict[str, Any]:
    job_id = request.job_id or "local-job"
    return {
        "status": "ok",
        "effects": [{"type": "job.started", "job_id": job_id, "status": "completed"}],
        "job_state": {
            "job": {
                "id": job_id,
                "mission_id": request.mission_id,
                "agent_slug": request.agent_slug,
                "status": "completed",
                "source": {"type": "fresh_start"},
            },
            "cases": [
                {
                    "id": "case-1",
                    "title": request.input["goal"],
                    "status": "completed",
                    "steps": [
                        {"id": "step-1", "activity": "operation", "status": "completed"}
                    ],
                }
            ],
        },
    }


if __name__ == "__main__":
    # Start the supervaize server
    sv_server.launch(log_level="DEBUG")
