# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Docker Operations

This module handles Docker-related operations for deployment.
"""

import os
from pathlib import Path
from typing import Optional

from rich.console import Console

from supervaizer.common import log

console = Console()

TEMPLATE_DIR = Path(__file__).parent / "templates"

# List of environment variables to include in Dockerfile
DOCKER_ENV_VARS = [
    "SUPERVAIZE_API_KEY",
    "SUPERVAIZE_WORKSPACE_ID",
    "SUPERVAIZE_API_URL",
    "SUPERVAIZER_PORT",
    "SUPERVAIZER_PUBLIC_URL",
]


def get_docker_env_vars(port: int = 8000) -> dict[str, str]:
    """Get environment variables for Docker deployment.

    Args:
        port: The application port to use for SUPERVAIZER_PORT

    Returns:
        Dictionary mapping environment variable names to their values
    """
    env_vars = {}

    for var_name in DOCKER_ENV_VARS:
        if var_name == "SUPERVAIZER_PORT":
            env_vars[var_name] = str(port)
        else:
            env_vars[var_name] = os.getenv(var_name, "")

    return env_vars


def get_docker_build_args(port: int = 8000) -> dict[str, str]:
    """Get build arguments for Docker deployment.

    Args:
        port: The application port to use for SUPERVAIZER_PORT

    Returns:
        Dictionary mapping build argument names to their values
    """
    build_args = {}

    for var_name in DOCKER_ENV_VARS:
        if var_name == "SUPERVAIZER_PORT":
            build_args[var_name] = str(port)
        else:
            # Only include build args for variables that are set
            value = os.getenv(var_name)
            if value:
                build_args[var_name] = value

    return build_args


class DockerManager:
    """Manages Docker operations for deployment."""

    def __init__(self, require_docker: bool = True) -> None:
        """Initialize Docker manager."""
        self.client = None
        if require_docker:
            try:
                from docker import DockerClient
                from docker.errors import DockerException
            except ImportError:
                raise RuntimeError(
                    "Docker package not installed. Install with: pip install supervaizer[deploy]"
                ) from None

            try:
                self.client = DockerClient.from_env()
                self.client.ping()  # Test connection
            except DockerException as e:
                log.error(f"Failed to connect to Docker: {e}")
                raise RuntimeError("Docker is not running or not accessible") from e

    def generate_dockerfile(
        self,
        output_path: Optional[Path] = None,
        python_version: str = "3.12",
        app_port: int = 8000,
        controller_file: str = "supervaizer_control.py",
    ) -> None:
        """Generate a Dockerfile for Supervaizer deployment."""
        if output_path is None:
            output_path = Path(".deployment/Dockerfile")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Read template and customize it
        template_path = TEMPLATE_DIR / "Dockerfile.template"
        dockerfile_content = template_path.read_text()

        # Replace template placeholders with actual values
        dockerfile_content = dockerfile_content.replace(
            "{{PYTHON_VERSION}}", python_version
        )
        dockerfile_content = dockerfile_content.replace("{{APP_PORT}}", str(app_port))
        dockerfile_content = dockerfile_content.replace(
            "{{CONTROLLER_FILE}}", controller_file
        )

        # Replace environment variables placeholder
        env_vars = get_docker_env_vars(app_port)
        env_lines = []
        for var_name in env_vars.keys():
            env_lines.append(f"ARG {var_name}")
            env_lines.append(f"ENV {var_name}=${{{var_name}}}")
        env_vars_section = "\n".join(env_lines)
        dockerfile_content = dockerfile_content.replace(
            "{{ENV_VARS}}", env_vars_section
        )

        output_path.write_text(dockerfile_content)
        log.info(f"Generated Dockerfile at {output_path}")

        # Copy entrypoint script to deployment directory
        entrypoint_script_path = output_path.parent / "entrypoint.sh"
        entrypoint_template_path = TEMPLATE_DIR / "entrypoint.sh"
        if entrypoint_template_path.exists():
            entrypoint_script_path.write_text(entrypoint_template_path.read_text())
            # Make it executable
            entrypoint_script_path.chmod(0o755)
            log.info(f"Generated entrypoint script at {entrypoint_script_path}")

        # Copy debug script to deployment directory
        debug_script_path = output_path.parent / "debug_env.py"
        debug_template_path = TEMPLATE_DIR / "debug_env.py"
        if debug_template_path.exists():
            debug_script_path.write_text(debug_template_path.read_text())
            log.info(f"Generated debug script at {debug_script_path}")

    def generate_dockerignore(self, output_path: Optional[Path] = None) -> None:
        """Generate a .dockerignore file."""
        if output_path is None:
            output_path = Path(".deployment/.dockerignore")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Read template
        template_path = TEMPLATE_DIR / "dockerignore.template"
        dockerignore_content = template_path.read_text()

        output_path.write_text(dockerignore_content)
        log.info(f"Generated .dockerignore at {output_path}")

    def generate_docker_compose(
        self,
        output_path: Optional[Path] = None,
        port: int = 8000,
        service_name: str = "supervaizer-dev",
        environment: str = "dev",
        api_key: str = "test-api-key",
        rsa_key: str = "test-rsa-key",
    ) -> None:
        """Generate a docker-compose.yml for local testing."""
        if output_path is None:
            output_path = Path(".deployment/docker-compose.yml")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Read template and customize it
        template_path = TEMPLATE_DIR / "docker-compose.yml.template"
        compose_content = template_path.read_text()

        # Get environment variables for build args
        env_vars = get_docker_env_vars(port)

        # Replace template placeholders with actual values
        compose_content = compose_content.replace("{{PORT}}", str(port))
        compose_content = compose_content.replace("{{SERVICE_NAME}}", service_name)
        compose_content = compose_content.replace("{{ENVIRONMENT}}", environment)
        compose_content = compose_content.replace("{{API_KEY}}", api_key)
        compose_content = compose_content.replace("{{RSA_KEY}}", rsa_key)
        compose_content = compose_content.replace(
            "{{ env.SV_LOG_LEVEL | default('INFO') }}", "INFO"
        )

        # Replace environment variable placeholders for build args
        compose_content = compose_content.replace(
            "{{WORKSPACE_ID}}", env_vars.get("SUPERVAIZE_WORKSPACE_ID", "")
        )
        compose_content = compose_content.replace(
            "{{API_URL}}", env_vars.get("SUPERVAIZE_API_URL", "")
        )
        compose_content = compose_content.replace(
            "{{PUBLIC_URL}}", env_vars.get("SUPERVAIZER_PUBLIC_URL", "")
        )

        output_path.write_text(compose_content)
        log.info(f"Generated docker-compose.yml at {output_path}")

    def build_image(
        self,
        tag: str,
        context_path: Optional[Path] = None,
        dockerfile_path: Optional[Path] = None,
        verbose: bool = False,
        build_args: Optional[dict] = None,
    ) -> str:
        """Build Docker image and return the image ID."""
        from docker.errors import APIError, BuildError, DockerException

        if self.client is None:
            raise RuntimeError(
                "Docker client not available. Initialize DockerManager with require_docker=True"
            )

        if context_path is None:
            context_path = Path(".")
        if dockerfile_path is None:
            dockerfile_path = Path(".deployment/Dockerfile")

        try:
            log.info(f"Building Docker image with tag: {tag}")

            # Use low-level API to get logs even when build fails
            # Access the low-level API through the existing client
            build_kwargs = {
                "path": str(context_path),
                "dockerfile": str(dockerfile_path),
                "tag": tag,
                "rm": True,
                "forcerm": True,
                "buildargs": build_args or {},
                "decode": True,
            }

            response = [line for line in self.client.api.build(**build_kwargs)]

            if not response:
                raise RuntimeError("Failed to get a response from docker client")

            # Process and display logs (always show output, especially errors)
            image_id = None
            last_error = None
            for result in response:
                if isinstance(result, dict):
                    # Check for errors first
                    if "error" in result or "errorDetail" in result:
                        error_msg = result.get("error") or result.get(
                            "errorDetail", {}
                        ).get("message", "Unknown error")
                        last_error = error_msg

                    for key, value in result.items():
                        if isinstance(value, str):
                            # Always print string values (logs, errors, etc.)
                            print(value, end="", flush=True)
                        elif key == "aux" and isinstance(value, dict):
                            # Extract image ID from aux data
                            image_id = value.get("ID")

            # If we found an error, raise it
            if last_error:
                raise RuntimeError(f"Docker build failed: {last_error}")

            # If we didn't get image ID from aux, try to get it from the tag
            if image_id is None:
                try:
                    image = self.client.images.get(tag)
                    image_id = image.id
                except DockerException:
                    raise RuntimeError(
                        "Docker build completed but no image was returned"
                    )

            log.info(f"Successfully built image: {image_id}")
            return image_id

        except (BuildError, APIError) as e:
            log.error(f"Failed to build Docker image: {e}")
            raise RuntimeError(f"Docker build failed: {e}") from e
        except DockerException as e:
            log.error(f"Failed to build Docker image: {e}")
            raise RuntimeError(f"Docker build failed: {e}") from e

    def tag_image(self, source_tag: str, target_tag: str) -> None:
        """Tag a Docker image."""
        from docker.errors import DockerException

        if self.client is None:
            raise RuntimeError(
                "Docker client not available. Initialize DockerManager with require_docker=True"
            )

        try:
            image = self.client.images.get(source_tag)
            image.tag(target_tag)
            log.info(f"Tagged {source_tag} as {target_tag}")
        except DockerException as e:
            log.error(f"Failed to tag image: {e}")
            raise RuntimeError(f"Failed to tag image: {e}") from e

    def push_image(self, tag: str) -> None:
        """Push Docker image to registry."""
        from docker.errors import DockerException

        if self.client is None:
            raise RuntimeError(
                "Docker client not available. Initialize DockerManager with require_docker=True"
            )

        try:
            log.info(f"Pushing image: {tag}")
            push_logs = self.client.images.push(tag, stream=True, decode=True)

            for log_line in push_logs:
                if "error" in log_line:
                    log.error(f"Push error: {log_line}")
                    raise RuntimeError(f"Push failed: {log_line}")
                elif "status" in log_line:
                    log.debug(f"Push status: {log_line['status']}")

            log.info(f"Successfully pushed image: {tag}")

        except DockerException as e:
            log.error(f"Failed to push image: {e}")
            raise RuntimeError(f"Failed to push image: {e}") from e

    def get_image_digest(self, tag: str) -> Optional[str]:
        """Get the digest of a Docker image."""
        from docker.errors import DockerException

        if self.client is None:
            raise RuntimeError(
                "Docker client not available. Initialize DockerManager with require_docker=True"
            )

        try:
            image = self.client.images.get(tag)
            repo_digests = image.attrs.get("RepoDigests", [])
            return repo_digests[0] if repo_digests else None
        except DockerException as e:
            log.error(f"Failed to get image digest: {e}")
            return None


def ensure_docker_running() -> bool:
    """Check if Docker is running and accessible."""
    try:
        from docker import DockerClient
        from docker.errors import DockerException

        client = DockerClient.from_env()
        client.ping()
        return True
    except ImportError:
        return False
    except DockerException:
        return False
