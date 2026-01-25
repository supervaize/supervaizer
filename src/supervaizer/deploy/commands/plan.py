# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Plan Command

Shows what changes will be made during deployment.
"""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from supervaizer.common import log
from supervaizer.deploy.driver_factory import create_driver, get_supported_platforms
from supervaizer.deploy.utils import get_git_sha
from supervaizer.deploy.drivers.base import DeploymentPlan

console = Console()


def plan_deployment(
    platform: str,
    name: Optional[str] = None,
    env: str = "dev",
    region: Optional[str] = None,
    project_id: Optional[str] = None,
    verbose: bool = False,
    source_dir: Optional[Path] = None,
) -> None:
    """Plan deployment changes without applying them."""
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

    console.print(f"[bold blue]Planning deployment to {platform}[/bold blue]")
    console.print(f"Service name: {name}")
    console.print(f"Environment: {env}")
    console.print(f"Region: {region}")
    if project_id:
        console.print(f"Project ID: {project_id}")

    try:
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
        image_tag = _generate_image_tag(name, env)

        # Create deployment plan
        plan = driver.plan_deployment(
            service_name=name,
            environment=env,
            image_tag=image_tag,
            port=8000,
            env_vars=_get_default_env_vars(env),
            secrets=_get_default_secrets(name, env),
        )

        # Display plan
        _display_plan(plan)

    except Exception as e:
        log.error(f"Planning failed: {e}")
        console.print(f"[bold red]Planning failed:[/] {e}")


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


def _get_default_env_vars(environment: str) -> dict[str, str]:
    """Get default environment variables."""
    return {
        "SUPERVAIZER_ENVIRONMENT": environment,
        "SUPERVAIZER_HOST": "0.0.0.0",
        "SUPERVAIZER_PORT": "8000",
        "SV_LOG_LEVEL": "INFO",
    }


def _get_default_secrets(service_name: str, environment: str) -> dict[str, str]:
    """Get default secrets for deployment."""
    return {
        f"{service_name}-{environment}-api-key": "placeholder-api-key",
        f"{service_name}-{environment}-rsa-key": "placeholder-rsa-key",
    }


def _display_plan(plan: DeploymentPlan) -> None:
    """Display deployment plan."""
    console.print(
        f"\n[bold]Deployment Plan for {plan.service_name}-{plan.environment}[/bold]"
    )
    console.print(f"Platform: {plan.platform}")
    console.print(f"Region: {plan.region}")
    console.print(f"Target Image: {plan.target_image}")

    if plan.current_image:
        console.print(f"Current Image: {plan.current_image}")
    if plan.current_url:
        console.print(f"Current URL: {plan.current_url}")

    # Display actions
    if plan.actions:
        table = Table(title="Actions")
        table.add_column("Type", style="cyan")
        table.add_column("Resource", style="magenta")
        table.add_column("Action", style="green")
        table.add_column("Description", style="white")

        for action in plan.actions:
            table.add_row(
                action.resource_type.value,
                action.resource_name,
                action.action_type.value,
                action.description,
            )

        console.print(table)
    else:
        console.print("[yellow]No actions required[/yellow]")

    # Display environment variables
    if plan.target_env_vars:
        console.print("\n[bold]Environment Variables:[/bold]")
        for key, value in plan.target_env_vars.items():
            console.print(f"  {key}={value}")

    # Display secrets
    if plan.target_secrets:
        console.print("\n[bold]Secrets:[/bold]")
        for key in plan.target_secrets.keys():
            console.print(f"  {key}=***")
