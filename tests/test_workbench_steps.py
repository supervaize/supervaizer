# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Scheduled-step endpoints of the workbench: execute now, cancel, reschedule.

Calls go over HTTP. Cases and jobs live in the real Cases and Jobs registries.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    AgentMethods,
    Case,
    CaseNodeUpdate,
    EntityStatus,
    Job,
    JobContext,
)
from supervaizer.admin.routes import create_admin_routes
from supervaizer.case import Cases
from supervaizer.job import Jobs

JOB_ID = "step-job"
CASE_ID = "step-case"
AGENT_NAME = "Step Agent"
SCHEDULED_AT = datetime(2030, 1, 1, tzinfo=UTC)


@dataclass
class StepRig:
    client: TestClient
    agent: Agent
    job: Job
    case: Case

    def url(self, action: str, index: int = 0, case_id: str = CASE_ID) -> str:
        return (
            f"/manage/agents/{self.agent.slug}/workbench/jobs/{JOB_ID}"
            f"/steps/{case_id}/{index}/{action}"
        )

    def post(self, action: str, index: int = 0, case_id: str = CASE_ID) -> Any:
        return self.client.post(self.url(action, index, case_id))

    def patch(self, body: dict[str, Any], index: int = 0) -> Any:
        return self.client.patch(self.url("schedule", index), json=body)

    def step(self, index: int = 0) -> CaseNodeUpdate:
        return self.case.updates[index]


@pytest.fixture
def rig(account_fixture: Account) -> Iterator[StepRig]:
    Cases().reset()
    Jobs().reset()
    agent = Agent(
        name=AGENT_NAME,
        version="1.0.0",
        description="Agent with scheduled steps",
        methods=AgentMethods(
            job_start=AgentMethod(name="job_start", method="test_module.start"),
        ),
    )
    context = JobContext(
        workspace_id="ws",
        job_id=JOB_ID,
        started_by="tester",
        started_at=datetime.now(UTC),
        mission_id="m",
        mission_name="M",
    )
    job = Job.new(job_context=context, agent_name=AGENT_NAME)
    case = Case(
        id=CASE_ID,
        job_id=JOB_ID,
        account=account_fixture,
        status=EntityStatus.IN_PROGRESS,
        name="Case",
        description="Case with steps",
    )
    case.updates = [
        CaseNodeUpdate(
            scheduled_at=SCHEDULED_AT,
            scheduled_status="pending",
            scheduled_method="test_module.later",
            scheduled_params={"x": 1},
        )
    ]
    job.add_case_id(case.id)
    app = FastAPI()
    app.state.server = type("Server", (), {"agents": [agent]})()
    app.include_router(create_admin_routes(), prefix="/manage")
    yield StepRig(TestClient(app), agent, job, case)
    Cases().reset()
    Jobs().reset()


ACTIONS = ["execute", "cancel"]


@pytest.mark.parametrize("action", ACTIONS)
class TestStepPreconditions:
    """Checks that execute and cancel share, in the order they apply."""

    def test_unknown_agent_slug_is_404(self, rig: StepRig, action: str) -> None:
        response = rig.client.post(rig.url(action).replace(rig.agent.slug, "nobody"))
        assert response.status_code == 404
        assert "nobody" in response.json()["detail"]

    def test_unknown_case_is_404(self, rig: StepRig, action: str) -> None:
        response = rig.post(action, case_id="nope")
        assert response.status_code == 404
        assert response.json()["detail"] == "Case 'nope' not found"

    @pytest.mark.parametrize("index", [-1, 1, 99])
    def test_step_index_out_of_range_is_404(
        self, rig: StepRig, action: str, index: int
    ) -> None:
        response = rig.post(action, index=index)
        assert response.status_code == 404
        assert response.json()["detail"] == "Step not found"

    def test_step_without_schedule_is_400(self, rig: StepRig, action: str) -> None:
        rig.case.updates = [CaseNodeUpdate(name="plain")]
        response = rig.post(action)
        assert response.status_code == 400
        assert response.json()["detail"] == "Step is not a scheduled step"

    @pytest.mark.parametrize("status", ["completed", "cancelled", "executing", None])
    def test_step_not_pending_is_409_and_unchanged(
        self, rig: StepRig, action: str, status: str | None
    ) -> None:
        object.__setattr__(rig.step(), "scheduled_status", status)
        response = rig.post(action)
        assert response.status_code == 409
        assert response.json()["detail"] == f"Step is not pending (current: {status})"
        assert rig.step().scheduled_status == status


class TestExecuteStep:
    def test_runs_the_scheduled_method_with_the_agent_allow_list(
        self, rig: StepRig, mocker: MockerFixture
    ) -> None:
        run = mocker.patch(
            "supervaizer.admin.workbench_routes._execute_scheduled_method"
        )
        response = rig.post("execute")
        assert response.status_code == 200
        assert response.json() == {
            "status": "completed",
            "message": "Step executed successfully",
        }
        run.assert_called_once_with(
            "test_module.later",
            {"x": 1},
            allowed_methods=rig.agent._declared_method_paths(),
        )
        assert rig.step().scheduled_status == "completed"

    def test_step_without_method_completes_without_running_anything(
        self, rig: StepRig, mocker: MockerFixture
    ) -> None:
        run = mocker.patch(
            "supervaizer.admin.workbench_routes._execute_scheduled_method"
        )
        object.__setattr__(rig.step(), "scheduled_method", None)
        assert rig.post("execute").status_code == 200
        run.assert_not_called()
        assert rig.step().scheduled_status == "completed"

    def test_missing_params_are_passed_as_empty_dict(
        self, rig: StepRig, mocker: MockerFixture
    ) -> None:
        run = mocker.patch(
            "supervaizer.admin.workbench_routes._execute_scheduled_method"
        )
        object.__setattr__(rig.step(), "scheduled_params", None)
        rig.post("execute")
        assert run.call_args.args[1] == {}

    def test_failing_method_is_reported_as_500_and_marks_step_failed(
        self, rig: StepRig, mocker: MockerFixture
    ) -> None:
        mocker.patch(
            "supervaizer.admin.workbench_routes._execute_scheduled_method",
            side_effect=RuntimeError("kaput"),
        )
        response = rig.post("execute")
        assert response.status_code == 500
        assert response.json() == {
            "status": "failed",
            "message": "Execution failed: kaput",
        }
        assert rig.step().scheduled_status == "failed"

    def test_unknown_job_is_404(self, rig: StepRig) -> None:
        Jobs().reset()
        response = rig.post("execute")
        assert response.status_code == 404
        assert response.json()["detail"] == (
            f"Job '{JOB_ID}' not found for agent '{rig.agent.slug}'"
        )

    def test_case_outside_the_job_is_404_and_not_run(
        self, rig: StepRig, mocker: MockerFixture
    ) -> None:
        run = mocker.patch(
            "supervaizer.admin.workbench_routes._execute_scheduled_method"
        )
        rig.job.case_ids.clear()
        response = rig.post("execute")
        assert response.status_code == 404
        assert response.json()["detail"] == (
            f"Case '{CASE_ID}' not found for agent '{rig.agent.slug}'"
        )
        run.assert_not_called()
        assert rig.step().scheduled_status == "pending"


class TestCancelStep:
    def test_pending_step_is_cancelled(self, rig: StepRig) -> None:
        response = rig.post("cancel")
        assert response.status_code == 200
        assert response.json() == {"status": "cancelled", "message": "Step cancelled"}
        assert rig.step().scheduled_status == "cancelled"


class TestRescheduleStep:
    def test_pending_step_moves_to_the_new_time(self, rig: StepRig) -> None:
        response = rig.patch({"scheduled_at": "2031-05-06T07:08:09+00:00"})
        assert response.status_code == 200
        assert response.json() == {
            "status": "rescheduled",
            "message": "Step rescheduled to 2031-05-06T07:08:09+00:00",
        }
        assert rig.step().scheduled_at == datetime(2031, 5, 6, 7, 8, 9, tzinfo=UTC)
        assert rig.step().scheduled_status == "pending"

    def test_zulu_suffix_is_accepted(self, rig: StepRig) -> None:
        response = rig.patch({"scheduled_at": "2031-05-06T07:08:09Z"})
        assert response.status_code == 200
        assert rig.step().scheduled_at == datetime(2031, 5, 6, 7, 8, 9, tzinfo=UTC)

    @pytest.mark.parametrize("body", [{}, {"scheduled_at": ""}, {"scheduled_at": None}])
    def test_missing_time_is_400(self, rig: StepRig, body: dict[str, Any]) -> None:
        response = rig.patch(body)
        assert response.status_code == 400
        assert response.json()["detail"] == "scheduled_at is required"
        assert rig.step().scheduled_at == SCHEDULED_AT

    @pytest.mark.parametrize("value", ["tomorrow", "2031-13-45", 12345])
    def test_unreadable_time_is_400(self, rig: StepRig, value: object) -> None:
        response = rig.patch({"scheduled_at": value})
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid datetime format"
        assert rig.step().scheduled_at == SCHEDULED_AT

    def test_unknown_case_is_404(self, rig: StepRig) -> None:
        response = rig.client.patch(
            rig.url("schedule", case_id="nope"), json={"scheduled_at": "2031-01-01"}
        )
        assert response.status_code == 404

    def test_step_not_pending_is_409_before_the_body_is_read(
        self, rig: StepRig
    ) -> None:
        object.__setattr__(rig.step(), "scheduled_status", "completed")
        response = rig.patch({})
        assert response.status_code == 409

    def test_unknown_agent_slug_is_404(self, rig: StepRig) -> None:
        response = rig.client.patch(
            rig.url("schedule").replace(rig.agent.slug, "nobody"),
            json={"scheduled_at": "2031-01-01"},
        )
        assert response.status_code == 404
