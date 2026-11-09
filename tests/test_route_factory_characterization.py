# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize legacy route factories before their nested handlers move."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from supervaizer.agent import Agent
from supervaizer.routes import create_agent_route, create_default_routes
from supervaizer.server import Server


def _factory_app(server: Server, agent: Agent) -> FastAPI:
    app = FastAPI()
    app.state.server = server
    app.include_router(create_default_routes(server))
    app.include_router(create_agent_route(server, agent))
    return app


def _operation_rows(app: FastAPI) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for path, operations in app.openapi()["paths"].items():
        for method, operation in operations.items():
            rows.append((path, method.upper(), operation["operationId"]))
    return rows


def test_route_factories_have_a_stable_openapi_operation_snapshot(
    server_fixture: Server, agent_fixture: Agent
) -> None:
    first = _operation_rows(_factory_app(server_fixture, agent_fixture))
    second = _operation_rows(_factory_app(server_fixture, agent_fixture))

    assert first == second
    assert first == [
        (
            "/supervaizer/contract",
            "GET",
            "get_controller_contract_supervaizer_contract_get",
        ),
        (
            "/supervaizer/registration/refresh",
            "POST",
            "refresh_controller_registration_supervaizer_registration_refresh_post",
        ),
        (
            "/supervaizer/jobs/{job_id}",
            "GET",
            "get_job_status_supervaizer_jobs__job_id__get",
        ),
        ("/supervaizer/jobs", "GET", "get_all_jobs_supervaizer_jobs_get"),
        (
            "/supervaizer/jobs/{job_id}/cases/{case_id}/update",
            "POST",
            "update_case_with_answer_supervaizer_jobs__job_id__cases__case_id__update_post",
        ),
        ("/supervaizer/agents", "GET", "get_all_agents_supervaizer_agents_get"),
        (
            "/supervaizer/agent/{agent_id}",
            "GET",
            "get_agent_details_supervaizer_agent__agent_id__get",
        ),
        (
            f"{agent_fixture.path}/",
            "GET",
            "agent_info_agents_agentname__get",
        ),
        (
            f"{agent_fixture.path}/{agent_fixture.instructions_path}",
            "GET",
            "supervaize_instructions_agents_agentname_supervaize_instructions_html_get",
        ),
        (
            f"{agent_fixture.path}/validate-agent-parameters",
            "POST",
            "validate_agent_parameters_agents_agentname_validate_agent_parameters_post",
        ),
        (
            f"{agent_fixture.path}/validate-method-fields",
            "POST",
            "validate_method_fields_agents_agentname_validate_method_fields_post",
        ),
        (
            f"{agent_fixture.path}/parameters",
            "POST",
            "server_update_agent_agents_agentname_parameters_post",
        ),
        (f"{agent_fixture.path}/jobs", "POST", "start_job_agents_agentname_jobs_post"),
        (
            f"{agent_fixture.path}/jobs",
            "GET",
            "get_agent_jobs_agents_agentname_jobs_get",
        ),
        (
            f"{agent_fixture.path}/jobs/{{job_id}}",
            "GET",
            "get_job_status_agents_agentname_jobs__job_id__get",
        ),
        (f"{agent_fixture.path}/stop", "POST", "stop_agent_agents_agentname_stop_post"),
        (
            f"{agent_fixture.path}/status",
            "POST",
            "status_agent_agents_agentname_status_post",
        ),
    ]


def test_agent_info_route_keeps_its_bound_agent(
    server_fixture: Server, agent_fixture: Agent
) -> None:
    client = TestClient(_factory_app(server_fixture, agent_fixture))

    response = client.get(f"{agent_fixture.path}/")

    assert response.status_code == 200
    assert response.json()["id"] == agent_fixture.id
    assert response.json()["name"] == agent_fixture.name


def test_agent_route_rejects_an_agent_without_v1_or_v2_registration(
    server_fixture: Server, agent_fixture: Agent
) -> None:
    agent_without_routes = agent_fixture.model_copy(
        update={"methods": None, "supervaizer_v2_registration": None}
    )

    with pytest.raises(ValueError, match="has no methods defined"):
        create_agent_route(server_fixture, agent_without_routes)
