# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
AWS App Runner Driver

This module implements deployment to AWS App Runner.
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

# Conditional imports for AWS libraries
if TYPE_CHECKING:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    AWS_AVAILABLE = True
else:
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        AWS_AVAILABLE = True
    except ImportError:
        AWS_AVAILABLE = False

        # Create dummy classes for type hints when not available
        class ClientError(Exception):
            pass

        class NoCredentialsError(Exception):
            pass

        class boto3:
            @staticmethod
            def client(*args: Any, **kwargs: Any) -> Any:
                pass


class AWSAppRunnerDriver(BaseDriver):
    """Driver for deploying to AWS App Runner."""

    def __init__(self, region: str, project_id: Optional[str] = None):
        """Initialize AWS App Runner driver."""
        if not AWS_AVAILABLE:
            raise ImportError(
                "AWS libraries not available. Install with: pip install boto3"
            )

        super().__init__(region, project_id)

        # Initialize AWS clients
        try:
            self.apprunner_client = boto3.client("apprunner", region_name=region)
            self.ecr_client = boto3.client("ecr", region_name=region)
            self.secrets_client = boto3.client("secretsmanager", region_name=region)
            self.iam_client = boto3.client("iam", region_name=region)
        except NoCredentialsError:
            raise RuntimeError("AWS credentials not found")

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

        # Check if service exists
        try:
            response = self.apprunner_client.describe_service(
                ServiceArn=f"arn:aws:apprunner:{self.region}:{self._get_account_id()}:service/{full_service_name}"
            )
            service = response["Service"]
            current_image = service["ServiceUrl"]
            current_url = service["ServiceUrl"]
            current_status = service["Status"]

            # Check if update is needed
            # Note: App Runner doesn't easily expose the current image, so we'll assume update is needed
            actions.append(
                ResourceAction(
                    resource_type=ResourceType.SERVICE,
                    action_type=ActionType.UPDATE,
                    resource_name=full_service_name,
                    description=f"Update App Runner service with image {image_tag}",
                )
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                # Service doesn't exist, need to create
                actions.append(
                    ResourceAction(
                        resource_type=ResourceType.SERVICE,
                        action_type=ActionType.CREATE,
                        resource_name=full_service_name,
                        description=f"Create new App Runner service with image {image_tag}",
                    )
                )
            else:
                raise

        # Check ECR repository
        repo_name = f"{service_name}-{environment}"
        try:
            self.ecr_client.describe_repositories(repositoryNames=[repo_name])
            actions.append(
                ResourceAction(
                    resource_type=ResourceType.REGISTRY,
                    action_type=ActionType.NOOP,
                    resource_name=repo_name,
                    description="ECR repository exists",
                )
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "RepositoryNotFoundException":
                actions.append(
                    ResourceAction(
                        resource_type=ResourceType.REGISTRY,
                        action_type=ActionType.CREATE,
                        resource_name=repo_name,
                        description=f"Create ECR repository {repo_name}",
                    )
                )
            else:
                raise

        # Check secrets
        if secrets:
            for secret_name, secret_value in secrets.items():
                try:
                    self.secrets_client.describe_secret(SecretId=secret_name)
                    actions.append(
                        ResourceAction(
                            resource_type=ResourceType.SECRET,
                            action_type=ActionType.UPDATE,
                            resource_name=secret_name,
                            description=f"Update secret {secret_name}",
                        )
                    )
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ResourceNotFoundException":
                        actions.append(
                            ResourceAction(
                                resource_type=ResourceType.SECRET,
                                action_type=ActionType.CREATE,
                                resource_name=secret_name,
                                description=f"Create secret {secret_name}",
                            )
                        )
                    else:
                        raise

        return DeploymentPlan(
            platform="aws-app-runner",
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
            # Ensure ECR repository exists
            repo_name = f"{service_name}-{environment}"
            self._ensure_ecr_repository(repo_name)

            # Create/update secrets
            if secrets:
                self._create_or_update_secrets(secrets)

            # Create/update service
            service_arn = self._create_or_update_service(
                full_service_name,
                repo_name,
                image_tag,
                port,
                env_vars or {},
                secrets or {},
            )

            # Wait for service to be ready
            service_url = self._wait_for_service_ready(service_arn, timeout)

            # Set SUPERVAIZER_PUBLIC_URL
            if service_url:
                self._set_public_url(service_arn, service_url)

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
                service_id=service_arn,
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
        service_arn = f"arn:aws:apprunner:{self.region}:{self._get_account_id()}:service/{full_service_name}"

        try:
            # Delete service
            self.apprunner_client.delete_service(ServiceArn=service_arn)
            log.info(f"Deleted App Runner service: {full_service_name}")

            # Delete ECR repository
            repo_name = f"{service_name}-{environment}"
            try:
                self.ecr_client.delete_repository(
                    repositoryName=repo_name,
                    force=True,  # Delete even if images exist
                )
                log.info(f"Deleted ECR repository: {repo_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "RepositoryNotFoundException":
                    log.warning(f"Failed to delete ECR repository: {e}")

            # Delete secrets if requested
            if not keep_secrets:
                self._delete_secrets(full_service_name)

            return DeploymentResult(
                success=True,
                status="deleted",
            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                log.warning(f"Service {full_service_name} not found")
                return DeploymentResult(
                    success=True,
                    status="not_found",
                )
            else:
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
        service_arn = f"arn:aws:apprunner:{self.region}:{self._get_account_id()}:service/{full_service_name}"

        try:
            response = self.apprunner_client.describe_service(ServiceArn=service_arn)
            service = response["Service"]

            # Check health
            health_status = "unknown"
            if service["ServiceUrl"]:
                health_status = (
                    "healthy"
                    if self.verify_health(service["ServiceUrl"])
                    else "unhealthy"
                )

            return DeploymentResult(
                success=True,
                service_url=service["ServiceUrl"],
                service_id=service_arn,
                status=service["Status"],
                health_status=health_status,
            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return DeploymentResult(
                    success=False,
                    status="not_found",
                    error_message="Service not found",
                )
            else:
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

        # Check AWS CLI
        try:
            result = subprocess.run(
                ["aws", "--version"], capture_output=True, text=True, check=True
            )
            log.debug(f"AWS CLI version: {result.stdout}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            errors.append("AWS CLI not found or not working")

        # Check AWS credentials
        try:
            sts_client = boto3.client("sts")
            sts_client.get_caller_identity()
        except NoCredentialsError:
            errors.append("AWS credentials not found")
        except Exception as e:
            errors.append(f"AWS credentials check failed: {e}")

        # This is a simplified check - in practice you'd want to test actual permissions
        try:
            self._get_account_id()
        except Exception as e:
            errors.append(f"Failed to get AWS account ID: {e}")

        return errors

    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        sts_client = boto3.client("sts")
        response = sts_client.get_caller_identity()
        return response["Account"]

    def _ensure_ecr_repository(self, repo_name: str) -> None:
        """Ensure ECR repository exists."""
        try:
            self.ecr_client.describe_repositories(repositoryNames=[repo_name])
            log.info(f"ECR repository {repo_name} exists")
        except ClientError as e:
            if e.response["Error"]["Code"] == "RepositoryNotFoundException":
                # Create repository
                self.ecr_client.create_repository(
                    repositoryName=repo_name,
                    imageTagMutability="MUTABLE",
                    imageScanningConfiguration={"scanOnPush": True},
                )
                log.info(f"Created ECR repository: {repo_name}")
            else:
                raise

    def _create_or_update_secrets(self, secrets: Dict[str, str]) -> None:
        """Create or update secrets in Secrets Manager."""
        for secret_name, secret_value in secrets.items():
            try:
                # Try to update existing secret
                self.secrets_client.update_secret(
                    SecretId=secret_name, SecretString=secret_value
                )
                log.info(f"Updated secret {secret_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    # Create new secret
                    self.secrets_client.create_secret(
                        Name=secret_name,
                        SecretString=secret_value,
                        Description="Secret for Supervaizer deployment",
                    )
                    log.info(f"Created secret {secret_name}")
                else:
                    raise

    def _create_or_update_service(
        self,
        service_name: str,
        repo_name: str,
        image_tag: str,
        port: int,
        env_vars: Dict[str, str],
        secrets: Dict[str, str],
    ) -> str:
        """Create or update App Runner service."""
        account_id = self._get_account_id()
        service_arn = (
            f"arn:aws:apprunner:{self.region}:{account_id}:service/{service_name}"
        )

        # Build environment variables
        env_vars_list = []
        for key, value in env_vars.items():
            env_vars_list.append({"Name": key, "Value": value})

        # Build secret references
        secret_refs = []
        for secret_name in secrets.keys():
            secret_refs.append(
                {
                    "Name": secret_name,
                    "ValueFrom": f"arn:aws:secretsmanager:{self.region}:{account_id}:secret:{secret_name}",
                }
            )

        # Service configuration
        service_config = {
            "ServiceName": service_name,
            "SourceConfiguration": {
                "ImageRepository": {
                    "ImageIdentifier": f"{account_id}.dkr.ecr.{self.region}.amazonaws.com/{repo_name}:{image_tag}",
                    "ImageConfiguration": {
                        "Port": str(port),
                        "RuntimeEnvironmentVariables": env_vars_list + secret_refs,
                    },
                    "ImageRepositoryType": "ECR",
                },
                "AutoDeploymentsEnabled": False,
            },
            "InstanceConfiguration": {
                "Cpu": "0.25 vCPU",
                "Memory": "0.5 GB",
            },
            "HealthCheckConfiguration": {
                "Protocol": "HTTP",
                "Path": "/.well-known/health",
                "Interval": 10,
                "Timeout": 5,
                "HealthyThreshold": 1,
                "UnhealthyThreshold": 5,
            },
        }

        try:
            # Try to update existing service
            response = self.apprunner_client.update_service(
                ServiceArn=service_arn,
                SourceConfiguration=service_config["SourceConfiguration"],
                InstanceConfiguration=service_config["InstanceConfiguration"],
                HealthCheckConfiguration=service_config["HealthCheckConfiguration"],
            )
            log.info(f"Updated App Runner service: {service_name}")
            return service_arn

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                # Create new service
                response = self.apprunner_client.create_service(**service_config)
                log.info(f"Created App Runner service: {service_name}")
                return response["Service"]["ServiceArn"]
            else:
                raise

    def _wait_for_service_ready(self, service_arn: str, timeout: int) -> Optional[str]:
        """Wait for service to be ready and return URL."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.apprunner_client.describe_service(
                    ServiceArn=service_arn
                )
                service = response["Service"]

                if service["Status"] == "RUNNING" and service["ServiceUrl"]:
                    log.info(f"Service ready at: {service['ServiceUrl']}")
                    return service["ServiceUrl"]
                elif service["Status"] in [
                    "CREATE_FAILED",
                    "UPDATE_FAILED",
                    "DELETE_FAILED",
                ]:
                    raise RuntimeError(
                        f"Service failed with status: {service['Status']}"
                    )

            except Exception as e:
                log.debug(f"Waiting for service to be ready: {e}")

            time.sleep(10)

        raise TimeoutError(f"Service did not become ready within {timeout} seconds")

    def _set_public_url(self, service_arn: str, public_url: str) -> None:
        """Set SUPERVAIZER_PUBLIC_URL environment variable."""
        try:
            # Get current service configuration
            response = self.apprunner_client.describe_service(ServiceArn=service_arn)
            service = response["Service"]

            # Update environment variables
            current_env_vars = service["SourceConfiguration"]["ImageRepository"][
                "ImageConfiguration"
            ].get("RuntimeEnvironmentVariables", [])

            # Remove existing SUPERVAIZER_PUBLIC_URL
            env_vars = [
                env
                for env in current_env_vars
                if env["Name"] != "SUPERVAIZER_PUBLIC_URL"
            ]

            # Add the public URL
            env_vars.append(
                {
                    "Name": "SUPERVAIZER_PUBLIC_URL",
                    "Value": public_url,
                }
            )

            # Update service
            self.apprunner_client.update_service(
                ServiceArn=service_arn,
                SourceConfiguration={
                    **service["SourceConfiguration"],
                    "ImageRepository": {
                        **service["SourceConfiguration"]["ImageRepository"],
                        "ImageConfiguration": {
                            **service["SourceConfiguration"]["ImageRepository"][
                                "ImageConfiguration"
                            ],
                            "RuntimeEnvironmentVariables": env_vars,
                        },
                    },
                },
            )

            log.info(f"Set SUPERVAIZER_PUBLIC_URL to {public_url}")

        except Exception as e:
            log.error(f"Failed to set SUPERVAIZER_PUBLIC_URL: {e}")

    def _delete_secrets(self, service_name: str) -> None:
        """Delete secrets associated with the service."""
        common_secrets = [
            f"{service_name}-api-key",
            f"{service_name}-rsa-key",
        ]

        for secret_name in common_secrets:
            try:
                self.secrets_client.delete_secret(
                    SecretId=secret_name, ForceDeleteWithoutRecovery=True
                )
                log.info(f"Deleted secret {secret_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceNotFoundException":
                    log.warning(f"Failed to delete secret {secret_name}: {e}")
