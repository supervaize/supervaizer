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
Down Command

Destroy the service and cleanup resources.
"""

import shutil
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from supervaizer.common import log
from supervaizer.deploy.driver_factory import create_driver, get_supported_platforms
from supervaizer.deploy.drivers.base import BaseDriver
from supervaizer.deploy.state import StateManager
from supervaizer.deploy.utils import (
    display_service_target,
    get_default_region as _get_default_region,
    prerequisites_met,
)

console = Console()


def deploy_down(
    platform: str,
    name: str | None = None,
    env: str = "dev",
    region: str | None = None,
    project_id: str | None = None,
    yes: bool = False,
    source_dir: Path | None = None,
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

    _display_destruction_target(platform, name, env, region, project_id)

    try:
        # Check local state
        deployment_dir = (source_dir or Path.cwd()) / ".deployment"
        state_manager = StateManager(deployment_dir)
        _display_current_deployment(state_manager)

        # Confirmation prompt
        if not yes and not Confirm.ask(
            f"\nAre you sure you want to destroy {name}-{env}?"
        ):
            console.print("[yellow]Destruction cancelled[/yellow]")
            return

        # Create driver
        driver = create_driver(platform, region, project_id)
        _destroy_deployment(driver, name, env, state_manager, deployment_dir)

    except Exception as e:
        log.error(f"Destruction failed: {e}")
        console.print(f"[bold red]Destruction failed:[/] {e}")


def _display_destruction_target(
    platform: str, name: str, env: str, region: str, project_id: str | None
) -> None:
    console.print(f"[bold red]Destroying service on {platform}[/bold red]")
    display_service_target(console, name, env, region, project_id)


def _display_current_deployment(state_manager: StateManager) -> None:
    state = state_manager.load_state()
    if state:
        console.print("\n[bold]Current Deployment:[/bold]")
        console.print(f"  Service URL: {state.service_url}")
        console.print(f"  Image Tag: {state.image_tag}")
        console.print(f"  Status: {state.status}")


def _destroy_deployment(
    driver: BaseDriver,
    name: str,
    env: str,
    state_manager: StateManager,
    deployment_dir: Path,
) -> None:
    if not prerequisites_met(driver, console):
        return

    console.print("\n[bold]Destroying service...[/bold]")
    result = driver.destroy_service(name, env, keep_secrets=False)
    if result.success:
        console.print("[bold green]Service destroyed successfully[/bold green]")
        if state_manager.state_file.exists():
            state_manager.delete_state()
            console.print("Cleaned up local deployment state")
        if deployment_dir.exists():
            shutil.rmtree(deployment_dir)
            console.print("Cleaned up deployment directory")
    else:
        console.print(f"[bold red]Destruction failed:[/] {result.error_message}")
