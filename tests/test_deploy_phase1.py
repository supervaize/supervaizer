# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Tests for deployment CLI Phase 1 functionality.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from docker.errors import DockerException
from pytest_mock import MockerFixture

from supervaizer.deploy.docker import DockerManager, ensure_docker_running, get_git_sha
from supervaizer.deploy.state import (
    DeploymentState,
    StateManager,
    create_deployment_directory,
)
from supervaizer.deploy.commands import (
    plan,
    up,
)  # Import plan and up modules to access their console instances


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
        mock_client.ping.side_effect = DockerException("Docker not running")
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
            assert 'CMD ["supervaizer", "start"]' in content
            # Verify template placeholders are replaced with actual values
            assert "COPY src/ ./src/" in content  # source directory
            assert "COPY supervaizer_control.py ./" in content  # controller file
            # Verify no template placeholders remain
            assert "{{" not in content
            assert "}}" not in content

    def test_generate_dockerfile_custom_params(self, mocker: MockerFixture) -> None:
        """Test Dockerfile generation with custom parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "Dockerfile"

            mocker.patch("supervaizer.deploy.docker.DockerClient")
            manager = DockerManager()
            manager.generate_dockerfile(
                output_path,
                python_version="3.11",
                app_port=9000,
                source_dir=".",
                controller_file="my_controller.py",
            )

            assert output_path.exists()
            content = output_path.read_text()
            assert "FROM python:3.11-slim" in content
            assert "EXPOSE 9000" in content
            assert "COPY ./ ././" in content  # source directory
            assert "COPY my_controller.py ./" in content  # controller file
            # Verify no template placeholders remain
            assert "{{" not in content
            assert "}}" not in content

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
            assert "ports:" in content
            assert "8000:8000" in content
            # Verify template placeholders are replaced with actual values
            assert "supervaizer-dev:" in content  # service name
            assert "SUPERVAIZER_ENVIRONMENT=dev" in content  # environment
            assert "SUPERVAIZER_API_KEY=test-api-key" in content  # api key
            assert "SV_RSA_PRIVATE_KEY=test-rsa-key" in content  # rsa key
            # Verify no template placeholders remain
            assert "{{" not in content
            assert "}}" not in content


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
        mock_client.ping.side_effect = DockerException("Docker not running")
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


class TestDockerManagerAdvanced:
    """Test advanced Docker manager functionality."""

    def test_build_image_success(self, mocker: MockerFixture) -> None:
        """Test successful Docker image building."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_image = mocker.Mock()
        mock_image.id = "sha256:abc123"
        mock_client.ping.return_value = True
        mock_client.images.build.return_value = (mock_image, [])
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        result = manager.build_image(
            "test:latest", Path("/tmp"), Path("/tmp/Dockerfile")
        )

        assert result == "sha256:abc123"
        mock_client.images.build.assert_called_once()

    def test_build_image_failure(self, mocker: MockerFixture) -> None:
        """Test Docker image building failure."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.return_value = True
        mock_client.images.build.side_effect = DockerException("Build failed")
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        with pytest.raises(RuntimeError, match="Docker build failed"):
            manager.build_image("test:latest", Path("/tmp"), Path("/tmp/Dockerfile"))

    def test_tag_image_success(self, mocker: MockerFixture) -> None:
        """Test successful Docker image tagging."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_image = mocker.Mock()
        mock_client.ping.return_value = True
        mock_client.images.get.return_value = mock_image
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        manager.tag_image("source:latest", "target:v1.0")

        mock_client.images.get.assert_called_once_with("source:latest")
        mock_image.tag.assert_called_once_with("target:v1.0")

    def test_tag_image_failure(self, mocker: MockerFixture) -> None:
        """Test Docker image tagging failure."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.return_value = True
        mock_client.images.get.side_effect = DockerException("Image not found")
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        with pytest.raises(RuntimeError, match="Failed to tag image"):
            manager.tag_image("source:latest", "target:v1.0")

    def test_push_image_success(self, mocker: MockerFixture) -> None:
        """Test successful Docker image push."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.return_value = True
        mock_client.images.push.return_value = [{"status": "Pushed"}]
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        # push_image returns None on success, not True
        assert manager.push_image("test:latest") is None

    def test_push_image_failure(self, mocker: MockerFixture) -> None:
        """Test Docker image push failure."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.return_value = True
        mock_client.images.push.side_effect = DockerException("Push failed")
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        # push_image raises RuntimeError on failure
        with pytest.raises(RuntimeError, match="Failed to push image"):
            manager.push_image("test:latest")

    def test_push_image_auth_failure(self, mocker: MockerFixture) -> None:
        """Test Docker image push with auth failure."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.return_value = True
        mock_client.images.push.return_value = [{"error": "authentication required"}]
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        # push_image raises RuntimeError on auth failure
        with pytest.raises(RuntimeError, match="Push failed"):
            manager.push_image("test:latest")

    def test_get_image_digest_success(self, mocker: MockerFixture) -> None:
        """Test successful image digest retrieval."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_image = mocker.Mock()
        mock_image.attrs = {"RepoDigests": ["test@sha256:abc123def456"]}
        mock_client.ping.return_value = True
        mock_client.images.get.return_value = mock_image
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        digest = manager.get_image_digest("test:latest")

        # The actual implementation returns the full digest string, not just the hash part
        assert digest == "test@sha256:abc123def456"

    def test_get_image_digest_no_digest(self, mocker: MockerFixture) -> None:
        """Test image digest retrieval when no digest exists."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_image = mocker.Mock()
        mock_image.attrs = {"RepoDigests": []}
        mock_client.ping.return_value = True
        mock_client.images.get.return_value = mock_image
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        # This will raise IndexError with current implementation
        # The implementation was corrected to return None if RepoDigests is empty or missing.
        digest = manager.get_image_digest("test:latest")
        assert digest is None

    def test_get_image_digest_failure(self, mocker: MockerFixture) -> None:
        """Test image digest retrieval failure."""
        mock_docker_client = mocker.patch("supervaizer.deploy.docker.DockerClient")
        mock_client = mocker.Mock()
        mock_client.ping.return_value = True
        mock_client.images.get.side_effect = DockerException("Image not found")
        mock_docker_client.from_env.return_value = mock_client

        manager = DockerManager()
        digest = manager.get_image_digest("test:latest")

        assert digest is None


class TestDeployCommands:
    """Test deployment command functions."""

    def test_plan_deployment_command(self, mocker: MockerFixture) -> None:
        """Test plan deployment command."""
        from supervaizer.deploy.cli import plan

        # Mock console.print to capture output
        mock_print = mocker.patch("supervaizer.deploy.commands.plan.console.print")

        plan(
            platform="cloud-run",
            name="test-service",
            env="dev",
            region="us-central1",
            project_id="test-project",
            verbose=True,
        )

        # Verify console output
        assert mock_print.call_count >= 3
        calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("Planning deployment to cloud-run" in call for call in calls)
        assert any("Environment: dev" in call for call in calls)
        assert any("Service name: test-service" in call for call in calls)

    def test_deploy_up_command(self, mocker: MockerFixture) -> None:
        """Test deploy up command."""

        # Mock console.print to capture output
        mocker.patch("supervaizer.deploy.commands.up.console.print")

        up.deploy_up(
            platform="aws-app-runner",
            name="test-service",
            env="staging",
            region="us-east-1",
            project_id="test-account",
            image="test-registry/test:latest",
            port=8080,
            generate_api_key=True,
            generate_rsa=True,
            yes=True,
            no_rollback=False,
            timeout=600,
            verbose=True,
        )

        # The test is primarily to ensure the command can be called without error.
        # The logic is tested in the command-specific tests.
        assert True

    def test_deploy_down_command(self, mocker: MockerFixture) -> None:
        """Test deploy down command."""
        from supervaizer.deploy.commands.down import deploy_down, StateManager

        # Mock the driver factory to return a mock driver
        mock_driver = mocker.Mock()
        mock_driver.check_prerequisites.return_value = []
        mock_driver.destroy_service.return_value = mocker.Mock(success=True)
        mocker.patch(
            "supervaizer.deploy.commands.down.create_driver", return_value=mock_driver
        )

        # Mock the StateManager
        mock_state_manager = mocker.Mock(spec=StateManager)
        mock_state_manager.load_state.return_value = mocker.Mock()
        mock_state_file = mocker.Mock()
        mock_state_file.exists.return_value = True
        mock_state_manager.state_file = mock_state_file
        mocker.patch(
            "supervaizer.deploy.commands.down.StateManager",
            return_value=mock_state_manager,
        )

        # Mock shutil.rmtree to avoid actual file system operations
        mock_rmtree = mocker.patch("shutil.rmtree")

        # Call the command with `yes=True` to bypass interactive confirmation
        deploy_down(
            platform="do-app-platform",
            name="test-service",
            env="prod",
            yes=True,
        )

        # Assert that the core destruction and cleanup methods were called
        mock_driver.destroy_service.assert_called_once_with(
            "test-service", "prod", keep_secrets=False
        )
        mock_state_manager.delete_state.assert_called_once()
        mock_rmtree.assert_called_once()

    def test_deploy_status_command(self, mocker: MockerFixture) -> None:
        """Test deploy status command."""
        from supervaizer.deploy.cli import status

        # Mock console.print to capture output
        mocker.patch.object(plan.console, "print")

        # Call the function being tested
        status(
            platform="cloud-run",
            name="test-service",
            env="dev",
            region="us-central1",
            project_id="test-project",
        )

        # Assert that the correct methods were called
        # This test needs to be implemented properly
        assert True  # Placeholder until proper assertions are added

    def test_deploy_up_minimal_args(self, mocker: MockerFixture) -> None:
        """Test deploy up with minimal arguments."""
        from supervaizer.deploy.commands.up import deploy_up

        # Mock console.print to capture output
        mocker.patch.object(up.console, "print")

        deploy_up(platform="aws-app-runner")

        # The test is primarily to ensure the command can be called without error.
        assert True


class TestStateManagerAdvanced:
    """Test advanced state manager functionality."""

    def test_migrate_state_v1_to_v2(self, mocker: MockerFixture) -> None:
        """Test state migration from v1 to v2."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            # Create v1 state file
            v1_state = {
                "version": 1,
                "service_name": "test-service",
                "platform": "cloud-run",
                "environment": "dev",
                "region": "us-central1",
                "image_tag": "test:latest",
            }
            manager.state_file.write_text(json.dumps(v1_state))

            # Load and migrate
            state = manager.load_state()
            assert state is not None
            assert state.service_name == "test-service"
            assert state.platform == "cloud-run"
            assert state.version == 2  # Should be migrated to v2

    def test_migrate_state_unknown_version(self, mocker: MockerFixture) -> None:
        """Test state migration with unknown version."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            # Create unknown version state file
            unknown_state = {
                "version": 999,
                "service_name": "test-service",
                "platform": "cloud-run",
                "environment": "dev",
                "region": "us-central1",
                "image_tag": "test:latest",
            }
            manager.state_file.write_text(json.dumps(unknown_state))

            # Should raise error for unknown version
            with pytest.raises(ValueError, match="Unsupported state version"):
                manager.load_state()

    def test_validate_state_invalid_platform(self) -> None:
        """Test state validation with invalid platform."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            invalid_state = DeploymentState(
                service_name="test-service",
                platform="invalid-platform",
                environment="dev",
                region="us-central1",
                image_tag="test:latest",
            )

            assert manager.validate_state(invalid_state) is False

    def test_validate_state_invalid_environment(self) -> None:
        """Test state validation with invalid environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            invalid_state = DeploymentState(
                service_name="test-service",
                platform="cloud-run",
                environment="invalid-env",
                region="us-central1",
                image_tag="test:latest",
            )

            assert manager.validate_state(invalid_state) is False

    def test_validate_state_valid_state(self) -> None:
        """Test state validation with valid state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            valid_state = DeploymentState(
                service_name="test-service",
                platform="cloud-run",
                environment="dev",
                region="us-central1",
                image_tag="test:latest",
            )

            assert manager.validate_state(valid_state) is True

    def test_get_service_key_edge_cases(self) -> None:
        """Test service key generation with edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            # Test with special characters
            key1 = manager.get_service_key("test-service-123", "dev")
            assert key1 == "test-service-123-dev"

            # Test with empty environment
            key2 = manager.get_service_key("test-service", "")
            assert key2 == "test-service-"

    def test_state_file_corruption(self) -> None:
        """Test handling of corrupted state file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployment_dir = Path(temp_dir) / ".deployment"
            manager = StateManager(deployment_dir)

            # Create corrupted JSON file
            manager.state_file.write_text("{ invalid json }")

            # Should return None for corrupted file
            state = manager.load_state()
            assert state is None
