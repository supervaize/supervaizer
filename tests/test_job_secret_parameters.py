# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from supervaizer.agent import Agent, AgentMethod, AgentMethods
from supervaizer.common import ApiSuccess, encrypt_value
from supervaizer.job import Job, JobContext, JobResponse, Jobs
from supervaizer.lifecycle import EntityStatus
from supervaizer.parameter import Parameter, ParametersSetup
from supervaizer.routes import create_agent_route
from supervaizer.server import Server
from supervaizer.storage import storage_manager


@patch.object(Agent, "job_start")
def test_start_job_never_returns_or_persists_decrypted_parameters(
    _mock_job_start: MagicMock, context_fixture: JobContext
) -> None:
    """Decrypted secrets reach the agent method, never the response or storage."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = MagicMock(spec=Server)
    server.private_key = private_key
    server.api_key = "test-api-key"
    agent = Agent(
        name="secret_agent",
        version="1.0.0",
        methods=AgentMethods(
            job_start=AgentMethod(name="start", method="test.start"),
            job_stop=AgentMethod(name="stop", method="test.stop"),
            job_status=AgentMethod(name="status", method="test.status"),
        ),
        parameters_setup=ParametersSetup.from_list([
            Parameter(name="API_KEY", is_secret=True, is_required=True),
        ]),
    )
    app = FastAPI()
    app.state.server = server
    app.include_router(create_agent_route(server, agent))
    parameters = [{"name": "API_KEY", "value": "s3cr3t-value", "is_secret": True}]

    start = TestClient(app).post(
        "/agents/secret-agent/jobs",
        json={
            "job_context": context_fixture.model_dump(mode="json"),
            "job_fields": {},
            "encrypted_agent_parameters": encrypt_value(
                json.dumps(parameters), private_key.public_key()
            ),
        },
        headers={"X-API-Key": "test-api-key"},
    )

    assert start.status_code == 202, start.text
    assert "s3cr3t-value" not in start.text
    job = Jobs().get_job(context_fixture.job_id)
    assert job is not None
    assert job.agent_parameters == parameters
    assert "s3cr3t-value" not in json.dumps(job.to_dict)
    assert "s3cr3t-value" not in repr(job)
    stored = storage_manager.get_object_by_id("Job", job.id)
    assert stored is not None
    assert "s3cr3t-value" not in json.dumps(stored)


def test_job_start_uses_call_parameters_without_changing_the_job(
    server_fixture: Server,
    context_fixture: JobContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom calls on one job must not share their decrypted parameters."""
    method = AgentMethod(
        name="custom", method="supervaizer.examples.hello_world_agent.job_start"
    )
    agent = Agent(
        name="secret_agent",
        version="1.0.0",
        methods=AgentMethods(
            job_start=method,
            job_stop=method,
            job_status=method,
            custom={"custom": method},
        ),
    )
    job = Job.new(job_context=context_fixture, agent_name=agent.name)
    seen: list[Any] = []

    def fake_execute(action: str, params: dict[str, Any]) -> JobResponse:
        seen.append(params["agent_parameters"])
        return JobResponse(
            job_id=job.id, status=EntityStatus.COMPLETED, message="ok", payload=None
        )

    monkeypatch.setattr(agent, "_execute", fake_execute)
    monkeypatch.setattr(
        "supervaizer.account_service.send_event_sync",
        lambda account, sender, event: ApiSuccess(message="ok", detail={}, code=200),
    )
    monkeypatch.setattr(
        "supervaizer.agent.service_job_finished", lambda job_arg, server=None: None
    )
    call_parameters = [{"name": "API_KEY", "value": "call-only"}]

    agent.job_start(
        job,
        {},
        context_fixture,
        server_fixture,
        method_name="custom",
        agent_parameters=call_parameters,
    )

    assert seen == [call_parameters]
    assert job.agent_parameters is None
