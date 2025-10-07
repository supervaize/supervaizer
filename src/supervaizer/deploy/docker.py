# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Docker Operations

This module handles Docker-related operations for deployment.
"""

import subprocess
from pathlib import Path
from typing import Optional

from docker import DockerClient
from docker.errors import DockerException
from rich.console import Console

from supervaizer.common import log

console = Console()

TEMPLATE_DIR = Path(__file__).parent / "templates"


class DockerManager:
    """Manages Docker operations for deployment."""

    def __init__(self) -> None:
        """Initialize Docker manager."""
        try:
            self.client = DockerClient.from_env()
            self.client.ping()  # Test connection
        except DockerException as e:
            log.error(f"Failed to connect to Docker: {e}")
            raise RuntimeError("Docker is not running or not accessible") from e

    def generate_dockerfile(self, output_path: Path) -> None:
        """Generate a Dockerfile for Supervaizer deployment."""
        dockerfile_content = (TEMPLATE_DIR / "Dockerfile.template").read_text()
        output_path.write_text(dockerfile_content)
        log.info(f"Generated Dockerfile at {output_path}")

    def generate_dockerignore(self, output_path: Path) -> None:
        """Generate a .dockerignore file."""
        dockerignore_content = (TEMPLATE_DIR / "dockerignore.template").read_text()
        output_path.write_text(dockerignore_content)
        log.info(f"Generated .dockerignore at {output_path}")

    def generate_docker_compose(self, output_path: Path) -> None:
        """Generate a docker-compose.yml for local testing."""
        compose_content = (TEMPLATE_DIR / "docker-compose.yml.template").read_text()
        output_path.write_text(compose_content)
        log.info(f"Generated docker-compose.yml at {output_path}")

    def build_image(self, tag: str, context_path: Path, dockerfile_path: Path) -> str:
        """Build Docker image and return the image ID."""
        try:
            log.info(f"Building Docker image with tag: {tag}")
            image, build_logs = self.client.images.build(
                path=str(context_path),
                dockerfile=str(dockerfile_path),
                tag=tag,
                rm=True,
                forcerm=True,
            )

            log.info(f"Successfully built image: {image.id}")
            return image.id

        except DockerException as e:
            log.error(f"Failed to build Docker image: {e}")
            raise RuntimeError(f"Docker build failed: {e}") from e

    def tag_image(self, source_tag: str, target_tag: str) -> None:
        """Tag a Docker image."""
        try:
            image = self.client.images.get(source_tag)
            image.tag(target_tag)
            log.info(f"Tagged {source_tag} as {target_tag}")
        except DockerException as e:
            log.error(f"Failed to tag image: {e}")
            raise RuntimeError(f"Failed to tag image: {e}") from e

    def push_image(self, tag: str) -> None:
        """Push Docker image to registry."""
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
        client = DockerClient.from_env()
        client.ping()
        return True
    except DockerException:
        return False


def get_git_sha() -> str:
    """Get the current git SHA for tagging."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()[:8]  # Use short SHA
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "latest"
