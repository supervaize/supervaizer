# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Clean Command

This module provides functionality to clean up deployment artifacts and generated files.
"""

import shutil
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from supervaizer.common import log

console = Console()


def clean_deployment(
    deployment_dir: Path | None = None,
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
        _display_directory_contents(deployment_dir)

    file_count, total_size = _measure_directory(deployment_dir)
    size_mb = total_size / (1024 * 1024)
    if file_count > 0:
        console.print(f"\n[bold]Summary:[/] {file_count} files, {size_mb:.2f} MB")

    if not _confirm_cleanup(
        force,
        (
            "\n[yellow]This will permanently delete all deployment artifacts.[/]",
            "This includes:",
            "  • Generated Docker files",
            "  • Deployment state",
            "  • Configuration files",
            "  • Logs and debug information",
        ),
        "\n[bold red]Are you sure you want to continue?[/]",
    ):
        return

    # Perform cleanup
    try:
        console.print(f"\n[bold]Deleting {deployment_dir}...[/]")
        shutil.rmtree(deployment_dir)
        _display_cleanup_result(deployment_dir, file_count, size_mb)

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

    files_to_delete = _existing_paths(
        deployment_dir,
        ("Dockerfile", ".dockerignore", "docker-compose.yml", "docker-compose.yaml"),
    )
    dirs_to_delete = [
        path for path in _existing_paths(deployment_dir, ("logs",)) if path.is_dir()
    ]

    if not files_to_delete and not dirs_to_delete:
        console.print("[yellow]No Docker artifacts found to clean[/]")
        return

    # Show what will be deleted
    console.print("[bold blue]Cleaning Docker artifacts[/]")

    if verbose:
        console.print("\n[bold]Files to be deleted:[/]")
        _display_paths(deployment_dir, files_to_delete)

        console.print("\n[bold]Directories to be deleted:[/]")
        _display_paths(deployment_dir, dirs_to_delete, directories=True)

    if not _confirm_cleanup(
        force,
        (
            "\n[yellow]This will delete Docker-related files only.[/]",
            "Deployment state and configuration will be preserved.",
        ),
        "\n[bold red]Continue with Docker cleanup?[/]",
    ):
        return

    try:
        deleted_count = _delete_paths(deployment_dir, files_to_delete, verbose)
        deleted_count += _delete_paths(
            deployment_dir, dirs_to_delete, verbose, directories=True
        )

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

    files_to_delete = _existing_paths(
        deployment_dir, ("state.json", "config.yaml", "config.yml")
    )

    if not files_to_delete:
        console.print("[yellow]No state files found to clean[/]")
        return

    # Show what will be deleted
    console.print("[bold blue]Cleaning deployment state[/]")

    if verbose:
        console.print("\n[bold]State files to be deleted:[/]")
        _display_paths(deployment_dir, files_to_delete)

    if not _confirm_cleanup(
        force,
        (
            "\n[yellow]This will delete deployment state only.[/]",
            "Generated Docker files will be preserved.",
            "You will need to redeploy to recreate the state.",
        ),
        "\n[bold red]Continue with state cleanup?[/]",
    ):
        return

    # Perform cleanup
    try:
        _delete_paths(deployment_dir, files_to_delete, verbose)

        console.print("[green]✓[/] Deployment state cleaned successfully")
        console.print(f"Deleted {len(files_to_delete)} state files")

    except Exception as e:
        console.print("[bold red]Error:[/] Failed to clean deployment state")
        console.print(f"Details: {e}")
        raise RuntimeError(f"Failed to clean deployment state: {e}") from e


def _display_directory_contents(deployment_dir: Path) -> None:
    console.print("\n[bold]Contents to be deleted:[/]")
    try:
        for item in deployment_dir.rglob("*"):
            if item.is_file():
                console.print(f"  📄 {item.relative_to(deployment_dir)}")
            elif item.is_dir():
                console.print(f"  📁 {item.relative_to(deployment_dir)}/")
    except Exception as e:
        log.debug(f"Error listing directory contents: {e}")


def _measure_directory(deployment_dir: Path) -> tuple[int, int]:
    file_count = 0
    total_size = 0
    try:
        for item in deployment_dir.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
                file_count += 1
    except Exception as e:
        # Keep counts from completed entries if a later entry cannot be read.
        log.debug(f"Error calculating directory size: {e}")
    return file_count, total_size


def _confirm_cleanup(force: bool, warnings: Sequence[str], prompt: str) -> bool:
    if force:
        return True
    for warning in warnings:
        console.print(warning)
    if Confirm.ask(prompt):
        return True
    console.print("[yellow]Cleanup cancelled.[/]")
    return False


def _display_cleanup_result(
    deployment_dir: Path, file_count: int, size_mb: float
) -> None:
    console.print("[green]✓[/] Deployment directory cleaned successfully")
    console.print("\n[bold green]Cleanup completed![/]")
    console.print(f"Removed: {deployment_dir}")
    if file_count > 0:
        console.print(f"Files deleted: {file_count}")
        console.print(f"Space freed: {size_mb:.2f} MB")
    console.print("\n[bold]Next steps:[/]")
    console.print(
        "  • Run [bold]supervaizer deploy local[/] to regenerate files for local testing"
    )
    console.print("  • Run [bold]supervaizer deploy up[/] to deploy to cloud platforms")
    console.print("  • Run [bold]supervaizer deploy plan[/] to plan new deployments")


def _existing_paths(deployment_dir: Path, names: Sequence[str]) -> list[Path]:
    paths = []
    for name in names:
        path = deployment_dir / name
        if path.exists():
            paths.append(path)
    return paths


def _display_paths(
    deployment_dir: Path, paths: Sequence[Path], *, directories: bool = False
) -> None:
    marker, suffix = ("📁", "/") if directories else ("📄", "")
    for path in paths:
        console.print(f"  {marker} {path.relative_to(deployment_dir)}{suffix}")


def _delete_paths(
    deployment_dir: Path,
    paths: Sequence[Path],
    verbose: bool,
    *,
    directories: bool = False,
) -> int:
    suffix = "/" if directories else ""
    for path in paths:
        if verbose:
            console.print(f"Deleting {path.relative_to(deployment_dir)}{suffix}...")
        if directories:
            shutil.rmtree(path)
        else:
            path.unlink()
    return len(paths)
