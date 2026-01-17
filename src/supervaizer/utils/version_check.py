# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.


import httpx

try:
    from packaging import version
except ImportError:
    version = None

from supervaizer import __version__


async def get_latest_version() -> str | None:
    """
    Retrieve the latest version number of supervaizer from PyPI.

    Returns:
        The latest version string (e.g., "0.9.8") if successful, None otherwise.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://pypi.org/pypi/supervaizer/json")
            response.raise_for_status()
            data = response.json()
            return data.get("info", {}).get("version")
    except Exception:
        return None


async def check_is_latest_version() -> tuple[bool, str | None]:
    """
    Check if the currently running supervaizer version is the latest available on PyPI.

    Returns:
        A tuple of (is_latest: bool, latest_version: str | None).
        - is_latest: True if current version is latest or if check failed
        - latest_version: The latest version string if available, None otherwise
    """
    current_version = __version__.VERSION
    latest_version = await get_latest_version()

    if latest_version is None:
        return True, None

    # Compare versions using packaging.version for proper semantic version comparison
    if version is not None:
        is_latest = version.parse(current_version) >= version.parse(latest_version)
    else:
        # Fallback to simple string comparison if packaging is not available
        is_latest = current_version >= latest_version
    return is_latest, latest_version
