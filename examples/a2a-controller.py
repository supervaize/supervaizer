# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

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

# Create a console with default style set to yellow
console = Console(style="yellow")


# Define the parameters and secrets expected by the agent
agent_parameters = ParametersSetup.from_list(
    [
        Parameter(
            name="OPEN_API_KEY",
            description="OpenAPI Key",
            is_environment=True,
        ),
        Parameter(
            name="SERPER_API", description="Server API key updated", is_environment=True
        ),
        Parameter(
            name="COMPETITOR_SUMMARY_URL",
            description="Competitor Summary URL",
            is_environment=True,
        ),
    ]
)

# Define the method used to start a job
job_start_method = AgentMethod(
    name="start",
    method="example_agent.example_synchronous_job_start",
    is_async=False,
    params={"action": "start"},
    fields=[
        {
            "name": "Company to research",
            "type": str,
            "field_type": "CharField",
            "max_length": 100,
            "required": True,
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

job_stop_method = AgentMethod(
    name="stop",
    method="control.stop",
    params={"action": "stop"},
    description="Stop the agent",
)
job_status_method = AgentMethod(
    name="status",
    method="hello.mystatus",
    params={"status": "statusvalue"},
    description="Get the status of the agent",
)
custom_method = AgentMethod(
    name="custom",
    method="control.custom",
    params={"action": "custom"},
    description="Custom method",
)

custom_method2 = AgentMethod(
    name="custom2",
    method="control.custom2",
    params={"action": "custom2"},
    description="Custom method",
)


agent_name = "competitor_summary"

# Define the Agent
agent = Agent(
    name=agent_name,
    id=shortuuid.uuid(f"{agent_name}"),
    author="John Doe",
    developer="Developer",
    maintainer="Ive Maintained",
    editor="Yuri Editor",
    version="1.3",
    description="This is a test agent",
    urls={"dev": "http://host.docker.internal:8001", "prod": ""},
    active_environment="dev",
    tags=["testtag", "testtag2"],
    methods=AgentMethods(
        job_start=job_start_method,
        job_stop=job_stop_method,
        job_status=job_status_method,
        chat=None,
        custom={"custom1": custom_method, "custom2": custom_method2},
    ),
    parameters_setup=agent_parameters,
)

# Define the Server
sv_server = Server(
    agents=[agent],
    a2a_enabled=True,
    supervisor_account=None,
)


if __name__ == "__main__":
    # Start the supervaize server
    sv_server.launch(log_level="DEBUG")
