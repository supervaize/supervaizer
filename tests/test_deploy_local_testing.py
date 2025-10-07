# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Tests for Local Docker Testing

This module tests the local Docker testing functionality.
"""

import subprocess

import httpx
import pytest
from pytest_mock import MockerFixture

from supervaizer.deploy.commands.local import (
    local_docker,
    _check_docker_available,
    _generate_test_secrets,
    _start_docker_compose,
    _wait_for_service,
    _run_health_checks,
    _display_health_results,
    _display_service_info,
    _show_service_logs,
    _cleanup_test_resources,
)


class TestLocalTesting:
    """Test local Docker testing functionality."""

    def test_check_docker_available_success(self, mocker: MockerFixture):
        """Test successful Docker availability check."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        result = _check_docker_available()

        assert result is True
        mock_run.assert_called_once_with(
            ["docker", "version"], capture_output=True, text=True, timeout=10
        )

    def test_check_docker_available_failure(self, mocker: MockerFixture):
        """Test Docker availability check failure."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1

        result = _check_docker_available()

        assert result is False

    def test_check_docker_available_timeout(self, mocker: MockerFixture):
        """Test Docker availability check timeout."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired("docker", 10)

        result = _check_docker_available()

        assert result is False

    def test_generate_test_secrets_with_api_key(self, mocker: MockerFixture):
        """Test secret generation with API key."""
        mock_token = mocker.patch("secrets.token_urlsafe")
        mock_token.return_value = "test-api-key-123"

        secrets = _generate_test_secrets(generate_api_key=True, generate_rsa=False)

        assert secrets["api_key"] == "test-api-key-123"
        assert secrets["rsa_private_key"] == "test-rsa-key-local"

    def test_generate_test_secrets_with_rsa(self, mocker: MockerFixture):
        """Test secret generation with RSA key."""
        mock_rsa = mocker.patch(
            "cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key"
        )
        mock_private_key = mocker.Mock()
        mock_rsa.return_value = mock_private_key

        mock_private_key.private_bytes.return_value = b"test-rsa-key"

        secrets = _generate_test_secrets(generate_api_key=False, generate_rsa=True)

        assert secrets["api_key"] == "test-api-key-local"
        assert secrets["rsa_private_key"] == "test-rsa-key"

    def test_generate_test_secrets_default(self):
        """Test default secret generation."""
        secrets = _generate_test_secrets(generate_api_key=False, generate_rsa=False)

        assert secrets["api_key"] == "test-api-key-local"
        assert secrets["rsa_private_key"] == "test-rsa-key-local"

    def test_start_docker_compose_success(self, mocker: MockerFixture):
        """Test successful Docker Compose start."""
        mock_path = mocker.patch("pathlib.Path.exists")
        mock_path.return_value = True

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        secrets = {"api_key": "test-key", "rsa_private_key": "test-rsa"}
        _start_docker_compose("test-service", 8000, secrets, False)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == [
            "docker-compose",
            "-f",
            ".deployment/docker-compose.yml",
            "up",
            "-d",
        ]

    def test_start_docker_compose_failure(self, mocker: MockerFixture):
        """Test Docker Compose start failure."""
        mock_path = mocker.patch("pathlib.Path.exists")
        mock_path.return_value = True

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Docker Compose error"

        secrets = {"api_key": "test-key", "rsa_private_key": "test-rsa"}

        with pytest.raises(RuntimeError, match="Failed to start Docker Compose"):
            _start_docker_compose("test-service", 8000, secrets, False)

    def test_start_docker_compose_missing_file(self, mocker: MockerFixture):
        """Test Docker Compose start with missing file."""
        mock_path = mocker.patch("pathlib.Path.exists")
        mock_path.return_value = False

        secrets = {"api_key": "test-key", "rsa_private_key": "test-rsa"}

        with pytest.raises(RuntimeError, match="Docker Compose file not found"):
            _start_docker_compose("test-service", 8000, secrets, False)

    def test_wait_for_service_success(self, mocker: MockerFixture):
        """Test successful service wait."""
        mock_httpx = mocker.patch("supervaizer.deploy.commands.local.httpx.get")
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_httpx.return_value = mock_response

        result = _wait_for_service("http://localhost:8000", 10)

        assert result is True

    def test_wait_for_service_timeout(self, mocker: MockerFixture):
        """Test service wait timeout."""
        mock_httpx = mocker.patch("supervaizer.deploy.commands.local.httpx.get")
        mock_httpx.side_effect = httpx.RequestError("Connection failed")

        result = _wait_for_service("http://localhost:8000", 1)

        assert result is False

    def test_run_health_checks_success(self, mocker: MockerFixture):
        """Test successful health checks."""
        mock_httpx = mocker.patch("supervaizer.deploy.commands.local.httpx.get")

        # Mock health endpoint response
        health_response = mocker.Mock()
        health_response.status_code = 200
        health_response.elapsed.total_seconds.return_value = 0.1

        # Mock API docs response
        docs_response = mocker.Mock()
        docs_response.status_code = 200

        # Mock the httpx.get calls - first call for health, second for docs
        mock_httpx.side_effect = [health_response, docs_response]

        results = _run_health_checks("http://localhost:8000", None)  # No API key

        assert results["health_endpoint"]["success"] is True
        assert results["api_docs"]["success"] is True
        # Should not have api_health_endpoint when no API key provided
        assert "api_health_endpoint" not in results

    def test_run_health_checks_with_api_key(self, mocker: MockerFixture):
        """Test health checks with API key."""
        mock_httpx = mocker.patch("supervaizer.deploy.commands.local.httpx.get")

        # Mock all responses
        health_response = mocker.Mock()
        health_response.status_code = 200
        health_response.elapsed.total_seconds.return_value = 0.1

        api_response = mocker.Mock()
        api_response.status_code = 200
        api_response.elapsed.total_seconds.return_value = 0.2

        docs_response = mocker.Mock()
        docs_response.status_code = 200

        mock_httpx.side_effect = [health_response, api_response, docs_response]

        results = _run_health_checks("http://localhost:8000", "test-api-key")

        assert results["health_endpoint"]["success"] is True
        assert results["api_health_endpoint"]["success"] is True
        assert results["api_docs"]["success"] is True

    def test_display_health_results(self, mocker: MockerFixture):
        """Test health results display."""
        mock_console = mocker.patch("supervaizer.deploy.commands.local.console")

        results = {
            "health_endpoint": {"success": True, "status": 200, "response_time": 0.1},
            "api_docs": {"success": False, "status": 404, "error": "Not found"},
        }

        _display_health_results(results)

        # Verify console.print was called (table creation)
        assert mock_console.print.called

    def test_display_service_info(self, mocker: MockerFixture):
        """Test service info display."""
        mock_console = mocker.patch("supervaizer.deploy.commands.local.console")

        secrets = {"api_key": "test-api-key-123456789"}
        _display_service_info("test-service", "http://localhost:8000", 8000, secrets)

        # Verify console.print was called (table creation)
        assert mock_console.print.called

    def test_show_service_logs(self, mocker: MockerFixture):
        """Test service logs display."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = "Service logs here"
        mock_run.return_value.stderr = ""

        _show_service_logs("test-service")

        mock_run.assert_called_once_with(
            [
                "docker-compose",
                "-f",
                ".deployment/docker-compose.yml",
                "logs",
                "--tail=50",
            ],
            capture_output=True,
            text=True,
        )

    def test_cleanup_test_resources(self, mocker: MockerFixture):
        """Test test resources cleanup."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        _cleanup_test_resources("test-service")

        mock_run.assert_called_once_with(
            ["docker-compose", "-f", ".deployment/docker-compose.yml", "down"],
            capture_output=True,
            text=True,
        )

    def test_cleanup_test_resources_failure(self, mocker: MockerFixture):
        """Test test resources cleanup failure."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = Exception("Cleanup failed")

        # Should not raise exception
        _cleanup_test_resources("test-service")

    def test_test_local_success(
        self,
        mocker: MockerFixture,
    ):
        """Test successful local testing."""
        # Setup mocks
        mock_check_docker = mocker.patch(
            "supervaizer.deploy.commands.local._check_docker_available"
        )
        mock_docker_manager = mocker.patch(
            "supervaizer.deploy.commands.local.DockerManager"
        )
        mock_generate_secrets = mocker.patch(
            "supervaizer.deploy.commands.local._generate_test_secrets"
        )
        mock_start_compose = mocker.patch(
            "supervaizer.deploy.commands.local._start_docker_compose"
        )
        mock_wait_service = mocker.patch(
            "supervaizer.deploy.commands.local._wait_for_service"
        )
        mock_run_health = mocker.patch(
            "supervaizer.deploy.commands.local._run_health_checks"
        )
        mock_display_health = mocker.patch(
            "supervaizer.deploy.commands.local._display_health_results"
        )
        mock_display_info = mocker.patch(
            "supervaizer.deploy.commands.local._display_service_info"
        )

        mock_check_docker.return_value = True
        mock_docker_instance = mocker.Mock()
        mock_docker_manager.return_value = mock_docker_instance
        mock_generate_secrets.return_value = {
            "api_key": "test-key",
            "rsa_private_key": "test-rsa",
        }
        mock_wait_service.return_value = True
        mock_run_health.return_value = {"health_endpoint": {"success": True}}

        # Run test
        local_docker("test-service", "dev", 8000, True, False, 30, False)

        # Verify calls
        mock_check_docker.assert_called_once()
        mock_docker_instance.generate_dockerfile.assert_called_once()
        mock_docker_instance.generate_dockerignore.assert_called_once()
        mock_docker_instance.generate_docker_compose.assert_called_once_with(port=8000)
        mock_docker_instance.build_image.assert_called_once()
        mock_generate_secrets.assert_called_once_with(True, False)
        mock_start_compose.assert_called_once()
        mock_wait_service.assert_called_once()
        mock_run_health.assert_called_once()
        mock_display_health.assert_called_once()
        mock_display_info.assert_called_once()

    def test_test_local_docker_unavailable(self, mocker: MockerFixture):
        """Test local testing with Docker unavailable."""
        mock_check_docker = mocker.patch(
            "supervaizer.deploy.commands.local._check_docker_available"
        )
        mock_check_docker.return_value = False

        with pytest.raises(RuntimeError, match="Docker not available"):
            local_docker("test-service", "dev", 8000, True, False, 30, False)

    def test_test_local_service_timeout(
        self,
        mocker: MockerFixture,
    ):
        """Test local testing with service timeout."""
        # Setup mocks
        mock_check_docker = mocker.patch(
            "supervaizer.deploy.commands.local._check_docker_available"
        )
        mock_docker_manager = mocker.patch(
            "supervaizer.deploy.commands.local.DockerManager"
        )
        mock_generate_secrets = mocker.patch(
            "supervaizer.deploy.commands.local._generate_test_secrets"
        )
        mock_start_compose = mocker.patch(
            "supervaizer.deploy.commands.local._start_docker_compose"
        )
        mock_wait_service = mocker.patch(
            "supervaizer.deploy.commands.local._wait_for_service"
        )
        mock_cleanup = mocker.patch(
            "supervaizer.deploy.commands.local._cleanup_test_resources"
        )

        mock_check_docker.return_value = True
        mock_docker_instance = mocker.Mock()
        mock_docker_manager.return_value = mock_docker_instance
        mock_generate_secrets.return_value = {
            "api_key": "test-key",
            "rsa_private_key": "test-rsa",
        }
        mock_wait_service.return_value = False

        with pytest.raises(RuntimeError, match="Service startup timeout"):
            local_docker("test-service", "dev", 8000, True, False, 30, False)

        mock_cleanup.assert_called_once()
