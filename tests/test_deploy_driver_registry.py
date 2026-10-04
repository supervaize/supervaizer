# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Registry, secret, and environment wiring in the deployment drivers."""

import base64
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from pytest_mock import MockerFixture

from supervaizer.deploy.drivers import cloud_run
from supervaizer.deploy.drivers.aws_app_runner import AWSAppRunnerDriver, ClientError
from supervaizer.deploy.drivers.base import BaseDriver
from supervaizer.deploy.drivers.cloud_run import CloudRunDriver
from supervaizer.deploy.drivers.do_app_platform import DOAppPlatformDriver

SECRETS = {"SUPERVAIZER_API_KEY": "k", "SUPERVAIZER_PRIVATE_KEY": "pem"}


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class TestCloudRun:
    @pytest.fixture
    def driver(self, mocker: MockerFixture) -> CloudRunDriver:
        mocker.patch.object(cloud_run, "GOOGLE_CLOUD_AVAILABLE", True)
        mocker.patch.object(cloud_run, "run_v2")
        mocker.patch.object(cloud_run, "secretmanager")
        mocker.patch.object(cloud_run, "artifactregistry_v1")
        return CloudRunDriver("us-central1", "proj")

    def test_prepare_registry_creates_missing_repository(
        self, driver: CloudRunDriver
    ) -> None:
        registry = driver.registry_client
        registry.get_repository.side_effect = cloud_run.NotFound("missing")

        image = driver.prepare_registry("my-agent-dev:abc")

        assert image == "us-central1-docker.pkg.dev/proj/my-agent-dev/my-agent-dev:abc"
        kwargs = registry.create_repository.call_args.kwargs
        assert kwargs["parent"] == "projects/proj/locations/us-central1"
        assert kwargs["repository_id"] == "my-agent-dev"
        registry.create_repository.return_value.result.assert_called_once()

    def test_registry_auth_uses_gcloud_access_token(
        self, driver: CloudRunDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            cloud_run.subprocess, "run", return_value=_completed("tok\n")
        )

        assert driver.registry_auth() == {
            "username": "oauth2accesstoken",
            "password": "tok",
        }

    def test_service_maps_secrets_to_server_variables(
        self, driver: CloudRunDriver
    ) -> None:
        driver._create_or_update_service(
            "my-agent-dev", "img", 8080, {"SUPERVAIZER_PORT": "8080"}, SECRETS
        )

        request = driver.run_client.update_service.call_args.kwargs["request"]
        assert request["allow_missing"] is True
        assert set(request) == {"service", "allow_missing"}
        service = request["service"]
        assert (
            service["name"]
            == "projects/proj/locations/us-central1/services/my-agent-dev"
        )
        container = service["template"]["containers"][0]
        assert container["ports"] == [{"container_port": 8080}]
        refs = {
            e["name"]: e["value_source"]["secret_key_ref"]["secret"]
            for e in container["env"]
            if "value_source" in e
        }
        assert refs == {
            "SUPERVAIZER_API_KEY": "projects/proj/secrets/my-agent-dev-api-key",
            "SUPERVAIZER_PRIVATE_KEY": "projects/proj/secrets/my-agent-dev-rsa-key",
        }
        driver.run_client.update_service.return_value.result.assert_called_once()

    def test_secrets_stored_under_service_scoped_names(
        self, driver: CloudRunDriver
    ) -> None:
        driver.secret_client.get_secret.side_effect = cloud_run.NotFound("missing")

        driver._create_or_update_secrets("my-agent-dev", SECRETS)

        ids = [
            c.kwargs["request"]["secret_id"]
            for c in driver.secret_client.create_secret.call_args_list
        ]
        assert ids == ["my-agent-dev-api-key", "my-agent-dev-rsa-key"]


class TestAppRunner:
    @pytest.fixture
    def driver(self, mocker: MockerFixture) -> AWSAppRunnerDriver:
        mocker.patch(
            "supervaizer.deploy.drivers.aws_app_runner.boto3.client",
            return_value=mocker.Mock(),
        )
        driver = AWSAppRunnerDriver("us-east-1")
        mocker.patch.object(driver, "_get_account_id", return_value="123")
        return driver

    def test_prepare_registry_returns_ecr_reference(
        self, driver: AWSAppRunnerDriver
    ) -> None:
        driver.ecr_client.describe_repositories.side_effect = ClientError(
            {"Error": {"Code": "RepositoryNotFoundException"}}, "DescribeRepositories"
        )

        image = driver.prepare_registry("my-agent-dev:abc")

        assert image == "123.dkr.ecr.us-east-1.amazonaws.com/my-agent-dev:abc"
        assert (
            driver.ecr_client.create_repository.call_args.kwargs["repositoryName"]
            == "my-agent-dev"
        )

    def test_registry_auth_decodes_ecr_token(self, driver: AWSAppRunnerDriver) -> None:
        token = base64.b64encode(b"AWS:secret").decode()
        driver.ecr_client.get_authorization_token.return_value = {
            "authorizationData": [{"authorizationToken": token}]
        }

        assert driver.registry_auth() == {"username": "AWS", "password": "secret"}

    def test_service_uses_env_map_and_secret_arns(
        self, driver: AWSAppRunnerDriver
    ) -> None:
        driver.apprunner_client.update_service.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}}, "UpdateService"
        )
        driver.apprunner_client.create_service.return_value = {
            "Service": {"ServiceArn": "arn:svc"}
        }
        image = "123.dkr.ecr.us-east-1.amazonaws.com/my-agent-dev:abc"

        driver._create_or_update_service(
            "my-agent-dev",
            image,
            8080,
            {"SUPERVAIZER_PORT": "8080"},
            {"SUPERVAIZER_API_KEY": "arn:k"},
        )

        repo = driver.apprunner_client.create_service.call_args.kwargs[
            "SourceConfiguration"
        ]["ImageRepository"]
        assert repo["ImageIdentifier"] == image
        config = repo["ImageConfiguration"]
        assert config["Port"] == "8080"
        assert config["RuntimeEnvironmentVariables"] == {"SUPERVAIZER_PORT": "8080"}
        assert config["RuntimeEnvironmentSecrets"] == {"SUPERVAIZER_API_KEY": "arn:k"}

    def test_secrets_return_arns_by_variable(self, driver: AWSAppRunnerDriver) -> None:
        driver.secrets_client.update_secret.return_value = {"ARN": "arn:api"}

        arns = driver._create_or_update_secrets(
            "my-agent-dev", {"SUPERVAIZER_API_KEY": "k"}
        )

        assert arns == {"SUPERVAIZER_API_KEY": "arn:api"}
        assert (
            driver.secrets_client.update_secret.call_args.kwargs["SecretId"]
            == "my-agent-dev-api-key"
        )

    def test_public_url_update_keeps_env_map(self, driver: AWSAppRunnerDriver) -> None:
        source = {
            "ImageRepository": {
                "ImageConfiguration": {"RuntimeEnvironmentVariables": {"A": "1"}}
            }
        }
        driver.apprunner_client.describe_service.return_value = {
            "Service": {"SourceConfiguration": source}
        }

        driver._set_public_url("arn:svc", "https://x.awsapprunner.com")

        sent = driver.apprunner_client.update_service.call_args.kwargs[
            "SourceConfiguration"
        ]
        assert sent["ImageRepository"]["ImageConfiguration"][
            "RuntimeEnvironmentVariables"
        ] == {
            "A": "1",
            "SUPERVAIZER_PUBLIC_URL": "https://x.awsapprunner.com",
        }


class TestDOAppPlatform:
    @pytest.fixture
    def driver(self) -> DOAppPlatformDriver:
        return DOAppPlatformDriver("nyc3")

    def test_prepare_registry_uses_account_registry(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch("subprocess.run", return_value=_completed("acme\n"))

        assert (
            driver.prepare_registry("my-agent-dev:abc")
            == "registry.digitalocean.com/acme/my-agent-dev:abc"
        )

    def test_prepare_registry_fails_without_registry(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture
    ) -> None:
        mocker.patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "doctl")
        )

        with pytest.raises(RuntimeError, match="doctl registry create"):
            driver.prepare_registry("my-agent-dev:abc")

    def test_registry_auth_reads_docker_config(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture
    ) -> None:
        auth = base64.b64encode(b"tok:tok").decode()
        config = {"auths": {"registry.digitalocean.com": {"auth": auth}}}
        mocker.patch("subprocess.run", return_value=_completed(json.dumps(config)))

        assert driver.registry_auth() == {"username": "tok", "password": "tok"}

    def test_app_spec_deploys_pushed_image_with_secret_values(
        self,
        driver: DOAppPlatformDriver,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)

        spec_path = driver._create_app_spec(
            "my-agent-dev",
            "registry.digitalocean.com/acme/my-agent-dev:abc",
            8080,
            {"SUPERVAIZER_PORT": "8080"},
            {"SUPERVAIZER_API_KEY": "k"},
        )

        service = yaml.safe_load(spec_path.read_text())["services"][0]
        assert service["image"] == {
            "registry_type": "DOCR",
            "repository": "my-agent-dev",
            "tag": "abc",
        }
        assert "github" not in service
        assert service["http_port"] == 8080
        assert {
            "key": "SUPERVAIZER_API_KEY",
            "value": "k",
            "scope": "RUN_TIME",
            "type": "SECRET",
        } in service["envs"]
        assert spec_path.stat().st_mode & 0o077 == 0

    def test_destroy_keeps_shared_registry(
        self, driver: DOAppPlatformDriver, mocker: MockerFixture
    ) -> None:
        run: Mock = mocker.patch("subprocess.run")

        driver.destroy_service("my-agent", "dev")

        commands = [c.args[0][:3] for c in run.call_args_list]
        assert ["doctl", "registry", "delete"] not in commands


class TestBaseDriverCompatibility:
    def test_driver_without_prepare_registry_still_instantiates(self) -> None:
        """Drivers written before prepare_registry existed must still load."""

        class LegacyDriver(BaseDriver):
            plan_deployment = deploy_service = destroy_service = Mock()
            get_service_status = verify_health = check_prerequisites = Mock()

        driver = LegacyDriver("region")

        with pytest.raises(NotImplementedError, match="LegacyDriver"):
            driver.prepare_registry("my-agent-dev:abc")
