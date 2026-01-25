# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Up Command

Deploy or update the service.
"""

import secrets
import string
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from supervaizer.common import log
from supervaizer.deploy.docker import DockerManager, ensure_docker_running
from supervaizer.deploy.driver_factory import create_driver, get_supported_platforms
from supervaizer.deploy.drivers.base import DeploymentResult
from supervaizer.deploy.state import StateManager
from supervaizer.deploy.utils import create_deployment_directory, get_git_sha

console = Console()


def deploy_up(
    platform: str,
    name: Optional[str] = None,
    env: str = "dev",
    region: Optional[str] = None,
    project_id: Optional[str] = None,
    image: Optional[str] = None,
    port: int = 8000,
    generate_api_key: bool = False,
    generate_rsa: bool = False,
    yes: bool = False,
    no_rollback: bool = False,
    timeout: int = 300,
    verbose: bool = False,
    source_dir: Optional[Path] = None,
) -> None:
    """Deploy or update the service."""
    # Validate platform
    if platform not in get_supported_platforms():
        console.print(f"[bold red]Error:[/] Unsupported platform: {platform}")
        console.print(f"Supported platforms: {', '.join(get_supported_platforms())}")
        return

    # Set defaults
    if not name:
        name = (source_dir or Path.cwd()).name
    if not region:
        region = _get_default_region(platform)

    console.print(f"[bold green]Deploying to {platform}[/bold green]")
    console.print(f"Service name: {name}")
    console.print(f"Environment: {env}")
    console.print(f"Region: {region}")
    console.print(f"Port: {port}")
    if project_id:
        console.print(f"Project ID: {project_id}")
    if image:
        console.print(f"Image: {image}")

    try:
        # Check Docker
        if not ensure_docker_running():
            console.print("[bold red]Error:[/] Docker is not running")
            return

        # Create deployment directory
        deployment_dir = create_deployment_directory(source_dir or Path.cwd())
        state_manager = StateManager(deployment_dir)

        # Create driver
        driver = create_driver(platform, region, project_id)

        # Check prerequisites
        prerequisites = driver.check_prerequisites()
        if prerequisites:
            console.print("[bold red]Prerequisites not met:[/]")
            for prereq in prerequisites:
                console.print(f"  • {prereq}")
            return

        # Generate image tag
        if not image:
            image = _generate_image_tag(name, env)

        # Generate secrets
        secrets_dict = _generate_secrets(name, env, generate_api_key, generate_rsa)

        # Build and push Docker image
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Building Docker image...", total=None)

            docker_manager = DockerManager()

            # Generate Docker files
            dockerfile_path = deployment_dir / "Dockerfile"
            dockerignore_path = deployment_dir / ".dockerignore"
            compose_path = deployment_dir / "docker-compose.yml"

            docker_manager.generate_dockerfile(
                output_path=dockerfile_path,
                app_port=port,
            )
            docker_manager.generate_dockerignore(dockerignore_path)
            docker_manager.generate_docker_compose(
                compose_path,
                port=port,
                service_name=name,
                environment=env,
                api_key=secrets_dict.get("api_key", "test-api-key"),
                rsa_key=secrets_dict.get("rsa_private_key", "test-rsa-key"),
            )

            # Build image
            progress.update(task, description="Building Docker image...")

            # Get build arguments for environment variables
            from supervaizer.deploy.docker import get_docker_build_args

            build_args = get_docker_build_args(port)

            docker_manager.build_image(
                image, source_dir or Path.cwd(), dockerfile_path, build_args=build_args
            )

            # Push image (this would be platform-specific)
            progress.update(task, description="Pushing Docker image...")
            # Note: Actual push would depend on the platform's registry

        # Deploy service
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Deploying service...", total=None)

            result = driver.deploy_service(
                service_name=name,
                environment=env,
                image_tag=image,
                port=port,
                env_vars=_get_default_env_vars(env),
                secrets=secrets_dict,
                timeout=timeout,
            )

        # Update state
        if result.success:
            state_manager.update_state(
                service_name=name,
                platform=platform,
                environment=env,
                region=region,
                project_id=project_id,
                image_tag=image,
                image_digest=result.image_digest,
                service_url=result.service_url,
                revision=result.revision,
                status=result.status,
                health_status=result.health_status,
                port=port,
                api_key_generated=generate_api_key,
                rsa_key_generated=generate_rsa,
            )

            # Display results
            _display_deployment_result(result)
        else:
            console.print(f"[bold red]Deployment failed:[/] {result.error_message}")
            if not no_rollback:
                console.print(
                    "[yellow]Consider using --no-rollback to keep failed revision[/yellow]"
                )

    except Exception as e:
        log.error(f"Deployment failed: {e}")
        console.print(f"[bold red]Deployment failed:[/] {e}")


def _get_default_region(platform: str) -> str:
    """Get default region for platform."""
    defaults = {
        "cloud-run": "us-central1",
        "aws-app-runner": "us-east-1",
        "do-app-platform": "nyc3",
    }
    return defaults.get(platform, "us-central1")


def _generate_image_tag(service_name: str, environment: str) -> str:
    """Generate image tag for deployment."""
    git_sha = get_git_sha()
    return f"{service_name}-{environment}:{git_sha}"


def _generate_secrets(
    service_name: str, environment: str, generate_api_key: bool, generate_rsa: bool
) -> dict[str, str]:
    """Generate secrets for deployment."""
    secrets_dict = {}

    if generate_api_key:
        api_key = _generate_api_key()
        secrets_dict[f"{service_name}-{environment}-api-key"] = api_key

    if generate_rsa:
        rsa_key = _generate_rsa_key()
        secrets_dict[f"{service_name}-{environment}-rsa-key"] = rsa_key

    return secrets_dict


def _generate_api_key() -> str:
    """Generate a secure API key."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def _generate_rsa_key() -> str:
    """Generate an RSA private key."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return pem.decode("utf-8")


def _get_default_env_vars(environment: str) -> dict[str, str]:
    """Get default environment variables."""
    return {
        "SUPERVAIZER_ENVIRONMENT": environment,
        "SUPERVAIZER_HOST": "0.0.0.0",
        "SUPERVAIZER_PORT": "8000",
        "SV_LOG_LEVEL": "INFO",
    }


def _display_deployment_result(result: DeploymentResult) -> None:
    """Display deployment result."""
    console.print("\n[bold green]Deployment successful![/bold green]")

    if result.service_url:
        console.print(f"Service URL: {result.service_url}")
        console.print(f"API Documentation: {result.service_url}/docs")
        console.print(f"ReDoc Documentation: {result.service_url}/redoc")

    if result.service_id:
        console.print(f"Service ID: {result.service_id}")

    if result.revision:
        console.print(f"Revision: {result.revision}")

    console.print(f"Status: {result.status}")
    console.print(f"Health: {result.health_status}")

    if result.deployment_time:
        console.print(f"Deployment time: {result.deployment_time:.1f}s")
