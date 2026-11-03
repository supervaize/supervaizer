# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from collections.abc import Callable
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess
from types import ModuleType
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture
from rich.console import Console
from typer.testing import CliRunner

from supervaizer.deploy import cli
from supervaizer.deploy.commands import down, plan, status, up
from supervaizer.deploy.drivers.base import DeploymentResult
from supervaizer.deploy.state import DeploymentState, StateManager

REMOTE_IMAGE = "registry.example/dummy:v1"
SERVICE_URL = "https://dummy.example"


@pytest.fixture
def command_output(mocker: MockerFixture) -> StringIO:
    output = StringIO()
    for module in (up, down, status, cli):
        mocker.patch.object(
            module, "console", Console(file=output, color_system=None, width=240)
        )
    return output


@pytest.fixture
def provider(mocker: MockerFixture) -> Mock:
    driver = mocker.Mock()
    driver.check_prerequisites.return_value = []
    driver.prepare_registry.return_value = REMOTE_IMAGE
    driver.registry_auth.return_value = {"username": "dummy", "password": "dummy"}
    result = DeploymentResult(
        success=True,
        service_url=SERVICE_URL,
        service_id="service-id",
        revision="revision-1",
        image_digest="sha256:0123456789abcdef",
        status="running",
        health_status="healthy",
        deployment_time=12.34,
    )
    driver.deploy_service.return_value = result
    driver.get_service_status.return_value = result
    driver.destroy_service.return_value = DeploymentResult(
        success=True, status="deleted"
    )
    for module in (up, down, status):
        mocker.patch.object(module, "create_driver", return_value=driver)
    return driver


@pytest.fixture
def docker(mocker: MockerFixture) -> Mock:
    manager = mocker.Mock()
    mocker.patch.object(up, "DockerManager", return_value=manager)
    mocker.patch.object(up, "ensure_docker_running", return_value=True)
    mocker.patch.object(
        up, "get_container_env", return_value={"SUPERVAIZER_PORT": "9001"}
    )
    mocker.patch.object(
        up, "_generate_secrets", return_value={"SUPERVAIZER_API_KEY": "dummy-key"}
    )
    return manager


def save_command_state(project: Path, *, full: bool = True) -> DeploymentState:
    state = DeploymentState(
        version=2,
        service_name="saved-service",
        platform="cloud-run",
        environment="staging",
        region="saved-region",
        image_tag="saved-image:old",
        created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        port=9001,
        api_key_generated=full,
        rsa_key_generated=full,
        project_id="saved-project" if full else None,
        image_digest="sha256:abcdefghijklmnop" if full else None,
        service_url=SERVICE_URL if full else None,
        revision="saved-revision" if full else None,
        status="running",
        health_status="healthy",
    )
    StateManager(project / ".deployment").save_state(state)
    return state


def test_up_builds_pushes_deploys_and_saves_the_remote_result_in_order(
    tmp_path: Path,
    provider: Mock,
    docker: Mock,
    command_output: StringIO,
    mocker: MockerFixture,
) -> None:
    operations = mocker.Mock()
    operations.attach_mock(docker, "docker")
    operations.attach_mock(provider, "driver")

    up.deploy_up(
        "cloud-run",
        "dummy",
        "staging",
        "chosen-region",
        "chosen-project",
        image="local-image:v1",
        port=9001,
        generate_api_key=True,
        generate_rsa=True,
        timeout=123,
        source_dir=tmp_path,
    )

    assert [entry[0] for entry in operations.mock_calls] == [
        "driver.check_prerequisites",
        "docker.generate_dockerfile",
        "docker.generate_dockerignore",
        "docker.build_image",
        "driver.prepare_registry",
        "docker.tag_image",
        "driver.registry_auth",
        "docker.push_image",
        "driver.deploy_service",
    ]
    docker.generate_dockerfile.assert_called_once_with(
        output_path=tmp_path / ".deployment/Dockerfile", app_port=9001
    )
    docker.generate_dockerignore.assert_called_once_with(
        tmp_path / ".deployment/.dockerignore"
    )
    docker.build_image.assert_called_once_with(
        "local-image:v1", tmp_path, tmp_path / ".deployment/Dockerfile"
    )
    provider.deploy_service.assert_called_once_with(
        service_name="dummy",
        environment="staging",
        image_tag=REMOTE_IMAGE,
        port=9001,
        env_vars={"SUPERVAIZER_PORT": "9001"},
        secrets={"SUPERVAIZER_API_KEY": "dummy-key"},
        timeout=123,
    )
    state = StateManager(tmp_path / ".deployment").load_state()
    assert state is not None
    assert state.model_dump(
        exclude={"created_at", "updated_at", "provider_data", "version"}
    ) == {
        "service_name": "dummy",
        "platform": "cloud-run",
        "environment": "staging",
        "region": "chosen-region",
        "project_id": "chosen-project",
        "image_tag": REMOTE_IMAGE,
        "image_digest": "sha256:0123456789abcdef",
        "service_url": SERVICE_URL,
        "revision": "revision-1",
        "status": "running",
        "health_status": "healthy",
        "port": 9001,
        "api_key_generated": True,
        "rsa_key_generated": True,
    }
    output = command_output.getvalue()
    assert "Deployment successful!" in output
    assert f"API Documentation: {SERVICE_URL}/docs" in output
    assert "Deployment time: 12.3s" in output


def test_up_uses_the_source_name_region_and_generated_image_defaults(
    tmp_path: Path,
    provider: Mock,
    docker: Mock,
    command_output: StringIO,
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "supervaizer.deploy.utils.subprocess.run",
        return_value=CompletedProcess(["git"], 0, stdout="123456789abcdef\n"),
    )

    up.deploy_up("aws-app-runner", source_dir=tmp_path)

    docker.build_image.assert_called_once_with(
        f"{tmp_path.name}-dev:12345678", tmp_path, tmp_path / ".deployment/Dockerfile"
    )
    assert provider.deploy_service.call_args.kwargs["service_name"] == tmp_path.name
    assert "Region: us-east-1" in command_output.getvalue()


@pytest.mark.parametrize(
    "failure", ["prerequisites", "build", "push", "deploy", "save", "result"]
)
def test_up_reports_failure_without_saving_a_successful_deployment(
    tmp_path: Path,
    provider: Mock,
    docker: Mock,
    command_output: StringIO,
    mocker: MockerFixture,
    failure: str,
) -> None:
    if failure == "prerequisites":
        provider.check_prerequisites.return_value = [
            "dummy login missing",
            "dummy CLI missing",
        ]
    elif failure == "build":
        docker.build_image.side_effect = RuntimeError("dummy build failure")
    elif failure == "push":
        docker.push_image.side_effect = RuntimeError("dummy push failure")
    elif failure == "deploy":
        provider.deploy_service.side_effect = RuntimeError("dummy deploy failure")
    elif failure == "save":
        mocker.patch.object(
            StateManager, "save_state", side_effect=OSError("dummy save failure")
        )
    else:
        provider.deploy_service.return_value = DeploymentResult(
            success=False, error_message="dummy result failure"
        )

    up.deploy_up("cloud-run", "dummy", image="dummy:v1", source_dir=tmp_path)

    assert not (tmp_path / ".deployment/state.json").exists()
    output = command_output.getvalue()
    assert "Deployment successful!" not in output
    if failure == "prerequisites":
        assert "Prerequisites not met:" in output
        assert output.index("dummy login missing") < output.index("dummy CLI missing")
        docker.build_image.assert_not_called()
    else:
        assert f"Deployment failed: dummy {failure} failure" in output
    if failure in {"prerequisites", "build", "push"}:
        provider.deploy_service.assert_not_called()


@pytest.mark.parametrize("rejection", ["platform", "registry-image", "docker"])
def test_up_rejects_invalid_setup_before_creating_deployment_files(
    tmp_path: Path,
    provider: Mock,
    docker: Mock,
    command_output: StringIO,
    mocker: MockerFixture,
    rejection: str,
) -> None:
    mocker.patch.object(up, "ensure_docker_running", return_value=False)
    platform = "unknown" if rejection == "platform" else "cloud-run"
    image = "registry.example/image:v1" if rejection == "registry-image" else None

    up.deploy_up(platform, "dummy", image=image, source_dir=tmp_path)

    assert not (tmp_path / ".deployment").exists()
    docker.build_image.assert_not_called()
    provider.check_prerequisites.assert_not_called()
    assert "Error:" in command_output.getvalue()


def test_up_preserves_previous_state_when_the_provider_rejects_the_update(
    tmp_path: Path,
    provider: Mock,
    docker: Mock,
    command_output: StringIO,
) -> None:
    save_command_state(tmp_path)
    state_file = tmp_path / ".deployment/state.json"
    before = state_file.read_text()
    provider.deploy_service.return_value = DeploymentResult(
        success=False, error_message="dummy update rejected"
    )

    up.deploy_up("cloud-run", "dummy", image="dummy:v2", source_dir=tmp_path)

    assert state_file.read_text() == before
    assert "Deployment failed: dummy update rejected" in command_output.getvalue()


@pytest.mark.parametrize("existing_state", [False, True])
@pytest.mark.parametrize("yes", [False, True])
def test_down_removes_only_the_selected_project_deployment_after_provider_success(
    tmp_path: Path,
    provider: Mock,
    command_output: StringIO,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    existing_state: bool,
    yes: bool,
) -> None:
    project = tmp_path / "source-project"
    project.mkdir()
    if existing_state:
        save_command_state(project)
    other = tmp_path / ".deployment"
    other.mkdir()
    (other / "keep.txt").write_text("other project")
    monkeypatch.chdir(tmp_path)
    confirm = mocker.patch.object(down.Confirm, "ask", return_value=True)

    down.deploy_down("cloud-run", "dummy", yes=yes, source_dir=project)

    provider.destroy_service.assert_called_once_with("dummy", "dev", keep_secrets=False)
    if yes:
        confirm.assert_not_called()
    else:
        confirm.assert_called_once_with("\nAre you sure you want to destroy dummy-dev?")
    assert not (project / ".deployment").exists()
    assert (other / "keep.txt").read_text() == "other project"
    output = command_output.getvalue()
    assert "Service destroyed successfully" in output
    if existing_state:
        assert output.index("Current Deployment:") < output.index(
            "Destroying service..."
        )
        assert output.index("Cleaned up local deployment state") < output.index(
            "Cleaned up deployment directory"
        )
    else:
        assert "Current Deployment:" not in output
        assert "Cleaned up local deployment state" not in output


@pytest.mark.parametrize(
    "failure", ["cancelled", "prerequisites", "provider", "result"]
)
def test_down_preserves_local_state_when_the_service_is_not_destroyed(
    tmp_path: Path,
    provider: Mock,
    command_output: StringIO,
    mocker: MockerFixture,
    failure: str,
) -> None:
    save_command_state(tmp_path)
    state_file = tmp_path / ".deployment/state.json"
    before = state_file.read_text()
    confirm = mocker.patch.object(
        down.Confirm, "ask", return_value=failure != "cancelled"
    )
    if failure == "prerequisites":
        provider.check_prerequisites.return_value = ["dummy prerequisite"]
    elif failure == "provider":
        provider.destroy_service.side_effect = RuntimeError("dummy provider failure")
    elif failure == "result":
        provider.destroy_service.return_value = DeploymentResult(
            success=False, error_message="dummy result failure"
        )

    down.deploy_down("cloud-run", env="staging", source_dir=tmp_path)

    confirm.assert_called_once_with(
        f"\nAre you sure you want to destroy {tmp_path.name}-staging?"
    )
    assert state_file.read_text() == before
    output = command_output.getvalue()
    assert "Service destroyed successfully" not in output
    if failure == "cancelled":
        assert "Destruction cancelled" in output
        provider.check_prerequisites.assert_not_called()
    elif failure == "prerequisites":
        assert "dummy prerequisite" in output
    else:
        assert f"Destruction failed: dummy {failure} failure" in output
    if failure in {"cancelled", "prerequisites"}:
        provider.destroy_service.assert_not_called()


def test_down_reports_directory_cleanup_failure_after_removing_state(
    tmp_path: Path, provider: Mock, command_output: StringIO, mocker: MockerFixture
) -> None:
    save_command_state(tmp_path)
    artifact = tmp_path / ".deployment/Dockerfile"
    artifact.write_text("dummy image")
    mocker.patch("shutil.rmtree", side_effect=PermissionError("dummy cleanup denied"))

    down.deploy_down("cloud-run", "dummy", yes=True, source_dir=tmp_path)

    assert artifact.read_text() == "dummy image"
    assert not (tmp_path / ".deployment/state.json").exists()
    output = command_output.getvalue()
    assert "Service destroyed successfully" in output
    assert "Cleaned up local deployment state" in output
    assert "Destruction failed: dummy cleanup denied" in output


@pytest.mark.parametrize("full", [False, True])
def test_status_displays_saved_state_before_live_status_without_changing_it(
    tmp_path: Path, provider: Mock, command_output: StringIO, full: bool
) -> None:
    saved = save_command_state(tmp_path, full=full)
    state_file = tmp_path / ".deployment/state.json"
    before = state_file.read_text()

    status.deploy_status("cloud-run", "dummy", source_dir=tmp_path)

    assert state_file.read_text() == before
    provider.get_service_status.assert_called_once_with("dummy", "dev")
    output = command_output.getvalue()
    local, live = output.split("Live Status:", maxsplit=1)
    assert "Local State:" in local
    for text in (
        "saved-service",
        "saved-image:old",
        "staging",
        "saved-region",
        "9001",
        saved.created_at.isoformat(),
        saved.updated_at.isoformat(),
    ):
        assert text in local
    assert "API Key Generated" in local
    assert "RSA Key Generated" in local
    assert str(full) in local
    if full:
        for text in (
            "saved-project",
            "saved-revision",
            "sha256:abcdefghi...",
            SERVICE_URL,
        ):
            assert text in local
    else:
        for label in ("Project ID", "Image Digest", "Service URL", "Revision"):
            assert label not in local
    for text in (
        SERVICE_URL,
        f"{SERVICE_URL}/docs",
        f"{SERVICE_URL}/redoc",
        "service-id",
        "revision-1",
        "sha256:012345678...",
        "12.3s",
        "Service is healthy",
    ):
        assert text in live


@pytest.mark.parametrize(
    ("health", "url", "message"),
    [
        ("healthy", SERVICE_URL, "Service is healthy"),
        ("unhealthy", SERVICE_URL, "Service is unhealthy"),
        ("unknown", SERVICE_URL, "Health status unknown"),
        ("unknown", None, None),
    ],
)
def test_status_displays_minimal_live_results_and_health_messages(
    tmp_path: Path,
    provider: Mock,
    command_output: StringIO,
    health: str,
    url: str | None,
    message: str | None,
) -> None:
    provider.get_service_status.return_value = DeploymentResult(
        success=True, health_status=health, service_url=url, deployment_time=0.0
    )

    status.deploy_status("aws-app-runner", source_dir=tmp_path)

    output = command_output.getvalue()
    assert "Local State:" not in output
    assert f"Deployment Status for {tmp_path.name}-dev" in output
    assert "Region: us-east-1" in output
    assert "Live Status:" in output
    for absent in ("Service ID", "Revision", "Image Digest", "Deployment Time"):
        assert absent not in output
    if message:
        assert message in output
    else:
        assert "Health Check:" not in output
        assert "Service URL" not in output
    assert not (tmp_path / ".deployment").exists()


@pytest.mark.parametrize("state_content", [None, "invalid JSON"])
def test_status_queries_the_provider_when_local_state_is_missing_or_corrupt(
    tmp_path: Path,
    provider: Mock,
    command_output: StringIO,
    state_content: str | None,
) -> None:
    deployment_dir = tmp_path / ".deployment"
    deployment_dir.mkdir()
    if state_content is not None:
        (deployment_dir / "state.json").write_text(state_content)

    status.deploy_status("cloud-run", "dummy", source_dir=tmp_path)

    provider.get_service_status.assert_called_once_with("dummy", "dev")
    output = command_output.getvalue()
    assert "Local State:" not in output
    assert "Live Status:" in output
    if state_content is not None:
        assert (deployment_dir / "state.json").read_text() == state_content


@pytest.mark.parametrize("failure", ["prerequisites", "provider", "result", "state"])
def test_status_reports_failures_and_preserves_local_state(
    tmp_path: Path,
    provider: Mock,
    command_output: StringIO,
    mocker: MockerFixture,
    failure: str,
) -> None:
    save_command_state(tmp_path)
    state_file = tmp_path / ".deployment/state.json"
    before = state_file.read_text()
    if failure == "prerequisites":
        provider.check_prerequisites.return_value = ["dummy prerequisite"]
    elif failure == "provider":
        provider.get_service_status.side_effect = RuntimeError("dummy provider failure")
    elif failure == "state":
        mocker.patch.object(
            StateManager, "load_state", side_effect=ValueError("dummy state failure")
        )
    else:
        provider.get_service_status.return_value = DeploymentResult(
            success=False, error_message="dummy service missing"
        )

    status.deploy_status("cloud-run", "dummy", source_dir=tmp_path)

    assert state_file.read_text() == before
    output = command_output.getvalue()
    assert "Live Status:" not in output
    if failure == "prerequisites":
        assert "Prerequisites not met:" in output
        provider.get_service_status.assert_not_called()
    elif failure == "result":
        assert "Service not found or error: dummy service missing" in output
    else:
        assert f"Status check failed: dummy {failure} failure" in output


@pytest.mark.parametrize(
    ("flags", "selected"),
    [
        ([], "clean_deployment"),
        (["--docker-only"], "clean_docker_artifacts"),
        (["--state-only"], "clean_state_only"),
    ],
)
def test_cli_clean_selects_one_scope_and_forwards_force_and_verbose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    command_output: StringIO,
    flags: list[str],
    selected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='dummy'\n")
    cleaners = {
        name: mocker.patch.object(cli, name)
        for name in ("clean_deployment", "clean_docker_artifacts", "clean_state_only")
    }

    result = CliRunner().invoke(
        cli.deploy_app, ["clean", "--force", "--verbose", *flags]
    )

    assert result.exit_code == 0
    for name, cleaner in cleaners.items():
        if name == selected:
            cleaner.assert_called_once_with(force=True, verbose=True)
        else:
            cleaner.assert_not_called()


def test_cli_clean_rejects_conflicting_scopes_before_any_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    command_output: StringIO,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='dummy'\n")
    cleaners = [
        mocker.patch.object(cli, name)
        for name in ("clean_deployment", "clean_docker_artifacts", "clean_state_only")
    ]

    result = CliRunner().invoke(
        cli.deploy_app, ["clean", "--docker-only", "--state-only"]
    )

    assert result.exit_code == 1
    assert "Cannot use both --docker-only and --state-only" in command_output.getvalue()
    for cleaner in cleaners:
        cleaner.assert_not_called()


@pytest.mark.parametrize("module", [plan, up, down, status])
@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("cloud-run", "us-central1"),
        ("aws-app-runner", "us-east-1"),
        ("do-app-platform", "nyc3"),
        ("unknown", "us-central1"),
    ],
)
def test_default_region_helpers_keep_existing_platform_and_unknown_defaults(
    module: ModuleType, platform: str, expected: str
) -> None:
    helper: Callable[[str], str] = module._get_default_region
    assert helper(platform) == expected


@pytest.mark.parametrize("module", [plan, up])
def test_generated_image_tag_uses_service_environment_and_short_git_sha(
    module: ModuleType, mocker: MockerFixture
) -> None:
    mocker.patch(
        "supervaizer.deploy.utils.subprocess.run",
        return_value=CompletedProcess(["git"], 0, stdout="0123456789abcdef\n"),
    )
    helper: Callable[[str, str], str] = module._generate_image_tag

    assert helper("dummy-service", "staging") == "dummy-service-staging:01234567"
