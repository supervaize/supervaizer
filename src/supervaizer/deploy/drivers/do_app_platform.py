# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
DigitalOcean App Platform Driver

This module implements deployment to DigitalOcean App Platform.
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from supervaizer.common import log
from supervaizer.deploy.drivers.base import (
    ActionType,
    BaseDriver,
    DeploymentPlan,
    DeploymentResult,
    ResourceAction,
    ResourceType,
)

console = Console()


class DOAppPlatformDriver(BaseDriver):
    """Driver for deploying to DigitalOcean App Platform."""

    def __init__(self, region: str, project_id: Optional[str] = None):
        """Initialize DigitalOcean App Platform driver."""
        super().__init__(region, project_id)
        self.project_id = project_id

    def plan_deployment(
        self,
        service_name: str,
        environment: str,
        image_tag: str,
        port: int = 8000,
        env_vars: Optional[Dict[str, str]] = None,
        secrets: Optional[Dict[str, str]] = None,
    ) -> DeploymentPlan:
        """Plan deployment changes without applying them."""
        full_service_name = self.get_service_key(service_name, environment)

        actions = []
        current_image = None
        current_url = None
        current_status = None

        # Check if app exists
        try:
            result = subprocess.run(
                ["doctl", "apps", "get", full_service_name, "--format", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            app_data = json.loads(result.stdout)
            current_url = (
                app_data.get("spec", {}).get("ingress", {}).get("default_route")
            )
            current_status = app_data.get("last_deployment_active_at")

            # Check if update is needed
            actions.append(
                ResourceAction(
                    resource_type=ResourceType.SERVICE,
                    action_type=ActionType.UPDATE,
                    resource_name=full_service_name,
                    description=f"Update App Platform app with image {image_tag}",
                )
            )
        except subprocess.CalledProcessError:
            # App doesn't exist, need to create
            actions.append(
                ResourceAction(
                    resource_type=ResourceType.SERVICE,
                    action_type=ActionType.CREATE,
                    resource_name=full_service_name,
                    description=f"Create new App Platform app with image {image_tag}",
                )
            )

        # Check registry
        registry_name = f"{service_name}-{environment}"
        try:
            result = subprocess.run(
                ["doctl", "registry", "get", registry_name, "--format", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            actions.append(
                ResourceAction(
                    resource_type=ResourceType.REGISTRY,
                    action_type=ActionType.NOOP,
                    resource_name=registry_name,
                    description="Container registry exists",
                )
            )
        except subprocess.CalledProcessError:
            actions.append(
                ResourceAction(
                    resource_type=ResourceType.REGISTRY,
                    action_type=ActionType.CREATE,
                    resource_name=registry_name,
                    description=f"Create container registry {registry_name}",
                )
            )

        return DeploymentPlan(
            platform="do-app-platform",
            service_name=service_name,
            environment=environment,
            region=self.region,
            project_id=self.project_id,
            actions=actions,
            current_image=current_image,
            current_url=current_url,
            current_status=current_status,
            target_image=image_tag,
            target_port=port,
            target_env_vars=env_vars or {},
            target_secrets=secrets or {},
        )

    def deploy_service(
        self,
        service_name: str,
        environment: str,
        image_tag: str,
        port: int = 8000,
        env_vars: Optional[Dict[str, str]] = None,
        secrets: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> DeploymentResult:
        """Deploy or update the service."""
        start_time = time.time()
        full_service_name = self.get_service_key(service_name, environment)

        try:
            # Ensure registry exists
            registry_name = f"{service_name}-{environment}"
            self._ensure_registry(registry_name)

            # Create/update app spec
            app_spec_path = self._create_app_spec(
                full_service_name,
                registry_name,
                image_tag,
                port,
                env_vars or {},
                secrets or {},
            )

            # Deploy app
            service_url = self._deploy_app(full_service_name, app_spec_path, timeout)

            # Set SUPERVAIZER_PUBLIC_URL
            if service_url:
                self._set_public_url(full_service_name, service_url, app_spec_path)

            # Verify health
            health_status = (
                "healthy"
                if service_url and self.verify_health(service_url)
                else "unhealthy"
            )

            deployment_time = time.time() - start_time

            return DeploymentResult(
                success=True,
                service_url=service_url,
                service_id=full_service_name,
                status="running",
                health_status=health_status,
                deployment_time=deployment_time,
            )

        except Exception as e:
            log.error(f"Deployment failed: {e}")
            return DeploymentResult(
                success=False,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
            )

    def destroy_service(
        self,
        service_name: str,
        environment: str,
        keep_secrets: bool = False,
    ) -> DeploymentResult:
        """Destroy the service and cleanup resources."""
        full_service_name = self.get_service_key(service_name, environment)

        try:
            # Delete app
            subprocess.run(
                ["doctl", "apps", "delete", full_service_name, "--force"], check=True
            )
            log.info(f"Deleted App Platform app: {full_service_name}")

            # Delete registry
            registry_name = f"{service_name}-{environment}"
            try:
                subprocess.run(
                    ["doctl", "registry", "delete", registry_name, "--force"],
                    check=True,
                )
                log.info(f"Deleted container registry: {registry_name}")
            except subprocess.CalledProcessError:
                log.warning(f"Failed to delete registry {registry_name}")

            return DeploymentResult(
                success=True,
                status="deleted",
            )

        except subprocess.CalledProcessError as e:
            log.error(f"Failed to destroy service: {e}")
            return DeploymentResult(
                success=False,
                error_message=str(e),
            )

    def get_service_status(
        self,
        service_name: str,
        environment: str,
    ) -> DeploymentResult:
        """Get current service status and health."""
        full_service_name = self.get_service_key(service_name, environment)

        try:
            result = subprocess.run(
                ["doctl", "apps", "get", full_service_name, "--format", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            app_data = json.loads(result.stdout)

            service_url = (
                app_data.get("spec", {}).get("ingress", {}).get("default_route")
            )
            status = app_data.get("last_deployment_active_at", "unknown")

            # Check health
            health_status = "unknown"
            if service_url:
                health_status = (
                    "healthy" if self.verify_health(service_url) else "unhealthy"
                )

            return DeploymentResult(
                success=True,
                service_url=service_url,
                service_id=full_service_name,
                status=status,
                health_status=health_status,
            )

        except subprocess.CalledProcessError:
            return DeploymentResult(
                success=False,
                status="not_found",
                error_message="App not found",
            )

    def verify_health(self, service_url: str, timeout: int = 60) -> bool:
        """Verify service health by checking the health endpoint."""
        return self.verify_health_enhanced(service_url, timeout=timeout)

    def check_prerequisites(self) -> List[str]:
        """Check prerequisites and return list of missing requirements."""
        errors = []

        # Check doctl CLI
        try:
            result = subprocess.run(
                ["doctl", "version"], capture_output=True, text=True, check=True
            )
            log.debug(f"doctl version: {result.stdout}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            errors.append("doctl CLI not found or not working")

        # Check authentication
        try:
            result = subprocess.run(
                ["doctl", "account", "get", "--output", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            account_data = json.loads(result.stdout)
            if not account_data.get("email"):
                errors.append("doctl authentication not configured")
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            errors.append("doctl authentication check failed")

        return errors

    def _ensure_registry(self, registry_name: str) -> None:
        """Ensure container registry exists."""
        try:
            subprocess.run(
                ["doctl", "registry", "get", registry_name],
                capture_output=True,
                check=True,
            )
            log.info(f"Container registry {registry_name} exists")
        except subprocess.CalledProcessError:
            # Create registry
            subprocess.run(
                ["doctl", "registry", "create", registry_name, "--region", self.region],
                check=True,
            )
            log.info(f"Created container registry: {registry_name}")

    def _create_app_spec(
        self,
        app_name: str,
        registry_name: str,
        image_tag: str,
        port: int,
        env_vars: Dict[str, str],
        secrets: Dict[str, str],
    ) -> Path:
        """Create App Platform specification file."""
        # Build environment variables
        env_vars_list = []
        for key, value in env_vars.items():
            env_vars_list.append({"key": key, "value": value})

        # Build secret references
        secret_refs = []
        for secret_name in secrets.keys():
            secret_refs.append(
                {
                    "key": secret_name,
                    "scope": "RUN_TIME",
                    "type": "SECRET",
                }
            )

        # App spec
        app_spec = {
            "name": app_name,
            "services": [
                {
                    "name": "web",
                    "source_dir": "/",
                    "github": {
                        "repo": "supervaizer",
                        "branch": "main",
                        "deploy_on_push": False,
                    },
                    "dockerfile_path": "Dockerfile",
                    "http_port": port,
                    "instance_count": 1,
                    "instance_size_slug": "basic-xxs",
                    "routes": [{"path": "/"}],
                    "health_check": {
                        "http_path": "/.well-known/health",
                        "initial_delay_seconds": 10,
                        "period_seconds": 10,
                        "timeout_seconds": 5,
                        "success_threshold": 1,
                        "failure_threshold": 3,
                    },
                    "envs": env_vars_list + secret_refs,
                }
            ],
            "region": self.region,
        }

        # Write spec to file
        spec_path = Path(".deployment") / "do-app-spec.yaml"
        spec_path.parent.mkdir(exist_ok=True)

        import yaml  # type: ignore[import-untyped]

        with open(spec_path, "w") as f:
            yaml.dump(app_spec, f, default_flow_style=False)

        log.info(f"Created app spec at {spec_path}")
        return spec_path

    def _deploy_app(
        self, app_name: str, spec_path: Path, timeout: int
    ) -> Optional[str]:
        """Deploy app using doctl."""
        try:
            # Check if app exists
            try:
                subprocess.run(
                    ["doctl", "apps", "get", app_name], capture_output=True, check=True
                )
                # App exists, update it
                subprocess.run(
                    ["doctl", "apps", "update", app_name, "--spec", str(spec_path)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                log.info(f"Updated App Platform app: {app_name}")
            except subprocess.CalledProcessError:
                # App doesn't exist, create it
                subprocess.run(
                    ["doctl", "apps", "create", "--spec", str(spec_path)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                log.info(f"Created App Platform app: {app_name}")

            # Wait for deployment to complete
            return self._wait_for_deployment(app_name, timeout)

        except subprocess.CalledProcessError as e:
            log.error(f"Failed to deploy app: {e}")
            raise RuntimeError(f"App deployment failed: {e}") from e

    def _wait_for_deployment(self, app_name: str, timeout: int) -> Optional[str]:
        """Wait for deployment to complete and return URL."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ["doctl", "apps", "get", app_name, "--format", "json"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                app_data = json.loads(result.stdout)

                # Check if deployment is active
                if app_data.get("last_deployment_active_at"):
                    service_url = (
                        app_data.get("spec", {}).get("ingress", {}).get("default_route")
                    )
                    if service_url:
                        log.info(f"App deployed at: {service_url}")
                        return service_url

                # Check for failed deployment
                if app_data.get("last_deployment_created_at") and not app_data.get(
                    "last_deployment_active_at"
                ):
                    raise RuntimeError("Deployment failed")

            except Exception as e:
                log.debug(f"Waiting for deployment: {e}")

            time.sleep(10)

        raise TimeoutError(f"Deployment did not complete within {timeout} seconds")

    def _set_public_url(self, app_name: str, public_url: str, spec_path: Path) -> None:
        """Set SUPERVAIZER_PUBLIC_URL environment variable."""
        try:
            # Read current spec
            import yaml

            with open(spec_path, "r") as f:
                spec = yaml.safe_load(f)

            # Update environment variables
            envs = spec["services"][0].get("envs", [])

            # Remove existing SUPERVAIZER_PUBLIC_URL
            envs = [env for env in envs if env.get("key") != "SUPERVAIZER_PUBLIC_URL"]

            # Add the public URL
            envs.append({"key": "SUPERVAIZER_PUBLIC_URL", "value": public_url})

            spec["services"][0]["envs"] = envs

            # Write updated spec
            with open(spec_path, "w") as f:
                yaml.dump(spec, f, default_flow_style=False)

            # Update app
            subprocess.run(
                ["doctl", "apps", "update", app_name, "--spec", str(spec_path)],
                check=True,
            )

            log.info(f"Set SUPERVAIZER_PUBLIC_URL to {public_url}")

        except Exception as e:
            log.error(f"Failed to set SUPERVAIZER_PUBLIC_URL: {e}")
