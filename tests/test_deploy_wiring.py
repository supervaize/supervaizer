# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Container wiring for `supervaizer deploy up` and `deploy local`."""

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml
from pytest_mock import MockerFixture

from supervaizer.deploy.commands.local import (
    _generate_test_secrets,
    _run_health_checks,
    _start_docker_compose,
    local_docker,
)
from supervaizer.deploy.commands.up import deploy_up
from supervaizer.deploy.docker import DockerManager, get_container_env
from supervaizer.deploy.drivers.base import DeploymentResult

WORKSPACE_AUTH_ENV = {
    "SUPERVAIZER_WORKSPACE_AUTH_REQUIRED": "true",
    "SUPERVAIZER_WORKSPACE_AUTH_ISSUER": "https://studio.example",
    "SUPERVAIZER_WORKSPACE_AUTH_AUDIENCE": "controller",
    "SUPERVAIZER_WORKSPACE_AUTH_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----\n",
    "SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL": "https://studio.example/jwks",
    "SUPERVAIZER_WORKSPACE_AUTH_LEEWAY_SECONDS": "15",
}
HOST_ENV_NAMES = [
    "SUPERVAIZE_API_KEY",
    "SUPERVAIZE_WORKSPACE_ID",
    "SUPERVAIZE_API_URL",
    "SUPERVAIZER_PUBLIC_URL",
    "SUPERVAIZER_SERVER_ID",
    "SUPERVAIZER_LOG_LEVEL",
    *WORKSPACE_AUTH_ENV,
]
REMOTE_IMAGE = "registry.example/my-agent-dev:abc12345"


@pytest.fixture(autouse=True)
def clean_host_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in HOST_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def up_mocks(mocker: MockerFixture, tmp_path: Path) -> dict[str, Mock]:
    """Patch every external dependency of deploy_up."""
    mocker.patch("supervaizer.deploy.commands.up.console.print")
    mocker.patch(
        "supervaizer.deploy.commands.up.ensure_docker_running", return_value=True
    )
    mocker.patch(
        "supervaizer.deploy.commands.up.create_deployment_directory",
        return_value=tmp_path / ".deployment",
    )
    mocker.patch("supervaizer.deploy.commands.up.get_git_sha", return_value="abc12345")
    state = mocker.patch("supervaizer.deploy.commands.up.StateManager").return_value
    docker = mocker.patch("supervaizer.deploy.commands.up.DockerManager").return_value
    driver = mocker.Mock()
    driver.check_prerequisites.return_value = []
    driver.prepare_registry.return_value = REMOTE_IMAGE
    driver.registry_auth.return_value = {"username": "u", "password": "p"}
    driver.deploy_service.return_value = DeploymentResult(
        success=True, status="running"
    )
    mocker.patch("supervaizer.deploy.commands.up.create_driver", return_value=driver)
    return {"docker": docker, "driver": driver, "state": state}


def _deploy_kwargs(up_mocks: dict[str, Mock]) -> dict[str, Any]:
    return up_mocks["driver"].deploy_service.call_args.kwargs


class TestDeployUpImagePush:
    def test_pushes_built_image_to_driver_registry(
        self, up_mocks: dict[str, Mock], tmp_path: Path
    ) -> None:
        docker, driver = up_mocks["docker"], up_mocks["driver"]
        driver.deploy_service.side_effect = lambda **_: (
            DeploymentResult(success=True, status="running")
            if docker.push_image.called
            else DeploymentResult(success=False, error_message="deployed before push")
        )

        deploy_up("cloud-run", "my-agent", "dev", project_id="p", source_dir=tmp_path)

        assert docker.build_image.call_args.args[0] == "my-agent-dev:abc12345"
        driver.prepare_registry.assert_called_once_with("my-agent-dev:abc12345")
        docker.tag_image.assert_called_once_with("my-agent-dev:abc12345", REMOTE_IMAGE)
        docker.push_image.assert_called_once_with(
            REMOTE_IMAGE, auth_config={"username": "u", "password": "p"}
        )
        assert _deploy_kwargs(up_mocks)["image_tag"] == REMOTE_IMAGE
        assert (
            up_mocks["state"].update_state.call_args.kwargs["image_tag"] == REMOTE_IMAGE
        )

    def test_push_failure_stops_before_deploy(
        self, up_mocks: dict[str, Mock], tmp_path: Path
    ) -> None:
        up_mocks["docker"].push_image.side_effect = RuntimeError("Push failed: denied")

        deploy_up("cloud-run", "my-agent", "dev", project_id="p", source_dir=tmp_path)

        up_mocks["driver"].deploy_service.assert_not_called()
        up_mocks["state"].update_state.assert_not_called()

    def test_image_with_registry_host_is_rejected(
        self, up_mocks: dict[str, Mock], tmp_path: Path
    ) -> None:
        deploy_up("cloud-run", "my-agent", image="gcr.io/p/img:v1", source_dir=tmp_path)

        up_mocks["docker"].build_image.assert_not_called()
        up_mocks["driver"].deploy_service.assert_not_called()


class TestDeployUpEnvironment:
    def test_generated_secrets_use_server_variable_names(
        self, up_mocks: dict[str, Mock], tmp_path: Path
    ) -> None:
        deploy_up(
            "cloud-run",
            "my-agent",
            project_id="p",
            generate_api_key=True,
            generate_rsa=True,
            source_dir=tmp_path,
        )

        secrets = _deploy_kwargs(up_mocks)["secrets"]
        assert set(secrets) == {"SUPERVAIZER_API_KEY", "SUPERVAIZER_PRIVATE_KEY"}
        assert secrets["SUPERVAIZER_PRIVATE_KEY"].startswith(
            "-----BEGIN PRIVATE KEY-----"
        )

    def test_studio_key_is_a_secret_and_workspace_auth_is_passed(
        self,
        up_mocks: dict[str, Mock],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for name, value in WORKSPACE_AUTH_ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setenv("SUPERVAIZE_API_KEY", "studio-key")
        monkeypatch.setenv("SUPERVAIZE_WORKSPACE_ID", "ws-1")
        monkeypatch.setenv("SUPERVAIZER_SERVER_ID", "server-1")
        monkeypatch.setenv("SUPERVAIZER_PUBLIC_URL", "http://localhost:8000")

        deploy_up("cloud-run", "my-agent", project_id="p", source_dir=tmp_path)

        env_vars = _deploy_kwargs(up_mocks)["env_vars"]
        assert {k: env_vars[k] for k in WORKSPACE_AUTH_ENV} == WORKSPACE_AUTH_ENV
        assert env_vars["SUPERVAIZE_WORKSPACE_ID"] == "ws-1"
        assert env_vars["SUPERVAIZER_SERVER_ID"] == "server-1"
        assert "SUPERVAIZE_API_KEY" not in env_vars
        assert "SUPERVAIZER_PUBLIC_URL" not in env_vars  # set by the driver
        assert _deploy_kwargs(up_mocks)["secrets"] == {
            "SUPERVAIZE_API_KEY": "studio-key"
        }

    def test_port_flag_reaches_server_port(
        self, up_mocks: dict[str, Mock], tmp_path: Path
    ) -> None:
        deploy_up(
            "cloud-run", "my-agent", project_id="p", port=8080, source_dir=tmp_path
        )

        kwargs = _deploy_kwargs(up_mocks)
        assert kwargs["port"] == 8080
        assert kwargs["env_vars"]["SUPERVAIZER_PORT"] == "8080"
        assert kwargs["env_vars"]["SUPERVAIZER_LOG_LEVEL"] == "INFO"
        assert "SV_LOG_LEVEL" not in kwargs["env_vars"]


class TestContainerFiles:
    def test_container_env_skips_unset_host_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SUPERVAIZER_WORKSPACE_AUTH_REQUIRED", "true")

        assert get_container_env("prod", 9000) == {
            "SUPERVAIZER_ENVIRONMENT": "prod",
            "SUPERVAIZER_HOST": "0.0.0.0",
            "SUPERVAIZER_PORT": "9000",
            "SUPERVAIZER_LOG_LEVEL": "INFO",
            "SUPERVAIZER_WORKSPACE_AUTH_REQUIRED": "true",
        }

    def test_dockerfile_never_bakes_credentials(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SUPERVAIZE_API_KEY", "studio-secret")
        dockerfile = tmp_path / "Dockerfile"

        DockerManager(require_docker=False).generate_dockerfile(
            dockerfile, app_port=8080
        )

        content = dockerfile.read_text()
        assert "studio-secret" not in content
        assert "SUPERVAIZE_API_KEY" not in content
        assert "ENV SUPERVAIZER_PORT=8080" in content
        assert "EXPOSE 8080" in content

    def test_compose_quotes_multiline_values_and_uses_port(
        self, tmp_path: Path
    ) -> None:
        compose = tmp_path / "docker-compose.yml"
        pem = "-----BEGIN PRIVATE KEY-----\nline\n-----END PRIVATE KEY-----\n"

        DockerManager(require_docker=False).generate_docker_compose(
            {"SUPERVAIZER_PRIVATE_KEY": pem, "SUPERVAIZE_API_KEY": "a$b"},
            output_path=compose,
            port=8080,
            service_name="svc-dev",
        )

        service = yaml.safe_load(compose.read_text())["services"]["svc-dev"]
        assert f"SUPERVAIZER_PRIVATE_KEY={pem}" in service["environment"]
        assert "SUPERVAIZE_API_KEY=a$$b" in service["environment"]  # compose escape
        assert service["ports"] == ["127.0.0.1:8080:8080"]
        assert "args" not in service["build"]
        assert (
            "http://localhost:8080/.well-known/health" in service["healthcheck"]["test"]
        )
        assert compose.stat().st_mode & 0o077 == 0

    def test_push_image_forwards_registry_credentials(
        self, mocker: MockerFixture
    ) -> None:
        manager = DockerManager(require_docker=False)
        manager.client = mocker.Mock()
        manager.client.images.push.return_value = iter([{"status": "Pushed"}])

        manager.push_image(REMOTE_IMAGE, auth_config={"username": "u", "password": "p"})

        manager.client.images.push.assert_called_once_with(
            REMOTE_IMAGE,
            stream=True,
            decode=True,
            auth_config={"username": "u", "password": "p"},
        )


class TestDeployLocal:
    def test_secrets_use_server_variable_names(self) -> None:
        assert _generate_test_secrets(False, False) == {
            "SUPERVAIZER_API_KEY": "test-api-key-local"
        }
        secrets = _generate_test_secrets(True, True)
        assert secrets["SUPERVAIZER_API_KEY"] != "test-api-key-local"
        assert secrets["SUPERVAIZER_PRIVATE_KEY"].startswith(
            "-----BEGIN PRIVATE KEY-----"
        )

    def test_compose_gets_host_studio_key_and_workspace_auth(
        self, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name, value in WORKSPACE_AUTH_ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setenv("SUPERVAIZE_API_KEY", "studio-key")
        mocker.patch("supervaizer.deploy.commands.local.console.print")
        mocker.patch(
            "supervaizer.deploy.commands.local._check_docker_available",
            return_value=True,
        )
        manager = mocker.patch(
            "supervaizer.deploy.commands.local.DockerManager"
        ).return_value

        local_docker("svc", "dev", 8080, False, False, 30, False, True)

        env_vars = manager.generate_docker_compose.call_args.kwargs["env_vars"]
        assert env_vars["SUPERVAIZE_API_KEY"] == "studio-key"
        assert env_vars["SUPERVAIZER_API_KEY"] == "test-api-key-local"
        assert env_vars["SUPERVAIZER_PORT"] == "8080"
        assert {k: env_vars[k] for k in WORKSPACE_AUTH_ENV} == WORKSPACE_AUTH_ENV
        assert "SV_RSA_PRIVATE_KEY" not in env_vars

    def test_compose_uses_docker_compose_v2(self, mocker: MockerFixture) -> None:
        mocker.patch("pathlib.Path.exists", return_value=True)
        run = mocker.patch("subprocess.run")
        run.return_value.returncode = 0

        _start_docker_compose()

        assert run.call_args.args[0] == [
            "docker",
            "compose",
            "-f",
            ".deployment/docker-compose.yml",
            "up",
            "-d",
        ]

    def test_health_checks_never_probe_removed_route(
        self, mocker: MockerFixture
    ) -> None:
        get = mocker.patch("supervaizer.deploy.commands.local.httpx.get")
        get.return_value.status_code = 200
        get.return_value.elapsed.total_seconds.return_value = 0.1

        results = _run_health_checks("http://localhost:8000")

        urls = [call.args[0] for call in get.call_args_list]
        assert urls == [
            "http://localhost:8000/.well-known/health",
            "http://localhost:8000/docs",
        ]
        assert set(results) == {"health_endpoint", "api_docs"}
