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

from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import sys
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import typer
from click.core import ParameterSource
from rich.console import Console
from rich.prompt import Confirm

from supervaizer.__version__ import VERSION
from supervaizer.deploy.cli import deploy_app
from supervaizer.studio_login import (
    DEFAULT_API_URL,
    StudioLoginError,
    ensure_env_file_writable,
    env_values,
    request_device_code,
    wait_for_credentials,
    write_env_file,
)
from supervaizer.utils.version_check import check_is_latest_version

if TYPE_CHECKING:
    from supervaizer.server import Server

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


def _env_flag_is_true(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("true", "1", "yes")


def _cli_set_parameter(ctx: typer.Context, param: str) -> bool:
    """True when the user passed `param` on the command line (not a Typer/Click default)."""
    source = ctx.get_parameter_source(param)
    if source is None:
        return False
    # Typer may resolve ParameterSource from a different Click install than ours.
    return getattr(source, "name", None) == ParameterSource.COMMANDLINE.name


def _apply_start_environment(
    ctx: typer.Context,
    *,
    host: str,
    port: int,
    environment: str,
    persist: bool,
    log_level: str,
    debug: bool,
    reload: bool,
    public_url: str | None,
) -> None:
    """Apply start settings: explicit CLI beats env file and shell; file beats Typer defaults."""

    def set_env(param: str, env_key: str, value: str) -> None:
        if _cli_set_parameter(ctx, param):
            os.environ[env_key] = value
        elif env_key not in os.environ:
            os.environ[env_key] = value

    set_env("host", "SUPERVAIZER_HOST", host)
    set_env("port", "SUPERVAIZER_PORT", str(port))
    set_env("environment", "SUPERVAIZER_ENVIRONMENT", environment)
    set_env("persist", "SUPERVAIZER_PERSISTENCE", str(persist).lower())
    set_env("log_level", "SUPERVAIZER_LOG_LEVEL", log_level)
    set_env("debug", "SUPERVAIZER_DEBUG", str(debug))
    set_env("reload", "SUPERVAIZER_RELOAD", str(reload))
    if public_url is not None:
        set_env("public_url", "SUPERVAIZER_PUBLIC_URL", public_url)
    if debug:
        console.print(
            "[bold yellow]Warning:[/] --debug is deprecated and will be removed. "
            "Set debug=True on the Server in your control script."
        )
    if reload:
        console.print(
            "[bold yellow]Warning:[/] --reload is deprecated and will be removed. "
            "The Server does not support auto-reload."
        )


def _sync_start_runtime_from_environ() -> tuple[str, int, str, bool, str, bool]:
    host = os.environ["SUPERVAIZER_HOST"]
    port = int(os.environ["SUPERVAIZER_PORT"])
    environment = os.environ["SUPERVAIZER_ENVIRONMENT"]
    persist = _env_flag_is_true("SUPERVAIZER_PERSISTENCE")
    log_level = os.environ["SUPERVAIZER_LOG_LEVEL"]
    debug = _env_flag_is_true("SUPERVAIZER_DEBUG")
    return host, port, environment, persist, log_level, debug


@app.command()
def start(
    ctx: typer.Context,
    public_url: str | None = typer.Option(
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
    # Deprecated: kept so existing commands still run. Set debug=True on the
    # Server in the control script instead.
    debug: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_DEBUG") or "False").lower() == "true",
        hidden=True,
    ),
    reload: bool = typer.Option(
        (os.environ.get("SUPERVAIZER_RELOAD") or "False").lower() == "true",
        hidden=True,
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
    env_file: str | None = typer.Option(
        None,
        "--env-file",
        help="Load variables from this file before the start, for example the file "
        "that `supervaizer login` wrote. Values already exported in the shell keep "
        "their value. Explicit start flags override the file. Other file values override "
        "command defaults.",
    ),
    script_path: str | None = typer.Argument(
        None,
        help="Path to the supervaizer_control.py script",
    ),
) -> None:
    """Start the Supervaizer Controller server."""
    if env_file is not None:
        if not os.path.isfile(env_file):
            console.print(f"[bold red]Error:[/] environment file {env_file} not found")
            sys.exit(1)
        _load_environment_file(env_file)
    _apply_start_environment(
        ctx,
        host=host,
        port=port,
        environment=environment,
        persist=persist,
        log_level=log_level,
        debug=debug,
        reload=reload,
        public_url=public_url,
    )
    host, port, environment, persist, log_level, debug = _sync_start_runtime_from_environ()
    explicit_public_url = _cli_set_parameter(ctx, "public_url")
    public_url = os.environ.get("SUPERVAIZER_PUBLIC_URL") or None
    if local:
        _load_environment_file(os.path.join(os.getcwd(), ".env"))
        host, public_url = _prepare_local_start(
            host, port, public_url, explicit_public_url
        )
    else:
        public_url = _resolve_start_public_url(public_url, explicit_public_url)

    script_path, use_fallback = _resolve_start_script(script_path, local)
    if not local:
        console.print(f"[bold green]Starting Supervaizer Controller v{VERSION}[/]")
    if use_fallback:
        _launch_local_fallback(host, port, debug, environment, log_level)
        return
    _launch_control_script(script_path, host, port, public_url, log_level)


def _load_environment_file(env_file: str) -> None:
    """Set the variables of the file that are not set yet. A missing file is skipped."""
    if os.path.isfile(env_file):
        with open(env_file) as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip().removeprefix("export ").strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value


def _prepare_local_start(
    host: str, port: int, public_url: str | None, explicit_public_url: bool
) -> tuple[str, str | None]:
    os.environ["SUPERVAIZER_LOCAL_MODE"] = "true"
    # The local development API key requires a loopback default.
    if host in ("0.0.0.0", "::", ""):
        host = "127.0.0.1"
        os.environ["SUPERVAIZER_HOST"] = host
    if not explicit_public_url:
        public_url = f"http://{host}:{port}"
        os.environ["SUPERVAIZER_PUBLIC_URL"] = public_url
    console.print(
        f"[bold green]Starting Supervaizer Controller v{VERSION}[/] (local test mode)"
    )
    console.print("[dim]No Studio registration — agents run locally[/]")
    api_key_display = os.environ.get("SUPERVAIZER_API_KEY") or "local-dev"
    console.print(
        f"[bold]API:[/] {public_url}/docs  [bold]Admin/Workbench:[/] {public_url}/manage/"
    )
    console.print(f"[dim]API key for /manage: {api_key_display}[/]")
    return host, public_url


def _resolve_start_public_url(
    public_url: str | None, explicit_public_url: bool
) -> str | None:
    if not explicit_public_url:
        public_url = os.environ.get("SUPERVAIZER_PUBLIC_URL") or None
        if public_url is not None:
            os.environ["SUPERVAIZER_PUBLIC_URL"] = public_url
    return public_url


def _resolve_start_script(script_path: str | None, local: bool) -> tuple[str, bool]:
    if script_path is None:
        script_path = (
            os.environ.get("SUPERVAIZER_SCRIPT_PATH") or "supervaizer_control.py"
        )
    if not os.path.exists(script_path):
        if local:
            return script_path, True
        console.print(f"[bold red]Error:[/] {script_path} not found")
        console.print("Run [bold]supervaizer scaffold[/] to create a default script")
        sys.exit(1)
    return script_path, False


def _controller_type() -> type[Server]:
    # Keep the controller runtime out of version and scaffold command startup.
    from supervaizer.server import Server

    return Server


def _launch_local_fallback(
    host: str, port: int, debug: bool, environment: str, log_level: str
) -> None:
    console.print("[dim]No control script found — using built-in Hello World agent[/]")
    server = _controller_type()(
        agents=[],
        supervisor_account=None,
        a2a_endpoints=True,
        admin_interface=True,
        host=host,
        port=port,
        public_url=os.environ.get("SUPERVAIZER_PUBLIC_URL"),
        debug=debug,
        environment=environment,
        api_key=None,
    )
    server.launch(log_level=log_level)


def _launch_control_script(
    script_path: str, host: str, port: int, public_url: str | None, log_level: str
) -> None:
    console.print(f"Loading configuration from [bold]{script_path}[/]")
    spec = importlib.util.spec_from_file_location("supervaizer_control", script_path)
    if spec is None or spec.loader is None:
        console.print(f"[bold red]Error:[/] Could not load {script_path} as a module")
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    script_dir = os.path.dirname(os.path.abspath(script_path))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec.loader.exec_module(module)

    server_type = _controller_type()
    server_instance: Server | None = None
    for attr_name in dir(module):
        obj = getattr(module, attr_name, None)
        if isinstance(obj, server_type):
            server_instance = obj
            break
    if server_instance is None:
        console.print(
            "[bold red]Error:[/] No Server instance found in the control script. "
            "Define a variable of type supervaizer.Server in your script."
        )
        sys.exit(1)
    server_instance.host = host
    server_instance.port = port
    if public_url is not None:
        server_instance.public_url = public_url
    server_instance.launch(log_level=log_level)


@app.command()
def login(
    api_url: str = typer.Option(
        os.environ.get("SUPERVAIZE_API_URL") or DEFAULT_API_URL,
        "--api-url",
        help="Address of the Studio API",
    ),
    env_file: str = typer.Option(
        ".env",
        "--env-file",
        help="File that receives the Studio credentials. Keep it out of git.",
    ),
    browser: bool = typer.Option(
        True, "--browser/--no-browser", help="Open the approval page in the browser"
    ),
) -> None:
    """Log in to Supervaize Studio in the browser and save the credentials of the workspace."""
    env_path = Path(env_file)
    try:
        ensure_env_file_writable(env_path)
    except StudioLoginError as exc:
        console.print(f"Error: {exc}", style="bold red", markup=False)
        raise typer.Exit(code=1) from exc

    try:
        with httpx.Client(base_url=api_url.rstrip("/"), timeout=30) as client:
            device = request_device_code(client)
            approval_url = str(device["verification_uri_complete"])
            # Text from Studio is printed without markup.
            console.print("Open this page, sign in or sign up, and approve the login:")
            console.print(f"  {approval_url}", markup=False)
            console.print(
                f"The page must show this code: {device['user_code']}", markup=False
            )
            if browser:
                webbrowser.open(approval_url)
            console.print("Waiting for the approval in Studio...")
            credentials = wait_for_credentials(client, device)
        values = env_values(credentials)
        try:
            write_env_file(env_path, values)
        except (OSError, UnicodeError) as exc:
            raise StudioLoginError(
                "Studio issued credentials but the file could not be written. "
                "Create a new API key on the Developer page of Studio, then try again."
            ) from exc
    except (StudioLoginError, httpx.HTTPError) as exc:
        console.print(f"Error: {exc}", style="bold red", markup=False)
        raise typer.Exit(code=1) from exc

    # Names only: the value of a credential is never printed.
    console.print("[bold green]Logged in.[/]")
    console.print(f"Workspace: {credentials.get('workspace_name', '')}", markup=False)
    console.print(f"Wrote to {env_file}: {', '.join(values)}", markup=False)
    console.print(f"Make sure that git ignores {env_file}.", markup=False)
    console.print(
        f"Next: supervaizer start --env-file {env_file}  "
        "(the log then shows the page of each agent in Studio)",
        markup=False,
    )


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
                "Use [bold]--force[/] to overwrite it, or run [bold]supervaizer scaffold refresh-instructions[/]"
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
    control_file: str | None = typer.Option(
        None,
        help="Path to supervaizer_control.py (default: auto-detect)",
    ),
    output_path: str | None = typer.Option(
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
    control_file: str | None = typer.Option(
        None,
        help="Path to supervaizer_control.py (default: auto-detect)",
    ),
    output_path: str | None = typer.Option(
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
