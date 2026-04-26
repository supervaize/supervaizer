# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import httpx
import pytest
from pytest_mock import MockerFixture
from unittest.mock import AsyncMock, MagicMock

from supervaizer.deploy.health import (
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    HealthVerifier,
    display_health_results,
    verify_service_health,
)


def mock_sync_health_client(
    mocker: MockerFixture,
    *responses: httpx.Response | Exception,
) -> tuple[MagicMock, MagicMock]:
    client_context = mocker.MagicMock()
    client = mocker.MagicMock()
    client.get.side_effect = responses
    client_context.__enter__.return_value = client

    client_class = mocker.patch(
        "supervaizer.deploy.health.httpx.Client",
        return_value=client_context,
    )
    return client_class, client


def mock_async_health_client(
    mocker: MockerFixture,
    *responses: httpx.Response | Exception,
) -> tuple[MagicMock, AsyncMock]:
    client_context = mocker.MagicMock()
    client = mocker.AsyncMock()
    client.get.side_effect = responses
    client_context.__aenter__ = mocker.AsyncMock(return_value=client)
    client_context.__aexit__ = mocker.AsyncMock(return_value=None)

    client_class = mocker.patch(
        "supervaizer.deploy.health.httpx.AsyncClient",
        return_value=client_context,
    )
    return client_class, client


class TestHealthCheckConfig:
    def test_default_endpoint_is_created(self) -> None:
        config = HealthCheckConfig()

        assert config.endpoints == ["/.well-known/health"]

    def test_result_timestamp_is_initialized(self) -> None:
        result = HealthCheckResult(status=HealthStatus.UNKNOWN, response_time=0.0)

        assert result.timestamp > 0


class TestHealthVerifier:
    def test_verify_health_success(self, mocker: MockerFixture) -> None:
        client_class, client = mock_sync_health_client(mocker, httpx.Response(200))

        result = HealthVerifier().verify_health("https://service.test/", "api-key")

        assert result.status == HealthStatus.HEALTHY
        assert result.status_code == 200
        assert result.endpoint == "/.well-known/health"
        client_class.assert_called_once_with(timeout=60)
        client.get.assert_called_once_with(
            "https://service.test/.well-known/health",
            headers={"X-API-Key": "api-key"},
        )

    def test_verify_health_retries_until_success(self, mocker: MockerFixture) -> None:
        mocker.patch("supervaizer.deploy.health.time.sleep")
        _, client = mock_sync_health_client(
            mocker,
            httpx.Response(503),
            httpx.Response(200),
        )
        config = HealthCheckConfig(max_retries=2, base_delay=0)

        result = HealthVerifier(config).verify_health("https://service.test")

        assert result.status == HealthStatus.HEALTHY
        assert client.get.call_count == 2

    def test_verify_health_returns_unhealthy_for_bad_status(
        self,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("supervaizer.deploy.health.time.sleep")
        mock_sync_health_client(mocker, httpx.Response(500))
        config = HealthCheckConfig(max_retries=1)

        result = HealthVerifier(config).verify_health("https://service.test")

        assert result.status == HealthStatus.UNHEALTHY
        assert result.error_message == "Endpoint /.well-known/health returned 500"

    def test_verify_health_handles_no_endpoints(self, mocker: MockerFixture) -> None:
        mocker.patch("supervaizer.deploy.health.time.sleep")
        config = HealthCheckConfig(max_retries=1, endpoints=[])

        result = HealthVerifier(config).verify_health("https://service.test")

        assert result.status == HealthStatus.UNHEALTHY
        assert result.error_message == "No endpoints configured"
        assert result.endpoint is None

    def test_verify_health_handles_request_errors(
        self,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("supervaizer.deploy.health.time.sleep")
        mock_sync_health_client(mocker, httpx.RequestError("connection failed"))
        config = HealthCheckConfig(max_retries=1)

        result = HealthVerifier(config).verify_health("https://service.test")

        assert result.status == HealthStatus.UNHEALTHY
        assert result.error_message == "Request error: connection failed"

    def test_verify_health_handles_timeouts(self, mocker: MockerFixture) -> None:
        mocker.patch("supervaizer.deploy.health.time.sleep")
        mock_sync_health_client(mocker, httpx.TimeoutException("timeout"))
        config = HealthCheckConfig(timeout=3, max_retries=1)

        result = HealthVerifier(config).verify_health("https://service.test")

        assert result.status == HealthStatus.UNHEALTHY
        assert result.error_message == "Request timeout after 3s"

    def test_verify_multiple_endpoints_returns_each_endpoint_result(
        self,
        mocker: MockerFixture,
    ) -> None:
        mock_sync_health_client(mocker, httpx.Response(200), httpx.Response(500))
        config = HealthCheckConfig(max_retries=1)

        results = HealthVerifier(config).verify_multiple_endpoints(
            "https://service.test",
            ["/health", "/ready"],
        )

        assert results["/health"].status == HealthStatus.HEALTHY
        assert results["/ready"].status == HealthStatus.UNHEALTHY

    def test_get_health_summary_counts_endpoint_statuses(self) -> None:
        results = {
            "/health": HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time=0.2,
            ),
            "/ready": HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time=0.0,
            ),
        }

        summary = HealthVerifier().get_health_summary(results)

        assert summary["overall_status"] == HealthStatus.UNHEALTHY
        assert summary["total_endpoints"] == 2
        assert summary["healthy_endpoints"] == 1
        assert summary["unhealthy_endpoints"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["average_response_time"] == 0.2

    def test_get_health_summary_handles_empty_results(self) -> None:
        summary = HealthVerifier().get_health_summary({})

        assert summary["overall_status"] == HealthStatus.HEALTHY
        assert summary["success_rate"] == 0.0
        assert summary["average_response_time"] == 0.0

    @pytest.mark.asyncio
    async def test_verify_health_async_success(self, mocker: MockerFixture) -> None:
        client_class, client = mock_async_health_client(mocker, httpx.Response(200))
        config = HealthCheckConfig(timeout=7)

        result = await HealthVerifier(config)._verify_health_async(
            "https://service.test",
            "api-key",
        )

        assert result.status == HealthStatus.HEALTHY
        client_class.assert_called_once_with(timeout=7)
        client.get.assert_awaited_once_with(
            "https://service.test/.well-known/health",
            headers={"X-API-Key": "api-key"},
        )

    @pytest.mark.asyncio
    async def test_verify_health_async_retries_after_failure(
        self,
        mocker: MockerFixture,
    ) -> None:
        sleep = mocker.patch("supervaizer.deploy.health.asyncio.sleep")
        _, client = mock_async_health_client(
            mocker,
            httpx.Response(503),
            httpx.Response(200),
        )
        config = HealthCheckConfig(max_retries=2, base_delay=0)

        result = await HealthVerifier(config)._verify_health_async(
            "https://service.test"
        )

        assert result.status == HealthStatus.HEALTHY
        assert client.get.await_count == 2
        sleep.assert_awaited_once_with(0)


def test_verify_service_health_returns_boolean(mocker: MockerFixture) -> None:
    mock_sync_health_client(mocker, httpx.Response(200))

    assert verify_service_health("https://service.test") is True


def test_display_health_results_prints_table(mocker: MockerFixture) -> None:
    console = mocker.patch("supervaizer.deploy.health.console")
    results = {
        "/health": HealthCheckResult(
            status=HealthStatus.HEALTHY,
            response_time=0.1,
            status_code=200,
        )
    }

    display_health_results(results)

    console.print.assert_called_once()
