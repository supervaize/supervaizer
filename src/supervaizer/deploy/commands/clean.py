# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Clean Command

This module provides functionality to clean up deployment artifacts and generated files.
"""

import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm

from supervaizer.common import log

console = Console()


def clean_deployment(
    deployment_dir: Optional[Path] = None,
    force: bool = False,
    verbose: bool = False,
) -> None:
    """
    Clean up deployment artifacts and generated files.

    Args:
        deployment_dir: Path to deployment directory (default: .deployment)
        force: Skip confirmation prompt
        verbose: Show detailed output
    """
    if deployment_dir is None:
        deployment_dir = Path(".deployment")

    # Check if deployment directory exists
    if not deployment_dir.exists():
        console.print(f"[yellow]No deployment directory found at {deployment_dir}[/]")
        console.print("Nothing to clean up.")
        return

    # Show what will be deleted
    console.print(f"[bold blue]Cleaning deployment directory: {deployment_dir}[/]")

    if verbose:
        console.print("\n[bold]Contents to be deleted:[/]")
        try:
            for item in deployment_dir.rglob("*"):
                if item.is_file():
                    console.print(f"  📄 {item.relative_to(deployment_dir)}")
                elif item.is_dir():
                    console.print(f"  📁 {item.relative_to(deployment_dir)}/")
        except Exception as e:
            log.debug(f"Error listing directory contents: {e}")

    # Calculate total size
    total_size = 0
    file_count = 0
    try:
        for item in deployment_dir.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
                file_count += 1
    except Exception as e:
        log.debug(f"Error calculating directory size: {e}")

    if file_count > 0:
        size_mb = total_size / (1024 * 1024)
        console.print(f"\n[bold]Summary:[/] {file_count} files, {size_mb:.2f} MB")

    # Confirmation prompt (unless forced)
    if not force:
        console.print(
            "\n[yellow]This will permanently delete all deployment artifacts.[/]"
        )
        console.print("This includes:")
        console.print("  • Generated Docker files")
        console.print("  • Deployment state")
        console.print("  • Configuration files")
        console.print("  • Logs and debug information")

        if not Confirm.ask("\n[bold red]Are you sure you want to continue?[/]"):
            console.print("[yellow]Cleanup cancelled.[/]")
            return

    # Perform cleanup
    try:
        console.print(f"\n[bold]Deleting {deployment_dir}...[/]")
        shutil.rmtree(deployment_dir)
        console.print("[green]✓[/] Deployment directory cleaned successfully")

        # Show what was cleaned
        console.print("\n[bold green]Cleanup completed![/]")
        console.print(f"Removed: {deployment_dir}")
        if file_count > 0:
            console.print(f"Files deleted: {file_count}")
            console.print(f"Space freed: {size_mb:.2f} MB")

        # Show next steps
        console.print("\n[bold]Next steps:[/]")
        console.print(
            "  • Run [bold]supervaizer deploy local[/] to regenerate files for local testing"
        )
        console.print(
            "  • Run [bold]supervaizer deploy up[/] to deploy to cloud platforms"
        )
        console.print(
            "  • Run [bold]supervaizer deploy plan[/] to plan new deployments"
        )

    except PermissionError as e:
        console.print(
            f"[bold red]Error:[/] Permission denied while deleting {deployment_dir}"
        )
        console.print(
            "Make sure no processes are using files in the deployment directory."
        )
        console.print(f"Details: {e}")
        raise RuntimeError(f"Failed to clean deployment directory: {e}") from e
    except Exception as e:
        console.print("[bold red]Error:[/] Failed to clean deployment directory")
        console.print(f"Details: {e}")
        raise RuntimeError(f"Failed to clean deployment directory: {e}") from e


def clean_docker_artifacts(
    force: bool = False,
    verbose: bool = False,
) -> None:
    """
    Clean up Docker-related artifacts only.

    Args:
        force: Skip confirmation prompt
        verbose: Show detailed output
    """
    deployment_dir = Path(".deployment")

    if not deployment_dir.exists():
        console.print("[yellow]No deployment directory found[/]")
        return

    # List of Docker-related files to clean
    docker_files = [
        "Dockerfile",
        ".dockerignore",
        "docker-compose.yml",
        "docker-compose.yaml",
    ]

    docker_dirs = [
        "logs",
    ]

    files_to_delete = []
    dirs_to_delete = []

    # Find files to delete
    for file_name in docker_files:
        file_path = deployment_dir / file_name
        if file_path.exists():
            files_to_delete.append(file_path)

    # Find directories to delete
    for dir_name in docker_dirs:
        dir_path = deployment_dir / dir_name
        if dir_path.exists() and dir_path.is_dir():
            dirs_to_delete.append(dir_path)

    if not files_to_delete and not dirs_to_delete:
        console.print("[yellow]No Docker artifacts found to clean[/]")
        return

    # Show what will be deleted
    console.print("[bold blue]Cleaning Docker artifacts[/]")

    if verbose:
        console.print("\n[bold]Files to be deleted:[/]")
        for file_path in files_to_delete:
            console.print(f"  📄 {file_path.relative_to(deployment_dir)}")

        console.print("\n[bold]Directories to be deleted:[/]")
        for dir_path in dirs_to_delete:
            console.print(f"  📁 {dir_path.relative_to(deployment_dir)}/")

    # Confirmation prompt (unless forced)
    if not force:
        console.print("\n[yellow]This will delete Docker-related files only.[/]")
        console.print("Deployment state and configuration will be preserved.")

        if not Confirm.ask("\n[bold red]Continue with Docker cleanup?[/]"):
            console.print("[yellow]Cleanup cancelled.[/]")
            return

    # Perform cleanup
    deleted_count = 0

    try:
        # Delete files
        for file_path in files_to_delete:
            if verbose:
                console.print(f"Deleting {file_path.relative_to(deployment_dir)}...")
            file_path.unlink()
            deleted_count += 1

        # Delete directories
        for dir_path in dirs_to_delete:
            if verbose:
                console.print(f"Deleting {dir_path.relative_to(deployment_dir)}/...")
            shutil.rmtree(dir_path)
            deleted_count += 1

        console.print("[green]✓[/] Docker artifacts cleaned successfully")
        console.print(f"Deleted {deleted_count} items")

    except Exception as e:
        console.print("[bold red]Error:[/] Failed to clean Docker artifacts")
        console.print(f"Details: {e}")
        raise RuntimeError(f"Failed to clean Docker artifacts: {e}") from e


def clean_state_only(
    force: bool = False,
    verbose: bool = False,
) -> None:
    """
    Clean up deployment state only, preserving generated files.

    Args:
        force: Skip confirmation prompt
        verbose: Show detailed output
    """
    deployment_dir = Path(".deployment")

    if not deployment_dir.exists():
        console.print("[yellow]No deployment directory found[/]")
        return

    # State-related files to clean
    state_files = [
        "state.json",
        "config.yaml",
        "config.yml",
    ]

    files_to_delete = []

    # Find state files to delete
    for file_name in state_files:
        file_path = deployment_dir / file_name
        if file_path.exists():
            files_to_delete.append(file_path)

    if not files_to_delete:
        console.print("[yellow]No state files found to clean[/]")
        return

    # Show what will be deleted
    console.print("[bold blue]Cleaning deployment state[/]")

    if verbose:
        console.print("\n[bold]State files to be deleted:[/]")
        for file_path in files_to_delete:
            console.print(f"  📄 {file_path.relative_to(deployment_dir)}")

    # Confirmation prompt (unless forced)
    if not force:
        console.print("\n[yellow]This will delete deployment state only.[/]")
        console.print("Generated Docker files will be preserved.")
        console.print("You will need to redeploy to recreate the state.")

        if not Confirm.ask("\n[bold red]Continue with state cleanup?[/]"):
            console.print("[yellow]Cleanup cancelled.[/]")
            return

    # Perform cleanup
    try:
        for file_path in files_to_delete:
            if verbose:
                console.print(f"Deleting {file_path.relative_to(deployment_dir)}...")
            file_path.unlink()

        console.print("[green]✓[/] Deployment state cleaned successfully")
        console.print(f"Deleted {len(files_to_delete)} state files")

    except Exception as e:
        console.print("[bold red]Error:[/] Failed to clean deployment state")
        console.print(f"Details: {e}")
        raise RuntimeError(f"Failed to clean deployment state: {e}") from e
