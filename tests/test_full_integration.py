# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import shortuuid

from supervaize_control import (
    Account,
    Agent,
    AgentMethod,
    Parameter,
    ParametersSetup,
    Server,
)


def test_agent_setup(agent_fixture, job_fixture):
    """
    Test the full setup. Serves as a template for the implementation of the agent.
    """
    sv_account = Account(
        name="CUSTOMERFIRST",
        id="o34Z484gY9Nxz8axgTAdiH",
        api_key="APIKEY",
        api_url="http://localhost:8000",
    )

    # Define the secrets expected by the agent
    agent_parameters = ParametersSetup.from_list([
        Parameter(
            name="OPEN_API_KEY",
            description="OpenAPI Key",
            is_environment=True,
        ),
        Parameter(name="SERPER_API", description="Server API key", is_environment=True),
    ])

    job_start_method = AgentMethod(
        name="start",
        method="control.example_synchronous_job_start",
        params={"action": "start"},
        fields=[
            {
                "name": "full_name",
                "type": str,
                "field_type": "CharField",
                "max_length": 100,
                "required": True,
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
    agent_name = "competitor_summary"
    agent = Agent(
        name=agent_name,
        id=shortuuid.uuid(f"{agent_name}"),
        author="John Doe",
        developer="Develop",
        version="1.0b",
        description="This is a test agent",
        urls={"dev": "http://host.docker.internal:8001", "prod": ""},
        active_environment="dev",
        tags=["testtag", "testtag2"],
        job_start_method=job_start_method,
        job_stop_method=job_stop_method,
        job_status_method=job_status_method,
        custom_methods={"custom1": custom_method},
        parameters_setup=agent_parameters,
    )

    sv_server = Server(
        account=sv_account,
        agents=[agent],
    )

    assert isinstance(sv_server, Server)
