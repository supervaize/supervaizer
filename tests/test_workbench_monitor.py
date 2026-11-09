# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Workbench job pages: HITL form parsing, monitor, stop, status, console, history.

Calls go over HTTP on the real Cases and Jobs registries; template input is
read from the recorded TemplateResponse call.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from jinja2 import Environment
from pytest_mock import MockerFixture

from supervaizer import Agent, CaseNodeUpdate, EntityStatus
from supervaizer.admin import workbench_routes
from supervaizer.admin.workbench_routes import _normalize_hitl_form
from tests.workbench_rig import AGENT_NAME, JOB_ID, WorkbenchRig


class TestNormalizeHitlForm:
    def test_non_dict_gives_empty_form(self) -> None:
        assert _normalize_hitl_form("not a form") == {}  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "form",
        [
            {"question": "Ok?"},
            {"answer": "text"},
            {"answer": {"fields": "nope"}},
            {"answer": {}},
            {"approved": {"type": "checkbox"}},
        ],
    )
    def test_form_without_a_field_list_is_returned_as_is(
        self, form: dict[str, Any]
    ) -> None:
        assert _normalize_hitl_form(form) == form

    def test_fields_become_a_dict_keyed_by_name(self) -> None:
        form = {
            "answer": {
                "fields": [
                    {"name": "note", "description": "Your note", "required": True},
                    {"name": "plain"},
                ]
            }
        }
        assert _normalize_hitl_form(form) == {
            "note": {"type": "text", "label": "Your note", "required": True},
            "plain": {"type": "text", "label": "plain", "required": False},
        }

    @pytest.mark.parametrize(
        ("field_type", "expected"),
        [
            ("BooleanField", "checkbox"),
            ("CharField", "text"),
            ("TextField", "textarea"),
            ("IntegerField", "number"),
            ("ChoiceField", "select"),
            ("SomethingElse", "text"),
        ],
    )
    def test_field_type_maps_to_an_input_type(
        self, field_type: str, expected: str
    ) -> None:
        form = {"answer": {"fields": [{"name": "f", "field_type": field_type}]}}
        assert _normalize_hitl_form(form)["f"]["type"] == expected

    def test_choice_field_keeps_its_choices_as_options(self) -> None:
        form = {
            "answer": {
                "fields": [
                    {"name": "c", "field_type": "ChoiceField", "choices": ["a", "b"]},
                    {"name": "d", "field_type": "ChoiceField"},
                    {"name": "e", "field_type": "CharField", "choices": ["x"]},
                ]
            }
        }
        result = _normalize_hitl_form(form)
        assert result["c"]["options"] == ["a", "b"]
        assert "options" not in result["d"]
        assert "options" not in result["e"]

    def test_entries_that_are_not_named_fields_are_skipped(self) -> None:
        form = {
            "answer": {"fields": ["junk", {"description": "no name"}, {"name": "ok"}]}
        }
        assert list(_normalize_hitl_form(form)) == ["ok"]


def _await(rig: WorkbenchRig, *payloads: dict[str, Any] | None) -> None:
    rig.case.status = EntityStatus.AWAITING
    rig.case.updates = [
        CaseNodeUpdate(name=f"u{i}", payload=p) for i, p in enumerate(payloads)
    ]


FORM = {
    "supervaizer_form": {
        "answer": {"fields": [{"name": "ok", "field_type": "BooleanField"}]}
    }
}
DIALOG = {"supervaizer_dialog": {"title": "Pick one"}}
NORMALIZED = {"ok": {"type": "checkbox", "label": "ok", "required": False}}


class TestJobMonitor:
    def monitor(self, rig: WorkbenchRig) -> dict[str, Any]:
        page = rig.get(rig.job_url())
        assert page.status == 200
        assert page.template == "workbench_monitor.html"
        return page.context

    def test_unknown_job_shows_a_notice(self, workbench: WorkbenchRig) -> None:
        response = workbench.get(workbench.url("/jobs/nope")).response
        assert response.status_code == 200
        assert "Job not found" in response.text

    def test_unknown_agent_is_404(self, workbench: WorkbenchRig) -> None:
        response = workbench.get(
            workbench.url(f"/jobs/{JOB_ID}", slug="nobody")
        ).response
        assert response.status_code == 404

    def test_context_names_the_job_slug_and_cases(
        self, workbench: WorkbenchRig
    ) -> None:
        context = self.monitor(workbench)
        assert context["agent_slug"] == workbench.agent.slug
        assert context["job"] is workbench.job
        assert context["has_human_answer"] is False
        [entry] = context["cases_data"]
        assert entry == {"case": workbench.case, "hitl_form": None, "hitl_dialog": None}

    def test_case_not_awaiting_has_no_hitl_data(self, workbench: WorkbenchRig) -> None:
        workbench.case.updates = [CaseNodeUpdate(name="u", payload=FORM)]
        [entry] = self.monitor(workbench)["cases_data"]
        assert (entry["hitl_form"], entry["hitl_dialog"]) == (None, None)

    def test_awaiting_case_shows_its_form_normalized(
        self, workbench: WorkbenchRig
    ) -> None:
        _await(workbench, FORM)
        [entry] = self.monitor(workbench)["cases_data"]
        assert entry["hitl_form"] == NORMALIZED
        assert entry["hitl_dialog"] is None

    def test_awaiting_case_shows_its_dialog(self, workbench: WorkbenchRig) -> None:
        _await(workbench, DIALOG)
        [entry] = self.monitor(workbench)["cases_data"]
        assert entry["hitl_dialog"] == {"title": "Pick one"}
        assert entry["hitl_form"] is None

    @pytest.mark.parametrize(
        ("payloads", "expect_form"),
        [([FORM, DIALOG], False), ([DIALOG, FORM], True)],
    )
    def test_latest_hitl_update_wins(
        self, workbench: WorkbenchRig, payloads: list[dict[str, Any]], expect_form: bool
    ) -> None:
        _await(workbench, *payloads)
        [entry] = self.monitor(workbench)["cases_data"]
        assert (entry["hitl_form"] is not None) is expect_form
        assert (entry["hitl_dialog"] is not None) is not expect_form

    def test_scan_skips_later_updates_that_carry_no_hitl_data(
        self, workbench: WorkbenchRig
    ) -> None:
        _await(workbench, FORM, None, {"other": 1})
        [entry] = self.monitor(workbench)["cases_data"]
        assert entry["hitl_form"] == NORMALIZED

    def test_awaiting_case_without_hitl_updates_has_none(
        self, workbench: WorkbenchRig
    ) -> None:
        _await(workbench, None, {"other": 1})
        [entry] = self.monitor(workbench)["cases_data"]
        assert (entry["hitl_form"], entry["hitl_dialog"]) == (None, None)

    def test_human_answer_method_is_reported(self, workbench: WorkbenchRig) -> None:
        workbench.agent.methods.human_answer = SimpleNamespace(method="x.y")
        assert self.monitor(workbench)["has_human_answer"] is True


class TestStopJob:
    def test_stops_the_job_and_runs_the_stop_method(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        run = mocker.patch.object(
            Agent, "_execute", return_value=SimpleNamespace(message="halted")
        )
        response = workbench.request("POST", workbench.job_url("/stop")).response
        assert response.status_code == 200
        assert response.json() == {"status": "stopped", "message": "halted"}
        assert workbench.job.status == EntityStatus.STOPPED
        run.assert_called_once()
        assert run.call_args.args[1] == {"job_id": JOB_ID}

    def test_unknown_job_still_runs_the_stop_method(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        run = mocker.patch.object(
            Agent, "_execute", return_value=SimpleNamespace(message="m")
        )
        response = workbench.request("POST", workbench.url("/jobs/other/stop")).response
        assert response.status_code == 200
        assert run.call_args.args[1] == {"job_id": "other"}

    def test_failing_stop_method_is_500(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(Agent, "_execute", side_effect=RuntimeError("kaput"))
        response = workbench.request("POST", workbench.job_url("/stop")).response
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to stop job: kaput"

    def test_agent_without_stop_method_is_400(
        self, account_fixture: Any, mocker: MockerFixture
    ) -> None:
        rig = WorkbenchRig(account_fixture, mocker, stoppable=False)
        try:
            response = rig.request("POST", rig.job_url("/stop")).response
        finally:
            rig.close()
        assert response.status_code == 400
        assert response.json()["detail"] == "Agent has no job_stop method"


class TestJobStatus:
    def test_asks_the_agent_status_method(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        run = mocker.patch.object(
            Agent,
            "_execute",
            return_value=SimpleNamespace(status=EntityStatus.COMPLETED, message="done"),
        )
        response = workbench.get(workbench.job_url("/status")).response
        assert response.status_code == 200
        assert response.json() == {"status": "completed", "message": "done"}
        assert run.call_args.args[1] == {"job_id": JOB_ID}

    def test_failing_status_method_is_500(
        self, workbench: WorkbenchRig, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(Agent, "_execute", side_effect=RuntimeError("kaput"))
        response = workbench.get(workbench.job_url("/status")).response
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to get status: kaput"

    def test_without_status_method_reads_the_job_directly(
        self, account_fixture: Any, mocker: MockerFixture
    ) -> None:
        rig = WorkbenchRig(account_fixture, mocker, reports_status=False)
        try:
            found = rig.get(rig.job_url("/status")).response
            missing = rig.get(rig.url("/jobs/nope/status")).response
        finally:
            rig.close()
        assert found.status_code == 200
        assert found.json() == {"job_id": JOB_ID, "status": rig.job.status.value}
        assert missing.status_code == 404
        assert missing.json()["detail"] == "Job not found"


class TestConsole:
    @pytest.fixture(autouse=True)
    def _buffer(self, mocker: MockerFixture) -> None:
        entries = [
            {"timestamp": f"t{n}", "level": "INFO", "message": f"m{n}"}
            for n in range(3)
        ]
        mocker.patch.object(workbench_routes, "_workbench_log_buffer", entries)

    def test_returns_entries_after_last_index(self, workbench: WorkbenchRig) -> None:
        page = workbench.get(workbench.url("/console?last_index=1"))
        assert page.template == "workbench_console.html"
        assert [e["message"] for e in page.context["entries"]] == ["m1", "m2"]
        assert page.context["next_index"] == 3
        assert page.context["agent_slug"] == workbench.agent.slug

    @pytest.mark.parametrize("query", ["", "?last_index=abc", "?last_index="])
    def test_missing_or_bad_index_starts_from_the_beginning(
        self, workbench: WorkbenchRig, query: str
    ) -> None:
        page = workbench.get(workbench.url(f"/console{query}"))
        assert len(page.context["entries"]) == 3

    def test_index_past_the_end_gives_no_entries(self, workbench: WorkbenchRig) -> None:
        page = workbench.get(workbench.url("/console?last_index=9"))
        assert page.context["entries"] == []
        assert page.context["next_index"] == 3


class TestJobsList:
    def test_lists_the_agent_jobs_newest_first(self, workbench: WorkbenchRig) -> None:
        older = workbench.job
        older_dt = older.created_at
        newer = type(older).new(
            job_context=older.job_context.model_copy(update={"job_id": "wb-job-2"}),
            agent_name=AGENT_NAME,
        )
        assert newer.created_at >= older_dt
        page = workbench.get(workbench.url("/jobs"))
        assert page.template == "workbench_jobs_list.html"
        assert page.context["agent_slug"] == workbench.agent.slug
        assert [j.id for j in page.context["jobs"]] == [newer.id, older.id]

    def test_unknown_agent_is_404(self, workbench: WorkbenchRig) -> None:
        assert workbench.get(workbench.url("/jobs", slug="nobody")).status == 404


def test_every_admin_template_compiles() -> None:
    """A template with a syntax error only fails when a page renders it."""
    env = workbench_routes.templates.env
    assert isinstance(env, Environment)
    names = env.list_templates(extensions=["html"])
    assert names
    for name in names:
        env.get_template(name)


def test_monitor_renders_scheduled_step_controls(workbench: WorkbenchRig) -> None:
    workbench.case.updates = [
        CaseNodeUpdate(
            name="later",
            scheduled_at=datetime(2030, 1, 1, tzinfo=UTC),
            scheduled_status="pending",
        )
    ]
    response = workbench.get(workbench.job_url()).response
    assert response.status_code == 200
    assert "later" in response.text
