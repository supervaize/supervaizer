# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Health Check Utilities

This module provides enhanced health verification functionality with retry logic,
exponential backoff, and detailed health reporting for deployment verification.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from rich.console import Console

from supervaizer.common import log

console = Console()


class HealthStatus(Enum):
    """Health check status enumeration."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    status: HealthStatus
    response_time: float
    status_code: int | None = None
    error_message: str | None = None
    endpoint: str | None = None
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class HealthCheckConfig:
    """Configuration for health check operations."""

    timeout: int = 60
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
    success_threshold: int = 1  # Number of successful checks required
    endpoints: list[str] | None = None

    def __post_init__(self) -> None:
        if self.endpoints is None:
            self.endpoints = ["/.well-known/health"]


class HealthVerifier:
    """Enhanced health verification with retry logic and exponential backoff."""

    def __init__(self, config: HealthCheckConfig | None = None) -> None:
        """Initialize the health verifier with configuration."""
        self.config = config or HealthCheckConfig()

    def verify_health(
        self,
        service_url: str,
        api_key: str | None = None,
        config: HealthCheckConfig | None = None,
    ) -> HealthCheckResult:
        """
        Verify service health with retry logic and exponential backoff.

        Args:
            service_url: Base URL of the service
            api_key: Optional API key for authenticated endpoints
            config: Optional configuration override

        Returns:
            HealthCheckResult with detailed status information
        """
        active_config = config or self.config
        return self._verify_health_sync(
            service_url,
            self._get_headers(api_key),
            active_config,
        )

    def verify_health_async(
        self,
        service_url: str,
        api_key: str | None = None,
        config: HealthCheckConfig | None = None,
    ) -> HealthCheckResult:
        """
        Async version of health verification.

        Args:
            service_url: Base URL of the service
            api_key: Optional API key for authenticated endpoints
            config: Optional configuration override

        Returns:
            HealthCheckResult with detailed status information
        """
        return asyncio.run(self._verify_health_async(service_url, api_key, config))

    async def _verify_health_async(
        self,
        service_url: str,
        api_key: str | None = None,
        config: HealthCheckConfig | None = None,
    ) -> HealthCheckResult:
        """Internal async health verification implementation."""
        active_config = config or self.config
        headers = self._get_headers(api_key)
        async with httpx.AsyncClient(timeout=active_config.timeout) as client:
            return await self._verify_health_async_with_client(
                service_url,
                headers,
                active_config,
                client,
            )

    def _verify_health_sync(
        self,
        service_url: str,
        headers: dict[str, str],
        config: HealthCheckConfig,
    ) -> HealthCheckResult:
        """Run synchronous health-check attempts with a new client per endpoint."""
        last_error: str | None = None
        successful_checks = 0

        for attempt in range(config.max_retries):
            start_time = time.time()
            try:
                if not config.endpoints:
                    last_error = "No endpoints configured"
                    continue

                healthy, error = self._verify_health_sync_endpoints(
                    service_url,
                    headers,
                    config.endpoints,
                    config.timeout,
                )
                if healthy:
                    successful_checks += 1
                    if successful_checks >= config.success_threshold:
                        return self._healthy_result(start_time, config)
                else:
                    last_error = error or "One or more endpoints failed"
            except Exception as error:
                last_error = self._request_error(error, config)

            if attempt < config.max_retries - 1:
                self._sleep_before_retry(attempt, config)

        return self._unhealthy_result(config, last_error)

    def _verify_health_sync_endpoints(
        self,
        service_url: str,
        headers: dict[str, str],
        endpoints: list[str],
        timeout: int,
    ) -> tuple[bool, str | None]:
        """Check synchronous endpoints and keep their client lifetime unchanged."""
        for endpoint in endpoints:
            endpoint_url = f"{service_url.rstrip('/')}{endpoint}"
            with httpx.Client(timeout=timeout) as client:
                response = client.get(endpoint_url, headers=headers)
                if response.status_code != 200:
                    return False, f"Endpoint {endpoint} returned {response.status_code}"

        return True, None

    async def _verify_health_async_with_client(
        self,
        service_url: str,
        headers: dict[str, str],
        config: HealthCheckConfig,
        client: httpx.AsyncClient,
    ) -> HealthCheckResult:
        """Run asynchronous health-check attempts with one shared client."""
        last_error: str | None = None
        successful_checks = 0

        for attempt in range(config.max_retries):
            start_time = time.time()
            try:
                if not config.endpoints:
                    last_error = "No endpoints configured"
                    continue

                healthy, error = await self._verify_health_async_endpoints(
                    service_url,
                    headers,
                    config.endpoints,
                    client,
                )
                if healthy:
                    successful_checks += 1
                    if successful_checks >= config.success_threshold:
                        return self._healthy_result(start_time, config)
                else:
                    last_error = error or "One or more endpoints failed"
            except Exception as error:
                last_error = self._request_error(error, config)

            if attempt < config.max_retries - 1:
                delay = self._retry_delay(attempt, config)
                self._log_retry(attempt, delay)
                await asyncio.sleep(delay)

        return self._unhealthy_result(config, last_error)

    async def _verify_health_async_endpoints(
        self,
        service_url: str,
        headers: dict[str, str],
        endpoints: list[str],
        client: httpx.AsyncClient,
    ) -> tuple[bool, str | None]:
        """Check asynchronous endpoints with the supplied client."""
        for endpoint in endpoints:
            endpoint_url = f"{service_url.rstrip('/')}{endpoint}"
            response = await client.get(endpoint_url, headers=headers)
            if response.status_code != 200:
                return False, f"Endpoint {endpoint} returned {response.status_code}"

        return True, None

    @staticmethod
    def _get_headers(api_key: str | None) -> dict[str, str]:
        """Build request headers for an optional API key."""
        return {"X-API-Key": api_key} if api_key else {}

    @staticmethod
    def _request_error(error: Exception, config: HealthCheckConfig) -> str:
        """Convert request failures to the established result text."""
        if isinstance(error, httpx.TimeoutException):
            return f"Request timeout after {config.timeout}s"
        if isinstance(error, httpx.RequestError):
            return f"Request error: {error!s}"
        return f"Unexpected error: {error!s}"

    @staticmethod
    def _retry_delay(attempt: int, config: HealthCheckConfig) -> float:
        """Calculate the capped retry delay for an attempt."""
        return min(
            config.base_delay * (config.backoff_multiplier**attempt),
            config.max_delay,
        )

    def _sleep_before_retry(self, attempt: int, config: HealthCheckConfig) -> None:
        """Log and sleep before the next synchronous attempt."""
        delay = self._retry_delay(attempt, config)
        self._log_retry(attempt, delay)
        time.sleep(delay)

    @staticmethod
    def _log_retry(attempt: int, delay: float) -> None:
        """Log the established retry message."""
        log.debug(
            f"Health check attempt {attempt + 1} failed, retrying in {delay:.1f}s"
        )

    @staticmethod
    def _healthy_result(
        start_time: float,
        config: HealthCheckConfig,
    ) -> HealthCheckResult:
        """Build the established successful health-check result."""
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            response_time=time.time() - start_time,
            status_code=200,
            endpoint=config.endpoints[0] if config.endpoints else None,
        )

    @staticmethod
    def _unhealthy_result(
        config: HealthCheckConfig,
        last_error: str | None,
    ) -> HealthCheckResult:
        """Build the established failed health-check result."""
        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY,
            response_time=0.0,
            error_message=last_error,
            endpoint=config.endpoints[0] if config.endpoints else None,
        )

    def verify_multiple_endpoints(
        self,
        service_url: str,
        endpoints: list[str],
        api_key: str | None = None,
        config: HealthCheckConfig | None = None,
    ) -> dict[str, HealthCheckResult]:
        """
        Verify multiple endpoints and return individual results.

        Args:
            service_url: Base URL of the service
            endpoints: List of endpoints to check
            api_key: Optional API key for authenticated endpoints
            config: Optional configuration override

        Returns:
            Dictionary mapping endpoints to their health check results
        """
        config = config or self.config
        config.endpoints = endpoints

        results = {}
        for endpoint in endpoints:
            single_endpoint_config = HealthCheckConfig(
                timeout=config.timeout,
                max_retries=config.max_retries,
                base_delay=config.base_delay,
                max_delay=config.max_delay,
                backoff_multiplier=config.backoff_multiplier,
                success_threshold=config.success_threshold,
                endpoints=[endpoint],
            )

            results[endpoint] = self.verify_health(
                service_url, api_key, single_endpoint_config
            )

        return results

    def get_health_summary(
        self, results: dict[str, HealthCheckResult]
    ) -> dict[str, Any]:
        """
        Generate a summary of health check results.

        Args:
            results: Dictionary of health check results

        Returns:
            Summary dictionary with overall status and statistics
        """
        total_checks = len(results)
        healthy_checks = sum(
            1 for r in results.values() if r.status == HealthStatus.HEALTHY
        )
        unhealthy_checks = total_checks - healthy_checks

        avg_response_time = 0.0
        if healthy_checks > 0:
            response_times = [
                r.response_time
                for r in results.values()
                if r.status == HealthStatus.HEALTHY
            ]
            avg_response_time = sum(response_times) / len(response_times)

        overall_status = (
            HealthStatus.HEALTHY if unhealthy_checks == 0 else HealthStatus.UNHEALTHY
        )

        return {
            "overall_status": overall_status,
            "total_endpoints": total_checks,
            "healthy_endpoints": healthy_checks,
            "unhealthy_endpoints": unhealthy_checks,
            "success_rate": healthy_checks / total_checks if total_checks > 0 else 0.0,
            "average_response_time": avg_response_time,
            "timestamp": time.time(),
            "details": results,
        }


def verify_service_health(
    service_url: str,
    api_key: str | None = None,
    timeout: int = 60,
    max_retries: int = 5,
) -> bool:
    """
    Simple health verification function for backward compatibility.

    Args:
        service_url: Base URL of the service
        api_key: Optional API key for authenticated endpoints
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts

    Returns:
        True if service is healthy, False otherwise
    """
    config = HealthCheckConfig(timeout=timeout, max_retries=max_retries)

    verifier = HealthVerifier(config)
    result = verifier.verify_health(service_url, api_key)

    return result.status == HealthStatus.HEALTHY


def display_health_results(results: dict[str, HealthCheckResult]) -> None:
    """
    Display health check results in a formatted table.

    Args:
        results: Dictionary of health check results
    """
    from rich.table import Table

    table = Table(title="Health Check Results")
    table.add_column("Endpoint", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Response Time", style="green")
    table.add_column("Status Code", style="blue")
    table.add_column("Error", style="red")

    for endpoint, result in results.items():
        status_style = "green" if result.status == HealthStatus.HEALTHY else "red"
        response_time = (
            f"{result.response_time:.3f}s" if result.response_time > 0 else "N/A"
        )
        status_code = str(result.status_code) if result.status_code else "N/A"
        error = result.error_message or "None"

        table.add_row(
            endpoint,
            f"[{status_style}]{result.status.value}[/]",
            response_time,
            status_code,
            error,
        )

    console.print(table)
