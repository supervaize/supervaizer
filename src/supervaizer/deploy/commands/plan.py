# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Plan Command

Shows what changes will be made during deployment.
"""

import typer
from rich.console import Console

console = Console()

app = typer.Typer(name="plan", help="Plan deployment changes")


@app.command()
def plan_deployment(
    platform: str = typer.Option(
        ...,
        "--platform",
        "-p",
        help="Target platform (cloud-run|aws-app-runner|do-app-platform)",
    ),
    name: str = typer.Option(None, "--name", "-n", help="Service name"),
    env: str = typer.Option(
        "dev", "--env", "-e", help="Environment (dev|staging|prod)"
    ),
    region: str = typer.Option(None, "--region", "-r", help="Provider region"),
    project_id: str = typer.Option(
        None, "--project-id", help="GCP project / AWS account / DO project"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Plan deployment changes without applying them."""
    console.print(f"[bold blue]Planning deployment to {platform}[/bold blue]")
    console.print(f"Environment: {env}")
    if name:
        console.print(f"Service name: {name}")
    if region:
        console.print(f"Region: {region}")
    if project_id:
        console.print(f"Project ID: {project_id}")

    # TODO: Implement actual planning logic
    console.print("[yellow]Planning logic not yet implemented[/yellow]")
