# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Tests for deployment CLI Phase 1 functionality.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from supervaizer.deploy.docker import DockerManager, ensure_docker_running, get_git_sha
from supervaizer.deploy.state import (
    DeploymentState,
    StateManager,
    create_deployment_directory,
)


class TestDockerManager:
    """Test Docker manager functionality."""

    def test_docker_manager_init(self, mocker: MockerFixture) -> None:
        """Test Docker manager initialization."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.return_value = True
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        assert manager.client == mock_client
        mock_client.ping.assert_called_once()

    def test_docker_manager_init_failure(self, mocker: MockerFixture) -> None:
        """Test Docker manager initialization failure."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.side_effect = Exception("Docker not running")
        mock_docker_client.from_env.return_value = mock_client

        with pytest.raises(RuntimeError, match="Docker is not running"):
            DockerManager()

    def test_generate_dockerfile(self, mocker: MockerFixture) -> None:
        """Test Dockerfile generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Dockerfile"

            mocker.patch("supervaizer.deploy.docker.DockerClient")
            manager = DockerManager()
            manager.generate_dockerfile(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "FROM python:3.12-slim" in content
            assert "EXPOSE 8000" in content
            assert 'CMD ["python", "-m", "supervaizer.__main__"]' in content

    def test_generate_dockerignore(self, mocker: MockerFixture) -> None:
        """Test .dockerignore generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / ".dockerignore"

            mocker.patch("supervaizer.deploy.docker.DockerClient")
            manager = DockerManager()
            manager.generate_dockerignore(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "__pycache__/" in content
            assert ".deployment/" in content

    def test_generate_docker_compose(self, mocker: MockerFixture) -> None:
        """Test docker-compose.yml generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "docker-compose.yml"

            mocker.patch("supervaizer.deploy.docker.DockerClient")
            manager = DockerManager()
            manager.generate_docker_compose(output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "version: '3.8'" in content
            assert "ports:" in content
            assert "8000:8000" in content


class TestStateManager:
    """Test state manager functionality."""

    def test_state_manager_init(self) -> None:
        """Test state manager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            assert manager.deployment_dir == deployment_dir
            assert manager.state_file == deployment_dir / "state.json"
            assert deployment_dir.exists()
            assert (deployment_dir / "logs").exists()

    def test_deployment_state_model(self) -> None:
        """Test deployment state model."""
        state = DeploymentState(
            service_name="test-service",
            platform="cloud-run",
            environment="dev",
            region="us-central1",
            project_id=None,
            image_tag="test:latest",
            image_digest=None,
            service_url=None,
            revision=None,
            status="unknown",
            health_status="unknown",
            port=8000,
            api_key_generated=False,
            rsa_key_generated=False,
        )

        assert state.service_name == "test-service"
        assert state.platform == "cloud-run"
        assert state.environment == "dev"
        assert state.region == "us-central1"
        assert state.image_tag == "test:latest"
        assert state.port == 8000
        assert state.status == "unknown"

    def test_save_and_load_state(self) -> None:
        """Test saving and loading deployment state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            # Create initial state
            state = DeploymentState(
                service_name="test-service",
                platform="cloud-run",
                environment="dev",
                region="us-central1",
                image_tag="test:latest",
            )

            # Save state
            manager.save_state(state)
            assert manager.state_file.exists()

            # Load state
            loaded_state = manager.load_state()
            assert loaded_state is not None
            assert loaded_state.service_name == "test-service"
            assert loaded_state.platform == "cloud-run"

    def test_update_state(self) -> None:
        """Test updating deployment state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            # Create initial state
            state = manager.update_state(
                service_name="test-service",
                platform="cloud-run",
                environment="dev",
                region="us-central1",
                image_tag="test:latest",
            )

            # Update state
            updated_state = manager.update_state(
                service_url="https://test.example.com", status="deployed"
            )

            assert updated_state.service_url == "https://test.example.com"
            assert updated_state.status == "deployed"
            assert updated_state.service_name == "test-service"  # Should be preserved

    def test_validate_state(self) -> None:
        """Test state validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            # Valid state
            valid_state = DeploymentState(
                service_name="test-service",
                platform="cloud-run",
                environment="dev",
                region="us-central1",
                image_tag="test:latest",
            )
            assert manager.validate_state(valid_state) is True

            # Invalid platform
            invalid_state = DeploymentState(
                service_name="test-service",
                platform="invalid-platform",
                environment="dev",
                region="us-central1",
                image_tag="test:latest",
            )
            assert manager.validate_state(invalid_state) is False

    def test_get_service_key(self) -> None:
        """Test service key generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            key = manager.get_service_key("test-service", "dev")
            assert key == "test-service-dev"

    def test_delete_state(self) -> None:
        """Test state deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            # Create and save state
            state = DeploymentState(
                service_name="test-service",
                platform="cloud-run",
                environment="dev",
                region="us-central1",
                image_tag="test:latest",
            )
            manager.save_state(state)
            assert manager.state_file.exists()

            # Delete state
            manager.delete_state()
            assert not manager.state_file.exists()


class TestUtilityFunctions:
    """Test utility functions."""

    def test_ensure_docker_running(self, mocker: MockerFixture) -> None:
        """Test Docker running check."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.return_value = True
        mock_docker_client.from_env.return_value = mock_client

        assert ensure_docker_running() is True

    def test_ensure_docker_not_running(self, mocker: MockerFixture) -> None:
        """Test Docker not running check."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.side_effect = Exception("Docker not running")
        mock_docker_client.from_env.return_value = mock_client

        assert ensure_docker_running() is False

    def test_get_git_sha(self, mocker: MockerFixture) -> None:
        """Test git SHA retrieval."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = "abc123def456\n"
        mock_run.return_value.returncode = 0

        sha = get_git_sha()
        assert sha == "abc123de"

    def test_get_git_sha_fallback(self, mocker: MockerFixture) -> None:
        """Test git SHA fallback to latest."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        sha = get_git_sha()
        assert sha == "latest"


class TestDeploymentDirectory:
    """Test deployment directory creation."""

    def test_create_deployment_directory(self) -> None:
        """Test deployment directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            deployment_dir = create_deployment_directory(project_root)

            assert deployment_dir == project_root / ".deployment"
            assert deployment_dir.exists()
            assert (deployment_dir / "logs").exists()

            # Check .gitignore
            gitignore_path = project_root / ".gitignore"
            assert gitignore_path.exists()
            assert ".deployment/" in gitignore_path.read_text()

    def test_create_deployment_directory_existing_gitignore(self) -> None:
        """Test deployment directory creation with existing .gitignore."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            # Create existing .gitignore
            gitignore_path = project_root / ".gitignore"
            gitignore_path.write_text("*.pyc\n__pycache__/\n")

            deployment_dir = create_deployment_directory(project_root)

            # Check that .deployment/ was added
            gitignore_content = gitignore_path.read_text()
            assert ".deployment/" in gitignore_content
            assert "*.pyc" in gitignore_content  # Original content preserved
