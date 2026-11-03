# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Shared rig for workbench endpoint tests: one agent, one job, one case."""

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    AgentMethods,
    Case,
    EntityStatus,
    Job,
    JobContext,
)
from supervaizer.admin import workbench_routes
from supervaizer.admin.routes import create_admin_routes
from supervaizer.admin.workbench_routes import create_workbench_ws_routes
from supervaizer.case import Cases
from supervaizer.job import Jobs
from tests.admin_rig import Page

JOB_ID = "wb-job"
CASE_ID = "wb-case"
AGENT_NAME = "Workbench Agent"


class WorkbenchRig:
    """The admin and workbench routers on an app that serves one live agent."""

    def __init__(
        self,
        account: Account,
        mocker: MockerFixture,
        *,
        stoppable: bool = True,
        reports_status: bool = True,
    ) -> None:
        Cases().reset()
        Jobs().reset()
        methods = AgentMethods(
            job_start=AgentMethod(name="job_start", method="test_module.start"),
            job_stop=AgentMethod(name="job_stop", method="test_module.stop")
            if stoppable
            else None,
            job_status=AgentMethod(name="job_status", method="test_module.status")
            if reports_status
            else None,
        )
        self.agent = Agent(
            name=AGENT_NAME,
            version="1.0.0",
            description="Agent for workbench tests",
            methods=methods,
        )
        context = JobContext(
            workspace_id="ws",
            job_id=JOB_ID,
            started_by="tester",
            started_at=datetime.now(UTC),
            mission_id="m",
            mission_name="M",
        )
        self.job = Job.new(job_context=context, agent_name=AGENT_NAME)
        self.case = Case(
            id=CASE_ID,
            job_id=JOB_ID,
            account=account,
            status=EntityStatus.IN_PROGRESS,
            name="Case",
            description="Case of the workbench job",
        )
        self.job.add_case_id(self.case.id)
        self.spy = mocker.spy(workbench_routes.templates, "TemplateResponse")
        app = FastAPI()
        app.state.server = type("Server", (), {"agents": [self.agent]})()
        app.include_router(create_admin_routes(), prefix="/manage")
        app.include_router(create_workbench_ws_routes(), prefix="/manage")
        self.client = TestClient(app, raise_server_exceptions=False)

    def url(self, suffix: str = "", slug: str | None = None) -> str:
        return f"/manage/agents/{slug or self.agent.slug}/workbench{suffix}"

    def job_url(self, suffix: str = "") -> str:
        return self.url(f"/jobs/{JOB_ID}{suffix}")

    def request(self, method: str, url: str, **kwargs: Any) -> Page:
        self.spy.reset_mock()
        response = self.client.request(method, url, **kwargs)
        if not self.spy.called:
            return Page(response, None, {})
        args = self.spy.call_args.args
        return Page(response, args[1], args[2])

    def get(self, url: str) -> Page:
        return self.request("GET", url)

    def close(self) -> None:
        Cases().reset()
        Jobs().reset()
