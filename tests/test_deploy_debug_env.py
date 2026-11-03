# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

import os
from unittest.mock import patch

import pytest

from supervaizer.deploy.templates.debug_env import debug_environment_variables

OUTPUT_HEADER = """=== Environment Variables Debug ===
Python version: test-python
Working directory: /dummy/project

=== Supervaize Environment Variables ===
"""

UNSET_SELECTED_VARIABLES = """SUPERVAIZE_API_KEY: [NOT SET]
SUPERVAIZE_WORKSPACE_ID: [NOT SET]
SUPERVAIZE_API_URL: [NOT SET]
SUPERVAIZER_PORT: [NOT SET]
SUPERVAIZER_PUBLIC_URL: [NOT SET]
SUPERVAIZER_ENVIRONMENT: [NOT SET]
SUPERVAIZER_HOST: [NOT SET]
SUPERVAIZER_API_KEY: [NOT SET]
SUPERVAIZER_PRIVATE_KEY: [NOT SET]
SUPERVAIZER_LOG_LEVEL: [NOT SET]
SUPERVAIZER_WORKSPACE_AUTH_REQUIRED: [NOT SET]
SUPERVAIZER_WORKSPACE_AUTH_ISSUER: [NOT SET]
"""


def capture_debug_output(
    capsys: pytest.CaptureFixture[str], environment: dict[str, str]
) -> str:
    with (
        patch.dict(os.environ, environment, clear=True),
        patch("supervaizer.deploy.templates.debug_env.sys.version", "test-python"),
        patch(
            "supervaizer.deploy.templates.debug_env.os.getcwd",
            return_value="/dummy/project",
        ),
    ):
        debug_environment_variables()
    return capsys.readouterr().out


def test_debug_environment_reports_all_selected_variables_when_unset(
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = capture_debug_output(capsys, {})

    assert output == (
        OUTPUT_HEADER
        + UNSET_SELECTED_VARIABLES
        + "\n=== All Environment Variables ===\n"
    )


def test_debug_environment_distinguishes_empty_values_and_masks_key_lengths(
    capsys: pytest.CaptureFixture[str],
) -> None:
    environment = {
        "SUPERVAIZER_PRIVATE_KEY": "123456789",
        "SUPERVAIZE_WORKSPACE_ID": "workspace-dummy",
        "SUPERVAIZER_HOST": "",
        "SUPERVAIZE_API_KEY": "12345678",
        "SUPERVAIZER_API_KEY": "",
        "SUPERVAIZER_PORT": "8000",
    }

    output = capture_debug_output(capsys, environment)

    assert output == (
        OUTPUT_HEADER
        + """SUPERVAIZE_API_KEY: ********
SUPERVAIZE_WORKSPACE_ID: workspace-dummy
SUPERVAIZE_API_URL: [NOT SET]
SUPERVAIZER_PORT: 8000
SUPERVAIZER_PUBLIC_URL: [NOT SET]
SUPERVAIZER_ENVIRONMENT: [NOT SET]
SUPERVAIZER_HOST: [EMPTY STRING]
SUPERVAIZER_API_KEY: [EMPTY STRING]
SUPERVAIZER_PRIVATE_KEY: 1234*6789
SUPERVAIZER_LOG_LEVEL: [NOT SET]
SUPERVAIZER_WORKSPACE_AUTH_REQUIRED: [NOT SET]
SUPERVAIZER_WORKSPACE_AUTH_ISSUER: [NOT SET]

=== All Environment Variables ===
SUPERVAIZER_API_KEY:\x20
SUPERVAIZER_HOST:\x20
SUPERVAIZER_PORT: 8000
SUPERVAIZER_PRIVATE_KEY: 1234*6789
SUPERVAIZE_API_KEY: ********
SUPERVAIZE_WORKSPACE_ID: workspace-dummy
"""
    )


def test_debug_environment_masks_uppercase_name_fragments_and_sorts_all_variables(
    capsys: pytest.CaptureFixture[str],
) -> None:
    environment = {
        "lower_secret": "dummy-secret",
        "lower_password": "dummy-password",
        "lower_key": "dummy-key",
        "Z_PASSWORD": "1234567890",
        "MONKEY": "12345678",
        "M_SECRET": "123456789",
        "A_KEY": "1",
        "EMPTY_SECRET": "",
        "PLAIN": "KEY SECRET PASSWORD",
    }

    output = capture_debug_output(capsys, environment)

    assert output == (
        OUTPUT_HEADER
        + UNSET_SELECTED_VARIABLES
        + """
=== All Environment Variables ===
A_KEY: *
EMPTY_SECRET:\x20
MONKEY: ********
M_SECRET: 1234*6789
PLAIN: KEY SECRET PASSWORD
Z_PASSWORD: 1234**7890
lower_key: dummy-key
lower_password: dummy-password
lower_secret: dummy-secret
"""
    )
