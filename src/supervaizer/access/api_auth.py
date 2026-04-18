# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""API key authentication and scope enforcement."""  # <-- ADDED

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from supervaizer.common import log_access_denied_api

# In-memory API key registry.  Populated at import time from SUPERVAIZER_API_KEY env.
# Empty by default — no hard-coded credentials ship in production.  # <-- ADDED
API_KEYS: dict[str, dict[str, str]] = {}

# Scope hierarchy: higher rank implies all lower scopes.
_SCOPE_RANK: dict[str, int] = {"read": 0, "write": 1}  # <-- ADDED


def _load_env_key() -> None:  # <-- ADDED
    """Register SUPERVAIZER_API_KEY as a full-access (write) entry for migration."""
    env_key = os.getenv("SUPERVAIZER_API_KEY", "").strip()
    if env_key:
        API_KEYS[env_key] = {"scope": "write"}


_load_env_key()


def require_api_key(  # <-- ADDED
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> dict[str, str]:
    """Verify X-API-Key header and return the key's metadata dict.

    Checks in order:
    1. In-memory ``API_KEYS`` registry (populated at import from ``SUPERVAIZER_API_KEY``).
    2. Live server's ``api_key`` on ``request.app.state.server`` — handles test fixtures
       and deployments where the key is set programmatically rather than via env var.

    Raises HTTP 401 for missing or unknown keys.
    """
    path = request.scope.get("path", "")
    if x_api_key:
        if x_api_key in API_KEYS:
            return API_KEYS[x_api_key]
        # Fallback: live server API key (covers test fixtures + programmatic config)
        live_server = getattr(getattr(request, "app", None), "state", None)
        live_server = getattr(live_server, "server", None) if live_server else None
        live_key = getattr(live_server, "api_key", None) if live_server else None
        if live_key and x_api_key == live_key:
            return {"scope": "write"}  # live server key always has full access
    log_access_denied_api(x_api_key, path, "invalid key")
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


def require_scope(required_scope: str) -> Callable[..., dict[str, str]]:  # <-- ADDED
    """Return a FastAPI dependency that enforces a minimum scope level.

    Scope is hierarchical: 'write' satisfies 'read' (but not the reverse).
    """

    def _check(
        meta: Annotated[dict[str, str], Depends(require_api_key)],
        request: Request,
    ) -> dict[str, str]:
        key_scope = meta.get("scope", "")
        key_rank = _SCOPE_RANK.get(key_scope, -1)
        req_rank = _SCOPE_RANK.get(required_scope, 0)
        if key_rank < req_rank:
            path = request.scope.get("path", "")
            log_access_denied_api(None, path, "insufficient scope")
            raise HTTPException(status_code=403, detail="Insufficient scope")
        return meta

    return _check
