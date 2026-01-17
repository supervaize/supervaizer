# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""
Deployment Drivers

This module contains platform-specific deployment drivers.
"""

from .base import BaseDriver, DeploymentPlan, DeploymentResult

# Conditional imports for platform-specific drivers
try:
    from .cloud_run import CloudRunDriver

    CLOUD_RUN_AVAILABLE = True
except ImportError:
    CLOUD_RUN_AVAILABLE = False

try:
    from .aws_app_runner import AWSAppRunnerDriver

    AWS_APP_RUNNER_AVAILABLE = True
except ImportError:
    AWS_APP_RUNNER_AVAILABLE = False

from .do_app_platform import DOAppPlatformDriver

__all__ = [
    "BaseDriver",
    "DeploymentPlan",
    "DeploymentResult",
    "CloudRunDriver",
    "AWSAppRunnerDriver",
    "DOAppPlatformDriver",
]
