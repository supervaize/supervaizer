# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
GCP Cloud Run Driver

This module implements deployment to Google Cloud Platform Cloud Run.
"""

import subprocess
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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

# Conditional imports for Google Cloud libraries
if TYPE_CHECKING:
    from google.cloud import artifactregistry_v1
    from google.cloud import run_v2
    from google.cloud import secretmanager
    from google.cloud.exceptions import NotFound

    GOOGLE_CLOUD_AVAILABLE = True
else:
    try:
        from google.cloud import artifactregistry_v1
        from google.cloud import run_v2
        from google.cloud import secretmanager
        from google.cloud.exceptions import NotFound

        GOOGLE_CLOUD_AVAILABLE = True
    except ImportError:
        GOOGLE_CLOUD_AVAILABLE = False

        # Create dummy classes for type hints when not available
        class NotFound(Exception):
            pass

        class artifactregistry_v1:
            class ArtifactRegistryClient:
                pass

        class run_v2:
            class ServicesClient:
                pass

        class secretmanager:
            class SecretManagerServiceClient:
                pass


class CloudRunDriver(BaseDriver):
    """Driver for deploying to GCP Cloud Run."""

    def __init__(self, region: str, project_id: str):
        """Initialize Cloud Run driver."""
        if not GOOGLE_CLOUD_AVAILABLE:
            raise ImportError(
                "Google Cloud libraries not available. Install with: "
                "pip install google-cloud-run google-cloud-secret-manager google-cloud-artifact-registry"
            )

        super().__init__(region, project_id)
        self.project_id = project_id

        # Initialize clients
        self.run_client = run_v2.ServicesClient()
        self.secret_client = secretmanager.SecretManagerServiceClient()
        self.registry_client = artifactregistry_v1.ArtifactRegistryClient()

        # Service configuration
        self.service_parent = f"projects/{project_id}/locations/{region}"
        self.registry_location = f"projects/{project_id}/locations/{region}"

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
        service_path = f"{self.service_parent}/services/{full_service_name}"

        actions = []
        current_image = None
        current_url = None
        current_status = None

        # Check if service exists
        try:
            service = self.run_client.get_service(name=service_path)
            current_image = service.template.containers[0].image
            current_url = service.uri
            current_status = "running"

            # Check if update is needed
            if current_image != image_tag:
                actions.append(
                    ResourceAction(
                        resource_type=ResourceType.SERVICE,
                        action_type=ActionType.UPDATE,
                        resource_name=full_service_name,
                        description=f"Update service image from {current_image} to {image_tag}",
                    )
                )
            else:
                actions.append(
                    ResourceAction(
                        resource_type=ResourceType.SERVICE,
                        action_type=ActionType.NOOP,
                        resource_name=full_service_name,
                        description="Service image is up to date",
                    )
                )
        except NotFound:
            # Service doesn't exist, need to create
            actions.append(
                ResourceAction(
                    resource_type=ResourceType.SERVICE,
                    action_type=ActionType.CREATE,
                    resource_name=full_service_name,
                    description=f"Create new Cloud Run service with image {image_tag}",
                )
            )

        # Check secrets
        if secrets:
            for secret_name, secret_value in secrets.items():
                secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
                try:
                    self.secret_client.get_secret(name=secret_path)
                    actions.append(
                        ResourceAction(
                            resource_type=ResourceType.SECRET,
                            action_type=ActionType.UPDATE,
                            resource_name=secret_name,
                            description=f"Update secret {secret_name}",
                        )
                    )
                except NotFound:
                    actions.append(
                        ResourceAction(
                            resource_type=ResourceType.SECRET,
                            action_type=ActionType.CREATE,
                            resource_name=secret_name,
                            description=f"Create secret {secret_name}",
                        )
                    )

        return DeploymentPlan(
            platform="cloud-run",
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
        service_path = f"{self.service_parent}/services/{full_service_name}"

        try:
            # Create/update secrets first
            if secrets:
                self._create_or_update_secrets(secrets)

            # Create/update service
            service = self._create_or_update_service(
                full_service_name,
                image_tag,
                port,
                env_vars or {},
                secrets or {},
            )

            # Wait for service to be ready
            service_url = self._wait_for_service_ready(service_path, timeout)

            # Set SUPERVAIZER_PUBLIC_URL
            if service_url:
                self._set_public_url(service_path, service_url)

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
                service_id=service.name,
                revision=service.latest_ready_revision,
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
        service_path = f"{self.service_parent}/services/{full_service_name}"

        try:
            # Delete service
            self.run_client.delete_service(name=service_path)
            log.info(f"Deleted Cloud Run service: {full_service_name}")

            # Delete secrets if requested
            if not keep_secrets:
                self._delete_secrets(full_service_name)

            return DeploymentResult(
                success=True,
                status="deleted",
            )

        except NotFound:
            log.warning(f"Service {full_service_name} not found")
            return DeploymentResult(
                success=True,
                status="not_found",
            )
        except Exception as e:
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
        service_path = f"{self.service_parent}/services/{full_service_name}"

        try:
            service = self.run_client.get_service(name=service_path)

            # Check health
            health_status = "unknown"
            if service.uri:
                health_status = (
                    "healthy" if self.verify_health(service.uri) else "unhealthy"
                )

            return DeploymentResult(
                success=True,
                service_url=service.uri,
                service_id=service.name,
                revision=service.latest_ready_revision,
                status="running",
                health_status=health_status,
            )

        except NotFound:
            return DeploymentResult(
                success=False,
                status="not_found",
                error_message="Service not found",
            )
        except Exception as e:
            return DeploymentResult(
                success=False,
                error_message=str(e),
            )

    def verify_health(self, service_url: str, timeout: int = 60) -> bool:
        """Verify service health by checking the health endpoint."""
        return self.verify_health_enhanced(service_url, timeout=timeout)

    def check_prerequisites(self) -> List[str]:
        """Check prerequisites and return list of missing requirements."""
        errors = []

        # Check gcloud CLI
        try:
            result = subprocess.run(
                ["gcloud", "version"], capture_output=True, text=True, check=True
            )
            log.debug(f"gcloud version: {result.stdout}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            errors.append("gcloud CLI not found or not working")

        # Check authentication
        try:
            result = subprocess.run(
                [
                    "gcloud",
                    "auth",
                    "list",
                    "--filter=status:ACTIVE",
                    "--format=value(account)",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            if not result.stdout.strip():
                errors.append("No active gcloud authentication found")
        except subprocess.CalledProcessError:
            errors.append("gcloud authentication check failed")

        # Check project
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                check=True,
            )
            if not result.stdout.strip():
                errors.append("No gcloud project configured")
        except subprocess.CalledProcessError:
            errors.append("gcloud project configuration check failed")

        # Check APIs
        required_apis = [
            "run.googleapis.com",
            "secretmanager.googleapis.com",
            "artifactregistry.googleapis.com",
        ]

        for api in required_apis:
            try:
                result = subprocess.run(
                    ["gcloud", "services", "list", "--enabled", f"--filter=name:{api}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if api not in result.stdout:
                    errors.append(f"API {api} not enabled")
            except subprocess.CalledProcessError:
                errors.append(f"Failed to check API {api}")

        return errors

    def _create_or_update_secrets(self, secrets: Dict[str, str]) -> None:
        """Create or update secrets in Secret Manager."""
        for secret_name, secret_value in secrets.items():
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"

            try:
                # Check if secret exists
                self.secret_client.get_secret(name=secret_path)

                # Update existing secret
                parent = f"projects/{self.project_id}"
                self.secret_client.add_secret_version(
                    request={
                        "parent": secret_path,
                        "payload": {"data": secret_value.encode("utf-8")},
                    }
                )
                log.info(f"Updated secret {secret_name}")

            except NotFound:
                # Create new secret
                parent = f"projects/{self.project_id}"
                secret = self.secret_client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": {"replication": {"automatic": {}}},
                    }
                )

                # Add secret version
                self.secret_client.add_secret_version(
                    request={
                        "parent": secret.name,
                        "payload": {"data": secret_value.encode("utf-8")},
                    }
                )
                log.info(f"Created secret {secret_name}")

    def _create_or_update_service(
        self,
        service_name: str,
        image_tag: str,
        port: int,
        env_vars: Dict[str, str],
        secrets: Dict[str, str],
    ) -> Any:
        """Create or update Cloud Run service."""
        service_path = f"{self.service_parent}/services/{service_name}"

        # Build environment variables
        env_vars_list = []
        for key, value in env_vars.items():
            env_vars_list.append({"name": key, "value": value})

        # Build secret references
        secret_refs = []
        for secret_name in secrets.keys():
            secret_refs.append(
                {
                    "name": secret_name,
                    "value_source": {
                        "secret_key_ref": {
                            "secret": f"projects/{self.project_id}/secrets/{secret_name}",
                            "version": "latest",
                        }
                    },
                }
            )

        # Service configuration
        service_config = {
            "template": {
                "containers": [
                    {
                        "image": image_tag,
                        "ports": [{"container_port": port}],
                        "env": env_vars_list + secret_refs,
                        "resources": {
                            "limits": {"cpu": "1", "memory": "512Mi"},
                        },
                    }
                ],
                "scaling": {
                    "min_instance_count": 1,
                    "max_instance_count": 10,
                },
            },
            "traffic": [
                {"percent": 100, "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"}
            ],
        }

        try:
            # Try to update existing service
            service = self.run_client.update_service(
                request={"service": service_config, "name": service_path}
            )
            log.info(f"Updated Cloud Run service: {service_name}")
            return service

        except NotFound:
            # Create new service
            service_config["name"] = service_path
            service = self.run_client.create_service(
                request={"parent": self.service_parent, "service": service_config}
            )
            log.info(f"Created Cloud Run service: {service_name}")
            return service

    def _wait_for_service_ready(self, service_path: str, timeout: int) -> Optional[str]:
        """Wait for service to be ready and return URL."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                service = self.run_client.get_service(name=service_path)
                if service.uri:
                    log.info(f"Service ready at: {service.uri}")
                    return service.uri
            except Exception as e:
                log.debug(f"Waiting for service to be ready: {e}")

            time.sleep(5)

        raise TimeoutError(f"Service did not become ready within {timeout} seconds")

    def _set_public_url(self, service_path: str, public_url: str) -> None:
        """Set SUPERVAIZER_PUBLIC_URL environment variable."""
        try:
            service = self.run_client.get_service(name=service_path)

            # Update environment variables
            env_vars = []
            for env_var in service.template.containers[0].env:
                if env_var.name != "SUPERVAIZER_PUBLIC_URL":
                    env_vars.append(env_var)

            # Add the public URL
            env_vars.append(
                {
                    "name": "SUPERVAIZER_PUBLIC_URL",
                    "value": public_url,
                }
            )

            # Update service
            service.template.containers[0].env = env_vars
            self.run_client.update_service(
                request={"service": service, "name": service_path}
            )

            log.info(f"Set SUPERVAIZER_PUBLIC_URL to {public_url}")

        except Exception as e:
            log.error(f"Failed to set SUPERVAIZER_PUBLIC_URL: {e}")

    def _delete_secrets(self, service_name: str) -> None:
        """Delete secrets associated with the service."""
        # This is a simplified implementation
        # In practice, you might want to be more selective about which secrets to delete
        common_secrets = [
            f"{service_name}-api-key",
            f"{service_name}-rsa-key",
        ]

        for secret_name in common_secrets:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            try:
                self.secret_client.delete_secret(name=secret_path)
                log.info(f"Deleted secret {secret_name}")
            except NotFound:
                pass  # Secret doesn't exist, that's fine
            except Exception as e:
                log.warning(f"Failed to delete secret {secret_name}: {e}")
