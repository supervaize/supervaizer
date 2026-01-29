# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Deployment CLI Commands

This module contains the main CLI commands for the deploy subcommand.
"""

import importlib.util
import typer
from pathlib import Path
from rich.console import Console

from supervaizer.deploy.commands.plan import plan_deployment
from supervaizer.deploy.commands.up import deploy_up
from supervaizer.deploy.commands.down import deploy_down
from supervaizer.deploy.commands.status import deploy_status
from supervaizer.deploy.commands.local import local_docker
from supervaizer.deploy.commands.clean import (
    clean_deployment,
    clean_docker_artifacts,
    clean_state_only,
)

console = Console()

# Create the deploy subcommand
deploy_app = typer.Typer(
    name="deploy",
    help="Deploy Supervaizer agents to cloud platforms. Python dependencies must be managed in pyproject.toml file.",
    no_args_is_help=True,
)

# Common parameters
platform_option = typer.Option(
    None,
    "--platform",
    "-p",
    help="Target platform (cloud-run|aws-app-runner|do-app-platform)",
)
name_option = typer.Option(
    ...,
    "--name",
    "-n",
    help="Service name. Required for local command.",
    prompt="Service name (e.g. my-service)",
)
env_option = typer.Option("dev", "--env", "-e", help="Environment (dev|staging|prod)")
region_option = typer.Option(None, "--region", "-r", help="Provider region")
project_id_option = typer.Option(
    None, "--project-id", help="GCP project / AWS account / DO project"
)
verbose_option = typer.Option(False, "--verbose", "-v", help="Show detailed output")

# Additional parameters for specific commands
image_option = typer.Option(None, "--image", help="Container image (registry/repo:tag)")
port_option = typer.Option(8000, "--port", help="Application port")
generate_api_key_option = typer.Option(
    False, "--generate-api-key", help="Generate secure API key"
)
generate_rsa_option = typer.Option(
    False, "--generate-rsa", help="Generate RSA private key"
)
yes_option = typer.Option(False, "--yes", "-y", help="Non-interactive mode")
no_rollback_option = typer.Option(False, "--no-rollback", help="Keep failed revision")
timeout_option = typer.Option(300, "--timeout", help="Deployment timeout in seconds")
docker_files_only_option = typer.Option(
    False, "--docker-files-only", help="Only generate Docker files without running them"
)

controller_file_option = typer.Option(
    "supervaizer_control.py",
    "--controller-file",
    help="Controller file name (default: supervaizer_control.py)",
)

# Clean command options
force_option = typer.Option(False, "--force", "-f", help="Skip confirmation prompts")
verbose_option_clean = typer.Option(
    False, "--verbose", "-v", help="Show detailed output"
)


def _check_pyproject_toml() -> Path:
    """Check if pyproject.toml exists in current directory or parent directories."""
    current_dir = Path.cwd()

    # Check current directory first
    pyproject_path = current_dir / "pyproject.toml"
    if pyproject_path.exists():
        return current_dir

    # Check parent directories up to 3 levels
    for _ in range(3):
        current_dir = current_dir.parent
        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.exists():
            return current_dir

    # If not found, show help and exit
    _show_pyproject_toml_help()
    raise typer.Exit(1)


def _show_pyproject_toml_help() -> None:
    """Show help message when pyproject.toml is not found."""
    console.print("[bold red]Error:[/] pyproject.toml file not found")
    console.print(
        "The supervaizer deploy command must be run from a directory containing pyproject.toml"
    )
    console.print("or from a subdirectory of such a directory.")
    console.print("\n[bold]Current directory:[/] " + str(Path.cwd()))
    console.print("\n[bold]Please ensure:[/]")
    console.print("  • You are in the correct project directory")
    console.print("  • The pyproject.toml file exists in the project root")
    console.print("  • Python dependencies are properly defined in pyproject.toml")
    console.print("\n[bold]Available deploy commands:[/]")
    console.print(
        "  • [bold]supervaizer deploy local[/] - Test deployment locally using Docker Compose"
    )
    console.print("  • [bold]supervaizer deploy up[/] - Deploy or update the service")
    console.print(
        "  • [bold]supervaizer deploy down[/] - Destroy the service and cleanup resources"
    )
    console.print(
        "  • [bold]supervaizer deploy status[/] - Show deployment status and health information"
    )
    console.print(
        "  • [bold]supervaizer deploy plan[/] - Plan deployment changes without applying them"
    )
    console.print(
        "  • [bold]supervaizer deploy clean[/] - Clean up deployment artifacts and generated files"
    )
    console.print(
        "\nUse [bold]supervaizer deploy <command> --help[/] for more information about each command."
    )


@deploy_app.callback()
def deploy_callback() -> None:
    """Deploy Supervaizer agents to cloud platforms."""
    # This callback is called when no subcommand is provided
    # The no_args_is_help=True will automatically show help
    pass


def _check_platform_required(platform: str, command_name: str) -> None:
    """Check if platform is provided and show helpful error if not."""
    if platform is None:
        console.print("[bold red]Error:[/] --platform is required")
        console.print(
            f"Use [bold]supervaizer deploy {command_name} --help[/] for more information"
        )
        raise typer.Exit(1)


@deploy_app.command(no_args_is_help=True)
def plan(
    platform: str = platform_option,
    name: str = name_option,
    env: str = env_option,
    region: str = region_option,
    project_id: str = project_id_option,
    verbose: bool = verbose_option,
) -> None:
    """Plan deployment changes without applying them."""
    # Check if deploy extras are installed (e.g., docker, cloud SDKs)
    if importlib.util.find_spec("docker") is None:
        console.print(
            "[bold red]Error:[/] 'deploy' extra requirements are not installed. "
            "Install them with: [bold]pip install supervaizer[deploy][/]"
        )
        raise typer.Exit(1)
    _check_platform_required(platform, "plan")
    source_dir = _check_pyproject_toml()
    plan_deployment(platform, name, env, region, project_id, verbose, source_dir)


@deploy_app.command(no_args_is_help=True)
def up(
    platform: str = platform_option,
    name: str = name_option,
    env: str = env_option,
    region: str = region_option,
    project_id: str = project_id_option,
    image: str = image_option,
    port: int = port_option,
    generate_api_key: bool = generate_api_key_option,
    generate_rsa: bool = generate_rsa_option,
    yes: bool = yes_option,
    no_rollback: bool = no_rollback_option,
    timeout: int = timeout_option,
    verbose: bool = verbose_option,
) -> None:
    """Deploy or update the service."""
    _check_platform_required(platform, "up")
    source_dir = _check_pyproject_toml()
    deploy_up(
        platform,
        name,
        env,
        region,
        project_id,
        image,
        port,
        generate_api_key,
        generate_rsa,
        yes,
        no_rollback,
        timeout,
        verbose,
        source_dir,
    )


@deploy_app.command(no_args_is_help=True)
def down(
    platform: str = platform_option,
    name: str = name_option,
    env: str = env_option,
    region: str = region_option,
    project_id: str = project_id_option,
    yes: bool = yes_option,
    verbose: bool = verbose_option,
) -> None:
    """Destroy the service and cleanup resources."""
    _check_platform_required(platform, "down")
    source_dir = _check_pyproject_toml()
    deploy_down(platform, name, env, region, project_id, yes, verbose, source_dir)


@deploy_app.command(no_args_is_help=True)
def status(
    platform: str = platform_option,
    name: str = name_option,
    env: str = env_option,
    region: str = region_option,
    project_id: str = project_id_option,
    verbose: bool = verbose_option,
) -> None:
    """Show deployment status and health information."""
    _check_platform_required(platform, "status")
    source_dir = _check_pyproject_toml()
    deploy_status(platform, name, env, region, project_id, verbose, source_dir)


@deploy_app.command()
def local(
    name: str = name_option,
    env: str = env_option,
    port: int = port_option,
    generate_api_key: bool = generate_api_key_option,
    generate_rsa: bool = generate_rsa_option,
    timeout: int = timeout_option,
    verbose: bool = verbose_option,
    docker_files_only: bool = docker_files_only_option,
    controller_file: str = controller_file_option,
) -> None:
    """Test deployment locally using Docker Compose. Requires --name."""
    source_dir = _check_pyproject_toml()
    local_docker(
        name,
        env,
        port,
        generate_api_key,
        generate_rsa,
        timeout,
        verbose,
        docker_files_only,
        str(source_dir),
        controller_file,
    )


@deploy_app.command()
def clean(
    force: bool = force_option,
    verbose: bool = verbose_option_clean,
    docker_only: bool = typer.Option(
        False, "--docker-only", help="Clean only Docker artifacts"
    ),
    state_only: bool = typer.Option(
        False, "--state-only", help="Clean only deployment state"
    ),
) -> None:
    """Clean up deployment artifacts and generated files."""
    _check_pyproject_toml()

    if docker_only and state_only:
        console.print(
            "[bold red]Error:[/] Cannot use both --docker-only and --state-only"
        )
        raise typer.Exit(1)

    if docker_only:
        clean_docker_artifacts(force=force, verbose=verbose)
    elif state_only:
        clean_state_only(force=force, verbose=verbose)
    else:
        clean_deployment(force=force, verbose=verbose)
