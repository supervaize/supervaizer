#!/usr/bin/env python3
# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Debug script to check environment variables in container."""

import os
import sys


def _masked_value(value: str) -> str:
    if len(value) > 8:
        return value[:4] + "*" * (len(value) - 8) + value[-4:]
    return "*" * len(value)


def _selected_value(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        return "[NOT SET]"
    if value == "":
        return "[EMPTY STRING]"
    if "KEY" in name or "SECRET" in name:
        return _masked_value(value)
    return value


def debug_environment_variables() -> None:
    """Print all environment variables for debugging."""
    print("=== Environment Variables Debug ===")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print()

    # Check specific Supervaize environment variables
    supervaize_vars = [
        "SUPERVAIZE_API_KEY",
        "SUPERVAIZE_WORKSPACE_ID",
        "SUPERVAIZE_API_URL",
        "SUPERVAIZER_PORT",
        "SUPERVAIZER_PUBLIC_URL",
        "SUPERVAIZER_ENVIRONMENT",
        "SUPERVAIZER_HOST",
        "SUPERVAIZER_API_KEY",
        "SUPERVAIZER_PRIVATE_KEY",
        "SUPERVAIZER_LOG_LEVEL",
        "SUPERVAIZER_WORKSPACE_AUTH_REQUIRED",
        "SUPERVAIZER_WORKSPACE_AUTH_ISSUER",
    ]

    print("=== Supervaize Environment Variables ===")
    for var_name in supervaize_vars:
        print(f"{var_name}: {_selected_value(var_name)}")

    print()
    print("=== All Environment Variables ===")
    for key, value in sorted(os.environ.items()):
        if "KEY" in key or "SECRET" in key or "PASSWORD" in key:
            value = _masked_value(value)
        print(f"{key}: {value}")


if __name__ == "__main__":
    debug_environment_variables()
