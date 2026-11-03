# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize DigitalOcean App Platform behavior at the doctl boundary."""

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from pytest_mock import MockerFixture

from supervaizer.deploy.drivers import do_app_platform
from supervaizer.deploy.drivers.base import ActionType, ResourceType
from supervaizer.deploy.drivers.do_app_platform import DOAppPlatformDriver


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class TestDOAppPlatformCharacterization:
    """Describe the current public DO driver contract without doctl access."""

    @pytest.fixture
    def driver(self) -> DOAppPlatformDriver:
        return DOAppPlatformDriver("nyc3", "project")

    def test_plan_reports_existing_app_and_account_registry(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture
    ) -> None:
        app_data = {
            "spec": {"ingress": {"default_route": "https://agent.ondigitalocean.app"}},
            "last_deployment_active_at": "2026-11-03T12:00:00Z",
        }
        mocker.patch.object(
            do_app_platform.subprocess,
            "run",
            return_value=_completed(json.dumps(app_data)),
        )
        mocker.patch.object(driver, "_get_registry_name", return_value="acme")

        plan = driver.plan_deployment(
            "agent", "prod", "registry.digitalocean.com/acme/agent:next", port=9000
        )

        assert (plan.current_url, plan.current_status, plan.target_port) == (
            "https://agent.ondigitalocean.app",
            "2026-11-03T12:00:00Z",
            9000,
        )
        assert [
            (action.resource_type, action.action_type) for action in plan.actions
        ] == [
            (ResourceType.SERVICE, ActionType.UPDATE),
            (ResourceType.REGISTRY, ActionType.NOOP),
        ]
        assert plan.actions[-1].resource_name == "acme"

    def test_plan_creates_missing_app_and_registry(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            do_app_platform.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["doctl", "apps", "get"]),
        )
        mocker.patch.object(
            driver, "_get_registry_name", side_effect=RuntimeError("registry absent")
        )

        plan = driver.plan_deployment("agent", "dev", "agent:next")

        assert [
            (action.resource_type, action.action_type) for action in plan.actions
        ] == [
            (ResourceType.SERVICE, ActionType.CREATE),
            (ResourceType.REGISTRY, ActionType.CREATE),
        ]
        assert plan.actions[-1].description == "registry absent"

    def test_deploy_returns_running_result_after_app_is_ready(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        spec_path = tmp_path / "app.yaml"
        mocker.patch.object(driver, "_create_app_spec", return_value=spec_path)
        mocker.patch.object(
            driver, "_deploy_app", return_value="https://agent.ondigitalocean.app"
        )
        set_public_url = mocker.patch.object(driver, "_set_public_url")
        mocker.patch.object(driver, "verify_health", return_value=False)
        mocker.patch.object(do_app_platform.time, "time", side_effect=[2.0, 5.0])

        result = driver.deploy_service(
            "agent", "prod", "registry/acme/agent:next", timeout=42
        )

        assert (
            result.success,
            result.service_id,
            result.status,
            result.health_status,
        ) == (
            True,
            "agent-prod",
            "running",
            "unhealthy",
        )
        assert result.deployment_time == 3.0
        set_public_url.assert_called_once_with(
            "agent-prod", "https://agent.ondigitalocean.app", spec_path
        )

    def test_deploy_returns_failure_details_when_spec_creation_fails(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            driver, "_create_app_spec", side_effect=RuntimeError("invalid image")
        )

        result = driver.deploy_service("agent", "prod", "invalid")

        assert (result.success, result.error_message, result.error_details) == (
            False,
            "invalid image",
            {"exception_type": "RuntimeError"},
        )

    def test_set_public_url_replaces_existing_value_and_preserves_other_envs(
        self,
        driver: DOAppPlatformDriver,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        spec_path = tmp_path / "app.yaml"
        spec_path.write_text(
            """services:
- envs:
  - key: MODE
    value: prod
  - key: SUPERVAIZER_PUBLIC_URL
    value: https://old.example
  - key: SUPERVAIZER_API_KEY
    value: secret
    scope: RUN_TIME
    type: SECRET
"""
        )
        run = mocker.patch.object(do_app_platform.subprocess, "run")

        driver._set_public_url("agent-prod", "https://new.example", spec_path)

        envs = yaml.safe_load(spec_path.read_text())["services"][0]["envs"]
        assert envs == [
            {"key": "MODE", "value": "prod"},
            {
                "key": "SUPERVAIZER_API_KEY",
                "value": "secret",
                "scope": "RUN_TIME",
                "type": "SECRET",
            },
            {"key": "SUPERVAIZER_PUBLIC_URL", "value": "https://new.example"},
        ]
        assert run.call_args.args[0] == [
            "doctl",
            "apps",
            "update",
            "agent-prod",
            "--spec",
            str(spec_path),
        ]

    @pytest.mark.parametrize("failure", [False, True])
    def test_destroy_maps_doctl_result(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture, failure: bool
    ) -> None:
        if failure:
            mocker.patch.object(
                do_app_platform.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(
                    1, ["doctl", "apps", "delete"]
                ),
            )
        else:
            run = mocker.patch.object(do_app_platform.subprocess, "run")

        result = driver.destroy_service("agent", "prod", keep_secrets=True)

        assert result.success is (not failure)
        assert result.status == ("deleted" if not failure else "unknown")
        if not failure:
            assert run.call_args.args[0] == [
                "doctl",
                "apps",
                "delete",
                "agent-prod",
                "--force",
            ]

    @pytest.mark.parametrize(
        ("app_data", "health", "expected_health"),
        [
            (
                {"spec": {"ingress": {"default_route": "https://agent.do"}}},
                True,
                "healthy",
            ),
            ({}, False, "unknown"),
        ],
    )
    def test_status_maps_doctl_json_and_health(
        self,
        driver: DOAppPlatformDriver,
        mocker: MockerFixture,
        app_data: dict[str, object],
        health: bool,
        expected_health: str,
    ) -> None:
        mocker.patch.object(
            do_app_platform.subprocess,
            "run",
            return_value=_completed(json.dumps(app_data)),
        )
        verify_health = mocker.patch.object(
            driver, "verify_health", return_value=health
        )

        result = driver.get_service_status("agent", "prod")

        assert (
            result.success,
            result.service_id,
            result.status,
            result.health_status,
        ) == (
            True,
            "agent-prod",
            app_data.get("last_deployment_active_at", "unknown"),
            expected_health,
        )
        if result.service_url:
            verify_health.assert_called_once_with(result.service_url)
        else:
            verify_health.assert_not_called()

    def test_status_missing_app_is_not_found(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            do_app_platform.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["doctl", "apps", "get"]),
        )

        result = driver.get_service_status("agent", "prod")

        assert (result.success, result.status, result.error_message) == (
            False,
            "not_found",
            "App not found",
        )

    @pytest.mark.parametrize(
        ("version_result", "account_result", "expected"),
        [
            (
                subprocess.CalledProcessError(1, ["doctl", "version"]),
                _completed("{}"),
                [
                    "doctl CLI not found or not working",
                    "doctl authentication not configured",
                ],
            ),
            (
                _completed("doctl 1.0"),
                _completed("not json"),
                ["doctl authentication check failed"],
            ),
        ],
    )
    def test_prerequisites_report_cli_and_auth_errors(
        self,
        driver: DOAppPlatformDriver,
        mocker: MockerFixture,
        version_result: subprocess.CompletedProcess[str]
        | subprocess.CalledProcessError,
        account_result: subprocess.CompletedProcess[str],
        expected: list[str],
    ) -> None:
        mocker.patch.object(
            do_app_platform.subprocess,
            "run",
            side_effect=[version_result, account_result],
        )

        assert driver.check_prerequisites() == expected

    @pytest.mark.parametrize("existing", [False, True])
    def test_deploy_app_creates_or_updates_then_waits(
        self,
        driver: DOAppPlatformDriver,
        mocker: MockerFixture,
        existing: bool,
        tmp_path: Path,
    ) -> None:
        if existing:
            run = mocker.patch.object(do_app_platform.subprocess, "run")
        else:
            run = mocker.patch.object(
                do_app_platform.subprocess,
                "run",
                side_effect=[
                    subprocess.CalledProcessError(1, ["doctl", "apps", "get"]),
                    None,
                ],
            )
        mocker.patch.object(
            driver, "_wait_for_deployment", return_value="https://agent.do"
        )

        assert (
            driver._deploy_app("agent-prod", tmp_path / "app.yaml", 30)
            == "https://agent.do"
        )
        assert run.call_args_list[0].args[0] == ["doctl", "apps", "get", "agent-prod"]
        assert run.call_args_list[1].args[0][2] == ("update" if existing else "create")

    @pytest.mark.parametrize(
        ("app_data", "expected_url"),
        [
            (
                {
                    "last_deployment_active_at": "2026-11-03T12:00:00Z",
                    "spec": {"ingress": {"default_route": "https://agent.do"}},
                },
                "https://agent.do",
            ),
            ({"last_deployment_created_at": "2026-11-03T12:00:00Z"}, None),
        ],
    )
    def test_wait_returns_active_url_or_times_out_after_failed_deployment(
        self,
        driver: DOAppPlatformDriver,
        mocker: MockerFixture,
        app_data: dict[str, object],
        expected_url: str | None,
    ) -> None:
        mocker.patch.object(
            do_app_platform.subprocess,
            "run",
            return_value=_completed(json.dumps(app_data)),
        )
        mocker.patch.object(do_app_platform.time, "sleep")
        if expected_url:
            mocker.patch.object(do_app_platform.time, "time", side_effect=[0.0, 0.0])
            assert driver._wait_for_deployment("agent-prod", 1) == expected_url
        else:
            mocker.patch.object(
                do_app_platform.time, "time", side_effect=[0.0, 0.0, 1.0]
            )
            with pytest.raises(TimeoutError, match="did not complete"):
                driver._wait_for_deployment("agent-prod", 1)
