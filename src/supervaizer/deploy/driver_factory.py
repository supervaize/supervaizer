# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Driver Factory

This module provides a factory for creating deployment drivers.
"""

from typing import Optional

from supervaizer.deploy.drivers.base import BaseDriver
from supervaizer.deploy.drivers.cloud_run import CloudRunDriver
from supervaizer.deploy.drivers.aws_app_runner import AWSAppRunnerDriver
from supervaizer.deploy.drivers.do_app_platform import DOAppPlatformDriver


def create_driver(
    platform: str, region: str, project_id: Optional[str] = None
) -> BaseDriver:
    """Create a deployment driver for the specified platform."""
    platform = platform.lower()

    match platform:
        case "cloud-run":
            if not project_id:
                raise ValueError("project_id is required for Cloud Run")
            return CloudRunDriver(region, project_id)
        case "aws-app-runner":
            return AWSAppRunnerDriver(region, project_id)
        case "do-app-platform":
            return DOAppPlatformDriver(region, project_id)
        case _:
            raise ValueError(f"Unsupported platform: {platform}")


def get_supported_platforms() -> list[str]:
    """Get list of supported platforms."""
    return ["cloud-run", "aws-app-runner", "do-app-platform"]
