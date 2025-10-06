# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Deployment CLI Commands

This module contains the main CLI commands for the deploy subcommand.
"""

import typer
from rich.console import Console

from supervaizer.deploy.commands import plan, up, down, status

console = Console()

# Create the deploy subcommand
deploy_app = typer.Typer(
    name="deploy",
    help="Deploy Supervaizer agents to cloud platforms",
    no_args_is_help=True,
)

# Add subcommands
deploy_app.add_typer(plan.app, name="plan", help="Plan deployment changes")
deploy_app.add_typer(up.app, name="up", help="Deploy or update service")
deploy_app.add_typer(down.app, name="down", help="Destroy service")
deploy_app.add_typer(status.app, name="status", help="Show deployment status")
