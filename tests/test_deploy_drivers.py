# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Tests for deployment drivers.
"""

import pytest
from pytest_mock import MockerFixture

from supervaizer.deploy.drivers.base import (
    ActionType,
    BaseDriver,
)
from supervaizer.deploy.drivers.cloud_run import CloudRunDriver
from supervaizer.deploy.drivers.aws_app_runner import AWSAppRunnerDriver
from supervaizer.deploy.drivers.do_app_platform import DOAppPlatformDriver
from supervaizer.deploy.driver_factory import create_driver, get_supported_platforms


class TestBaseDriver:
    """Test base driver functionality."""

    def test_get_service_key(self, mocker: MockerFixture):
        """Test service key generation."""
        driver = mocker.Mock(spec=BaseDriver)
        driver.get_service_key = BaseDriver.get_service_key.__get__(driver)

        key = driver.get_service_key("test-service", "dev")
        assert key == "test-service-dev"

    def test_validate_configuration(self, mocker: MockerFixture):
        """Test configuration validation."""
        driver = mocker.Mock(spec=BaseDriver)
        driver.validate_configuration = BaseDriver.validate_configuration.__get__(
            driver
        )

        errors = driver.validate_configuration()
        assert len(errors) == 1
        assert "Region is required" in errors[0]


class TestCloudRunDriver:
    """Test Cloud Run driver."""

    @pytest.fixture
    def driver(self, mocker: MockerFixture):
        """Create Cloud Run driver instance."""
        mocker.patch("supervaizer.deploy.drivers.cloud_run.run_v2.ServicesClient")
        mocker.patch(
            "supervaizer.deploy.drivers.cloud_run.secretmanager.SecretManagerServiceClient"
        )
        mocker.patch(
            "supervaizer.deploy.drivers.cloud_run.artifactregistry_v1.ArtifactRegistryClient"
        )
        return CloudRunDriver("us-central1", "test-project")

    def test_init(self, driver):
        """Test driver initialization."""
        assert driver.region == "us-central1"
        assert driver.project_id == "test-project"
        assert driver.service_parent == "projects/test-project/locations/us-central1"

    def test_get_service_key(self, driver):
        """Test service key generation."""
        key = driver.get_service_key("test-service", "dev")
        assert key == "test-service-dev"

    def test_plan_deployment_new_service(self, driver, mocker: MockerFixture):
        """Test planning deployment for new service."""
        mocker.patch.object(
            driver.run_client, "get_service", side_effect=Exception("Not found")
        )
        plan = driver.plan_deployment(
            service_name="test-service",
            environment="dev",
            image_tag="test-image:latest",
        )

        assert plan.platform == "cloud-run"
        assert plan.service_name == "test-service"
        assert plan.environment == "dev"
        assert plan.target_image == "test-image:latest"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == ActionType.CREATE

    def test_plan_deployment_existing_service(self, driver, mocker: MockerFixture):
        """Test planning deployment for existing service."""
        mock_service = mocker.Mock()
        mock_service.template.containers = [mocker.Mock()]
        mock_service.template.containers[0].image = "old-image:latest"
        mock_service.uri = "https://test-service-dev.example.com"

        mocker.patch.object(driver.run_client, "get_service", return_value=mock_service)
        plan = driver.plan_deployment(
            service_name="test-service",
            environment="dev",
            image_tag="new-image:latest",
        )

        assert plan.current_image == "old-image:latest"
        assert plan.current_url == "https://test-service-dev.example.com"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == ActionType.UPDATE

    def test_check_prerequisites(self, driver, mocker: MockerFixture):
        """Test prerequisite checking."""
        mocker.patch(
            "subprocess.run",
            return_value=mocker.Mock(stdout="gcloud version", returncode=0),
        )

        errors = driver.check_prerequisites()
        # Should have no errors with mocked successful commands
        assert len(errors) == 0


class TestAWSAppRunnerDriver:
    """Test AWS App Runner driver."""

    @pytest.fixture
    def driver(self, mocker: MockerFixture):
        """Create AWS App Runner driver instance."""
        mocker.patch(
            "supervaizer.deploy.drivers.aws_app_runner.boto3.client",
            return_value=mocker.Mock(),
        )
        return AWSAppRunnerDriver("us-east-1", "test-account")

    def test_init(self, driver):
        """Test driver initialization."""
        assert driver.region == "us-east-1"
        assert driver.project_id == "test-account"

    def test_get_service_key(self, driver):
        """Test service key generation."""
        key = driver.get_service_key("test-service", "dev")
        assert key == "test-service-dev"

    def test_plan_deployment_new_service(self, driver, mocker: MockerFixture):
        """Test planning deployment for new service."""
        mocker.patch.object(
            driver.apprunner_client,
            "describe_service",
            side_effect=Exception("ResourceNotFoundException"),
        )
        plan = driver.plan_deployment(
            service_name="test-service",
            environment="dev",
            image_tag="test-image:latest",
        )

        assert plan.platform == "aws-app-runner"
        assert plan.service_name == "test-service"
        assert plan.environment == "dev"
        assert plan.target_image == "test-image:latest"
        # Should have CREATE action for service and registry
        assert len(plan.actions) >= 1
        create_actions = [a for a in plan.actions if a.action_type == ActionType.CREATE]
        assert len(create_actions) >= 1


class TestDOAppPlatformDriver:
    """Test DigitalOcean App Platform driver."""

    @pytest.fixture
    def driver(self):
        """Create DO App Platform driver instance."""
        return DOAppPlatformDriver("nyc3", "test-project")

    def test_init(self, driver):
        """Test driver initialization."""
        assert driver.region == "nyc3"
        assert driver.project_id == "test-project"

    def test_get_service_key(self, driver):
        """Test service key generation."""
        key = driver.get_service_key("test-service", "dev")
        assert key == "test-service-dev"

    def test_plan_deployment_new_app(self, driver, mocker: MockerFixture):
        """Test planning deployment for new app."""
        import subprocess

        mocker.patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "doctl")
        )
        plan = driver.plan_deployment(
            service_name="test-service",
            environment="dev",
            image_tag="test-image:latest",
        )

        assert plan.platform == "do-app-platform"
        assert plan.service_name == "test-service"
        assert plan.environment == "dev"
        assert plan.target_image == "test-image:latest"
        # Should have CREATE actions
        create_actions = [a for a in plan.actions if a.action_type == ActionType.CREATE]
        assert len(create_actions) >= 1


class TestDriverFactory:
    """Test driver factory."""

    def test_get_supported_platforms(self):
        """Test getting supported platforms."""
        platforms = get_supported_platforms()
        assert "cloud-run" in platforms
        assert "aws-app-runner" in platforms
        assert "do-app-platform" in platforms

    def test_create_cloud_run_driver(self, mocker: MockerFixture):
        """Test creating Cloud Run driver."""
        mocker.patch("supervaizer.deploy.drivers.cloud_run.run_v2.ServicesClient")
        mocker.patch(
            "supervaizer.deploy.drivers.cloud_run.secretmanager.SecretManagerServiceClient"
        )
        mocker.patch(
            "supervaizer.deploy.drivers.cloud_run.artifactregistry_v1.ArtifactRegistryClient"
        )
        driver = create_driver("cloud-run", "us-central1", "test-project")
        assert isinstance(driver, CloudRunDriver)
        assert driver.region == "us-central1"
        assert driver.project_id == "test-project"

    def test_create_aws_app_runner_driver(self, mocker: MockerFixture):
        """Test creating AWS App Runner driver."""
        mocker.patch("supervaizer.deploy.drivers.aws_app_runner.boto3.client")
        driver = create_driver("aws-app-runner", "us-east-1", "test-account")
        assert isinstance(driver, AWSAppRunnerDriver)
        assert driver.region == "us-east-1"
        assert driver.project_id == "test-account"

    def test_create_do_app_platform_driver(self):
        """Test creating DO App Platform driver."""
        driver = create_driver("do-app-platform", "nyc3", "test-project")
        assert isinstance(driver, DOAppPlatformDriver)
        assert driver.region == "nyc3"
        assert driver.project_id == "test-project"

    def test_create_driver_invalid_platform(self):
        """Test creating driver with invalid platform."""
        with pytest.raises(ValueError, match="Unsupported platform"):
            create_driver("invalid-platform", "us-central1", "test-project")

    def test_create_cloud_run_driver_missing_project_id(self):
        """Test creating Cloud Run driver without project ID."""
        with pytest.raises(ValueError, match="project_id is required"):
            create_driver("cloud-run", "us-central1", None)
