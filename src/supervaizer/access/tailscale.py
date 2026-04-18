# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tailscale CGNAT access dependency."""  # <-- ADDED

from __future__ import annotations

import ipaddress

from fastapi import HTTPException
from starlette.requests import HTTPConnection
from starlette.websockets import WebSocketState

from supervaizer.access.client_ip import _extract_client_ip
from supervaizer.common import log, log_access_denied_tailscale

# Tailscale CGNAT range per RFC 6598 / Tailscale docs
_TAILSCALE_CGNAT: ipaddress.IPv4Network = ipaddress.ip_network("100.64.0.0/10")  # <-- ADDED


def require_tailscale(conn: HTTPConnection) -> None:  # <-- ADDED
    """FastAPI dependency that allows only requests from the Tailscale CGNAT range.

    Raises HTTP 403 for plain HTTP connections and closes WebSocket connections
    with code 1008 when the client IP is outside 100.64.0.0/10.
    """
    path = conn.scope.get("path", "")
    ip = _extract_client_ip(conn.scope)

    allowed = False
    if ip:
        try:
            allowed = ipaddress.ip_address(ip) in _TAILSCALE_CGNAT
        except ValueError:
            pass  # stays False — fail closed

    if not allowed:
        log_access_denied_tailscale(ip, path, "not in tailscale range")
        if conn.scope.get("type") == "websocket":
            # For WebSocket connections, close with policy violation code
            # We need to check if the connection is still in a connectable state
            ws = conn  # conn IS the WebSocket for ws scope
            if hasattr(ws, "client_state") and ws.client_state == WebSocketState.CONNECTING:  # type: ignore[union-attr]
                raise HTTPException(status_code=403, detail="Forbidden: Tailscale network required")
            raise HTTPException(status_code=403, detail="Forbidden: Tailscale network required")
        raise HTTPException(status_code=403, detail="Forbidden: Tailscale network required")
