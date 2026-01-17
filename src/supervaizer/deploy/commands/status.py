# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Status Command

Show deployment status and health information.
"""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from supervaizer.common import log
from supervaizer.deploy.driver_factory import create_driver, get_supported_platforms
from supervaizer.deploy.drivers.base import DeploymentResult
from supervaizer.deploy.state import DeploymentState, StateManager

console = Console()


def deploy_status(
    platform: str,
    name: Optional[str] = None,
    env: str = "dev",
    region: Optional[str] = None,
    project_id: Optional[str] = None,
    verbose: bool = False,
    source_dir: Optional[Path] = None,
) -> None:
    """Show deployment status and health information."""
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

    console.print(f"[bold blue]Deployment Status for {name}-{env}[/bold blue]")
    console.print(f"Platform: {platform}")
    console.print(f"Region: {region}")
    if project_id:
        console.print(f"Project ID: {project_id}")

    try:
        # Check local state first
        deployment_dir = (source_dir or Path.cwd()) / ".deployment"
        if deployment_dir.exists():
            state_manager = StateManager(deployment_dir)
            state = state_manager.load_state()

            if state:
                console.print("\n[bold]Local State:[/bold]")
                _display_state(state)

        # Get live status from platform
        driver = create_driver(platform, region, project_id)

        # Check prerequisites
        prerequisites = driver.check_prerequisites()
        if prerequisites:
            console.print("[bold red]Prerequisites not met:[/]")
            for prereq in prerequisites:
                console.print(f"  • {prereq}")
            return

        # Get service status
        result = driver.get_service_status(name, env)

        if result.success:
            console.print("\n[bold]Live Status:[/bold]")
            _display_service_status(result)
        else:
            console.print(
                f"\n[bold red]Service not found or error:[/] {result.error_message}"
            )

    except Exception as e:
        log.error(f"Status check failed: {e}")
        console.print(f"[bold red]Status check failed:[/] {e}")


def _get_default_region(platform: str) -> str:
    """Get default region for platform."""
    defaults = {
        "cloud-run": "us-central1",
        "aws-app-runner": "us-east-1",
        "do-app-platform": "nyc3",
    }
    return defaults.get(platform, "us-central1")


def _display_state(state: DeploymentState) -> None:
    """Display deployment state."""
    table = Table(title="Deployment State")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Service Name", state.service_name)
    table.add_row("Platform", state.platform)
    table.add_row("Environment", state.environment)
    table.add_row("Region", state.region)
    if state.project_id:
        table.add_row("Project ID", state.project_id)
    table.add_row("Image Tag", state.image_tag)
    if state.image_digest:
        table.add_row("Image Digest", state.image_digest[:16] + "...")
    if state.service_url:
        table.add_row("Service URL", state.service_url)
    if state.revision:
        table.add_row("Revision", state.revision)
    table.add_row("Status", state.status)
    table.add_row("Health Status", state.health_status)
    table.add_row("Port", str(state.port))
    table.add_row("API Key Generated", str(state.api_key_generated))
    table.add_row("RSA Key Generated", str(state.rsa_key_generated))
    table.add_row("Created At", state.created_at.isoformat())
    table.add_row("Updated At", state.updated_at.isoformat())

    console.print(table)


def _display_service_status(result: DeploymentResult) -> None:
    """Display service status."""
    table = Table(title="Service Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    if result.service_url:
        table.add_row("Service URL", result.service_url)
        table.add_row("API Documentation", f"{result.service_url}/docs")
        table.add_row("ReDoc Documentation", f"{result.service_url}/redoc")

    if result.service_id:
        table.add_row("Service ID", result.service_id)

    if result.revision:
        table.add_row("Revision", result.revision)

    if result.image_digest:
        table.add_row("Image Digest", result.image_digest[:16] + "...")

    table.add_row("Status", result.status)
    table.add_row("Health Status", result.health_status)

    if result.deployment_time:
        table.add_row("Deployment Time", f"{result.deployment_time:.1f}s")

    console.print(table)

    # Health check details
    if result.service_url:
        console.print("\n[bold]Health Check:[/bold]")
        if result.health_status == "healthy":
            console.print("[green]✓[/green] Service is healthy")
        elif result.health_status == "unhealthy":
            console.print("[red]✗[/red] Service is unhealthy")
        else:
            console.print("[yellow]?[/yellow] Health status unknown")
