# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Optional
from supervaizer.deploy.cli import deploy_app

import typer
from rich.console import Console
from rich.prompt import Confirm

from supervaizer.__version__ import VERSION
from supervaizer.utils.version_check import check_is_latest_version

console = Console()

# Cache version status to avoid multiple checks
_version_status: tuple[bool, str | None] | None = None


def _check_version() -> tuple[bool, str | None]:
    """Check version status, caching the result."""
    global _version_status
    if _version_status is None:
        try:
            _version_status = asyncio.run(check_is_latest_version())
        except Exception:
            # On error, assume we're on latest to avoid false positives
            _version_status = (True, None)
    return _version_status


def _display_version_info() -> None:
    """Display version information."""
    is_latest, latest_version = _check_version()
    console.print(f"Supervaizer v{VERSION}")
    if latest_version:
        if is_latest:
            console.print(f"[green]✓[/] Up to date (latest: v{latest_version})")
        else:
            console.print(f"[yellow]⚠[/] Latest available: v{latest_version}")
            console.print("Update with: [bold]pip install --upgrade supervaizer[/]")
    else:
        console.print("(Unable to check for latest version)")


def _display_update_warning() -> None:
    """Display update warning for commands."""
    is_latest, latest_version = _check_version()
    if latest_version and not is_latest:
        console.print(
            f"\n[bold yellow]⚠ Warning:[/] You are running Supervaizer v{VERSION}, "
            f"but v{latest_version} is available.\n"
            f"Update with: [bold]pip install --upgrade supervaizer[/]\n",
            style="yellow",
        )


app = typer.Typer(
    help=f"Supervaizer Controller CLI v{VERSION} - Documentation @ https://doc.supervaize.com/docs/category/supervaizer-controller"
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version information and exit"
    ),
) -> None:
    """CLI callback that runs before any command."""
    # Handle --version option
    if version:
        _display_version_info()
        raise typer.Exit()

    # Show version status in help or as warning for commands
    if ctx.invoked_subcommand is None:
        # For help display, show version status
        _display_version_info()
    else:
        # For actual commands, show warning if not latest
        _display_update_warning()


# Add deploy subcommand
app.add_typer(
    deploy_app,
    name="deploy",
    help="Deploy Supervaizer agents to cloud platforms (requires deploy extras: pip install supervaizer[deploy])",
)

# Create scaffold subcommand group
scaffold_app = typer.Typer(help="Scaffold commands for creating project files")
app.add_typer(scaffold_app, name="scaffold", invoke_without_command=True)


@app.command()
def start(
    public_url: Optional[str] = typer.Option(
        None,
        help="Public URL to use for inbound connections (reads SUPERVAIZER_PUBLIC_URL env var if not set)",
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
        help="Local test mode: run without Studio credentials, with built-in Hello World agent",
    ),
    script_path: Optional[str] = typer.Argument(
        None,
        help="Path to the supervaizer_control.py script",
    ),
) -> None:
    """Start the Supervaizer Controller server."""
    # Track whether the user explicitly passed --public-url on the CLI.
    # Since the default is None, a non-None value means it was explicit.
    user_provided_public_url = public_url is not None

    # Set CLI-provided env vars BEFORE .env loading so they take precedence.
    # The .env loader skips keys already present in os.environ.
    os.environ["SUPERVAIZER_HOST"] = host
    os.environ["SUPERVAIZER_PORT"] = str(port)
    os.environ["SUPERVAIZER_ENVIRONMENT"] = environment
    os.environ["SUPERVAIZER_PERSISTENCE"] = str(persist).lower()
    os.environ["SUPERVAIZER_LOG_LEVEL"] = log_level
    os.environ["SUPERVAIZER_DEBUG"] = str(debug)
    os.environ["SUPERVAIZER_RELOAD"] = str(reload)
    if user_provided_public_url:
        os.environ["SUPERVAIZER_PUBLIC_URL"] = public_url  # type: ignore[arg-type]

    # In local mode, load .env file so agent parameters are available.
    # CLI-provided values above won't be overridden (loader skips existing keys).
    if local:
        env_file = os.path.join(os.getcwd(), ".env")
        if os.path.isfile(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    # Don't override already-set env vars
                    if key and key not in os.environ:
                        os.environ[key] = value

    if local:
        os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
        # In local mode, force public_url to localhost unless the user
        # explicitly passed --public-url on the CLI.
        if not user_provided_public_url:
            public_url = f"http://{host}:{port}"
            os.environ["SUPERVAIZER_PUBLIC_URL"] = public_url
        console.print(
            f"[bold green]Starting Supervaizer Controller v{VERSION}[/] (local test mode)"
        )
        console.print("[dim]No Studio registration — agents run locally[/]")
        api_key_display = os.environ.get("SUPERVAIZER_API_KEY") or "local-dev"
        base = public_url
        console.print(
            f"[bold]API:[/] {base}/docs  [bold]Admin/Workbench:[/] {base}/admin/"
        )
        console.print(f"[dim]API key for /admin: {api_key_display}[/]")
    else:
        # Non-local mode: resolve public_url from env var if not explicitly provided
        if not user_provided_public_url:
            public_url = os.environ.get("SUPERVAIZER_PUBLIC_URL") or None
            if public_url is not None:
                os.environ["SUPERVAIZER_PUBLIC_URL"] = public_url

    if script_path is None:
        script_path = (
            os.environ.get("SUPERVAIZER_SCRIPT_PATH") or "supervaizer_control.py"
        )

    use_fallback_server = False
    if not os.path.exists(script_path):
        if local:
            # Use fallback: launch a Server with Hello World agent directly
            use_fallback_server = True
        else:
            console.print(f"[bold red]Error:[/] {script_path} not found")
            console.print(
                "Run [bold]supervaizer scaffold[/] to create a default script"
            )
            sys.exit(1)

    if not local:
        console.print(f"[bold green]Starting Supervaizer Controller v{VERSION}[/]")

    if use_fallback_server:
        # No control script found — create a minimal Server with Hello World agent
        console.print(
            "[dim]No control script found — using built-in Hello World agent[/]"
        )
        from supervaizer.server import Server as _Server

        server_instance = _Server(
            agents=[],
            supervisor_account=None,
            a2a_endpoints=True,
            admin_interface=True,
            host=host,
            port=port,
            public_url=os.environ.get("SUPERVAIZER_PUBLIC_URL"),
            debug=debug,
            reload=reload,
            environment=environment,
            api_key=None,
        )
        server_instance.launch(log_level=log_level)
        return

    console.print(f"Loading configuration from [bold]{script_path}[/]")

    # Import the control script as a module and auto-launch the Server if needed.
    # This allows scripts that only *define* a Server (without an `if __name__`
    # guard calling launch()) to still work via `supervaizer start`.
    import importlib.util

    spec = importlib.util.spec_from_file_location("supervaizer_control", script_path)
    if spec is None or spec.loader is None:
        console.print(f"[bold red]Error:[/] Could not load {script_path} as a module")
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)

    # Add the script's directory to sys.path so relative imports work
    script_dir = os.path.dirname(os.path.abspath(script_path))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    spec.loader.exec_module(module)

    # Look for a Server instance that hasn't been launched yet.
    # If the script already called launch() (via __main__ guard), uvicorn would
    # be running and we'd never reach this point. So if we're here, we need to
    # find the Server and call launch().
    from supervaizer.server import Server as _Server

    server_instance = None
    for attr_name in dir(module):
        obj = getattr(module, attr_name, None)
        if isinstance(obj, _Server):
            server_instance = obj
            break

    if server_instance is None:
        console.print(
            "[bold red]Error:[/] No Server instance found in the control script. "
            "Define a variable of type supervaizer.Server in your script."
        )
        sys.exit(1)

    # Override Server attributes with CLI values.
    # Python default arguments (os.getenv in Server.__init__) are evaluated at
    # class definition time, so if the module was already imported before the CLI
    # set env vars, the Server instance has stale defaults.
    server_instance.host = host
    server_instance.port = port
    if public_url is not None:
        server_instance.public_url = public_url

    server_instance.launch(log_level=log_level)


def _create_instructions_file(
    output_dir: Path, force: bool = False, silent: bool = False
) -> Path:
    """Create supervaize_instructions.html file in the given directory.

    Args:
        output_dir: Directory where to create the instructions file
        force: If True, overwrite existing file
        silent: If True, don't show warnings if file already exists (just skip)
    """
    instructions_path = output_dir / "supervaize_instructions.html"

    # Check if file already exists
    if instructions_path.exists() and not force:
        if not silent:
            console.print(
                f"[bold yellow]Warning:[/] {instructions_path} already exists"
            )
            console.print(
                "Use [bold]--force[/] to overwrite it, or run [bold]supervaizer refresh-instructions[/]"
            )
        return instructions_path

    # Get the path to the admin templates directory
    admin_templates_dir = Path(__file__).parent / "admin" / "templates"
    template_file = admin_templates_dir / "supervaize_instructions.html"

    if not template_file.exists():
        console.print("[bold red]Error:[/] Template file not found")
        sys.exit(1)

    # Copy the template file
    shutil.copy(template_file, instructions_path)
    return instructions_path


@scaffold_app.callback(invoke_without_command=True)
def scaffold(
    ctx: typer.Context,
    output_path: str = typer.Option(
        os.environ.get("SUPERVAIZER_OUTPUT_PATH", "supervaizer_control.py"),
        help="Path to save the script",
    ),
    force: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_FORCE_INSTALL") or "False").lower() == "true",
        help="Overwrite existing file",
    ),
) -> None:
    """Create a draft supervaizer_control.py script and supervaize_instructions.html."""
    # Only run if no subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return
    # Check if file already exists
    if os.path.exists(output_path) and not force:
        console.print(f"[bold red]Error:[/] {output_path} already exists")
        console.print("Use [bold]--force[/] to overwrite it")
        sys.exit(1)

    # Get the path to the examples directory
    examples_dir = Path(__file__).parent / "examples"
    example_file = examples_dir / "controller_template.py"

    if not example_file.exists():
        console.print("[bold red]Error:[/] Example file not found")
        sys.exit(1)

    # Copy the example file to the output path
    shutil.copy(example_file, output_path)
    console.print(
        f"[bold green]Success:[/] Created an example file at [bold blue]{output_path}[/]"
    )

    # Create instructions file in the same directory (silently if it already exists)
    output_dir = Path(output_path).parent
    instructions_path = output_dir / "supervaize_instructions.html"
    instructions_existed = instructions_path.exists()
    _create_instructions_file(output_dir, force=force, silent=True)
    # Only show success message if we actually created the file (didn't exist before or force was used)
    if not instructions_existed or force:
        console.print(
            f"[bold green]Success:[/] Created instructions template at [bold blue]{instructions_path}[/]"
        )

    console.print(
        "1. Copy this file to [bold]supervaizer_control.py[/] and edit it to configure your agent(s)"
    )
    console.print(
        "2. Customize [bold]supervaize_instructions.html[/] to match your agent's documentation"
    )
    console.print(
        "3. (Optional) Get your API from [bold]supervaizer.com and setup your environment variables"
    )
    console.print(
        "4. Run [bold]supervaizer start[/] to start the supervaizer controller"
    )
    console.print("5. Open [bold]http://localhost:8000/docs[/] to explore the API")
    sys.exit(0)


@scaffold_app.command(name="instructions")
def scaffold_instructions(
    control_file: Optional[str] = typer.Option(
        None,
        help="Path to supervaizer_control.py (default: auto-detect)",
    ),
    output_path: Optional[str] = typer.Option(
        None,
        help="Path to save supervaize_instructions.html (default: same directory as control file)",
    ),
    force: bool = typer.Option(
        False,
        help="Overwrite existing file",
    ),
) -> None:
    """Create supervaize_instructions.html file."""
    # Determine control file path
    if control_file is None:
        control_file = (
            os.environ.get("SUPERVAIZER_SCRIPT_PATH") or "supervaizer_control.py"
        )

    control_path = Path(control_file)

    # Determine output directory
    if output_path is None:
        output_dir = control_path.parent
        instructions_path = output_dir / "supervaize_instructions.html"
    else:
        instructions_path = Path(output_path)
        output_dir = instructions_path.parent

    # Check if control file exists (informational)
    if not control_path.exists():
        console.print(f"[bold yellow]Warning:[/] Control file {control_file} not found")
        console.print("Creating instructions file anyway...")

    # Create instructions file
    _create_instructions_file(output_dir, force=force)
    console.print(
        f"[bold green]Success:[/] Created instructions template at [bold blue]{instructions_path}[/]"
    )
    console.print(
        "Customize this file to match your agent's documentation and instructions."
    )


@scaffold_app.command(name="refresh-instructions")
def refresh_instructions(
    control_file: Optional[str] = typer.Option(
        None,
        help="Path to supervaizer_control.py (default: auto-detect)",
    ),
    output_path: Optional[str] = typer.Option(
        None,
        help="Path to supervaize_instructions.html (default: same directory as control file)",
    ),
    force: bool = typer.Option(
        False,
        help="Skip confirmation prompt",
    ),
) -> None:
    """Refresh/update supervaize_instructions.html file."""
    # Determine control file path
    if control_file is None:
        control_file = (
            os.environ.get("SUPERVAIZER_SCRIPT_PATH") or "supervaizer_control.py"
        )

    control_path = Path(control_file)

    # Determine output path
    if output_path is None:
        output_dir = control_path.parent
        instructions_path = output_dir / "supervaize_instructions.html"
    else:
        instructions_path = Path(output_path)

    # Check if instructions file exists
    if instructions_path.exists():
        if not force:
            console.print(
                f"[bold yellow]Warning:[/] {instructions_path} already exists"
            )
            if not Confirm.ask(
                "Delete existing file and create a fresh template?",
                default=False,
            ):
                console.print("[bold]Cancelled.[/]")
                sys.exit(0)

        # Delete existing file
        instructions_path.unlink()
        console.print(f"[bold]Deleted[/] existing {instructions_path}")

    # Create new instructions file
    output_dir = instructions_path.parent
    _create_instructions_file(output_dir, force=True)
    console.print(
        f"[bold green]Success:[/] Created fresh instructions template at [bold blue]{instructions_path}[/]"
    )
    console.print(
        "Customize this file to match your agent's documentation and instructions."
    )


if __name__ == "__main__":
    app()
