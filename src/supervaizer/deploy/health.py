# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
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
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

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
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    endpoint: Optional[str] = None
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
    endpoints: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.endpoints is None:
            self.endpoints = ["/.well-known/health"]


class HealthVerifier:
    """Enhanced health verification with retry logic and exponential backoff."""

    def __init__(self, config: Optional[HealthCheckConfig] = None):
        """Initialize the health verifier with configuration."""
        self.config = config or HealthCheckConfig()

    def verify_health(
        self,
        service_url: str,
        api_key: Optional[str] = None,
        config: Optional[HealthCheckConfig] = None,
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
        config = config or self.config
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key

        last_error = None
        successful_checks = 0
        total_attempts = 0

        for attempt in range(config.max_retries):
            total_attempts += 1
            start_time = time.time()

            try:
                # Check all configured endpoints
                if not config.endpoints:
                    last_error = "No endpoints configured"
                    continue
                all_healthy = True
                for endpoint in config.endpoints:
                    endpoint_url = f"{service_url.rstrip('/')}{endpoint}"

                    with httpx.Client(timeout=config.timeout) as client:
                        response = client.get(endpoint_url, headers=headers)

                        if response.status_code != 200:
                            all_healthy = False
                            last_error = (
                                f"Endpoint {endpoint} returned {response.status_code}"
                            )
                            break

                if all_healthy:
                    successful_checks += 1
                    if successful_checks >= config.success_threshold:
                        response_time = time.time() - start_time
                        return HealthCheckResult(
                            status=HealthStatus.HEALTHY,
                            response_time=response_time,
                            status_code=200,
                            endpoint=config.endpoints[0] if config.endpoints else None,
                        )
                else:
                    last_error = last_error or "One or more endpoints failed"

            except httpx.TimeoutException:
                last_error = f"Request timeout after {config.timeout}s"
            except httpx.RequestError as e:
                last_error = f"Request error: {str(e)}"
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"

            # Calculate delay for next attempt
            if attempt < config.max_retries - 1:
                delay = min(
                    config.base_delay * (config.backoff_multiplier**attempt),
                    config.max_delay,
                )
                log.debug(
                    f"Health check attempt {attempt + 1} failed, retrying in {delay:.1f}s"
                )
                time.sleep(delay)

        # All attempts failed
        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY,
            response_time=0.0,
            error_message=last_error,
            endpoint=config.endpoints[0] if config.endpoints else None,
        )

    def verify_health_async(
        self,
        service_url: str,
        api_key: Optional[str] = None,
        config: Optional[HealthCheckConfig] = None,
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
        api_key: Optional[str] = None,
        config: Optional[HealthCheckConfig] = None,
    ) -> HealthCheckResult:
        """Internal async health verification implementation."""
        config = config or self.config
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key

        last_error = None
        successful_checks = 0

        async with httpx.AsyncClient(timeout=config.timeout) as client:
            for attempt in range(config.max_retries):
                start_time = time.time()

                try:
                    # Check all configured endpoints
                    if not config.endpoints:
                        last_error = "No endpoints configured"
                        continue
                    all_healthy = True
                    for endpoint in config.endpoints:
                        endpoint_url = f"{service_url.rstrip('/')}{endpoint}"

                        response = await client.get(endpoint_url, headers=headers)

                        if response.status_code != 200:
                            all_healthy = False
                            last_error = (
                                f"Endpoint {endpoint} returned {response.status_code}"
                            )
                            break

                    if all_healthy:
                        successful_checks += 1
                        if successful_checks >= config.success_threshold:
                            response_time = time.time() - start_time
                            return HealthCheckResult(
                                status=HealthStatus.HEALTHY,
                                response_time=response_time,
                                status_code=200,
                                endpoint=config.endpoints[0]
                                if config.endpoints
                                else None,
                            )
                    else:
                        last_error = last_error or "One or more endpoints failed"

                except httpx.TimeoutException:
                    last_error = f"Request timeout after {config.timeout}s"
                except httpx.RequestError as e:
                    last_error = f"Request error: {str(e)}"
                except Exception as e:
                    last_error = f"Unexpected error: {str(e)}"

                # Calculate delay for next attempt
                if attempt < config.max_retries - 1:
                    delay = min(
                        config.base_delay * (config.backoff_multiplier**attempt),
                        config.max_delay,
                    )
                    log.debug(
                        f"Health check attempt {attempt + 1} failed, retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)

        # All attempts failed
        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY,
            response_time=0.0,
            error_message=last_error,
            endpoint=config.endpoints[0] if config.endpoints else None,
        )

    def verify_multiple_endpoints(
        self,
        service_url: str,
        endpoints: List[str],
        api_key: Optional[str] = None,
        config: Optional[HealthCheckConfig] = None,
    ) -> Dict[str, HealthCheckResult]:
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
        self, results: Dict[str, HealthCheckResult]
    ) -> Dict[str, Any]:
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
    api_key: Optional[str] = None,
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


def display_health_results(results: Dict[str, HealthCheckResult]) -> None:
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
