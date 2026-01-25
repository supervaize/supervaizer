# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Deployment State Management

This module handles deployment state persistence and management.
"""

import subprocess
from pathlib import Path

from supervaizer.common import log


def create_deployment_directory(project_root: Path) -> Path:
    """Create deployment directory and add to .gitignore."""
    deployment_dir = project_root / ".deployment"
    deployment_dir.mkdir(exist_ok=True)

    # Create logs subdirectory
    logs_dir = deployment_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Add to .gitignore if not already present
    gitignore_path = project_root / ".gitignore"
    gitignore_entry = ".deployment/"

    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text()
        if gitignore_entry not in gitignore_content:
            gitignore_path.write_text(gitignore_content + f"\n{gitignore_entry}\n")
            log.info(f"Added {gitignore_entry} to .gitignore")
    else:
        gitignore_path.write_text(f"{gitignore_entry}\n")
        log.info(f"Created .gitignore with {gitignore_entry}")

    return deployment_dir


def get_git_sha() -> str:
    """Get the current git SHA for tagging."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()[:8]  # Use short SHA
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "latest"
