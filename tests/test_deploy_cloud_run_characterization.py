# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize Cloud Run deployment behavior without provider access."""

import subprocess
from typing import Any, cast
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from supervaizer.deploy.drivers import cloud_run
from supervaizer.deploy.drivers.base import ActionType, ResourceType
from supervaizer.deploy.drivers.cloud_run import CloudRunDriver


def _service(
    *,
    name: str = "service-id",
    uri: str | None = "https://agent.example.com",
    revision: str = "revision-1",
    environment: list[Any] | None = None,
) -> Mock:
    service = Mock()
    service.name = name
    service.uri = uri
    service.latest_ready_revision = revision
    service.template.containers = [Mock()]
    service.template.containers[0].env = environment or []
    return service


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class TestCloudRunDriverCharacterization:
    @pytest.fixture
    def driver(self, mocker: MockerFixture) -> CloudRunDriver:
        mocker.patch.object(cloud_run, "GOOGLE_CLOUD_AVAILABLE", True)
        mocker.patch.object(cloud_run, "run_v2")
        mocker.patch.object(cloud_run, "secretmanager")
        mocker.patch.object(cloud_run, "artifactregistry_v1")
        return CloudRunDriver("us-central1", "project-1")

    @pytest.fixture
    def run_client(self, driver: CloudRunDriver) -> Mock:
        return cast(Mock, driver.run_client)

    @pytest.fixture
    def secret_client(self, driver: CloudRunDriver) -> Mock:
        return cast(Mock, driver.secret_client)

    @pytest.fixture
    def registry_client(self, driver: CloudRunDriver) -> Mock:
        return cast(Mock, driver.registry_client)

    def test_deploy_returns_running_result_after_ready_service(
        self, driver: CloudRunDriver, mocker: MockerFixture
    ) -> None:
        deployed = _service()
        create_service = mocker.patch.object(
            driver, "_create_or_update_service", return_value=deployed
        )
        mocker.patch.object(
            driver, "_wait_for_service_ready", return_value="https://agent.example.com"
        )
        set_public_url = mocker.patch.object(driver, "_set_public_url")
        mocker.patch.object(driver, "verify_health", return_value=True)
        secrets = {"SUPERVAIZER_API_KEY": "secret"}
        update_secrets = mocker.patch.object(driver, "_create_or_update_secrets")

        result = driver.deploy_service(
            "agent", "dev", "image:tag", 8080, {"PORT": "8080"}, secrets, 12
        )

        assert result.success is True
        assert result.service_url == "https://agent.example.com"
        assert result.service_id == "service-id"
        assert result.revision == "revision-1"
        assert result.status == "running"
        assert result.health_status == "healthy"
        assert result.deployment_time is not None
        update_secrets.assert_called_once_with("agent-dev", secrets)
        create_service.assert_called_once_with(
            "agent-dev", "image:tag", 8080, {"PORT": "8080"}, secrets
        )
        set_public_url.assert_called_once_with(
            "projects/project-1/locations/us-central1/services/agent-dev",
            "https://agent.example.com",
        )

    def test_deploy_returns_exception_details_when_secret_creation_fails(
        self, driver: CloudRunDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            driver, "_create_or_update_secrets", side_effect=RuntimeError("denied")
        )

        result = driver.deploy_service(
            "agent", "dev", "image:tag", secrets={"SUPERVAIZER_API_KEY": "secret"}
        )

        assert result.model_dump(exclude_none=True) == {
            "success": False,
            "status": "unknown",
            "health_status": "unknown",
            "error_message": "denied",
            "error_details": {"exception_type": "RuntimeError"},
        }

    def test_destroy_deletes_service_and_known_secrets(
        self, driver: CloudRunDriver, run_client: Mock, mocker: MockerFixture
    ) -> None:
        delete_secrets = mocker.patch.object(driver, "_delete_secrets")

        result = driver.destroy_service("agent", "dev")

        assert result.success is True
        assert result.status == "deleted"
        run_client.delete_service.assert_called_once_with(
            name="projects/project-1/locations/us-central1/services/agent-dev"
        )
        delete_secrets.assert_called_once_with("agent-dev")

    def test_destroy_reports_missing_service_without_deleting_secrets(
        self, driver: CloudRunDriver, run_client: Mock, mocker: MockerFixture
    ) -> None:
        run_client.delete_service.side_effect = cloud_run.NotFound("missing")
        delete_secrets = mocker.patch.object(driver, "_delete_secrets")

        result = driver.destroy_service("agent", "dev")

        assert result.success is True
        assert result.status == "not_found"
        delete_secrets.assert_not_called()

    def test_status_reports_health_for_service_url(
        self, driver: CloudRunDriver, run_client: Mock, mocker: MockerFixture
    ) -> None:
        run_client.get_service.return_value = _service()
        mocker.patch.object(driver, "verify_health", return_value=False)

        result = driver.get_service_status("agent", "dev")

        assert result.model_dump(exclude_none=True) == {
            "success": True,
            "service_url": "https://agent.example.com",
            "service_id": "service-id",
            "revision": "revision-1",
            "status": "running",
            "health_status": "unhealthy",
        }

    def test_status_uses_exact_not_found_error(
        self, driver: CloudRunDriver, run_client: Mock
    ) -> None:
        run_client.get_service.side_effect = cloud_run.NotFound("missing")

        result = driver.get_service_status("agent", "dev")

        assert result.model_dump(exclude_none=True) == {
            "success": False,
            "status": "not_found",
            "health_status": "unknown",
            "error_message": "Service not found",
        }

    def test_plan_marks_matching_service_and_existing_secret_for_update(
        self, driver: CloudRunDriver, run_client: Mock, secret_client: Mock
    ) -> None:
        service = _service()
        service.template.containers[0].image = "image:tag"
        run_client.get_service.return_value = service
        secret_client.get_secret.return_value = Mock()

        plan = driver.plan_deployment(
            "agent",
            "dev",
            "image:tag",
            port=8080,
            env_vars={"PORT": "8080"},
            secrets={"SUPERVAIZER_API_KEY": "secret"},
        )

        assert [
            (action.resource_type, action.action_type, action.resource_name)
            for action in plan.actions
        ] == [
            (ResourceType.SERVICE, ActionType.NOOP, "agent-dev"),
            (ResourceType.SECRET, ActionType.UPDATE, "agent-dev-api-key"),
        ]
        assert plan.current_image == "image:tag"
        assert plan.current_url == "https://agent.example.com"
        assert plan.current_status == "running"
        assert plan.target_port == 8080
        assert plan.target_env_vars == {"PORT": "8080"}
        assert plan.target_secrets == {"SUPERVAIZER_API_KEY": "secret"}

    def test_plan_marks_missing_service_and_secret_for_creation(
        self, driver: CloudRunDriver, run_client: Mock, secret_client: Mock
    ) -> None:
        run_client.get_service.side_effect = cloud_run.NotFound("missing")
        secret_client.get_secret.side_effect = cloud_run.NotFound("missing")

        plan = driver.plan_deployment(
            "agent", "dev", "image:tag", secrets={"SUPERVAIZER_API_KEY": "secret"}
        )

        assert [
            (action.resource_type, action.action_type, action.resource_name)
            for action in plan.actions
        ] == [
            (ResourceType.SERVICE, ActionType.CREATE, "agent-dev"),
            (ResourceType.SECRET, ActionType.CREATE, "agent-dev-api-key"),
        ]
        assert plan.current_image is None
        assert plan.current_url is None
        assert plan.current_status is None
        run_client.get_service.assert_called_once_with(
            name="projects/project-1/locations/us-central1/services/agent-dev"
        )
        secret_client.get_secret.assert_called_once_with(
            name="projects/project-1/secrets/agent-dev-api-key"
        )

    def test_existing_secret_adds_a_new_version(
        self, driver: CloudRunDriver, secret_client: Mock
    ) -> None:
        secret_client.get_secret.return_value = Mock()

        driver._create_or_update_secrets("agent-dev", {"SUPERVAIZER_API_KEY": "key"})

        secret_client.create_secret.assert_not_called()
        assert secret_client.add_secret_version.call_args.kwargs["request"] == {
            "parent": "projects/project-1/secrets/agent-dev-api-key",
            "payload": {"data": b"key"},
        }

    def test_missing_secret_is_created_before_its_version(
        self, driver: CloudRunDriver, secret_client: Mock
    ) -> None:
        secret_client.get_secret.side_effect = cloud_run.NotFound("missing")
        secret_client.create_secret.return_value.name = "created-secret"

        driver._create_or_update_secrets("agent-dev", {"SUPERVAIZER_API_KEY": "key"})

        assert secret_client.create_secret.call_args.kwargs["request"] == {
            "parent": "projects/project-1",
            "secret_id": "agent-dev-api-key",
            "secret": {"replication": {"automatic": {}}},
        }
        assert secret_client.add_secret_version.call_args.kwargs["request"] == {
            "parent": "created-secret",
            "payload": {"data": b"key"},
        }

    def test_prepare_registry_preserves_an_existing_repository(
        self, driver: CloudRunDriver, registry_client: Mock
    ) -> None:
        registry_client.get_repository.return_value = Mock()

        image = driver.prepare_registry("agent")

        assert image == "us-central1-docker.pkg.dev/project-1/agent/agent:latest"
        registry_client.create_repository.assert_not_called()

    def test_registry_auth_returns_trimmed_access_token(
        self, driver: CloudRunDriver, mocker: MockerFixture
    ) -> None:
        run = mocker.patch.object(
            cloud_run.subprocess, "run", return_value=_completed("token\n")
        )

        credentials = driver.registry_auth()

        assert credentials == {"username": "oauth2accesstoken", "password": "token"}
        run.assert_called_once_with(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_ready_poll_retries_after_provider_error(
        self, driver: CloudRunDriver, run_client: Mock, mocker: MockerFixture
    ) -> None:
        run_client.get_service.side_effect = [
            RuntimeError("pending"),
            _service(),
        ]
        mocker.patch.object(cloud_run.time, "time", side_effect=[0, 0, 1])
        sleep = mocker.patch.object(cloud_run.time, "sleep")

        result = driver._wait_for_service_ready("service-path", timeout=5)

        assert result == "https://agent.example.com"
        sleep.assert_called_once_with(5)

    def test_ready_poll_raises_exact_timeout_error(
        self, driver: CloudRunDriver, run_client: Mock, mocker: MockerFixture
    ) -> None:
        run_client.get_service.return_value = _service(uri=None)
        mocker.patch.object(cloud_run.time, "time", side_effect=[0, 0, 5])
        mocker.patch.object(cloud_run.time, "sleep")

        with pytest.raises(
            TimeoutError, match="Service did not become ready within 5 seconds"
        ):
            driver._wait_for_service_ready("service-path", timeout=5)

    def test_public_url_replaces_only_its_previous_environment_entry(
        self, driver: CloudRunDriver, run_client: Mock
    ) -> None:
        retained = Mock(name="kept")
        retained.name = "KEEP"
        previous = Mock(name="previous")
        previous.name = "SUPERVAIZER_PUBLIC_URL"
        service = _service(environment=[retained, previous])
        run_client.get_service.return_value = service

        driver._set_public_url("service-path", "https://new.example.com")

        assert service.template.containers[0].env == [
            retained,
            {"name": "SUPERVAIZER_PUBLIC_URL", "value": "https://new.example.com"},
        ]
        run_client.update_service.assert_called_once_with(request={"service": service})

    def test_delete_secrets_continues_after_provider_errors(
        self, driver: CloudRunDriver, secret_client: Mock
    ) -> None:
        secret_client.delete_secret.side_effect = [
            cloud_run.NotFound("missing"),
            RuntimeError("denied"),
            None,
        ]

        driver._delete_secrets("agent-dev")

        assert secret_client.delete_secret.call_count == 3

    def test_prerequisites_returns_all_failed_check_errors(
        self, driver: CloudRunDriver, mocker: MockerFixture
    ) -> None:
        run = mocker.patch.object(
            cloud_run.subprocess,
            "run",
            side_effect=[
                FileNotFoundError(),
                subprocess.CalledProcessError(1, "auth"),
                subprocess.CalledProcessError(1, "project"),
                subprocess.CalledProcessError(1, "run-api"),
                subprocess.CalledProcessError(1, "secret-api"),
                subprocess.CalledProcessError(1, "registry-api"),
            ],
        )

        errors = driver.check_prerequisites()

        assert errors == [
            "gcloud CLI not found or not working",
            "gcloud authentication check failed",
            "gcloud project configuration check failed",
            "Failed to check API run.googleapis.com",
            "Failed to check API secretmanager.googleapis.com",
            "Failed to check API artifactregistry.googleapis.com",
        ]
        assert run.call_count == 6
