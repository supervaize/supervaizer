# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Behavior of the admin endpoints that show or change one job, case or agent.

Covers the detail pages, status updates, deletes, recent activity, agent detail
and static file serving. Calls go over HTTP against a real in-memory storage.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from pytest_mock import MockerFixture

from tests.admin_rig import AdminRig

JOB: dict[str, Any] = {"id": "job-1", "name": "Alpha", "status": "in_progress"}
CASES_OF_JOB: list[dict[str, Any]] = [
    {"id": "case-1", "job_id": "job-1", "name": "First", "status": "in_progress"},
    {"id": "case-2", "job_id": "job-1", "name": "Second", "status": "completed"},
]
OTHER_CASE: dict[str, Any] = {
    "id": "case-9",
    "job_id": "job-2",
    "name": "Elsewhere",
    "status": "stopped",
}
ORPHAN_CASE: dict[str, Any] = {"id": "case-8", "name": "No job", "status": "stopped"}


class TestJobDetails:
    def test_shows_job_with_its_cases_only(self, rig: AdminRig) -> None:
        rig.seed("Job", [JOB])
        rig.seed("Case", [*CASES_OF_JOB, OTHER_CASE])
        page = rig.get("/manage/api/jobs/job-1")
        assert page.status == 200
        assert page.template == "job_detail.html"
        assert page.context["job"] == JOB
        assert page.ids("cases") == ["case-1", "case-2"]

    def test_unknown_job_is_404(self, rig: AdminRig) -> None:
        page = rig.get("/manage/api/jobs/nope")
        assert page.status == 404
        assert page.response.json()["detail"] == "Job not found"

    def test_storage_failure_is_500(self, rig: AdminRig, mocker: MockerFixture) -> None:
        mocker.patch.object(
            rig.storage, "get_object_by_id", side_effect=OSError("disk")
        )
        page = rig.get("/manage/api/jobs/job-1")
        assert page.status == 500
        assert page.response.json()["detail"] == "disk"


class TestCaseDetails:
    def test_shows_case_with_its_job(self, rig: AdminRig) -> None:
        rig.seed("Job", [JOB])
        rig.seed("Case", CASES_OF_JOB)
        page = rig.get("/manage/api/cases/case-2")
        assert page.status == 200
        assert page.template == "case_detail.html"
        assert page.context["case"] == CASES_OF_JOB[1]
        assert page.context["job"] == JOB

    def test_case_without_job_id_has_no_job(self, rig: AdminRig) -> None:
        rig.seed("Case", [ORPHAN_CASE])
        page = rig.get("/manage/api/cases/case-8")
        assert page.status == 200
        assert page.context["job"] is None

    def test_case_with_missing_job_has_no_job(self, rig: AdminRig) -> None:
        rig.seed("Case", [OTHER_CASE])
        page = rig.get("/manage/api/cases/case-9")
        assert page.status == 200
        assert page.context["job"] is None

    def test_unknown_case_is_404(self, rig: AdminRig) -> None:
        page = rig.get("/manage/api/cases/nope")
        assert page.status == 404
        assert page.response.json()["detail"] == "Case not found"

    def test_storage_failure_is_500(self, rig: AdminRig, mocker: MockerFixture) -> None:
        mocker.patch.object(
            rig.storage, "get_object_by_id", side_effect=OSError("disk")
        )
        assert rig.get("/manage/api/cases/case-1").status == 500


@pytest.mark.parametrize(
    ("kind", "entity_id", "url_part", "label"),
    [("Job", "job-1", "jobs", "Job"), ("Case", "case-1", "cases", "Case")],
)
class TestStatusUpdate:
    def _seed(self, rig: AdminRig, kind: str, entity_id: str) -> None:
        rig.seed(kind, [{"id": entity_id, "status": "in_progress"}])

    def post(
        self, rig: AdminRig, url_part: str, entity_id: str, body: dict[str, str]
    ) -> Any:
        return rig.request(
            "POST", f"/manage/api/{url_part}/{entity_id}/status", json=body
        ).response

    @pytest.mark.parametrize("final", ["completed", "failed", "cancelled"])
    def test_final_status_is_saved_with_finish_time(
        self,
        rig: AdminRig,
        kind: str,
        entity_id: str,
        url_part: str,
        label: str,
        final: str,
    ) -> None:
        self._seed(rig, kind, entity_id)
        response = self.post(rig, url_part, entity_id, {"status": final})
        assert response.status_code == 200
        assert response.json() == {"message": f"{label} status updated successfully"}
        saved = rig.storage.get_object_by_id(kind, entity_id)
        assert saved is not None
        assert saved["status"] == final
        assert saved["finished_at"]

    @pytest.mark.parametrize("running", ["in_progress", "awaiting", "stopped"])
    def test_non_final_status_sets_no_finish_time(
        self,
        rig: AdminRig,
        kind: str,
        entity_id: str,
        url_part: str,
        label: str,
        running: str,
    ) -> None:
        self._seed(rig, kind, entity_id)
        assert (
            self.post(rig, url_part, entity_id, {"status": running}).status_code == 200
        )
        saved = rig.storage.get_object_by_id(kind, entity_id)
        assert saved is not None
        assert saved["status"] == running
        assert "finished_at" not in saved

    @pytest.mark.parametrize("body", [{}, {"status": ""}, {"status": "closed"}])
    def test_invalid_status_is_400_and_changes_nothing(
        self,
        rig: AdminRig,
        kind: str,
        entity_id: str,
        url_part: str,
        label: str,
        body: dict[str, str],
    ) -> None:
        self._seed(rig, kind, entity_id)
        response = self.post(rig, url_part, entity_id, body)
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid status"
        saved = rig.storage.get_object_by_id(kind, entity_id)
        assert saved is not None
        assert saved["status"] == "in_progress"

    def test_unknown_entity_is_404(
        self, rig: AdminRig, kind: str, entity_id: str, url_part: str, label: str
    ) -> None:
        response = self.post(rig, url_part, "nope", {"status": "completed"})
        assert response.status_code == 404
        assert response.json()["detail"] == f"{label} not found"

    def test_storage_failure_is_500(
        self,
        rig: AdminRig,
        mocker: MockerFixture,
        kind: str,
        entity_id: str,
        url_part: str,
        label: str,
    ) -> None:
        self._seed(rig, kind, entity_id)
        mocker.patch.object(rig.storage, "save_object", side_effect=OSError("disk"))
        response = self.post(rig, url_part, entity_id, {"status": "completed"})
        assert response.status_code == 500
        assert response.json()["detail"] == "disk"


class TestDelete:
    def delete(self, rig: AdminRig, url: str) -> Any:
        return rig.request("DELETE", url).response

    def test_delete_job_removes_it_and_its_cases_only(self, rig: AdminRig) -> None:
        rig.seed("Job", [JOB])
        rig.seed("Case", [*CASES_OF_JOB, OTHER_CASE])
        response = self.delete(rig, "/manage/api/jobs/job-1")
        assert response.status_code == 200
        assert response.json() == {
            "message": "Job and related cases deleted successfully"
        }
        assert rig.storage.get_objects("Job") == []
        assert [c["id"] for c in rig.storage.get_objects("Case")] == ["case-9"]

    def test_delete_unknown_job_is_404(self, rig: AdminRig) -> None:
        response = self.delete(rig, "/manage/api/jobs/nope")
        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    def test_delete_case_removes_only_that_case(self, rig: AdminRig) -> None:
        rig.seed("Case", CASES_OF_JOB)
        response = self.delete(rig, "/manage/api/cases/case-1")
        assert response.status_code == 200
        assert response.json() == {"message": "Case deleted successfully"}
        assert [c["id"] for c in rig.storage.get_objects("Case")] == ["case-2"]

    def test_delete_unknown_case_is_404(self, rig: AdminRig) -> None:
        response = self.delete(rig, "/manage/api/cases/nope")
        assert response.status_code == 404
        assert response.json()["detail"] == "Case not found"

    @pytest.mark.parametrize("url", ["/manage/api/jobs/job-1", "/manage/api/cases/c"])
    def test_storage_failure_is_500(
        self, rig: AdminRig, mocker: MockerFixture, url: str
    ) -> None:
        mocker.patch.object(rig.storage, "delete_object", side_effect=OSError("disk"))
        mocker.patch.object(rig.storage, "get_cases_for_job", return_value=[])
        response = self.delete(rig, url)
        assert response.status_code == 500
        assert response.json()["detail"] == "disk"


class TestRecentActivity:
    def test_empty_storage_gives_no_activity(self, rig: AdminRig) -> None:
        page = rig.get("/manage/api/recent-activity")
        assert page.status == 200
        assert page.template == "recent_activity.html"
        assert page.context["activities"] == []

    def test_takes_last_five_of_each_kind_newest_first_capped_at_ten(
        self, rig: AdminRig
    ) -> None:
        rig.seed(
            "Job",
            [
                {"id": f"job-{n}", "name": f"J{n}", "created_at": f"2024-01-{n:02d}"}
                for n in range(1, 8)
            ],
        )
        rig.seed(
            "Case",
            [
                {
                    "id": f"case-{n}",
                    "name": f"C{n}",
                    "job_id": "job-1",
                    "created_at": f"2024-02-{n:02d}",
                }
                for n in range(1, 8)
            ],
        )
        activities = rig.get("/manage/api/recent-activity").context["activities"]
        assert [(a["type"], a["id"]) for a in activities] == [
            ("case", "case-7"),
            ("case", "case-6"),
            ("case", "case-5"),
            ("case", "case-4"),
            ("case", "case-3"),
            ("job", "job-7"),
            ("job", "job-6"),
            ("job", "job-5"),
            ("job", "job-4"),
            ("job", "job-3"),
        ]

    def test_each_kind_exposes_its_own_fields(self, rig: AdminRig) -> None:
        rig.seed(
            "Job",
            [
                {
                    "id": "job-1",
                    "name": "J",
                    "status": "completed",
                    "agent_name": "Agent",
                    "created_at": "2024-01-01",
                }
            ],
        )
        rig.seed(
            "Case",
            [
                {
                    "id": "case-1",
                    "name": "C",
                    "status": "failed",
                    "job_id": "job-1",
                    "created_at": "2024-01-02",
                }
            ],
        )
        case, job = rig.get("/manage/api/recent-activity").context["activities"]
        assert case == {
            "type": "case",
            "id": "case-1",
            "name": "C",
            "status": "failed",
            "created_at": "2024-01-02",
            "job_id": "job-1",
        }
        assert job == {
            "type": "job",
            "id": "job-1",
            "name": "J",
            "status": "completed",
            "created_at": "2024-01-01",
            "agent_name": "Agent",
        }

    def test_storage_failure_is_500(self, rig: AdminRig, mocker: MockerFixture) -> None:
        mocker.patch.object(rig.storage, "get_objects", side_effect=OSError("disk"))
        page = rig.get("/manage/api/recent-activity")
        assert page.status == 500
        assert page.response.json()["detail"] == "disk"


class TestAgentDetails:
    @pytest.fixture(autouse=True)
    def _server_info(self, mocker: MockerFixture) -> None:
        self.info = mocker.patch(
            "supervaizer.admin.routes._get_server_info",
            return_value=SimpleNamespace(
                agents=[{"name": "Zeta", "slug": "zeta"}, {"name": "No slug"}]
            ),
        )

    def test_shows_agent_matching_slug(self, rig: AdminRig) -> None:
        page = rig.get("/manage/api/agents/zeta")
        assert page.status == 200
        assert page.template == "agent_detail.html"
        assert page.context["agent"] == {"name": "Zeta", "slug": "zeta"}

    def test_unknown_slug_is_404(self, rig: AdminRig) -> None:
        page = rig.get("/manage/api/agents/nope")
        assert page.status == 404
        assert page.response.json()["detail"] == "Agent not found"

    def test_missing_server_info_is_503(self, rig: AdminRig) -> None:
        self.info.return_value = None
        page = rig.get("/manage/api/agents/zeta")
        assert page.status == 503
        assert page.response.json()["detail"] == "Server information not available"


class TestStaticFiles:
    def test_serves_javascript_with_its_media_type(self, rig: AdminRig) -> None:
        page = rig.get("/manage/static/js/workbench-form.js")
        assert page.status == 200
        assert page.response.headers["content-type"].startswith(
            "application/javascript"
        )
        assert page.response.content

    def test_unknown_suffix_is_served_as_binary(self, rig: AdminRig) -> None:
        page = rig.get("/manage/static/favicon.ico")
        assert page.status == 200
        assert page.response.headers["content-type"] == "application/octet-stream"

    @pytest.mark.parametrize("path", ["nope.js", "js", "..%2Froutes.py"])
    def test_missing_file_directory_or_escape_is_404(
        self, rig: AdminRig, path: str
    ) -> None:
        page = rig.get(f"/manage/static/{path}")
        assert page.status == 404
        assert page.response.json()["detail"] == "File not found"
