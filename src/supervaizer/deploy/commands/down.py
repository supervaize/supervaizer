# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Down Command

Destroy the service and cleanup resources.
"""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm

from supervaizer.common import log
from supervaizer.deploy.driver_factory import create_driver, get_supported_platforms
from supervaizer.deploy.state import StateManager

console = Console()


def deploy_down(
    platform: str,
    name: Optional[str] = None,
    env: str = "dev",
    region: Optional[str] = None,
    project_id: Optional[str] = None,
    yes: bool = False,
    verbose: bool = False,
    source_dir: Optional[Path] = None,
) -> None:
    """Destroy the service and cleanup resources."""
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

    console.print(f"[bold red]Destroying service on {platform}[/bold red]")
    console.print(f"Service name: {name}")
    console.print(f"Environment: {env}")
    console.print(f"Region: {region}")
    if project_id:
        console.print(f"Project ID: {project_id}")

    try:
        # Check local state
        deployment_dir = (source_dir or Path.cwd()) / ".deployment"
        state_manager = StateManager(deployment_dir)
        state = state_manager.load_state()

        if state:
            console.print("\n[bold]Current Deployment:[/bold]")
            console.print(f"  Service URL: {state.service_url}")
            console.print(f"  Image Tag: {state.image_tag}")
            console.print(f"  Status: {state.status}")

        # Confirmation prompt
        if not yes:
            if not Confirm.ask(f"\nAre you sure you want to destroy {name}-{env}?"):
                console.print("[yellow]Destruction cancelled[/yellow]")
                return

        # Create driver
        driver = create_driver(platform, region, project_id)

        # Check prerequisites
        prerequisites = driver.check_prerequisites()
        if prerequisites:
            console.print("[bold red]Prerequisites not met:[/]")
            for prereq in prerequisites:
                console.print(f"  • {prereq}")
            return

        # Destroy service
        console.print("\n[bold]Destroying service...[/bold]")
        result = driver.destroy_service(name, env, keep_secrets=False)

        if result.success:
            console.print("[bold green]Service destroyed successfully[/bold green]")

            # Clean up local state
            if state_manager.state_file.exists():
                state_manager.delete_state()
                console.print("Cleaned up local deployment state")

            # Clean up deployment directory
            if deployment_dir.exists():
                import shutil

                shutil.rmtree(deployment_dir)
                console.print("Cleaned up deployment directory")

        else:
            console.print(f"[bold red]Destruction failed:[/] {result.error_message}")

    except Exception as e:
        log.error(f"Destruction failed: {e}")
        console.print(f"[bold red]Destruction failed:[/] {e}")


def _get_default_region(platform: str) -> str:
    """Get default region for platform."""
    defaults = {
        "cloud-run": "us-central1",
        "aws-app-runner": "us-east-1",
        "do-app-platform": "nyc3",
    }
    return defaults.get(platform, "us-central1")
