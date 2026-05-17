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
Base Driver Interface

This module defines the base interface for deployment drivers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ActionType(str, Enum):
    """Type of deployment action."""

    CREATE = "create"
    UPDATE = "update"
    NOOP = "noop"
    DELETE = "delete"


class ResourceType(str, Enum):
    """Type of cloud resource."""

    SERVICE = "service"
    SECRET = "secret"
    REGISTRY = "registry"
    IMAGE = "image"


@dataclass
class ResourceAction:
    """Represents an action to be taken on a resource."""

    resource_type: ResourceType
    action_type: ActionType
    resource_name: str
    description: str
    cost_estimate: str | None = None
    metadata: dict[str, Any] | None = None


class DeploymentPlan(BaseModel):
    """Deployment plan containing all actions to be taken."""

    platform: str
    service_name: str
    environment: str
    region: str
    project_id: str | None = None

    # Plan details
    actions: list[ResourceAction] = []
    total_cost_estimate: str | None = None
    estimated_duration: str | None = None

    # Current state
    current_image: str | None = None
    current_url: str | None = None
    current_status: str | None = None

    # Target state
    target_image: str
    target_port: int = 8000
    target_env_vars: dict[str, str] = {}
    target_secrets: dict[str, str] = {}


class DeploymentResult(BaseModel):
    """Result of a deployment operation."""

    success: bool
    service_url: str | None = None
    service_id: str | None = None
    revision: str | None = None
    image_digest: str | None = None

    # Status information
    status: str = "unknown"
    health_status: str = "unknown"

    # Timing
    deployment_time: float | None = None

    # Error information
    error_message: str | None = None
    error_details: dict[str, Any] | None = None


class BaseDriver(ABC):
    """Base interface for deployment drivers."""

    def __init__(self, region: str, project_id: str | None = None):
        """Initialize the driver."""
        self.region = region
        self.project_id = project_id

    @abstractmethod
    def plan_deployment(
        self,
        service_name: str,
        environment: str,
        image_tag: str,
        port: int = 8000,
        env_vars: dict[str, str] | None = None,
        secrets: dict[str, str] | None = None,
    ) -> DeploymentPlan:
        """Plan deployment changes without applying them."""

    @abstractmethod
    def deploy_service(
        self,
        service_name: str,
        environment: str,
        image_tag: str,
        port: int = 8000,
        env_vars: dict[str, str] | None = None,
        secrets: dict[str, str] | None = None,
        timeout: int = 300,
    ) -> DeploymentResult:
        """Deploy or update the service."""

    @abstractmethod
    def destroy_service(
        self,
        service_name: str,
        environment: str,
        keep_secrets: bool = False,
    ) -> DeploymentResult:
        """Destroy the service and cleanup resources."""

    @abstractmethod
    def get_service_status(
        self,
        service_name: str,
        environment: str,
    ) -> DeploymentResult:
        """Get current service status and health."""

    @abstractmethod
    def verify_health(self, service_url: str, timeout: int = 60) -> bool:
        """Verify service health by checking the health endpoint."""

    def verify_health_enhanced(
        self,
        service_url: str,
        api_key: str | None = None,
        timeout: int = 60,
        max_retries: int = 5,
    ) -> bool:
        """
        Enhanced health verification with retry logic and exponential backoff.

        Args:
            service_url: Base URL of the service
            api_key: Optional API key for authenticated endpoints
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts

        Returns:
            True if service is healthy, False otherwise
        """
        from supervaizer.deploy.health import verify_service_health

        return verify_service_health(service_url, api_key, timeout, max_retries)

    @abstractmethod
    def check_prerequisites(self) -> list[str]:
        """Check prerequisites and return list of missing requirements."""

    def get_service_key(self, service_name: str, environment: str) -> str:
        """Generate a unique key for the service."""
        return f"{service_name}-{environment}"

    def validate_configuration(self, **kwargs: Any) -> list[str]:
        """Validate driver configuration and return list of errors."""
        errors = []

        if not self.region:
            errors.append("Region is required")

        return errors
