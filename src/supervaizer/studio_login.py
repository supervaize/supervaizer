# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Log a developer in to Supervaize Studio from the terminal.

The flow is a device authorization (RFC 8628): the CLI asks Studio for a code,
the developer approves it in the browser, and the CLI then receives a developer
API key and the settings of the workspace. No credential is typed in the terminal.
"""

from __future__ import annotations

import platform
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

DEFAULT_API_URL = "https://app.supervaize.com"
DEVICE_PATH = "/api/v1/cli/device/"
TOKEN_PATH = "/api/v1/cli/device/token/"
SLOW_DOWN_SECONDS = 5.0


class StudioLoginError(RuntimeError):
    """The login did not complete. The message says why, and what to do."""


def _field(data: Any, name: str) -> Any:
    """A field of a Studio answer. A missing field is an error, never a default."""
    if not isinstance(data, dict) or data.get(name) in (None, ""):
        raise StudioLoginError(
            f"Studio sent an answer without `{name}`. Check the Studio address."
        )
    return data[name]


def request_device_code(client: httpx.Client) -> dict[str, Any]:
    """Ask Studio for a device code and the page where the developer approves it."""
    response = client.post(
        DEVICE_PATH,
        json={"client_name": f"supervaizer on {platform.node() or 'unknown host'}"},
    )
    if response.status_code == 404:
        raise StudioLoginError(
            "This Studio does not support `supervaizer login`. "
            "Create an API key on the Developer page of Studio."
        )
    if response.status_code == 429:
        raise StudioLoginError(
            "Too many login requests. Wait some minutes, then try again."
        )
    response.raise_for_status()
    device = response.json()
    for name in ("device_code", "user_code", "expires_in", "interval"):
        _field(device, name)
    # The CLI opens this address in a browser, so it must be a web page.
    if not str(_field(device, "verification_uri_complete")).startswith((
        "https://",
        "http://",
    )):
        raise StudioLoginError(
            "Studio sent an approval address that is not a web page."
        )
    return dict(device)


def wait_for_credentials(
    client: httpx.Client,
    device: dict[str, Any],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Poll Studio until the developer approves or denies, or the code expires."""
    interval = float(device["interval"])
    deadline = clock() + float(device["expires_in"])
    while clock() < deadline:
        sleep(interval)
        response = client.post(TOKEN_PATH, json={"device_code": device["device_code"]})
        if response.status_code == 200:
            return dict(response.json())
        error = _error_code(response)
        if error == "authorization_pending":
            continue
        if error == "slow_down" or response.status_code == 429:
            interval += SLOW_DOWN_SECONDS
            continue
        if error == "access_denied":
            raise StudioLoginError("The request was denied in Studio. No key was made.")
        if error == "expired_token":
            break
        raise StudioLoginError(
            f"Studio refused the login: status {response.status_code}, error {error}."
        )
    raise StudioLoginError(
        "The code expired before the approval. Run `supervaizer login` again."
    )


def _error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return "unknown"
    return str(body.get("error", "unknown")) if isinstance(body, dict) else "unknown"


def env_values(credentials: dict[str, Any]) -> dict[str, str]:
    """The environment variables of a controller, from the answer of Studio."""
    workspace_auth = _field(credentials, "workspace_auth")
    values = {
        "SUPERVAIZE_API_KEY": _field(credentials, "api_key"),
        "SUPERVAIZE_WORKSPACE_ID": _field(credentials, "workspace_id"),
        "SUPERVAIZE_API_URL": _field(credentials, "api_url"),
        "SUPERVAIZER_WORKSPACE_AUTH_REQUIRED": "true",
        "SUPERVAIZER_WORKSPACE_AUTH_ISSUER": _field(workspace_auth, "issuer"),
        "SUPERVAIZER_WORKSPACE_AUTH_JWKS_URL": _field(workspace_auth, "jwks_url"),
    }
    for name, value in values.items():
        # A line break in a value would add a variable that Studio did not name.
        if not isinstance(value, str) or "\n" in value or "\r" in value:
            raise StudioLoginError(f"Studio sent a value for {name} that is not valid.")
    return values


def write_env_file(path: Path, values: dict[str, str]) -> None:
    """Set `values` in an environment file. Other lines of the file stay as they are."""
    prefix = "export " if path.name == ".envrc" else ""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    kept = [
        line
        for line in lines
        if line.split("=", 1)[0].removeprefix("export ").strip() not in values
    ]
    kept += [f"{prefix}{name}={value}" for name, value in values.items()]
    # A new file is private to its owner. An existing file keeps its mode.
    path.touch(mode=0o600, exist_ok=True)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
