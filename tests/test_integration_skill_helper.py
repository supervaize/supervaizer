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
    assert sent[0]["params"]["surface"] == "job.start"


def test_env_status_reports_workspace_auth_and_hostnames_only(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERVAIZE_API_KEY", "sk-secret")
    monkeypatch.setenv("SUPERVAIZE_WORKSPACE_ID", "acme")
    monkeypatch.setenv("SUPERVAIZE_API_URL", "https://app.supervaize.com")
    monkeypatch.setenv(
        "SUPERVAIZER_WORKSPACE_AUTH_ISSUER", "https://studio.supervaize.com"
    )
    monkeypatch.setenv(
        "SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL",
        "https://app.supervaize.com/w/acme/api/v1/workspace-agent-grants/jwks/",
    )
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_REQUIRED", "true")

    result = CliRunner().invoke(helper.app, ["env-status", "--pretty"])

    assert result.exit_code == 0
    assert "sk-secret" not in result.output
    report = json.loads(result.output)
    assert report["workspace_auth_configured"] is True
    assert report["ok"] is True
    assert report["url_hostnames"]["SUPERVAIZE_API_URL"] == "app.supervaize.com"
    assert report["url_hostnames"]["SUPERVAIZER_WORKSPACE_AUTH_ISSUER"] == (
        "studio.supervaize.com"
    )


def test_env_status_workspace_auth_not_configured_when_required_false(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERVAIZE_API_KEY", "x")
    monkeypatch.setenv("SUPERVAIZE_WORKSPACE_ID", "acme")
    monkeypatch.setenv("SUPERVAIZE_API_URL", "https://app.supervaize.com")
    monkeypatch.setenv(
        "SUPERVAIZER_WORKSPACE_AUTH_ISSUER", "https://studio.supervaize.com"
    )
    monkeypatch.setenv(
        "SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL",
        "https://app.supervaize.com/w/acme/api/v1/workspace-agent-grants/jwks/",
    )
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_REQUIRED", "false")

    result = CliRunner().invoke(helper.app, ["env-status"])

    report = json.loads(result.output)
    assert report["workspace_auth_required_enabled"] is False
    assert report["workspace_auth_configured"] is False
    assert report["ok"] is False


def test_probe_jwks_redacts_url_on_http_error(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    jwks_url = "https://evil.test/jwks"
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL", jwks_url)

    def fail_http(method: str, url: str, **_: Any) -> tuple[int, Any]:
        raise RuntimeError(
            json.dumps({
                "status": 403,
                "url": url,
                "error": {
                    "message": url,
                    "detail": f"fetch failed for {url}",
                    "url": url,
                    "raw_text": url,
                },
            })
        )

    monkeypatch.setattr(helper, "_http_json", fail_http)
    result = CliRunner().invoke(helper.app, ["env-status", "--probe-jwks"])

    report = json.loads(result.output)
    assert report["jwks_probe"]["url"] == "evil.test"
    assert report["jwks_probe"]["error"]["url"] == "evil.test"
    assert report["jwks_probe"]["error"]["raw_text"] == "<omitted>"
    assert report["jwks_probe"]["error"]["message"] == "evil.test"
    assert report["jwks_probe"]["error"]["detail"] == "<omitted>"


def test_probe_jwks_skipped_when_public_key_configured(
    helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERVAIZE_API_KEY", "x")
    monkeypatch.setenv("SUPERVAIZE_WORKSPACE_ID", "acme")
    monkeypatch.setenv("SUPERVAIZE_API_URL", "https://app.supervaize.com")
    monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_REQUIRED", "true")
    monkeypatch.setenv(
        "SUPERVAIZER_WORKSPACE_AUTH_ISSUER", "https://studio.supervaize.com"
    )
    monkeypatch.setenv(
        "SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY", "-----BEGIN PUBLIC KEY-----"
    )
    monkeypatch.delenv("SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL", raising=False)

    result = CliRunner().invoke(helper.app, ["env-status", "--probe-jwks"])

    report = json.loads(result.output)
    assert report["ok"] is True
    assert report["jwks_probe"]["probed"] is False
    assert report["jwks_probe"]["ok"] is True


def test_scaffold_integration_skips_existing_controller(
    helper: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = helper._spec_template()
    spec["project"]["output_dir"] = str(tmp_path)
    spec_path = tmp_path / "integration_spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    control = tmp_path / "supervaizer_control.py"
    control.write_text("# existing\n", encoding="utf-8")

    def forbid_scaffold(*_: Any, **__: Any) -> None:
        raise AssertionError("supervaizer scaffold must not run")

    monkeypatch.setattr(helper.subprocess, "run", forbid_scaffold)
    result = CliRunner().invoke(
        helper.app,
        ["scaffold-integration", "--spec-file", str(spec_path), "--pretty"],
    )

    assert result.exit_code == 0
    report = json.loads(result.output)
    assert "skipped" in report["scaffolded_by"]
    assert control.read_text(encoding="utf-8") == "# existing\n"


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
