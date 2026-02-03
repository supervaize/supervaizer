# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# This is an example file.
# It must be copied / renamed to supervaizer_control.py
# and edited to configure your agent(s)

import os
import shortuuid
from rich.console import Console

from supervaizer import (
    Agent,
    AgentMethod,
    AgentMethods,
    Parameter,
    ParametersSetup,
    Server,
)
from supervaizer.account import Account

# Create a console with default style set to yellow
console = Console(style="yellow")

# Public url of your hosted agent  (including port if needed)
# Use loca.lt or ngrok to get a public url during development.
# This can be setup from environment variables.
# SUPERVAIZER_HOST and SUPERVAIZER_PORT
DEV_PUBLIC_URL = "https://myagent-dev.loca.lt"
# Public url of your hosted agent
PROD_PUBLIC_URL = "https://myagent.cloud-hosting.net:8001"

# Define the parameters and secrets expected by the agent
agent_parameters: ParametersSetup | None = ParametersSetup.from_list([
    Parameter(
        name="OPEN_API_KEY",
        description="OpenAPI Key",
        is_environment=True,
        is_secret=True,
    ),
    Parameter(
        name="SERPER_API",
        description="Server API key updated",
        is_environment=True,
        is_secret=True,
    ),
    Parameter(
        name="COMPETITOR_SUMMARY_URL",
        description="Competitor Summary URL",
        is_environment=True,
        is_secret=False,
    ),
])

# Define the method used to start a job
job_start_method: AgentMethod = AgentMethod(
    name="start",  # This is required
    method="example_agent.example_synchronous_job_start",  # Path to the main function in dotted notation.
    is_async=False,  # Only use sync methods for the moment
    params={"action": "start"},  # If default parameters must be passed to the function.
    fields=[
        {
            "name": "Company to research",  # Field name - displayed in the UI
            "type": str,  # Python type of the field for pydantic validation - note , ChoiceField and MultipleChoiceField are a list[str]
            "field_type": "CharField",  # Field type for persistence.
            "description": "Company to research",  # Optional -  Description of the field - displayed in the UI
            "default": "Google",  # Optional - Default value for the field
            "required": True,  # Whether the field is required
        },
        {
            "name": "Max number of results",
            "type": int,
            "field_type": "IntegerField",
            "required": True,
        },
        {
            "name": "Subscribe to updates",
            "type": bool,
            "field_type": "BooleanField",
            "required": False,
        },
        {
            "name": "Type of research",
            "type": str,
            "field_type": "ChoiceField",
            "choices": [["A", "Advanced"], ["R", "Restricted"]],
            "widget": "RadioSelect",
            "required": True,
        },
        {
            "name": "Details of research",
            "type": str,
            "field_type": "CharField",
            "widget": "Textarea",
            "required": False,
        },
        {
            "name": "List of countries",
            "type": list[str],
            "field_type": "MultipleChoiceField",
            "choices": [
                ["PA", "Panama"],
                ["PG", "Papua New Guinea"],
                ["PY", "Paraguay"],
                ["PE", "Peru"],
                ["PH", "Philippines"],
                ["PN", "Pitcairn"],
                ["PL", "Poland"],
            ],
            "required": True,
        },
        {
            "name": "languages",
            "type": list[str],
            "field_type": "MultipleChoiceField",
            "choices": [["en", "English"], ["fr", "French"], ["es", "Spanish"]],
            "required": False,
        },
    ],
    description="Start the collection of new competitor summary",
)

job_stop_method: AgentMethod = AgentMethod(
    name="stop",
    method="control.stop",
    params={"action": "stop"},
    description="Stop the agent",
)
job_status_method: AgentMethod = AgentMethod(
    name="status",
    method="hello.mystatus",
    params={"status": "statusvalue"},
    description="Get the status of the agent",
)
custom_method: AgentMethod = AgentMethod(
    name="custom",
    method="control.custom",
    params={"action": "custom"},
    description="Custom method",
)

custom_method2: AgentMethod = AgentMethod(
    name="custom2",
    method="control.custom2",
    params={"action": "custom2"},
    description="Custom method",
)


agent_name = "competitor_summary"

# Define the Agent
agent: Agent = Agent(
    name=agent_name,
    id=shortuuid.uuid(f"{agent_name}"),
    author="John Doe",  # Author of the agent
    developer="Developer",  # Developer of the controller integration
    maintainer="Ive Maintained",  # Maintainer of the integration
    editor="DevAiExperts",  # Editor (usually a company)
    version="1.3",  # Version string
    description="This is a test agent",
    tags=["testtag", "testtag2"],
    methods=AgentMethods(
        job_start=job_start_method,
        job_stop=job_stop_method,
        job_status=job_status_method,
        chat=None,
        custom={"custom1": custom_method, "custom2": custom_method2},
    ),
    parameters_setup=agent_parameters,
    instructions_path="supervaize_instructions.html",  # Path where instructions page is served
)

# For export purposes, use dummy values if environment variables are not set
account: Account = Account(
    workspace_id=os.getenv("SUPERVAIZE_WORKSPACE_ID") or "dummy_workspace_id",
    api_key=os.getenv("SUPERVAIZE_API_KEY") or "dummy_api_key",
    api_url=os.getenv("SUPERVAIZE_API_URL") or "https://app.supervaize.com",
)

# Define the supervaizer server capabilities
sv_server: Server = Server(
    agents=[agent],
    a2a_endpoints=True,  # Enable A2A endpoints
    supervisor_account=account,  # Account of the supervisor from Supervaize
)


if __name__ == "__main__":
    # Start the supervaize server
    sv_server.launch(log_level="DEBUG")
