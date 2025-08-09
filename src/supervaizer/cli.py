# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from supervaizer.__version__ import VERSION

app = typer.Typer(help=f"Supervaizer Controller CLI v{VERSION}")
console = Console()


@app.command()
def start(
    host: str = typer.Option(
        os.environ.get("SUPERVAIZER_HOST", "0.0.0.0"), help="Host to bind the server to"
    ),
    port: int = typer.Option(
        int(os.environ.get("SUPERVAIZER_PORT", "8000")),
        help="Port to bind the server to",
    ),
    log_level: str = typer.Option(
        os.environ.get("SUPERVAIZER_LOG_LEVEL", "INFO"),
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    ),
    debug: bool = typer.Option(
        os.environ.get("SUPERVAIZER_DEBUG", "False").lower() == "true",
        help="Enable debug mode",
    ),
    reload: bool = typer.Option(
        os.environ.get("SUPERVAIZER_RELOAD", "False").lower() == "true",
        help="Enable auto-reload",
    ),
    environment: str = typer.Option(
        os.environ.get("SUPERVAIZER_ENVIRONMENT", "dev"), help="Environment name"
    ),
    script_path: Optional[str] = typer.Argument(
        os.environ.get("SUPERVAIZER_SCRIPT_PATH", None),
        help="Path to the supervaizer_control.py script",
    ),
) -> None:
    """Start the Supervaizer Controller server."""
    if script_path is None:
        # Try to find supervaizer_control.py in the current directory
        script_path = "supervaizer_control.py"

    if not os.path.exists(script_path):
        console.print(f"[bold red]Error:[/] {script_path} not found")
        console.print("Run [bold]supervaizer install[/] to create a default script")
        sys.exit(1)

    # Set environment variables for the server configuration
    os.environ["SUPERVAIZER_HOST"] = host
    os.environ["SUPERVAIZER_PORT"] = str(port)
    os.environ["SUPERVAIZER_ENVIRONMENT"] = environment
    os.environ["SUPERVAIZER_LOG_LEVEL"] = log_level
    os.environ["SUPERVAIZER_DEBUG"] = str(debug)
    os.environ["SUPERVAIZER_RELOAD"] = str(reload)

    console.print(f"[bold green]Starting Supervaizer Controller v{VERSION}[/]")
    console.print(f"Loading configuration from [bold]{script_path}[/]")

    # Execute the script
    with open(script_path, "r") as f:
        script_content = f.read()

    # Execute the script in the current global namespace
    exec(script_content, globals())


@app.command()
def scaffold(
    output_path: str = typer.Option(
        os.environ.get("SUPERVAIZER_OUTPUT_PATH", "supervaizer_control_example.py"),
        help="Path to save the script",
    ),
    force: bool = typer.Option(
        os.environ.get("SUPERVAIZER_FORCE_INSTALL", "False").lower() == "true",
        help="Overwrite existing file",
    ),
) -> None:
    """Create a draft supervaizer_control_example.py script."""
    # Check if file already exists
    if os.path.exists(output_path) and not force:
        console.print(f"[bold red]Error:[/] {output_path} already exists")
        console.print("Use [bold]--force[/] to overwrite it")
        sys.exit(1)

    # Get the path to the examples directory
    examples_dir = Path(__file__).parent / "examples"
    example_file = examples_dir / "controller-template.py"

    if not example_file.exists():
        console.print("[bold red]Error:[/] Example file not found")
        sys.exit(1)

    # Copy the example file to the output path
    shutil.copy(example_file, output_path)
    console.print(
        f"[bold green]Success:[/] Created an example file at [bold blue]{output_path}[/]"
    )
    console.print("1. Edit this file to configure your agent(s)")
    console.print(
        "2. (Optional) Get your API from [bold]supervaizer.com and setup your environment variables"
    )
    console.print(
        "3. Run [bold]supervaizer start[/] to start the supervaizer controller"
    )
    console.print("4. Open [bold]http://localhost:8000/docs[/] to explore the API")
    sys.exit(0)


if __name__ == "__main__":
    app()
