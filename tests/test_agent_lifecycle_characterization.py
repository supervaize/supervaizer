# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize public Agent lifecycle behavior before structural changes."""

import sys
from datetime import UTC, datetime
from types import ModuleType
from typing import Any
from unittest.mock import Mock

import pytest

from supervaizer.agent import Agent, AgentMethod, AgentMethods
from supervaizer.common import ApiSuccess
from supervaizer.examples import hello_world_agent
from supervaizer.job import Job, JobContext, JobResponse
from supervaizer.lifecycle import EntityStatus


def _context() -> JobContext:
    return JobContext(
        workspace_id="workspace-1",
        job_id="job-1",
        started_by="user-1",
        started_at=datetime.now(UTC),
        mission_id="mission-1",
        mission_name="Mission",
    )


def _agent(method_path: str) -> Agent:
    method = AgentMethod(name="start", method=method_path)
    return Agent(name="Lifecycle Agent", methods=AgentMethods(job_start=method))


def test_constructor_derives_id_and_registration_serializes_missing_server_id() -> None:
    agent = _agent("agent_lifecycle_module.run")

    assert agent.id
    assert agent.registration_info["server_agent_id"] == "None"
    assert agent.registration_info["methods"]["job_start"]["method"] == (
        "agent_lifecycle_module.run"
    )


def test_execute_calls_declared_module_method_with_unmodified_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, Any] = {}
    module = ModuleType("agent_lifecycle_module")

    def run(**params: Any) -> JobResponse:
        received.update(params)
        return JobResponse(
            job_id="job-1",
            status=EntityStatus.COMPLETED,
            message="done",
            payload={"answer": 42},
        )

    module.__dict__["run"] = run
    monkeypatch.setitem(sys.modules, module.__name__, module)
    agent = _agent(f"{module.__name__}.run")
    params = {"value": "kept", "agent_parameters": [{"name": "token"}]}

    response = agent._execute(f"{module.__name__}.run", params)

    assert response.payload == {"answer": 42}
    assert received == params


def test_execute_rejects_declared_method_that_returns_wrong_public_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = ModuleType("agent_lifecycle_invalid_module")

    def run() -> str:
        return "wrong"

    module.__dict__["run"] = run
    monkeypatch.setitem(sys.modules, module.__name__, module)
    agent = _agent(f"{module.__name__}.run")

    with pytest.raises(
        TypeError, match="Method run must return a JobResponse object, got str"
    ):
        agent._execute(f"{module.__name__}.run")


def test_execute_nested_module_keeps_parameters_out_of_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, Any] = {}
    messages: list[str] = []

    def run(**params: Any) -> JobResponse:
        received.update(params)
        return JobResponse(
            job_id="job-1", status=EntityStatus.COMPLETED, message="done", payload={}
        )

    monkeypatch.setattr(hello_world_agent, "test_nested_action", run, raising=False)
    monkeypatch.setattr("supervaizer.agent.log.debug", messages.append)
    path = "supervaizer.examples.hello_world_agent.test_nested_action"
    agent = _agent(path)
    params = {
        "prompt": "visible prompt",
        "agent_parameters": [{"name": "API_KEY", "value": "test-secret-value"}],
    }

    response = agent._execute(path, params)

    assert response.status == EntityStatus.COMPLETED
    assert received == params
    assert any("visible prompt" in message for message in messages)
    assert all("test-secret-value" not in message for message in messages)
    assert all("agent_parameters" not in message for message in messages)


def test_job_start_forwards_parameters_updates_metadata_and_finishes_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = _agent("agent_lifecycle_module.run")
    context = _context()
    job = Job.new(
        job_context=context,
        agent_name=agent.name,
        agent_parameters=[{"name": "stored"}],
    )
    account = Mock()
    server = Mock()
    server.supervisor_account = account
    response = JobResponse(
        job_id=job.id,
        status=EntityStatus.COMPLETED,
        message="done",
        payload={"document": "doc-1"},
    )
    execute = Mock(return_value=response)
    finished = Mock()
    monkeypatch.setattr(agent, "_execute", execute)
    monkeypatch.setattr("supervaizer.agent.service_job_finished", finished)

    returned = agent.job_start(
        job,
        {"prompt": "hello"},
        context,
        server,
        agent_parameters=[{"name": "call"}],
    )

    assert returned is job
    execute.assert_called_once_with(
        "agent_lifecycle_module.run",
        {
            "fields": {"prompt": "hello"},
            "context": context,
            "agent_parameters": [{"name": "call"}],
        },
    )
    assert job.metadata == {"document": "doc-1"}
    assert [item.status for item in job.responses] == [
        EntityStatus.IN_PROGRESS,
        EntityStatus.COMPLETED,
    ]
    account.send_event_sync.assert_called_once()
    finished.assert_called_once_with(job, server=server)


def test_job_start_records_failed_response_then_reraises_execution_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = _agent("agent_lifecycle_module.run")
    context = _context()
    job = Job.new(job_context=context, agent_name=agent.name, agent_parameters=None)
    server = Mock()
    server.supervisor_account = None
    failure = RuntimeError("boom")
    monkeypatch.setattr(agent, "_execute", Mock(side_effect=failure))

    with pytest.raises(RuntimeError, match="boom"):
        agent.job_start(job, {}, context, server)

    assert [item.status for item in job.responses] == [
        EntityStatus.IN_PROGRESS,
        EntityStatus.FAILED,
    ]
    assert job.responses[-1].message == "Job execution failed: boom"


def test_update_agent_uses_slug_and_forwards_configured_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = _agent("agent_lifecycle_module.run")
    account = Mock()
    account.get_agent_by.return_value = ApiSuccess(
        message="ok",
        detail={
            "object": {
                "id": "studio-agent-1",
                "status": "ready",
                "onboarding_status": "configured",
                "parameters_encrypted": "encrypted",
            }
        },
        code=200,
    )
    server = Mock()
    server.supervisor_account = account
    update_parameters = Mock()
    monkeypatch.setattr(Agent, "update_parameters_from_server", update_parameters)

    updated = agent.update_agent_from_server(server)

    assert updated is agent
    account.get_agent_by.assert_called_once_with(agent_slug=agent.slug)
    assert agent.server_agent_id == "studio-agent-1"
    assert agent.server_agent_status == "ready"
    assert agent.server_agent_onboarding_status == "configured"
    update_parameters.assert_called_once_with(server, "encrypted")


def test_agent_chat_calls_the_declared_method_with_message_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, str] = {}
    module = ModuleType("agent_chat_test_module")

    def chat(context: str, message: str) -> JobResponse:
        received.update(context=context, message=message)
        return JobResponse(
            job_id="job-1",
            status=EntityStatus.COMPLETED,
            message="answered",
            payload={"reply": "hello"},
        )

    module.__dict__["chat"] = chat
    monkeypatch.setitem(sys.modules, module.__name__, module)
    path = f"{module.__name__}.chat"
    method = AgentMethod(name="chat", method=path)
    agent = Agent(
        name="Chat Agent", methods=AgentMethods(job_start=method, chat=method)
    )

    result = agent.chat(context="case context", message="question")

    assert result.payload == {"reply": "hello"}
    assert received == {"context": "case context", "message": "question"}


@pytest.mark.parametrize("has_methods", [True, False])
def test_agent_chat_requires_a_configured_chat_method(has_methods: bool) -> None:
    agent = (
        _agent("agent_lifecycle_module.run")
        if has_methods
        else Agent(name="No methods")
    )

    with pytest.raises(ValueError, match="Chat method not configured"):
        agent.chat(context="case context", message="question")
