# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from supervaizer.deploy.commands.clean import (
    clean_deployment,
    clean_docker_artifacts,
    clean_state_only,
)


def create_deployment_artifacts(deployment_dir: Path) -> None:
    deployment_dir.mkdir()
    (deployment_dir / "Dockerfile").write_text("FROM python\n")
    (deployment_dir / ".dockerignore").write_text("__pycache__/\n")
    (deployment_dir / "state.json").write_text("{}\n")
    (deployment_dir / "config.yaml").write_text("name: service\n")
    logs_dir = deployment_dir / "logs"
    logs_dir.mkdir()
    (logs_dir / "deploy.log").write_text("ok\n")


class TestCleanDeployment:
    def test_clean_deployment_returns_when_directory_is_missing(
        self,
        tmp_path: Path,
    ) -> None:
        missing_dir = tmp_path / ".deployment"

        clean_deployment(missing_dir)

        assert not missing_dir.exists()

    def test_clean_deployment_deletes_directory_when_forced(
        self,
        tmp_path: Path,
    ) -> None:
        deployment_dir = tmp_path / ".deployment"
        create_deployment_artifacts(deployment_dir)

        clean_deployment(deployment_dir, force=True, verbose=True)

        assert not deployment_dir.exists()

    def test_clean_deployment_keeps_directory_when_cancelled(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        deployment_dir = tmp_path / ".deployment"
        create_deployment_artifacts(deployment_dir)
        confirm = mocker.patch(
            "supervaizer.deploy.commands.clean.Confirm.ask",
            return_value=False,
        )

        clean_deployment(deployment_dir)

        assert deployment_dir.exists()
        confirm.assert_called_once()

    def test_clean_deployment_wraps_permission_errors(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        deployment_dir = tmp_path / ".deployment"
        create_deployment_artifacts(deployment_dir)
        mocker.patch(
            "supervaizer.deploy.commands.clean.shutil.rmtree",
            side_effect=PermissionError("locked"),
        )

        with pytest.raises(RuntimeError, match="Failed to clean deployment directory"):
            clean_deployment(deployment_dir, force=True)


class TestCleanDockerArtifacts:
    def test_clean_docker_artifacts_returns_when_deployment_dir_is_missing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)

        clean_docker_artifacts()

        assert not (tmp_path / ".deployment").exists()

    def test_clean_docker_artifacts_deletes_only_docker_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        deployment_dir = tmp_path / ".deployment"
        create_deployment_artifacts(deployment_dir)

        clean_docker_artifacts(force=True, verbose=True)

        assert not (deployment_dir / "Dockerfile").exists()
        assert not (deployment_dir / ".dockerignore").exists()
        assert not (deployment_dir / "logs").exists()
        assert (deployment_dir / "state.json").exists()
        assert (deployment_dir / "config.yaml").exists()

    def test_clean_docker_artifacts_keeps_files_when_cancelled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: MockerFixture,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        deployment_dir = tmp_path / ".deployment"
        create_deployment_artifacts(deployment_dir)
        mocker.patch(
            "supervaizer.deploy.commands.clean.Confirm.ask",
            return_value=False,
        )

        clean_docker_artifacts()

        assert (deployment_dir / "Dockerfile").exists()
        assert (deployment_dir / "logs").exists()

    def test_clean_docker_artifacts_returns_when_no_artifacts_exist(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".deployment").mkdir()

        clean_docker_artifacts()

        assert (tmp_path / ".deployment").exists()


class TestCleanStateOnly:
    def test_clean_state_only_returns_when_deployment_dir_is_missing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)

        clean_state_only()

        assert not (tmp_path / ".deployment").exists()

    def test_clean_state_only_deletes_state_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        deployment_dir = tmp_path / ".deployment"
        create_deployment_artifacts(deployment_dir)

        clean_state_only(force=True, verbose=True)

        assert not (deployment_dir / "state.json").exists()
        assert not (deployment_dir / "config.yaml").exists()
        assert (deployment_dir / "Dockerfile").exists()
        assert (deployment_dir / "logs").exists()

    def test_clean_state_only_keeps_files_when_cancelled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: MockerFixture,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        deployment_dir = tmp_path / ".deployment"
        create_deployment_artifacts(deployment_dir)
        mocker.patch(
            "supervaizer.deploy.commands.clean.Confirm.ask",
            return_value=False,
        )

        clean_state_only()

        assert (deployment_dir / "state.json").exists()
        assert (deployment_dir / "config.yaml").exists()

    def test_clean_state_only_returns_when_no_state_files_exist(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        deployment_dir = tmp_path / ".deployment"
        deployment_dir.mkdir()
        (deployment_dir / "Dockerfile").write_text("FROM python\n")

        clean_state_only()

        assert (deployment_dir / "Dockerfile").exists()
