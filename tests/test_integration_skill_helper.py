# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for the helper script of the supervaizer-integration skill."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

HELPER_PATH = (
    Path(__file__).parent.parent
    / "skills/supervaizer-integration/scripts/supervaize_cli_helper.py"
)
SURFACE_ARGS = [
    "--controller-url",
    "http://controller.test",
    "--agent-slug",
    "my-agent",
    "--workspace-slug",
    "team_1",
]


@pytest.fixture(scope="module")
def helper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("supervaize_cli_helper", HELPER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _answer(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]
) -> list[dict[str, Any]]:
    """Make the controller answer `response`. Returns the list of request bodies sent."""
    sent: list[dict[str, Any]] = []

    def fake_http_json(
        method: str, url: str, *, body: dict[str, Any], **_: Any
    ) -> tuple[int, Any]:
        sent.append(body)
        return 200, response

    monkeypatch.setattr(helper, "_http_json", fake_http_json)
    return sent


def test_env_status_prints_names_and_no_value(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERVAIZE_API_KEY", "sk-secret-value-1234")
    monkeypatch.setenv("SUPERVAIZE_WORKSPACE_ID", "acme-workspace")
    monkeypatch.delenv("SUPERVAIZE_API_URL", raising=False)

    result = CliRunner().invoke(helper.app, ["env-status"])

    assert result.exit_code == 0
    assert "sk-s" not in result.output and "1234" not in result.output
    assert "acme-workspace" not in result.output
    report = json.loads(result.output)
    assert report["present"] == ["SUPERVAIZE_API_KEY", "SUPERVAIZE_WORKSPACE_ID"]
    assert report["missing"] == ["SUPERVAIZE_API_URL"]


def test_spec_template_keeps_an_existing_spec(
    helper: ModuleType, tmp_path: Path
) -> None:
    spec_file = tmp_path / "integration_spec.json"
    spec_file.write_text('{"reviewed": true}', encoding="utf-8")
    args = ["spec-template", "--output-file", str(spec_file)]

    refused = CliRunner().invoke(helper.app, args)
    assert refused.exit_code == 2
    assert spec_file.read_text(encoding="utf-8") == '{"reviewed": true}'

    forced = CliRunner().invoke(helper.app, [*args, "--force"])
    assert forced.exit_code == 0
    assert "steps" in json.loads(spec_file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("command", ["invoke-action", "load-surface"])
def test_json_rpc_error_fails_the_command(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    _answer(helper, monkeypatch, {"error": {"code": -32000, "message": "denied"}})
    extra = ["--action", "job.start"] if command == "invoke-action" else []
    surface = [] if command == "invoke-action" else ["--surface", "job.start"]

    result = CliRunner().invoke(helper.app, [command, *SURFACE_ARGS, *extra, *surface])

    assert result.exit_code == 1
    assert json.loads(result.output)["ok"] is False


def test_invoke_action_sends_no_job_id_when_none_is_given(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _answer(helper, monkeypatch, {"result": {}})

    result = CliRunner().invoke(
        helper.app, ["invoke-action", *SURFACE_ARGS, "--action", "resource.x.list"]
    )

    assert result.exit_code == 0
    assert "job_id" not in sent[0]["params"]


def test_load_surface_forwards_the_correlation_ids(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _answer(helper, monkeypatch, {"result": {}})

    result = CliRunner().invoke(
        helper.app,
        ["load-surface", *SURFACE_ARGS, "--surface", "job.analytics"]
        + ["--job-id", "job_1", "--case-id", "case_1", "--step-id", "step_1"],
    )

    assert result.exit_code == 0
    params = sent[0]["params"]
    assert (params["job_id"], params["case_id"], params["step_id"]) == (
        "job_1",
        "case_1",
        "step_1",
    )
    assert "draft_session_id" not in params


def test_checklist_has_no_cost_item_when_nothing_costs(helper: ModuleType) -> None:
    spec = helper._spec_template()
    pages = [item["guide"] for item in helper._spec_checklist(spec)]
    assert not any(page.endswith("cost-reporting") for page in pages)

    spec["steps"][0]["costs_money"] = True
    pages = [item["guide"] for item in helper._spec_checklist(spec)]
    assert any(page.endswith("cost-reporting") for page in pages)
