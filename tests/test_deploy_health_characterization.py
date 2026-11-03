# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Characterize HealthVerifier behavior before its retry-loop refactor."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pytest_mock import MockerFixture

from supervaizer.deploy.health import HealthCheckConfig, HealthStatus, HealthVerifier


@pytest.fixture
def fake_clock(mocker: MockerFixture) -> MagicMock:
    """Keep health-result timestamps deterministic."""
    return mocker.patch("supervaizer.deploy.health.time.time", return_value=100.0)


def mock_sync_client(
    mocker: MockerFixture,
    *responses: httpx.Response | Exception,
) -> tuple[MagicMock, MagicMock]:
    """Replace synchronous HTTP clients with a controlled context manager."""
    client_context = mocker.MagicMock()
    client = mocker.MagicMock()
    client.get.side_effect = responses
    client_context.__enter__.return_value = client
    client_class = mocker.patch(
        "supervaizer.deploy.health.httpx.Client",
        return_value=client_context,
    )
    return client_class, client


def mock_async_client(
    mocker: MockerFixture,
    *responses: httpx.Response | Exception,
) -> tuple[MagicMock, AsyncMock]:
    """Replace asynchronous HTTP clients with a controlled context manager."""
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


def test_sync_success_threshold_counts_successes_across_failures(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """Successful attempts accumulate even when a later attempt fails."""
    sleep = mocker.patch("supervaizer.deploy.health.time.sleep")
    _, client = mock_sync_client(
        mocker,
        httpx.Response(200),
        httpx.Response(503),
        httpx.Response(200),
    )
    config = HealthCheckConfig(
        max_retries=3,
        success_threshold=2,
        endpoints=["/health"],
    )

    result = HealthVerifier(config).verify_health("https://service.test")

    assert result.status is HealthStatus.HEALTHY
    assert client.get.call_count == 3
    sleep.assert_has_calls([mocker.call(1.0), mocker.call(2.0)])


@pytest.mark.asyncio
async def test_async_success_threshold_counts_successes_across_failures(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """Async successful attempts also accumulate across later failures."""
    sleep = mocker.patch("supervaizer.deploy.health.asyncio.sleep")
    _, client = mock_async_client(
        mocker,
        httpx.Response(200),
        httpx.Response(503),
        httpx.Response(200),
    )
    config = HealthCheckConfig(
        max_retries=3,
        success_threshold=2,
        endpoints=["/health"],
    )

    result = await HealthVerifier(config)._verify_health_async("https://service.test")

    assert result.status is HealthStatus.HEALTHY
    assert client.get.await_count == 3
    sleep.assert_has_awaits([mocker.call(1.0), mocker.call(2.0)])


def test_sync_no_endpoints_skips_clients_requests_and_delays(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """An empty endpoint list skips every request and retry delay."""
    client_class, _ = mock_sync_client(mocker)
    sleep = mocker.patch("supervaizer.deploy.health.time.sleep")
    config = HealthCheckConfig(max_retries=3, endpoints=[])

    result = HealthVerifier(config).verify_health("https://service.test")

    assert result.error_message == "No endpoints configured"
    client_class.assert_not_called()
    sleep.assert_not_called()


@pytest.mark.asyncio
async def test_async_no_endpoints_skips_requests_and_delays(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """The async client opens, but an empty endpoint list makes no requests."""
    client_class, client = mock_async_client(mocker)
    sleep = mocker.patch("supervaizer.deploy.health.asyncio.sleep")
    config = HealthCheckConfig(max_retries=3, endpoints=[])

    result = await HealthVerifier(config)._verify_health_async("https://service.test")

    assert result.error_message == "No endpoints configured"
    client_class.assert_called_once_with(timeout=60)
    client.get.assert_not_awaited()
    sleep.assert_not_awaited()


def test_sync_creates_one_client_for_each_endpoint_attempt(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """Synchronous verification creates a client for each endpoint request."""
    client_class, client = mock_sync_client(
        mocker,
        httpx.Response(200),
        httpx.Response(503),
        httpx.Response(200),
        httpx.Response(503),
    )
    mocker.patch("supervaizer.deploy.health.time.sleep")
    config = HealthCheckConfig(max_retries=2, endpoints=["/health", "/ready"])

    HealthVerifier(config).verify_health("https://service.test")

    assert client_class.call_count == 4
    assert client.get.call_count == 4


@pytest.mark.asyncio
async def test_async_reuses_one_client_across_endpoint_attempts(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """Asynchronous verification reuses one client across all attempts."""
    client_class, client = mock_async_client(
        mocker,
        httpx.Response(200),
        httpx.Response(503),
        httpx.Response(200),
        httpx.Response(503),
    )
    mocker.patch("supervaizer.deploy.health.asyncio.sleep")
    config = HealthCheckConfig(max_retries=2, endpoints=["/health", "/ready"])

    await HealthVerifier(config)._verify_health_async("https://service.test")

    client_class.assert_called_once_with(timeout=60)
    assert client.get.await_count == 4


def test_sync_stops_an_attempt_at_the_first_failing_endpoint(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """A later endpoint does not run after an earlier endpoint fails."""
    _, client = mock_sync_client(mocker, httpx.Response(503), httpx.Response(200))
    config = HealthCheckConfig(max_retries=1, endpoints=["/health", "/ready"])

    result = HealthVerifier(config).verify_health("https://service.test")

    assert result.error_message == "Endpoint /health returned 503"
    client.get.assert_called_once_with("https://service.test/health", headers={})


@pytest.mark.asyncio
async def test_async_stops_an_attempt_at_the_first_failing_endpoint(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """Async verification also stops an attempt after its first failure."""
    _, client = mock_async_client(mocker, httpx.Response(503), httpx.Response(200))
    config = HealthCheckConfig(max_retries=1, endpoints=["/health", "/ready"])

    result = await HealthVerifier(config)._verify_health_async("https://service.test")

    assert result.error_message == "Endpoint /health returned 503"
    client.get.assert_awaited_once_with("https://service.test/health", headers={})


def test_sync_retry_delay_is_capped_by_configuration(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """Exponential retry delays do not exceed the configured cap."""
    mock_sync_client(
        mocker, httpx.Response(503), httpx.Response(503), httpx.Response(503)
    )
    sleep = mocker.patch("supervaizer.deploy.health.time.sleep")
    config = HealthCheckConfig(
        max_retries=3,
        base_delay=2.0,
        backoff_multiplier=10.0,
        max_delay=5.0,
    )

    HealthVerifier(config).verify_health("https://service.test")

    sleep.assert_has_calls([mocker.call(2.0), mocker.call(5.0)])


@pytest.mark.asyncio
async def test_async_reports_unexpected_exception_text(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """Unexpected async request failures include their original text."""
    mock_async_client(mocker, RuntimeError("connection state failed"))
    config = HealthCheckConfig(max_retries=1)

    result = await HealthVerifier(config)._verify_health_async("https://service.test")

    assert result.error_message == "Unexpected error: connection state failed"


def test_call_config_overrides_the_verifier_config(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """A call-specific configuration controls its endpoint and timeout."""
    client_class, client = mock_sync_client(mocker, httpx.Response(200))
    verifier = HealthVerifier(HealthCheckConfig(timeout=1, endpoints=["/ignored"]))
    override = HealthCheckConfig(timeout=9, endpoints=["/override"])

    result = verifier.verify_health("https://service.test/", config=override)

    assert result.endpoint == "/override"
    client_class.assert_called_once_with(timeout=9)
    client.get.assert_called_once_with("https://service.test/override", headers={})


def test_sync_zero_retries_makes_no_request_and_keeps_no_error(
    mocker: MockerFixture,
    fake_clock: MagicMock,
) -> None:
    """Zero retry attempts return an unhealthy result without an error message."""
    client_class, _ = mock_sync_client(mocker)
    config = HealthCheckConfig(max_retries=0, endpoints=["/health"])

    result = HealthVerifier(config).verify_health("https://service.test")

    assert result.status is HealthStatus.UNHEALTHY
    assert result.error_message is None
    client_class.assert_not_called()
