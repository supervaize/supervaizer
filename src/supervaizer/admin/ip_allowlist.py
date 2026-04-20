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

"""IP allowlist for the /admin web UI (ADMIN_ALLOWED_IPS)."""

from __future__ import annotations

import ipaddress
import os

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from supervaizer.common import log

_ENV_KEY = "ADMIN_ALLOWED_IPS"


def is_admin_url_path(path: str) -> bool:
    """True for /admin and /admin/... but not /administrator."""
    return path == "/admin" or path.startswith("/admin/")


def get_effective_client_ip(request: Request) -> str:
    """Client IP for allowlist checks (reverse-proxy aware).

    Uses the first address in ``X-Forwarded-For`` when present (typical behind
    nginx/Traefik); otherwise ``request.client.host``.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


def _parse_allowed_entries(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def client_ip_is_allowed(client_ip: str, allowed_raw: str) -> bool:
    """Return True if client_ip matches any entry (exact IP or CIDR).

    ``allowed_raw`` is the value of ``ADMIN_ALLOWED_IPS`` (comma-separated).
    """
    if not allowed_raw.strip():
        return True
    if not client_ip:
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        log.warning(f"[Admin IP allowlist] Unparseable client IP: {client_ip!r}")
        return False
    for entry in _parse_allowed_entries(allowed_raw):
        if "/" in entry:
            try:
                net = ipaddress.ip_network(entry, strict=False)
                if addr in net:
                    return True
            except ValueError:
                log.warning(f"[Admin IP allowlist] Ignoring invalid CIDR: {entry!r}")
                continue
        else:
            try:
                if addr == ipaddress.ip_address(entry):
                    return True
            except ValueError:
                log.warning(f"[Admin IP allowlist] Ignoring invalid IP: {entry!r}")
                continue
    return False


def admin_request_ip_allowed(request: Request) -> bool:
    """True when ``ADMIN_ALLOWED_IPS`` is unset/empty or the client IP is allowed."""
    allowed = os.getenv(_ENV_KEY, "").strip()
    if not allowed:
        return True
    return client_ip_is_allowed(get_effective_client_ip(request), allowed)


class AdminIPAllowlistMiddleware(BaseHTTPMiddleware):
    """Reject requests to ``/admin`` when ``ADMIN_ALLOWED_IPS`` is set and IP is not listed."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not is_admin_url_path(request.url.path):
            return await call_next(request)
        if admin_request_ip_allowed(request):
            return await call_next(request)
        return JSONResponse(
            status_code=403,
            content={"detail": "Admin interface is not allowed for this client IP"},
        )
