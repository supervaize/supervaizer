# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Workbench page, job start and HITL answer endpoints.

Calls go over HTTP on the real Cases and Jobs registries. The agent method that
would run user code is replaced by a recorder.
"""

import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from pytest_mock import MockerFixture

from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    CaseNodeUpdate,
    EntityStatus,
    JobResponse,
    Parameter,
)
from supervaizer.agent import AgentMethodField, FieldTypeEnum
from supervaizer.job import Jobs
from tests.workbench_rig import AGENT_NAME, CASE_ID, JOB_ID, WorkbenchRig

TOKEN = Parameter(
    name="TOKEN", description="Access token", is_required=True, is_secret=True
)
REGION = Parameter(name="REGION", description="Where", value="eu-default")
COUNT = AgentMethodField(
    name="count",
    type=int,
    field_type=FieldTypeEnum.INT,
    description="How many",
    required=True,
    default=2,
)


def wait_until(condition: Callable[[], bool], seconds: float = 3.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.01)


@pytest.fixture
def configured(mocker: MockerFixture, account_fixture: Account) -> Any:
    """A workbench whose agent has two parameters and one start field."""
    rig = WorkbenchRig(
        account_fixture,
        mocker,
        parameters=[TOKEN.model_copy(), REGION.model_copy()],
        start_fields=[COUNT],
    )
    yield rig
    rig.close()


class TestWorkbenchPage:
    def test_page_context_describes_parameters_and_start_fields(
        self, configured: WorkbenchRig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TOKEN", raising=False)
        monkeypatch.delenv("REGION", raising=False)
        page = configured.get(configured.url())
        assert page.status == 200
        assert page.template == "workbench.html"
        assert page.context["agent_slug"] == configured.agent.slug
        assert page.context["parameters"] == [
            {
                "name": "TOKEN",
                "description": "Access token",
                "is_required": True,
                "is_secret": True,
                "value": "",
                "from_env": False,
            },
            {
                "name": "REGION",
                "description": "Where",
                "is_required": False,
                "is_secret": False,
                "value": "eu-default",
                "from_env": False,
            },
        ]
        assert page.context["job_fields"] == [
            {
                "name": "count",
                "field_type": "IntegerField",
                "description": "How many",
                "choices": None,
                "default": 2,
                "required": True,
                "widget": None,
            }
        ]

    def test_environment_value_wins_over_the_parameter_value(
        self, configured: WorkbenchRig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REGION", "us-east")
        monkeypatch.delenv("TOKEN", raising=False)
        by_name = {
            p["name"]: p for p in configured.get(configured.url()).context["parameters"]
        }
        assert (by_name["REGION"]["value"], by_name["REGION"]["from_env"]) == (
            "us-east",
            True,
        )

    def test_agent_without_parameters_or_fields_gets_empty_lists(
        self, workbench: WorkbenchRig
    ) -> None:
        context = workbench.get(workbench.url()).context
        assert (context["parameters"], context["job_fields"]) == ([], [])
        assert context["agents"] == [{"slug": workbench.agent.slug, "name": AGENT_NAME}]
        assert context["api_version"]

    def test_running_job_is_offered_as_the_active_job(
        self, workbench: WorkbenchRig
    ) -> None:
        workbench.job.status = EntityStatus.IN_PROGRESS
        assert workbench.get(workbench.url()).context["active_job"] is workbench.job

    def test_finished_job_is_not_active(self, workbench: WorkbenchRig) -> None:
        workbench.job.status = EntityStatus.COMPLETED
        assert workbench.get(workbench.url()).context["active_job"] is None

    def test_page_reports_human_answer_support_and_local_mode(
        self, workbench: WorkbenchRig
    ) -> None:
        context = workbench.get(workbench.url()).context
        assert context["has_human_answer"] is False
        assert context["local_mode"] is True  # no supervisor account on the test server
        workbench.agent.methods.human_answer = AgentMethod(name="h", method="m.h")
        assert workbench.get(workbench.url()).context["has_human_answer"] is True

    def test_unknown_agent_is_404(self, workbench: WorkbenchRig) -> None:
        assert workbench.get(workbench.url(slug="nobody")).status == 404


class TestStartJob:
    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TOKEN", raising=False)
        monkeypatch.delenv("REGION", raising=False)

    def start(self, rig: WorkbenchRig, body: dict[str, Any]) -> Any:
        return rig.request("POST", rig.url("/start"), json=body).response

    def test_started_job_is_registered_and_run_with_merged_parameters(
        self,
        configured: WorkbenchRig,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("REGION", "from-env")
        execute = mocker.patch.object(
            Agent,
            "_execute",
            return_value=JobResponse(
                job_id="x", status=EntityStatus.COMPLETED, message="done"
            ),
        )
        response = self.start(
            configured,
            {
                "parameters": {"TOKEN": "typed", "EXTRA": "kept", "BLANK": ""},
                "fields": {"count": 3},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "STARTING"
        assert body["message"] == "Job started from workbench"
        wait_until(lambda: execute.called)
        action, params = execute.call_args.args
        assert action == "test_module.start"
        assert params["fields"] == {"count": 3}
        assert params["agent_parameters"] == [
            {"name": "TOKEN", "value": "typed"},
            {"name": "REGION", "value": "from-env"},
            {"name": "EXTRA", "value": "kept"},
        ]
        context = params["context"]
        assert (context.workspace_id, context.started_by) == (
            "workbench",
            "workbench-admin",
        )
        assert (context.mission_id, context.mission_name) == ("local", "Workbench Test")
        assert context.job_id == body["id"]

    def test_typed_values_are_stored_on_the_agent_parameters(
        self, configured: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            Agent,
            "_execute",
            return_value=JobResponse(
                job_id="x", status=EntityStatus.COMPLETED, message=""
            ),
        )
        self.start(configured, {"parameters": {"TOKEN": "typed"}})
        definitions = configured.agent.parameters_setup.definitions
        assert definitions["TOKEN"].value == "typed"
        assert definitions["REGION"].value == "eu-default"

    def test_no_parameters_at_all_runs_with_an_empty_list(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        execute = mocker.patch.object(
            Agent,
            "_execute",
            return_value=JobResponse(
                job_id="x", status=EntityStatus.COMPLETED, message=""
            ),
        )
        assert self.start(workbench, {}).status_code == 200
        wait_until(lambda: execute.called)
        params = execute.call_args.args[1]
        assert (params["agent_parameters"], params["fields"]) == ([], {})

    def test_job_is_created_for_the_agent_and_gets_the_method_result(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            Agent,
            "_execute",
            return_value=JobResponse(
                job_id="x", status=EntityStatus.COMPLETED, message="all done"
            ),
        )
        job_id = self.start(workbench, {}).json()["id"]
        job = next(j for j in jobs_of(workbench) if j.id == job_id)
        assert (job.name, job.agent_name) == ("Workbench Test", AGENT_NAME)
        wait_until(lambda: job.status == EntityStatus.COMPLETED)

    def test_failing_method_marks_the_job_failed(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(Agent, "_execute", side_effect=RuntimeError("boom"))
        job_id = self.start(workbench, {}).json()["id"]
        job = next(j for j in jobs_of(workbench) if j.id == job_id)
        wait_until(lambda: job.status == EntityStatus.FAILED)
        assert any("Job failed: boom" in str(r.message) for r in job.responses)

    def test_agent_without_methods_is_rejected_before_any_job_exists(
        self, workbench: WorkbenchRig
    ) -> None:
        workbench.agent.methods = None
        before = len(jobs_of(workbench))
        response = self.start(workbench, {})
        assert response.status_code == 400
        assert "no methods" in response.json()["detail"]
        assert len(jobs_of(workbench)) == before

    def test_unknown_agent_is_404(self, workbench: WorkbenchRig) -> None:
        response = workbench.request(
            "POST", workbench.url("/start", slug="nobody"), json={}
        ).response
        assert response.status_code == 404


def jobs_of(rig: WorkbenchRig) -> list[Any]:
    return list(Jobs().get_agent_jobs(AGENT_NAME).values())


class TestAnswerHitl:
    @pytest.fixture(autouse=True)
    def _awaiting(self, workbench: WorkbenchRig, mocker: MockerFixture) -> None:
        mocker.patch(
            "supervaizer.account_service.send_event",
            new=mocker.AsyncMock(return_value=None),
        )
        workbench.case.status = EntityStatus.AWAITING
        workbench.case.updates = [
            CaseNodeUpdate(name="Approval", payload={"supervaizer_form": {"q": 1}})
        ]

    def answer(self, rig: WorkbenchRig, body: dict[str, Any]) -> Any:
        url = rig.job_url(f"/cases/{CASE_ID}/answer")
        return rig.request("POST", url, json=body).response

    def test_answer_moves_the_case_on_with_the_step_label(
        self, workbench: WorkbenchRig
    ) -> None:
        response = self.answer(workbench, {"answer": {"ok": True}})
        assert response.status_code == 200
        assert response.json() == {
            "status": "answered",
            "case_id": CASE_ID,
            "message": "HITL answer submitted and dispatched",
        }
        assert workbench.case.status == EntityStatus.IN_PROGRESS
        assert workbench.case.updates[-1].name == "HITL Answer"
        assert workbench.case.updates[-1].payload == {
            "ok": True,
            "_hitl_label": "Approval",
        }

    def test_label_defaults_when_no_update_asked_for_input(
        self, workbench: WorkbenchRig
    ) -> None:
        workbench.case.updates = [CaseNodeUpdate(name="plain", payload={"x": 1})]
        self.answer(workbench, {"answer": {"ok": True}})
        assert workbench.case.updates[-1].payload == {
            "ok": True,
            "_hitl_label": "User response",
        }

    def test_missing_answer_is_treated_as_empty(self, workbench: WorkbenchRig) -> None:
        assert self.answer(workbench, {}).status_code == 200
        assert workbench.case.updates[-1].payload == {"_hitl_label": "Approval"}

    def test_human_answer_method_is_run_with_the_answer(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        workbench.agent.methods.human_answer = AgentMethod(
            name="h", method="mod.answer"
        )
        execute = mocker.patch.object(Agent, "_execute", return_value=SimpleNamespace())
        assert self.answer(workbench, {"answer": {"ok": True}}).status_code == 200
        assert execute.call_args.args == (
            "mod.answer",
            {
                "fields": {"ok": True},
                "context": {"job_id": JOB_ID, "case_id": CASE_ID},
                "payload": {"ok": True},
                "case_id": CASE_ID,
                "job_id": JOB_ID,
            },
        )

    def test_failing_human_answer_is_500_after_the_case_moved_on(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        workbench.agent.methods.human_answer = AgentMethod(
            name="h", method="mod.answer"
        )
        mocker.patch.object(Agent, "_execute", side_effect=RuntimeError("nope"))
        response = self.answer(workbench, {"answer": {"ok": True}})
        assert response.status_code == 500
        assert response.json() == {
            "status": "error",
            "message": "human_answer failed: nope",
        }
        assert workbench.case.status == EntityStatus.IN_PROGRESS

    def test_no_methods_means_no_human_answer_call(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        workbench.agent.methods = None
        execute = mocker.patch.object(Agent, "_execute")
        assert self.answer(workbench, {"answer": {"ok": True}}).status_code == 200
        execute.assert_not_called()

    def test_unknown_case_is_404_and_not_awaiting_case_is_409(
        self, workbench: WorkbenchRig
    ) -> None:
        missing = workbench.request(
            "POST", workbench.job_url("/cases/nope/answer"), json={"answer": {}}
        ).response
        assert missing.status_code == 404
        workbench.case.status = EntityStatus.COMPLETED
        busy = self.answer(workbench, {"answer": {}})
        assert busy.status_code == 409
        assert CASE_ID in busy.json()["detail"]

    def test_unknown_agent_is_404(self, workbench: WorkbenchRig) -> None:
        url = workbench.url(f"/jobs/{JOB_ID}/cases/{CASE_ID}/answer", slug="nobody")
        assert workbench.request("POST", url, json={}).response.status_code == 404
