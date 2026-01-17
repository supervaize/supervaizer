# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Local Testing Command

This module provides local testing functionality using Docker Compose.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from supervaizer.deploy.docker import DockerManager

console = Console()


def local_docker(
    name: str,
    env: str,
    port: int,
    generate_api_key: bool,
    generate_rsa: bool,
    timeout: int,
    verbose: bool,
    docker_files_only: bool = False,
    source_dir: str = ".",
    controller_file: str = "supervaizer_control.py",
) -> None:
    """Test deployment locally using Docker Compose."""
    if docker_files_only:
        console.print(
            Panel.fit("[bold blue]Generate Docker Files Only[/]", border_style="blue")
        )
    else:
        console.print(
            Panel.fit("[bold blue]Local Docker Testing[/]", border_style="blue")
        )

    # Determine service name
    if name is None:
        name = Path(source_dir).name.lower().replace("_", "-")

    service_name = f"{name}-{env}"

    console.print(f"[bold]Testing service:[/] {service_name}")
    console.print(f"[bold]Environment:[/] {env}")
    console.print(f"[bold]Port:[/] {port}")

    try:
        # Step 1: Check Docker availability
        console.print("\n[bold]Step 1:[/] Checking Docker availability...")
        if not _check_docker_available():
            console.print("[bold red]Error:[/] Docker is not available or not running")
            raise RuntimeError("Docker not available")
        console.print("[green]✓[/] Docker is available")

        # Step 2: Generate secrets if needed
        console.print("\n[bold]Step 2:[/] Setting up secrets...")
        secrets = _generate_test_secrets(generate_api_key, generate_rsa)
        console.print("[green]✓[/] Test secrets configured")

        # Step 3: Generate deployment files
        console.print("\n[bold]Step 3:[/] Generating deployment files...")
        docker_manager = DockerManager(require_docker=False)
        docker_manager.generate_dockerfile(
            controller_file=controller_file,
            app_port=port,
        )
        docker_manager.generate_dockerignore()
        docker_manager.generate_docker_compose(
            port=port,
            service_name=service_name,
            environment=env,
            api_key=secrets.get("api_key", "test-api-key"),
            rsa_key=secrets.get("rsa_private_key", "test-rsa-key"),
        )
        console.print("[green]✓[/] Deployment files generated")

        # If docker_files_only is True, stop here
        if docker_files_only:
            console.print("\n[bold green]✓ Docker files generated successfully![/]")
            console.print("[bold]Generated files:[/]")
            console.print("  • .deployment/Dockerfile")
            console.print("  • .deployment/.dockerignore")
            console.print("  • .deployment/docker-compose.yml")
            console.print("\n[bold]To start the services:[/]")
            console.print("[dim]docker-compose -f .deployment/docker-compose.yml up[/]")
            console.print("\n[bold]To debug environment variables:[/]")
            console.print(
                f"[dim]docker-compose -f .deployment/docker-compose.yml run --rm {service_name} python debug_env.py[/]"
            )
            console.print(
                "\n[bold]Note:[/] Environment variables are automatically included from your host environment."
            )
            console.print("Make sure to set the following variables if needed:")
            console.print("  • SUPERVAIZE_API_KEY")
            console.print("  • SUPERVAIZE_WORKSPACE_ID")
            console.print("  • SUPERVAIZE_API_URL")
            console.print("  • SUPERVAIZER_PUBLIC_URL")
            return

        # Step 4: Build Docker image
        console.print("\n[bold]Step 4:[/] Building Docker image...")
        image_tag = f"{service_name}:local-test"
        # Create a new DockerManager instance that requires Docker for building
        build_docker_manager = DockerManager(require_docker=True)

        # Get build arguments for environment variables
        from supervaizer.deploy.docker import get_docker_build_args

        build_args = get_docker_build_args(port)

        build_docker_manager.build_image(
            image_tag, verbose=verbose, build_args=build_args
        )
        console.print(f"[green]✓[/] Image built: {image_tag}")

        # Step 5: Start services with Docker Compose
        console.print("\n[bold]Step 5:[/] Starting services...")
        _start_docker_compose(
            service_name=service_name, port=port, secrets=secrets, verbose=verbose
        )
        console.print("[green]✓[/] Services started")

        # Step 6: Wait for service to be ready
        console.print("\n[bold]Step 6:[/] Waiting for service to be ready...")
        service_url = f"http://localhost:{port}"
        if _wait_for_service(service_url, timeout):
            console.print("[green]✓[/] Service is ready")
        else:
            console.print("[bold red]Error:[/] Service failed to start within timeout")
            _show_service_logs(service_name)
            raise RuntimeError("Service startup timeout")

        # Step 7: Run health checks
        console.print("\n[bold]Step 7:[/] Running health checks...")
        health_results = _run_health_checks(service_url, secrets.get("api_key"))
        _display_health_results(health_results)

        # Step 8: Display service information
        console.print("\n[bold]Step 8:[/] Service Information")
        _display_service_info(service_name, service_url, port, secrets)

        console.print("\n[bold green]✓ Local testing completed successfully![/]")
        console.print(f"[bold]Service URL:[/] {service_url}")
        console.print(f"[bold]API Documentation:[/] {service_url}/docs")
        console.print(f"[bold]ReDoc:[/] {service_url}/redoc")

    except Exception as e:
        console.print(f"\n[bold red]Error during local testing:[/] {e}")
        _cleanup_test_resources(service_name)
        raise
    finally:
        # Always show cleanup instructions
        console.print("\n[bold]To stop the test services:[/]")
        console.print("[dim]docker-compose -f .deployment/docker-compose.yml down[/]")
        console.print("\n[bold]To debug environment variables:[/]")
        console.print(
            f"[dim]docker-compose -f .deployment/docker-compose.yml run --rm {service_name} python debug_env.py[/]"
        )
        console.print("\n[bold]To clean up all deployment files:[/]")
        console.print("[dim]supervaizer deploy clean[/]")


def _check_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _generate_test_secrets(generate_api_key: bool, generate_rsa: bool) -> dict:
    """Generate test secrets for local testing."""
    secrets = {}

    if generate_api_key:
        # Generate a test API key
        import secrets as secrets_module

        secrets["api_key"] = secrets_module.token_urlsafe(32)
    else:
        secrets["api_key"] = "test-api-key-local"

    if generate_rsa:
        # Generate a test RSA key
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        secrets["rsa_private_key"] = private_pem.decode()
    else:
        secrets["rsa_private_key"] = "test-rsa-key-local"

    return secrets


def _start_docker_compose(
    service_name: str, port: int, secrets: dict, verbose: bool = False
) -> None:
    """Start services using Docker Compose."""
    compose_file = Path(".deployment/docker-compose.yml")

    if not compose_file.exists():
        raise RuntimeError("Docker Compose file not found")

    # Set environment variables for Docker Compose
    env = os.environ.copy()
    env.update(
        {
            "SERVICE_NAME": service_name,
            "SERVICE_PORT": str(port),
            "SUPERVAIZER_API_KEY": secrets["api_key"],
            "SV_RSA_PRIVATE_KEY": secrets["rsa_private_key"],
            "SUPERVAIZER_ENVIRONMENT": "dev",
            "SUPERVAIZER_HOST": "0.0.0.0",
            "SUPERVAIZER_PORT": str(port),
            "SV_LOG_LEVEL": "INFO",
        }
    )

    cmd = ["docker-compose", "-f", str(compose_file), "up", "-d"]

    if verbose:
        # When verbose, capture output to display it
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        # Display the captured output
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[yellow]Stderr:[/] {result.stderr}")
    else:
        # When not verbose, capture output silently
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        error_msg = result.stderr if result.stderr else "Unknown error"
        raise RuntimeError(f"Failed to start Docker Compose: {error_msg}")


def _wait_for_service(url: str, timeout: int) -> bool:
    """Wait for service to be ready."""
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Waiting for service...", total=None)

        while time.time() - start_time < timeout:
            try:
                response = httpx.get(f"{url}/.well-known/health", timeout=5)
                if response.status_code == 200:
                    return True
            except httpx.RequestError:
                pass

            time.sleep(2)

    return False


def _run_health_checks(url: str, api_key: Optional[str]) -> dict:
    """Run comprehensive health checks."""
    results = {}

    # Basic health check
    try:
        response = httpx.get(f"{url}/.well-known/health", timeout=10)
        results["health_endpoint"] = {
            "status": response.status_code,
            "success": response.status_code == 200,
            "response_time": response.elapsed.total_seconds(),
        }
    except Exception as e:
        results["health_endpoint"] = {
            "status": None,
            "success": False,
            "error": str(e),
        }

    # API health check (if API key available)
    if api_key:
        try:
            headers = {"X-API-Key": api_key}
            response = httpx.get(f"{url}/agents/health", headers=headers, timeout=10)
            results["api_health_endpoint"] = {
                "status": response.status_code,
                "success": response.status_code == 200,
                "response_time": response.elapsed.total_seconds(),
            }
        except Exception as e:
            results["api_health_endpoint"] = {
                "status": None,
                "success": False,
                "error": str(e),
            }

    # API documentation check
    try:
        response = httpx.get(f"{url}/docs", timeout=10)
        results["api_docs"] = {
            "status": response.status_code,
            "success": response.status_code == 200,
        }
    except Exception as e:
        results["api_docs"] = {
            "status": None,
            "success": False,
            "error": str(e),
        }

    return results


def _display_health_results(results: dict) -> None:
    """Display health check results in a table."""
    table = Table(title="Health Check Results")
    table.add_column("Endpoint", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Response Time", style="yellow")
    table.add_column("Details", style="white")

    for endpoint, result in results.items():
        if result["success"]:
            status = f"[green]{result['status']}[/]"
            response_time = f"{result.get('response_time', 0):.3f}s"
            details = "✓ OK"
        else:
            status = f"[red]{result.get('status', 'ERROR')}[/]"
            response_time = "N/A"
            details = result.get("error", "Failed")

        table.add_row(
            endpoint.replace("_", " ").title(), status, response_time, details
        )

    console.print(table)


def _display_service_info(
    service_name: str, url: str, port: int, secrets: dict
) -> None:
    """Display service information."""
    info_table = Table(title="Service Information")
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value", style="white")

    info_table.add_row("Service Name", service_name)
    info_table.add_row("URL", url)
    info_table.add_row("Port", str(port))
    info_table.add_row(
        "API Key",
        secrets["api_key"][:8] + "..."
        if len(secrets["api_key"]) > 8
        else secrets["api_key"],
    )
    info_table.add_row("Environment", "dev")

    console.print(info_table)


def _show_service_logs(service_name: str) -> None:
    """Show service logs for debugging."""
    console.print("\n[bold]Service Logs:[/]")
    try:
        # Try docker-compose logs first
        result = subprocess.run(
            [
                "docker-compose",
                "-f",
                ".deployment/docker-compose.yml",
                "logs",
                "--tail=100",
                service_name,
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[yellow]Stderr:[/] {result.stderr}")

        # Also try direct docker logs as fallback
        if not result.stdout:
            console.print("\n[bold]Trying direct docker logs:[/]")
            docker_logs = subprocess.run(
                [
                    "docker",
                    "logs",
                    f"deployment-{service_name}-1",
                    "--tail=100",
                ],
                capture_output=True,
                text=True,
            )
            if docker_logs.stdout:
                console.print(docker_logs.stdout)
            if docker_logs.stderr:
                console.print(f"[yellow]Stderr:[/] {docker_logs.stderr}")

        # Also try to get container status
        console.print("\n[bold]Container Status:[/]")
        status_result = subprocess.run(
            [
                "docker-compose",
                "-f",
                ".deployment/docker-compose.yml",
                "ps",
                "-a",
            ],
            capture_output=True,
            text=True,
        )
        if status_result.stdout:
            console.print(status_result.stdout)
    except Exception as e:
        console.print(f"[red]Failed to get logs:[/] {e}")


def _cleanup_test_resources(service_name: str) -> None:
    """Clean up test resources."""
    console.print("\n[bold]Cleaning up test resources...[/]")
    try:
        subprocess.run(
            ["docker-compose", "-f", ".deployment/docker-compose.yml", "down"],
            capture_output=True,
            text=True,
        )
        console.print("[green]✓[/] Test resources cleaned up")
    except Exception as e:
        console.print(f"[yellow]Warning:[/] Failed to cleanup resources: {e}")
