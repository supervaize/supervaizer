# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Tests for deployment commands.
"""

from pytest_mock import MockerFixture
from pathlib import Path

from supervaizer.deploy.commands.plan import plan_deployment
from supervaizer.deploy.commands.up import deploy_up
from supervaizer.deploy.commands.down import deploy_down
from supervaizer.deploy.commands.status import deploy_status
from supervaizer.deploy.drivers.base import (
    DeploymentPlan,
    DeploymentResult,
    ResourceAction,
    ActionType,
    ResourceType,
)


class TestPlanCommand:
    """Test plan command."""

    def test_plan_deployment_success(self, mocker: MockerFixture):
        """Test successful planning."""
        mocker.patch(
            "supervaizer.deploy.commands.plan.get_supported_platforms",
            return_value=["cloud-run", "aws-app-runner", "do-app-platform"],
        )
        mock_driver = mocker.Mock()
        mock_driver.check_prerequisites.return_value = []

        mock_plan = DeploymentPlan(
            platform="cloud-run",
            service_name="test-service",
            environment="dev",
            region="us-central1",
            project_id="test-project",
            actions=[
                ResourceAction(
                    resource_type=ResourceType.SERVICE,
                    action_type=ActionType.CREATE,
                    resource_name="test-service-dev",
                    description="Create new service",
                )
            ],
            target_image="test-service-dev:abc123",
            target_env_vars={"SUPERVAIZER_ENVIRONMENT": "dev"},
            target_secrets={"test-service-dev-api-key": "placeholder"},
        )
        mock_driver.plan_deployment.return_value = mock_plan

        mocker.patch(
            "supervaizer.deploy.commands.plan.create_driver", return_value=mock_driver
        )

        # Should not raise any exceptions
        plan_deployment(
            "cloud-run", "test-service", "dev", "us-central1", "test-project"
        )

        mock_driver.check_prerequisites.assert_called_once()
        mock_driver.plan_deployment.assert_called_once()

    def test_plan_deployment_invalid_platform(self, mocker: MockerFixture):
        """Test planning with invalid platform."""
        mocker.patch(
            "supervaizer.deploy.commands.plan.get_supported_platforms",
            return_value=["cloud-run", "aws-app-runner", "do-app-platform"],
        )

        # Should not raise exceptions, just print error
        plan_deployment("invalid-platform", "test-service", "dev")

    def test_plan_deployment_prerequisites_failed(self, mocker: MockerFixture):
        """Test planning when prerequisites fail."""
        mocker.patch(
            "supervaizer.deploy.commands.plan.get_supported_platforms",
            return_value=["cloud-run"],
        )

        mock_driver = mocker.Mock()
        mock_driver.check_prerequisites.return_value = ["gcloud CLI not found"]
        mocker.patch(
            "supervaizer.deploy.commands.plan.create_driver", return_value=mock_driver
        )

        # Should not raise exceptions, just print prerequisites
        plan_deployment(
            "cloud-run", "test-service", "dev", "us-central1", "test-project"
        )


class TestUpCommand:
    """Test up command."""

    def test_deploy_up_success(self, mocker: MockerFixture):
        """Test successful deployment."""
        mocker.patch(
            "supervaizer.deploy.commands.up.get_supported_platforms",
            return_value=["cloud-run"],
        )
        mocker.patch(
            "supervaizer.deploy.commands.up.ensure_docker_running",
            return_value=True,
        )

        mock_deployment_dir = Path("/tmp/.deployment")
        mocker.patch(
            "supervaizer.deploy.commands.up.create_deployment_directory",
            return_value=mock_deployment_dir,
        )

        mock_state = mocker.Mock()
        mocker.patch(
            "supervaizer.deploy.commands.up.StateManager", return_value=mock_state
        )

        mock_docker = mocker.Mock()
        mocker.patch(
            "supervaizer.deploy.commands.up.DockerManager", return_value=mock_docker
        )

        mock_driver = mocker.Mock()
        mock_driver.check_prerequisites.return_value = []

        mock_result = DeploymentResult(
            success=True,
            service_url="https://test-service.example.com",
            service_id="test-service-id",
            status="running",
            health_status="healthy",
            deployment_time=30.5,
        )
        mock_driver.deploy_service.return_value = mock_result

        mocker.patch(
            "supervaizer.deploy.commands.up.create_driver", return_value=mock_driver
        )

        # Should not raise any exceptions
        deploy_up("cloud-run", "test-service", "dev", "us-central1", "test-project")

        mock_driver.check_prerequisites.assert_called_once()
        mock_driver.deploy_service.assert_called_once()
        mock_state.update_state.assert_called_once()

    def test_deploy_up_invalid_platform(self, mocker: MockerFixture):
        """Test deployment with invalid platform."""
        mocker.patch(
            "supervaizer.deploy.commands.up.get_supported_platforms",
            return_value=["cloud-run"],
        )

        # Should not raise exceptions, just print error
        deploy_up("invalid-platform", "test-service", "dev")

    def test_deploy_up_docker_not_running(self, mocker: MockerFixture):
        """Test deployment when Docker is not running."""
        mocker.patch(
            "supervaizer.deploy.commands.up.get_supported_platforms",
            return_value=["cloud-run"],
        )
        mocker.patch(
            "supervaizer.deploy.commands.up.ensure_docker_running",
            return_value=False,
        )

        # Should not raise exceptions, just print error
        deploy_up("cloud-run", "test-service", "dev")


class TestDownCommand:
    """Test down command."""

    def test_deploy_down_success(self, mocker: MockerFixture):
        """Test successful destruction."""
        mocker.patch(
            "supervaizer.deploy.commands.down.get_supported_platforms",
            return_value=["cloud-run"],
        )

        mock_state = mocker.Mock()
        mock_state.load_state.return_value = mocker.Mock(
            service_url="https://test.example.com"
        )
        mocker.patch(
            "supervaizer.deploy.commands.down.StateManager", return_value=mock_state
        )

        mock_driver = mocker.Mock()
        mock_driver.check_prerequisites.return_value = []

        mock_result = DeploymentResult(
            success=True,
            status="deleted",
        )
        mock_driver.destroy_service.return_value = mock_result

        mocker.patch(
            "supervaizer.deploy.commands.down.create_driver", return_value=mock_driver
        )

        # Should not raise any exceptions
        deploy_down(
            "cloud-run", "test-service", "dev", "us-central1", "test-project", yes=True
        )

        mock_driver.check_prerequisites.assert_called_once()
        mock_driver.destroy_service.assert_called_once()

    def test_deploy_down_invalid_platform(self, mocker: MockerFixture):
        """Test destruction with invalid platform."""
        mocker.patch(
            "supervaizer.deploy.commands.down.get_supported_platforms",
            return_value=["cloud-run"],
        )

        # Should not raise exceptions, just print error
        deploy_down("invalid-platform", "test-service", "dev")


class TestStatusCommand:
    """Test status command."""

    def test_deploy_status_success(self, mocker: MockerFixture):
        """Test successful status check."""
        mocker.patch(
            "supervaizer.deploy.commands.status.get_supported_platforms",
            return_value=["cloud-run"],
        )

        mock_state = mocker.Mock()
        mock_state.load_state.return_value = mocker.Mock(
            service_name="test-service",
            platform="cloud-run",
            environment="dev",
            service_url="https://test.example.com",
            status="running",
        )
        mocker.patch(
            "supervaizer.deploy.commands.status.StateManager", return_value=mock_state
        )

        mock_driver = mocker.Mock()
        mock_driver.check_prerequisites.return_value = []

        mock_result = DeploymentResult(
            success=True,
            service_url="https://test.example.com",
            service_id="test-service-id",
            status="running",
            health_status="healthy",
        )
        mock_driver.get_service_status.return_value = mock_result

        mocker.patch(
            "supervaizer.deploy.commands.status.create_driver", return_value=mock_driver
        )

        # Should not raise any exceptions
        deploy_status("cloud-run", "test-service", "dev", "us-central1", "test-project")

        mock_driver.check_prerequisites.assert_called_once()
        mock_driver.get_service_status.assert_called_once()

    def test_deploy_status_invalid_platform(self, mocker: MockerFixture):
        """Test status check with invalid platform."""
        mocker.patch(
            "supervaizer.deploy.commands.status.get_supported_platforms",
            return_value=["cloud-run"],
        )

        # Should not raise exceptions, just print error
        deploy_status("invalid-platform", "test-service", "dev")
