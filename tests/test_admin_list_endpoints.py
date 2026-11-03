# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Behavior of the admin list endpoints: jobs, cases and agents.

The tests call the endpoints over HTTP, with a real in-memory StorageManager.
They read what the page template receives: the filtered, sorted and paginated
rows. They pin current behavior so the handlers can be restructured safely.
"""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from supervaizer.admin import routes
from supervaizer.admin.routes import create_admin_routes
from supervaizer.storage import StorageManager

JOBS: list[dict[str, Any]] = [
    {
        "id": "job-a",
        "name": "Alpha",
        "agent_name": "Agent One",
        "status": "completed",
        "created_at": "2024-01-03",
        "finished_at": "2024-01-04",
        "case_ids": ["c1", "c2"],
    },
    {
        "id": "job-b",
        "name": "Bravo",
        "agent_name": "Agent Two",
        "status": "in_progress",
        "created_at": "2024-01-01",
    },
    {
        "id": "job-c",
        "name": "Charlie",
        "agent_name": "agent one",
        "status": "failed",
        "created_at": "2024-01-02",
    },
]

CASES: list[dict[str, Any]] = [
    {
        "id": "case-1",
        "name": "Intake",
        "description": "Reads invoices",
        "status": "completed",
        "job_id": "job-a",
        "created_at": "2024-01-02",
        "finished_at": "2024-01-05",
        "total_cost": 2.5,
    },
    {
        "id": "case-2",
        "name": "Review",
        "description": "Checks totals",
        "status": "in_progress",
        "job_id": "job-a",
        "created_at": "2024-01-01",
        "total_cost": 10,
    },
    {
        "id": "case-3",
        "name": "Archive",
        "status": "failed",
        "job_id": "job-b",
        "created_at": "2024-01-03",
    },
]

AGENTS: list[dict[str, str]] = [
    {
        "name": "Zeta",
        "slug": "zeta",
        "description": "Does Z things",
        "type": "conversational",
    },
    {
        "name": "Alpha",
        "slug": "alpha",
        "description": "Helper for Zeta",
        "type": "Tooling",
    },
    {"name": "Mid"},
]


class Page:
    """What one endpoint call produced: the HTTP response and the template input."""

    def __init__(self, response: Any, template: str | None, context: dict[str, Any]):
        self.response = response
        self.template = template
        self.context = context

    @property
    def status(self) -> int:
        return int(self.response.status_code)

    def ids(self, key: str) -> list[str]:
        return [row["id"] for row in self.context[key]]

    def names(self, key: str) -> list[str]:
        return [row["name"] for row in self.context[key]]


class AdminRig:
    """An admin router bound to a real in-memory storage, with template calls recorded."""

    def __init__(self, mocker: MockerFixture) -> None:
        self.storage = StorageManager(":memory:")
        # In-memory StorageManager instances share their data: start from empty.
        self.storage._db.drop_tables()
        mocker.patch(
            "supervaizer.admin.routes.StorageManager", return_value=self.storage
        )
        self.spy = mocker.spy(routes.templates, "TemplateResponse")
        app = FastAPI()
        app.include_router(create_admin_routes(), prefix="/manage")
        self.client = TestClient(app, raise_server_exceptions=False)

    def seed(self, kind: str, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.storage.save_object(kind, dict(row))

    def get(self, url: str) -> Page:
        self.spy.reset_mock()
        response = self.client.get(url)
        if not self.spy.called:
            return Page(response, None, {})
        args = self.spy.call_args.args
        return Page(response, args[1], args[2])


@pytest.fixture
def rig(mocker: MockerFixture) -> Iterator[AdminRig]:
    admin_rig = AdminRig(mocker)
    yield admin_rig
    admin_rig.storage._db.drop_tables()


class TestJobsEndpoint:
    @pytest.fixture(autouse=True)
    def _seed(self, rig: AdminRig) -> None:
        rig.seed("Job", JOBS)

    def test_default_order_is_newest_first_and_uses_jobs_table(
        self, rig: AdminRig
    ) -> None:
        page = rig.get("/manage/api/jobs")
        assert page.status == 200
        assert page.template == "jobs_table.html"
        assert page.ids("jobs") == ["job-a", "job-c", "job-b"]

    def test_rows_are_formatted_for_display(self, rig: AdminRig) -> None:
        page = rig.get("/manage/api/jobs?sort=name")
        alpha, bravo, _ = page.context["jobs"]
        assert alpha == {
            "id": "job-a",
            "name": "Alpha",
            "agent_name": "Agent One",
            "status": "completed",
            "created_at": "2024-01-03",
            "finished_at": "2024-01-04",
            "case_count": 2,
        }
        assert bravo["finished_at"] is None
        assert bravo["case_count"] == 0

    def test_missing_fields_become_empty_strings(self, rig: AdminRig) -> None:
        rig.seed("Job", [{"id": "job-bare"}])
        page = rig.get("/manage/api/jobs?search=job-bare")
        assert page.context["jobs"] == [
            {
                "id": "job-bare",
                "name": "",
                "agent_name": "",
                "status": "",
                "created_at": "",
                "finished_at": None,
                "case_count": 0,
            }
        ]

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("status=completed", ["job-a"]),
            ("status=unknown", []),
            ("agent_name=AGENT%20ONE", ["job-a", "job-c"]),
            ("agent_name=two", ["job-b"]),
            ("search=brav", ["job-b"]),
            ("search=JOB-C", ["job-c"]),
            ("search=nothing-matches", []),
            ("status=failed&agent_name=one&search=char", ["job-c"]),
            ("status=failed&agent_name=two", []),
        ],
    )
    def test_filters(self, rig: AdminRig, query: str, expected: list[str]) -> None:
        page = rig.get(f"/manage/api/jobs?{query}")
        assert page.ids("jobs") == expected
        assert page.context["total"] == len(expected)

    @pytest.mark.parametrize(
        ("sort", "expected"),
        [
            ("created_at", ["job-b", "job-c", "job-a"]),
            ("-created_at", ["job-a", "job-c", "job-b"]),
            ("name", ["job-a", "job-b", "job-c"]),
            ("-name", ["job-c", "job-b", "job-a"]),
            ("status", ["job-a", "job-c", "job-b"]),
            ("-status", ["job-b", "job-c", "job-a"]),
            ("agent_name", ["job-a", "job-b", "job-c"]),
            ("-bogus", ["job-a", "job-b", "job-c"]),
        ],
    )
    def test_sort(self, rig: AdminRig, sort: str, expected: list[str]) -> None:
        assert rig.get(f"/manage/api/jobs?sort={sort}").ids("jobs") == expected

    @pytest.mark.parametrize(
        ("query", "expected", "has_next", "has_prev"),
        [
            ("limit=2", ["job-a", "job-c"], True, False),
            ("limit=2&skip=2", ["job-b"], False, True),
            ("limit=1&skip=1", ["job-c"], True, True),
            ("limit=3", ["job-a", "job-c", "job-b"], False, False),
            ("skip=5", [], False, True),
        ],
    )
    def test_pagination(
        self,
        rig: AdminRig,
        query: str,
        expected: list[str],
        has_next: bool,
        has_prev: bool,
    ) -> None:
        page = rig.get(f"/manage/api/jobs?{query}")
        assert page.ids("jobs") == expected
        assert page.context["total"] == 3
        assert (page.context["has_next"], page.context["has_prev"]) == (
            has_next,
            has_prev,
        )

    def test_pagination_context_echoes_limit_and_skip(self, rig: AdminRig) -> None:
        page = rig.get("/manage/api/jobs?limit=7&skip=1")
        assert (page.context["limit"], page.context["skip"]) == (7, 1)

    @pytest.mark.parametrize("query", ["limit=101", "skip=-1"])
    def test_out_of_range_paging_is_rejected(self, rig: AdminRig, query: str) -> None:
        assert rig.get(f"/manage/api/jobs?{query}").status == 422

    def test_storage_failure_becomes_500_with_message(
        self, rig: AdminRig, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            rig.storage, "get_objects", side_effect=RuntimeError("boom")
        )
        page = rig.get("/manage/api/jobs")
        assert page.status == 500
        assert page.response.json()["detail"] == "boom"


class TestCasesEndpoint:
    @pytest.fixture(autouse=True)
    def _seed(self, rig: AdminRig) -> None:
        rig.seed("Case", CASES)

    def test_default_order_is_newest_first_and_uses_cases_table(
        self, rig: AdminRig
    ) -> None:
        page = rig.get("/manage/api/cases")
        assert page.status == 200
        assert page.template == "cases_table.html"
        assert page.ids("cases") == ["case-3", "case-1", "case-2"]

    def test_rows_are_formatted_for_display(self, rig: AdminRig) -> None:
        page = rig.get("/manage/api/cases?sort=name")
        archive, intake, _ = page.context["cases"]
        assert intake == {
            "id": "case-1",
            "name": "Intake",
            "description": "Reads invoices",
            "status": "completed",
            "job_id": "job-a",
            "created_at": "2024-01-02",
            "finished_at": "2024-01-05",
            "total_cost": 2.5,
        }
        assert archive["description"] == ""
        assert archive["finished_at"] is None
        assert archive["total_cost"] == 0.0

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("status=failed", ["case-3"]),
            ("job_id=job-a", ["case-1", "case-2"]),
            ("job_id=JOB-A", []),
            ("search=INTAKE", ["case-1"]),
            ("search=case-2", ["case-2"]),
            ("search=totals", ["case-2"]),
            ("search=nothing-matches", []),
            ("status=completed&job_id=job-a&search=invoices", ["case-1"]),
            ("status=completed&job_id=job-b", []),
        ],
    )
    def test_filters(self, rig: AdminRig, query: str, expected: list[str]) -> None:
        page = rig.get(f"/manage/api/cases?{query}")
        assert sorted(page.ids("cases")) == sorted(expected)
        assert page.context["total"] == len(expected)

    @pytest.mark.parametrize(
        ("sort", "expected"),
        [
            ("created_at", ["case-2", "case-1", "case-3"]),
            ("-created_at", ["case-3", "case-1", "case-2"]),
            ("name", ["case-3", "case-1", "case-2"]),
            ("status", ["case-1", "case-3", "case-2"]),
            ("total_cost", ["case-3", "case-1", "case-2"]),
            ("-total_cost", ["case-2", "case-1", "case-3"]),
            ("job_id", ["case-1", "case-2", "case-3"]),
        ],
    )
    def test_sort(self, rig: AdminRig, sort: str, expected: list[str]) -> None:
        assert rig.get(f"/manage/api/cases?sort={sort}").ids("cases") == expected

    @pytest.mark.parametrize(
        ("query", "expected", "has_next", "has_prev"),
        [
            ("limit=2", ["case-3", "case-1"], True, False),
            ("limit=2&skip=2", ["case-2"], False, True),
            ("skip=5", [], False, True),
        ],
    )
    def test_pagination(
        self,
        rig: AdminRig,
        query: str,
        expected: list[str],
        has_next: bool,
        has_prev: bool,
    ) -> None:
        page = rig.get(f"/manage/api/cases?{query}")
        assert page.ids("cases") == expected
        assert page.context["total"] == 3
        assert (page.context["has_next"], page.context["has_prev"]) == (
            has_next,
            has_prev,
        )

    @pytest.mark.parametrize("query", ["limit=101", "skip=-1"])
    def test_out_of_range_paging_is_rejected(self, rig: AdminRig, query: str) -> None:
        assert rig.get(f"/manage/api/cases?{query}").status == 422

    def test_storage_failure_becomes_500_with_message(
        self, rig: AdminRig, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            rig.storage, "get_objects", side_effect=RuntimeError("boom")
        )
        page = rig.get("/manage/api/cases")
        assert page.status == 500
        assert page.response.json()["detail"] == "boom"


class TestAgentsEndpoint:
    @pytest.fixture(autouse=True)
    def _server_info(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "supervaizer.admin.routes._get_server_info",
            return_value=SimpleNamespace(agents=[dict(a) for a in AGENTS]),
        )

    def test_uses_agents_grid_template_and_keeps_registration_order(
        self, rig: AdminRig
    ) -> None:
        page = rig.get("/manage/api/agents")
        assert page.status == 200
        assert page.template == "agents_grid.html"
        assert page.names("agents") == ["Zeta", "Alpha", "Mid"]

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("status=all", ["Zeta", "Alpha", "Mid"]),
            ("status=active", ["Zeta", "Alpha", "Mid"]),
            ("status=inactive", []),
            ("agent_type=conversational", ["Zeta", "Mid"]),
            ("agent_type=CONVERSATIONAL", ["Zeta", "Mid"]),
            ("agent_type=tooling", ["Alpha"]),
            ("agent_type=nothing", []),
            ("search=zeta", ["Zeta", "Alpha"]),
            ("search=helper", ["Alpha"]),
            ("search=MID", ["Mid"]),
            ("search=nothing-matches", []),
            ("agent_type=tooling&search=zeta", ["Alpha"]),
        ],
    )
    def test_filters(self, rig: AdminRig, query: str, expected: list[str]) -> None:
        assert rig.get(f"/manage/api/agents?{query}").names("agents") == expected

    @pytest.mark.parametrize(
        ("sort", "expected"),
        [
            ("name", ["Alpha", "Mid", "Zeta"]),
            ("-name", ["Zeta", "Mid", "Alpha"]),
            ("created_at", ["Zeta", "Alpha", "Mid"]),
            ("-created_at", ["Zeta", "Alpha", "Mid"]),
            ("bogus", ["Zeta", "Alpha", "Mid"]),
        ],
    )
    def test_sort(self, rig: AdminRig, sort: str, expected: list[str]) -> None:
        assert rig.get(f"/manage/api/agents?sort={sort}").names("agents") == expected


class TestAgentsEndpointWithoutServerInfo:
    def test_missing_server_info_is_reported_as_500(
        self, rig: AdminRig, mocker: MockerFixture
    ) -> None:
        mocker.patch("supervaizer.admin.routes._get_server_info", return_value=None)
        page = rig.get("/manage/api/agents")
        assert page.status == 500
        assert "Server information not available" in page.response.json()["detail"]
