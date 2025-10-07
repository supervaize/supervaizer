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
from supervaizer.deploy.drivers.aws_app_runner import AWSAppRunnerDriver, ClientError

from supervaizer.deploy.drivers.do_app_platform import DOAppPlatformDriver
from supervaizer.deploy.driver_factory import create_driver, get_supported_platforms


class TestBaseDriver:
    """Test base driver functionality."""

    def test_get_service_key(self, mocker: MockerFixture):
        """Test service key generation."""
        driver = mocker.Mock(spec=BaseDriver)
        driver.region = "us-east-1"  # Add region to mock
        driver.get_service_key = BaseDriver.get_service_key.__get__(driver)

        key = driver.get_service_key("test-service", "dev")
        assert key == "test-service-dev"

    def test_validate_configuration(self, mocker: MockerFixture):
        """Test configuration validation."""
        driver = mocker.Mock(spec=BaseDriver)
        driver.region = None  # Set region to None to trigger validation error
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
        # Mock the availability of Google Cloud libraries
        mocker.patch(
            "supervaizer.deploy.drivers.cloud_run.GOOGLE_CLOUD_AVAILABLE", True
        )

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
        # Import NotFound from the driver module to ensure the correct exception type is used
        from supervaizer.deploy.drivers.cloud_run import NotFound

        mocker.patch.object(
            driver.run_client, "get_service", side_effect=NotFound("Not found")
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

        def mock_gcloud_run(*args, **kwargs):
            command = args[0]
            if "version" in command:
                return mocker.Mock(stdout="Google Cloud SDK 450.0.0", returncode=0)
            if "auth" in command:
                return mocker.Mock(stdout="test@example.com", returncode=0)
            if "config" in command:
                return mocker.Mock(stdout="test-project", returncode=0)
            if "services" in command and "run.googleapis.com" in command[-1]:
                return mocker.Mock(stdout="run.googleapis.com", returncode=0)
            if "services" in command and "secretmanager.googleapis.com" in command[-1]:
                return mocker.Mock(stdout="secretmanager.googleapis.com", returncode=0)
            if (
                "services" in command
                and "artifactregistry.googleapis.com" in command[-1]
            ):
                return mocker.Mock(
                    stdout="artifactregistry.googleapis.com", returncode=0
                )
            return mocker.Mock(stdout="", returncode=1)

        mocker.patch("subprocess.run", side_effect=mock_gcloud_run)

        errors = driver.check_prerequisites()
        assert len(errors) == 0


class TestAWSAppRunnerDriver:
    """Test AWS App Runner driver."""

    @pytest.fixture
    def driver(self, mocker: MockerFixture):
        """Create AWS App Runner driver instance."""
        # Mock boto3 clients
        mock_apprunner = mocker.Mock()
        mock_ecr = mocker.Mock()
        mock_secrets = mocker.Mock()
        mock_sts = mocker.Mock()

        # Mock STS get_caller_identity response
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

        def mock_client(service_name, **kwargs):
            if service_name == "apprunner":
                return mock_apprunner
            elif service_name == "ecr":
                return mock_ecr
            elif service_name == "secretsmanager":
                return mock_secrets
            elif service_name == "sts":
                return mock_sts
            return mocker.Mock()

        mocker.patch(
            "supervaizer.deploy.drivers.aws_app_runner.boto3.client",
            side_effect=mock_client,
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
        # Mock botocore exceptions
        error_response = {"Error": {"Code": "ResourceNotFoundException"}}
        mock_exception = ClientError(error_response, "DescribeService")

        mocker.patch.object(
            driver.apprunner_client,
            "describe_service",
            side_effect=mock_exception,
        )
        repo_error_response = {"Error": {"Code": "RepositoryNotFoundException"}}
        mocker.patch.object(
            driver.ecr_client,
            "describe_repositories",
            side_effect=ClientError(repo_error_response, "DescribeRepositories"),
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
        # This driver uses subprocess, which is generally available.
        # No complex mocking needed for initialization.
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
        # Mock the availability of Google Cloud libraries
        mocker.patch(
            "supervaizer.deploy.drivers.cloud_run.GOOGLE_CLOUD_AVAILABLE", True
        )

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
