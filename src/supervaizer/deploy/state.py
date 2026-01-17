# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Deployment State Management

This module handles deployment state persistence and management.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from supervaizer.common import log


class DeploymentState(BaseModel):
    """Deployment state model."""

    # Versioning
    version: int = Field(2, description="State file format version")

    # Service identification
    service_name: str = Field(..., description="Name of the deployed service")
    platform: str = Field(
        ..., description="Target platform (cloud-run|aws-app-runner|do-app-platform)"
    )
    environment: str = Field(..., description="Environment (dev|staging|prod)")
    region: str = Field(..., description="Provider region")
    project_id: Optional[str] = Field(
        None, description="GCP project / AWS account / DO project"
    )

    # Deployment details
    image_tag: str = Field(..., description="Docker image tag")
    image_digest: Optional[str] = Field(None, description="Docker image digest")
    service_url: Optional[str] = Field(None, description="Public service URL")
    revision: Optional[str] = Field(None, description="Service revision/version")

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Deployment creation time",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update time",
    )

    # Status
    status: str = Field("unknown", description="Deployment status")
    health_status: str = Field("unknown", description="Health check status")

    # Configuration
    port: int = Field(8000, description="Application port")
    api_key_generated: bool = Field(False, description="Whether API key was generated")
    rsa_key_generated: bool = Field(False, description="Whether RSA key was generated")

    # Provider-specific data
    provider_data: Dict[str, Any] = Field(
        default_factory=dict, description="Platform-specific data"
    )


class StateManager:
    """Manages deployment state persistence."""

    def __init__(self, deployment_dir: Path) -> None:
        """Initialize state manager."""
        self.deployment_dir = deployment_dir
        self.state_file = deployment_dir / "state.json"
        self._ensure_deployment_dir()

    def _ensure_deployment_dir(self) -> None:
        """Ensure deployment directory exists."""
        self.deployment_dir.mkdir(exist_ok=True)

        # Create logs subdirectory
        logs_dir = self.deployment_dir / "logs"
        logs_dir.mkdir(exist_ok=True)

        log.info(f"Deployment directory: {self.deployment_dir}")

    def load_state(self) -> Optional[DeploymentState]:
        """Load deployment state from file."""
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)

            # Handle migration
            data = self.migrate_state(data)

            # Handle datetime deserialization
            if "created_at" in data:
                data["created_at"] = datetime.fromisoformat(data["created_at"])
            if "updated_at" in data:
                data["updated_at"] = datetime.fromisoformat(data["updated_at"])

            state = DeploymentState(**data)
            if not self.validate_state(state):
                return None
            return state

        except ValueError as e:
            if "Unsupported state version" in str(e):
                raise  # Re-raise the specific error for unsupported versions
            log.error(f"Failed to load or validate deployment state: {e}")
            return None
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.error(f"Failed to load or validate deployment state: {e}")
            return None

    def save_state(self, state: DeploymentState) -> None:
        """Save deployment state to file."""
        try:
            # Update timestamp
            state.updated_at = datetime.now(timezone.utc)

            # Convert to dict and handle datetime serialization
            data = state.model_dump()
            data["created_at"] = state.created_at.isoformat()
            data["updated_at"] = state.updated_at.isoformat()

            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)

            log.info(f"Saved deployment state to {self.state_file}")

        except (OSError, ValueError) as e:
            log.error(f"Failed to save deployment state: {e}")
            raise RuntimeError(f"Failed to save deployment state: {e}") from e

    def update_state(self, **kwargs: Any) -> DeploymentState:
        """Update deployment state with new values."""
        current_state = self.load_state()

        if current_state is None:
            # Create new state if none exists
            current_state = DeploymentState(**kwargs)
        else:
            # Update existing state
            for key, value in kwargs.items():
                if hasattr(current_state, key):
                    setattr(current_state, key, value)

        self.save_state(current_state)
        return current_state

    def delete_state(self) -> None:
        """Delete deployment state file."""
        if self.state_file.exists():
            self.state_file.unlink()
            log.info(f"Deleted deployment state file: {self.state_file}")

    def get_service_key(self, service_name: str, environment: str) -> str:
        """Generate a unique key for the service."""
        return f"{service_name}-{environment}"

    def validate_state(self, state: DeploymentState) -> bool:
        """Validate deployment state."""
        required_fields = ["service_name", "platform", "environment", "image_tag"]

        for field in required_fields:
            if not getattr(state, field):
                log.error(f"Missing required field in state: {field}")
                return False

        # Validate platform
        valid_platforms = ["cloud-run", "aws-app-runner", "do-app-platform"]
        if state.platform not in valid_platforms:
            log.error(f"Invalid platform: {state.platform}")
            return False

        # Validate environment
        valid_environments = ["dev", "staging", "prod"]
        if state.environment not in valid_environments:
            log.error(f"Invalid environment: {state.environment}")
            return False

        return True

    def migrate_state(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate state data from older versions."""
        version = state_data.get("version", 1)
        if version > 2:
            raise ValueError(f"Unsupported state version: {version}")

        migrated_data = state_data.copy()

        if version < 2:
            log.info("Migrating state from v1 to v2")
            # Example migration: add new fields with defaults
            if "api_key_generated" not in migrated_data:
                migrated_data["api_key_generated"] = False
            if "rsa_key_generated" not in migrated_data:
                migrated_data["rsa_key_generated"] = False
            if "provider_data" not in migrated_data:
                migrated_data["provider_data"] = {}
            migrated_data["version"] = 2

        return migrated_data
