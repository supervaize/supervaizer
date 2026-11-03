# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize AWS App Runner deployment behavior at provider boundaries."""

import subprocess

import pytest
from pytest_mock import MockerFixture

from supervaizer.deploy.drivers import aws_app_runner
from supervaizer.deploy.drivers.aws_app_runner import (
    AWSAppRunnerDriver,
    ClientError,
    NoCredentialsError,
)
from supervaizer.deploy.drivers.base import ActionType, ResourceType


def _client_error(code: str, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code}}, operation)


class TestAWSAppRunnerCharacterization:
    """Describe the current public AWS driver contract without AWS access."""

    @pytest.fixture
    def driver(self, mocker: MockerFixture) -> AWSAppRunnerDriver:
        mocker.patch.object(aws_app_runner.boto3, "client", return_value=mocker.Mock())
        driver = AWSAppRunnerDriver("us-east-1", "account")
        mocker.patch.object(driver, "_get_account_id", return_value="123456789012")
        return driver

    def test_plan_reports_existing_service_registry_and_secret_updates(
        self, driver: AWSAppRunnerDriver
    ) -> None:
        driver.apprunner_client.describe_service.return_value = {
            "Service": {"ServiceUrl": "https://app.aws", "Status": "RUNNING"}
        }

        plan = driver.plan_deployment(
            "agent",
            "prod",
            "registry/agent:next",
            port=9000,
            env_vars={"MODE": "prod"},
            secrets={"SUPERVAIZER_API_KEY": "secret"},
        )

        assert plan.current_image == "https://app.aws"
        assert plan.current_url == "https://app.aws"
        assert plan.current_status == "RUNNING"
        assert plan.target_port == 9000
        assert plan.target_env_vars == {"MODE": "prod"}
        assert [
            (action.resource_type, action.action_type) for action in plan.actions
        ] == [
            (ResourceType.SERVICE, ActionType.UPDATE),
            (ResourceType.REGISTRY, ActionType.NOOP),
            (ResourceType.SECRET, ActionType.UPDATE),
        ]

    def test_plan_creates_missing_resources_and_scopes_secret_names(
        self, driver: AWSAppRunnerDriver
    ) -> None:
        driver.apprunner_client.describe_service.side_effect = _client_error(
            "ResourceNotFoundException", "DescribeService"
        )
        driver.ecr_client.describe_repositories.side_effect = _client_error(
            "RepositoryNotFoundException", "DescribeRepositories"
        )
        driver.secrets_client.describe_secret.side_effect = _client_error(
            "ResourceNotFoundException", "DescribeSecret"
        )

        plan = driver.plan_deployment(
            "agent", "dev", "agent:next", secrets={"SUPERVAIZER_PRIVATE_KEY": "pem"}
        )

        assert [
            (action.resource_type, action.action_type) for action in plan.actions
        ] == [
            (ResourceType.SERVICE, ActionType.CREATE),
            (ResourceType.REGISTRY, ActionType.CREATE),
            (ResourceType.SECRET, ActionType.CREATE),
        ]
        assert plan.actions[-1].resource_name == "agent-dev-rsa-key"

    def test_deploy_returns_running_result_after_ready_service(
        self, driver: AWSAppRunnerDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            driver,
            "_create_or_update_secrets",
            return_value={"SUPERVAIZER_API_KEY": "arn:key"},
        )
        mocker.patch.object(
            driver, "_create_or_update_service", return_value="arn:service"
        )
        mocker.patch.object(
            driver, "_wait_for_service_ready", return_value="https://app.aws"
        )
        set_public_url = mocker.patch.object(driver, "_set_public_url")
        mocker.patch.object(driver, "verify_health", return_value=True)
        mocker.patch.object(aws_app_runner.time, "time", side_effect=[10.0, 13.5])

        result = driver.deploy_service(
            "agent", "prod", "image:next", env_vars={"MODE": "prod"}, timeout=42
        )

        assert (result.success, result.service_url, result.service_id) == (
            True,
            "https://app.aws",
            "arn:service",
        )
        assert (result.status, result.health_status, result.deployment_time) == (
            "running",
            "healthy",
            3.5,
        )
        set_public_url.assert_called_once_with("arn:service", "https://app.aws")

    def test_deploy_returns_provider_error_details(
        self, driver: AWSAppRunnerDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            driver, "_create_or_update_secrets", side_effect=ValueError("bad secret")
        )

        result = driver.deploy_service("agent", "prod", "image:next")

        assert result.success is False
        assert result.error_message == "bad secret"
        assert result.error_details == {"exception_type": "ValueError"}

    @pytest.mark.parametrize("keep_secrets", [False, True])
    def test_destroy_removes_service_repository_and_optional_secrets(
        self,
        driver: AWSAppRunnerDriver,
        mocker: MockerFixture,
        keep_secrets: bool,
    ) -> None:
        delete_secrets = mocker.patch.object(driver, "_delete_secrets")

        result = driver.destroy_service("agent", "prod", keep_secrets=keep_secrets)

        assert result.success is True
        assert result.status == "deleted"
        assert driver.ecr_client.delete_repository.call_args.kwargs == {
            "repositoryName": "agent-prod",
            "force": True,
        }
        if keep_secrets:
            delete_secrets.assert_not_called()
        else:
            delete_secrets.assert_called_once_with("agent-prod")

    def test_destroy_missing_service_is_successful_noop(
        self, driver: AWSAppRunnerDriver
    ) -> None:
        driver.apprunner_client.delete_service.side_effect = _client_error(
            "ResourceNotFoundException", "DeleteService"
        )

        result = driver.destroy_service("agent", "prod")

        assert (result.success, result.status) == (True, "not_found")

    @pytest.mark.parametrize(
        ("service_url", "health", "expected_health"),
        [("https://app.aws", True, "healthy"), (None, False, "unknown")],
    )
    def test_status_maps_provider_service_and_health(
        self,
        driver: AWSAppRunnerDriver,
        mocker: MockerFixture,
        service_url: str | None,
        health: bool,
        expected_health: str,
    ) -> None:
        driver.apprunner_client.describe_service.return_value = {
            "Service": {"ServiceUrl": service_url, "Status": "RUNNING"}
        }
        verify_health = mocker.patch.object(
            driver, "verify_health", return_value=health
        )

        result = driver.get_service_status("agent", "prod")

        assert (
            result.success,
            result.service_url,
            result.status,
            result.health_status,
        ) == (
            True,
            service_url,
            "RUNNING",
            expected_health,
        )
        if service_url:
            verify_health.assert_called_once_with(service_url)
        else:
            verify_health.assert_not_called()

    def test_status_missing_service_has_not_found_result(
        self, driver: AWSAppRunnerDriver
    ) -> None:
        driver.apprunner_client.describe_service.side_effect = _client_error(
            "ResourceNotFoundException", "DescribeService"
        )

        result = driver.get_service_status("agent", "prod")

        assert (result.success, result.status, result.error_message) == (
            False,
            "not_found",
            "Service not found",
        )

    def test_prerequisites_report_cli_credentials_and_identity_failures(
        self, driver: AWSAppRunnerDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            aws_app_runner.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["aws", "--version"]),
        )
        sts_client = mocker.Mock()
        sts_client.get_caller_identity.side_effect = NoCredentialsError()
        mocker.patch.object(aws_app_runner.boto3, "client", return_value=sts_client)
        mocker.patch.object(
            driver, "_get_account_id", side_effect=RuntimeError("denied")
        )

        assert driver.check_prerequisites() == [
            "AWS CLI not found or not working",
            "AWS credentials not found",
            "Failed to get AWS account ID: denied",
        ]

    @pytest.mark.parametrize(
        ("status", "expected_url"),
        [("RUNNING", "https://app.aws"), ("UPDATE_FAILED", None)],
    )
    def test_wait_polls_until_ready_or_times_out_after_failed_status(
        self,
        driver: AWSAppRunnerDriver,
        mocker: MockerFixture,
        status: str,
        expected_url: str | None,
    ) -> None:
        driver.apprunner_client.describe_service.return_value = {
            "Service": {"Status": status, "ServiceUrl": "https://app.aws"}
        }
        mocker.patch.object(aws_app_runner.time, "sleep")
        if expected_url:
            mocker.patch.object(aws_app_runner.time, "time", side_effect=[0.0, 0.0])
            assert driver._wait_for_service_ready("arn:service", 1) == expected_url
        else:
            mocker.patch.object(
                aws_app_runner.time, "time", side_effect=[0.0, 0.0, 1.0]
            )
            with pytest.raises(TimeoutError, match="did not become ready"):
                driver._wait_for_service_ready("arn:service", 1)
