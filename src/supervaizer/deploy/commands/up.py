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
Up Command

Deploy or update the service.
"""

import secrets
import string
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from supervaizer.common import log
from supervaizer.deploy.docker import (
    DockerManager,
    ensure_docker_running,
    get_container_env,
)
from supervaizer.deploy.driver_factory import create_driver, get_supported_platforms
from supervaizer.deploy.drivers.base import SECRET_ENV_VARS, DeploymentResult
from supervaizer.deploy.state import StateManager
from supervaizer.deploy.utils import create_deployment_directory, get_git_sha

console = Console()


def deploy_up(
    platform: str,
    name: str | None = None,
    env: str = "dev",
    region: str | None = None,
    project_id: str | None = None,
    image: str | None = None,
    port: int = 8000,
    generate_api_key: bool = False,
    generate_rsa: bool = False,
    timeout: int = 300,
    source_dir: Path | None = None,
) -> None:
    """Deploy or update the service."""
    # Validate platform
    if platform not in get_supported_platforms():
        console.print(f"[bold red]Error:[/] Unsupported platform: {platform}")
        console.print(f"Supported platforms: {', '.join(get_supported_platforms())}")
        return
    if image and "/" in image:
        console.print(
            "[bold red]Error:[/] --image takes name[:tag]; "
            "the platform registry is added automatically"
        )
        return

    # Set defaults
    project_dir = source_dir or Path.cwd()
    if not name:
        name = project_dir.name
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
        deployment_dir = create_deployment_directory(project_dir)
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

        env_vars, secrets_dict = build_service_env(
            env, port, _generate_secrets(generate_api_key, generate_rsa)
        )

        # Build and push Docker image
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Building Docker image...", total=None)

            docker_manager = DockerManager()
            dockerfile_path = deployment_dir / "Dockerfile"
            docker_manager.generate_dockerfile(
                output_path=dockerfile_path,
                app_port=port,
            )
            docker_manager.generate_dockerignore(deployment_dir / ".dockerignore")
            docker_manager.build_image(image, project_dir, dockerfile_path)

            progress.update(task, description="Pushing Docker image...")
            remote_image = driver.prepare_registry(image)
            docker_manager.tag_image(image, remote_image)
            docker_manager.push_image(remote_image, auth_config=driver.registry_auth())

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
                image_tag=remote_image,
                port=port,
                env_vars=env_vars,
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
                image_tag=remote_image,
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

    except Exception as e:
        log.error(f"Deployment failed: {e}")
        console.print(f"[bold red]Deployment failed:[/] {e}")


def build_service_env(
    environment: str, port: int, secrets: dict[str, str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Split the container environment into plain variables and platform secrets."""
    env_vars = get_container_env(environment, port)
    # Drivers set SUPERVAIZER_PUBLIC_URL from the deployed service URL.
    env_vars.pop("SUPERVAIZER_PUBLIC_URL", None)
    host_secrets = {
        name: env_vars.pop(name) for name in SECRET_ENV_VARS if name in env_vars
    }
    return env_vars, {**secrets, **host_secrets}


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


def _generate_secrets(generate_api_key: bool, generate_rsa: bool) -> dict[str, str]:
    """Generate controller secrets under the variable names the server reads."""
    secrets_dict = {}
    if generate_api_key:
        secrets_dict["SUPERVAIZER_API_KEY"] = _generate_api_key()
    if generate_rsa:
        secrets_dict["SUPERVAIZER_PRIVATE_KEY"] = _generate_rsa_key()
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
