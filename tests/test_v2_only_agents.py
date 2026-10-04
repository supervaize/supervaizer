# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Agents that declare only a v2 registration run with the /api router mounted."""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from supervaizer import Account, Agent, Server, build_v2_agent_registration
from supervaizer.admin.routes import create_admin_routes
from supervaizer.contracts import AgentRegistrationContract
from supervaizer.job import Jobs
from supervaizer.protocol.a2a import create_agent_card

AGENT_NAME = "V2 Only Agent"
AGENT_SLUG = "v2-only-agent"
AGENT_API_PATH = f"/api/supervaizer/agents/{AGENT_SLUG}"


def _v2_only_agent() -> Agent:
    registration = build_v2_agent_registration(
        agent_id=AGENT_SLUG,
        agent_slug=AGENT_SLUG,
        display_name=AGENT_NAME,
        agent_card_url=f"/.well-known/agents/v1.0.0/{AGENT_SLUG}_agent.json",
        controller_url="/a2a",
        a2ui_catalog_version="v2-only-ui.1",
        surfaces=["job.start"],
        actions=["job.start"],
    )
    return Agent(
        name=AGENT_NAME,
        version="1.0.0",
        description="Agent with a v2 registration and no v1 methods.",
        supervaizer_v2_registration=registration,
    )


def _assert_v1_job_routes_skipped(server: Server) -> None:
    paths = TestClient(server.app).get("/openapi.json").json()["paths"]
    assert f"{AGENT_API_PATH}/" in paths
    assert f"{AGENT_API_PATH}/parameters" in paths
    assert f"{AGENT_API_PATH}/jobs" not in paths
    assert f"{AGENT_API_PATH}/stop" not in paths
    assert f"{AGENT_API_PATH}/status" not in paths


def test_v2_only_agent_starts_in_local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
    monkeypatch.setenv("SUPERVAIZER_DISABLE_HELLO_WORLD", "true")

    server = Server(agents=[_v2_only_agent()], api_key="test-key")

    _assert_v1_job_routes_skipped(server)


def test_v2_only_agent_routes_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
    monkeypatch.setenv("SUPERVAIZER_DISABLE_HELLO_WORLD", "true")
    server = Server(agents=[_v2_only_agent()], api_key="test-key")
    client = TestClient(server.app)
    headers = {"X-API-Key": "test-key"}

    listed = client.get("/api/supervaizer/agents", headers=headers)
    info = client.get(f"{AGENT_API_PATH}/", headers=headers)
    updated = client.post(f"{AGENT_API_PATH}/parameters", headers=headers, json={})

    assert [r.status_code for r in (listed, info, updated)] == [200, 200, 200]
    assert info.json()["methods"] is None


def test_workbench_start_rejects_v2_only_agent_without_creating_a_job() -> None:
    app = FastAPI()
    app.state.server = Mock(agents=[_v2_only_agent()], supervisor_account=None)
    with patch("supervaizer.admin.routes.StorageManager"):
        app.include_router(create_admin_routes(), prefix="/manage")

    response = TestClient(app).post(
        f"/manage/agents/{AGENT_SLUG}/workbench/start", json={}
    )

    assert response.status_code == 400
    assert Jobs().get_agent_jobs(AGENT_NAME) == {}


def test_v2_only_agent_starts_with_supervisor_account(
    monkeypatch: pytest.MonkeyPatch, account_fixture: Account
) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "false")

    server = Server(
        agents=[_v2_only_agent()],
        supervisor_account=account_fixture,
        api_key="test-key",
    )

    assert server.supervisor_account is not None
    _assert_v1_job_routes_skipped(server)


def test_v2_only_agent_registration_sends_empty_methods() -> None:
    info = _v2_only_agent().registration_info

    contract = AgentRegistrationContract.model_validate({
        key: info[key] for key in ("slug", "name", "api_path", "methods")
    })

    assert info["methods"] == {}
    assert contract.methods == {}
    assert info["supervaizer_v2"]["agent"]["slug"] == AGENT_SLUG


def test_v2_only_agent_card_advertises_no_v1_job_routes() -> None:
    card = create_agent_card(_v2_only_agent(), "https://agent.example.com")

    assert card["tools"] == []
    examples = card["api_endpoints"][0]["examples"]
    assert [example["name"] for example in examples] == ["Get agent info"]
    assert card["supervaizer"]["v2"]["agent"]["slug"] == AGENT_SLUG


def test_agent_without_methods_or_v2_registration_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPERVAIZER_LOCAL_MODE", "true")
    monkeypatch.setenv("SUPERVAIZER_DISABLE_HELLO_WORLD", "true")
    agent = Agent(name="Bare Agent", version="1.0.0", description="No methods.")

    with pytest.raises(ValueError, match="has no methods defined"):
        Server(agents=[agent], api_key="test-key")
