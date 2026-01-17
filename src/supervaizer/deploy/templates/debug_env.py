#!/usr/bin/env python3
# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Debug script to check environment variables in container."""

import os
import sys


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
        "SV_RSA_PRIVATE_KEY",
        "SV_LOG_LEVEL",
    ]

    print("=== Supervaize Environment Variables ===")
    for var_name in supervaize_vars:
        value = os.getenv(var_name)
        if value is None:
            print(f"{var_name}: [NOT SET]")
        elif value == "":
            print(f"{var_name}: [EMPTY STRING]")
        else:
            # Mask sensitive values
            if "KEY" in var_name or "SECRET" in var_name:
                masked_value = (
                    value[:4] + "*" * (len(value) - 8) + value[-4:]
                    if len(value) > 8
                    else "*" * len(value)
                )
                print(f"{var_name}: {masked_value}")
            else:
                print(f"{var_name}: {value}")

    print()
    print("=== All Environment Variables ===")
    for key, value in sorted(os.environ.items()):
        if "KEY" in key or "SECRET" in key or "PASSWORD" in key:
            masked_value = (
                value[:4] + "*" * (len(value) - 8) + value[-4:]
                if len(value) > 8
                else "*" * len(value)
            )
            print(f"{key}: {masked_value}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    debug_environment_variables()
