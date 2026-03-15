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

app = typer.Typer(
    help=f"Supervaizer Controller CLI v{VERSION} - Documentation @ https://docs.supervaize.com"
)
console = Console()


@app.command()
def start(
    public_url: Optional[str] = typer.Option(
        os.environ.get("SUPERVAIZER_PUBLIC_URL") or None,
        help="Public URL to use for inbound connections",
    ),
    host: str = typer.Option(
        os.environ.get("SUPERVAIZER_HOST", "0.0.0.0"), help="Host to bind the server to"
    ),
    port: int = typer.Option(
        int(os.environ.get("SUPERVAIZER_PORT") or "8000"),
        help="Port to bind the server to",
    ),
    log_level: str = typer.Option(
        os.environ.get("SUPERVAIZER_LOG_LEVEL", "INFO"),
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    ),
    debug: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_DEBUG") or "False").lower() == "true",
        help="Enable debug mode",
    ),
    reload: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_RELOAD") or "False").lower() == "true",
        help="Enable auto-reload",
    ),
    environment: str = typer.Option(
        os.environ.get("SUPERVAIZER_ENVIRONMENT", "dev"), help="Environment name"
    ),
    persist: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_PERSISTENCE") or "false").lower()
        in ("true", "1", "yes"),
        "--persist/--no-persist",
        help="Persist data to file (default: off; set for self-hosted, off for Vercel/serverless)",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Local test mode: run without Studio credentials, with built-in Hello World agent (for agent workbench)",
    ),
    script_path: Optional[str] = typer.Argument(
        None,
        help="Path to the supervaizer_control.py script (ignored when --local)",
    ),
) -> None:
    """Start the Supervaizer Controller server."""
    # Set environment variables for the server configuration
    os.environ["SUPERVAIZER_HOST"] = host
    os.environ["SUPERVAIZER_PORT"] = str(port)
    os.environ["SUPERVAIZER_ENVIRONMENT"] = environment
    os.environ["SUPERVAIZER_LOG_LEVEL"] = log_level
    os.environ["SUPERVAIZER_DEBUG"] = str(debug)
    os.environ["SUPERVAIZER_RELOAD"] = str(reload)
    if public_url is not None:
        os.environ["SUPERVAIZER_PUBLIC_URL"] = public_url

    if local:
        console.print(f"[bold green]Starting Supervaizer Controller v{VERSION}[/] (local test mode)")
        console.print("[dim]No Studio registration — built-in Hello World agent only[/]")
        from supervaizer.examples.local_server import create_local_server

        server = create_local_server(
            host=host,
            port=port,
            public_url=public_url,
            debug=debug,
            reload=reload,
            environment=environment,
        )
        base = server.public_url or f"http://{server.host}:{server.port}"
        console.print(f"[bold]API:[/] {base}/docs  [bold]Admin/Workbench:[/] {base}/admin/")
        console.print("[dim]API key for /admin: local-dev (set SUPERVAIZER_API_KEY to override)[/]")
        server.launch(log_level=log_level)
        return

    if script_path is None:
        script_path = (
            os.environ.get("SUPERVAIZER_SCRIPT_PATH") or "supervaizer_control.py"
        )

    if not os.path.exists(script_path):
        console.print(f"[bold red]Error:[/] {script_path} not found")
        console.print("Run [bold]supervaizer scaffold[/] to create a default script")
        sys.exit(1)

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
        os.environ.get("SUPERVAIZER_OUTPUT_PATH", "supervaizer_control.py"),
        help="Path to save the script",
    ),
    force: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_FORCE_INSTALL") or "False").lower() == "true",
        help="Overwrite existing file",
    ),
) -> None:
    """Create a draft supervaizer_control.py script."""
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
    console.print(
        "1. Copy this file to [bold]supervaizer_control.py[/] and edit it to configure your agent(s)"
    )
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
