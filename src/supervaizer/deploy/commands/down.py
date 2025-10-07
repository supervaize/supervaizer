# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Down Command

Destroy the service and cleanup resources.
"""

from rich.console import Console

console = Console()


def deploy_down(
    platform: str,
    name: str = None,
    env: str = "dev",
    region: str = None,
    project_id: str = None,
    yes: bool = False,
    verbose: bool = False,
) -> None:
    """Destroy the service and cleanup resources."""
    console.print(f"[bold red]Destroying service on {platform}[/bold red]")
    console.print(f"Environment: {env}")
    if name:
        console.print(f"Service name: {name}")
    if region:
        console.print(f"Region: {region}")
    if project_id:
        console.print(f"Project ID: {project_id}")

    # TODO: Implement actual destruction logic
    console.print("[yellow]Destruction logic not yet implemented[/yellow]")
